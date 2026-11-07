# Copyright (c) Belfry contributors
"""GET /api/v2/hosts/{id}/overview/: a host with its variables, groups, facts and jobs in one call."""

from django.db.models import Max
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from awx.api.generics import RetrieveAPIView
from awx.api.versioning import reverse
from awx.main import models

DEFAULT_JOBS = 5
MAX_JOBS = 50


def _jobs_param(request):
    value = request.query_params.get('jobs', DEFAULT_JOBS)
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ParseError(_('jobs must be an integer between 0 and %d') % MAX_JOBS)
    if value < 0 or value > MAX_JOBS:
        raise ParseError(_('jobs must be an integer between 0 and %d') % MAX_JOBS)
    return value


def _facts_param(request):
    value = request.query_params.get('facts')
    if value is None:
        return None
    return [k.strip() for k in value.split(',') if k.strip()]


class HostOverview(RetrieveAPIView):
    """Return a host together with its variables, groups, facts, last job per job template and recent jobs."""

    model = models.Host
    resource_purpose = 'overview of a host: variables, groups, facts and jobs'

    def get_serializer_class(self):
        from awx.api.serializers import EmptySerializer

        return EmptySerializer

    def retrieve(self, request, *args, **kwargs):
        jobs = _jobs_param(request)
        fact_keys = _facts_param(request)
        host = self.get_object()  # checks read permission on the host
        return Response(
            {
                'host': self._host(host),
                'variables': host.variables_dict,
                'groups': self._groups(host),
                'facts': self._facts(host, fact_keys),
                'ansible_facts_modified': host.ansible_facts_modified,
                'last_job_per_template': self._last_job_per_template(host),
                'recent_jobs': self._recent_jobs(host, jobs),
            }
        )

    def get_queryset(self):
        return super().get_queryset().select_related('inventory')

    def filter_queryset(self, queryset):
        # facts and jobs are options of this view, not field filters
        return queryset

    def _host(self, host):
        return {
            'id': host.id,
            'type': 'host',
            'url': reverse('api:host_detail', kwargs={'pk': host.pk}, request=self.request),
            'name': host.name,
            'description': host.description,
            'enabled': host.enabled,
            'instance_id': host.instance_id,
            'inventory': {'id': host.inventory_id, 'name': host.inventory.name, 'kind': host.inventory.kind},
            'created': host.created,
            'modified': host.modified,
        }

    def _groups(self, host):
        direct = list(host.groups.order_by('name', 'id').values('id', 'name'))
        group_parents_map = host.inventory.get_group_parents_map()
        all_pks = {g['id'] for g in direct}
        to_check = set(all_pks)
        while to_check:
            parents = group_parents_map.get(to_check.pop(), set()) - all_pks
            all_pks |= parents
            to_check |= parents
        inherited_pks = all_pks - {g['id'] for g in direct}
        inherited = list(models.Group.objects.filter(pk__in=inherited_pks).order_by('name', 'id').values('id', 'name')) if inherited_pks else []
        return {'direct': direct, 'all': sorted(direct + inherited, key=lambda g: (g['name'], g['id']))}

    def _facts(self, host, keys):
        facts = host.ansible_facts or {}
        if host.inventory.kind == 'constructed' and host.instance_id:
            # Facts of a constructed inventory host live on the input inventory's host.
            source = models.Host.objects.filter(pk=host.instance_id).values_list('ansible_facts', flat=True).first()
            facts = source or {}
        if keys is None:
            return facts
        return {k: facts[k] for k in keys if k in facts}

    def _last_job_per_template(self, host):
        last_ids = (
            models.JobHostSummary.objects.filter(host=host, job__unified_job_template__isnull=False)
            .values('job__unified_job_template')
            .annotate(last_job=Max('job_id'))
            .values_list('last_job', flat=True)
        )
        summaries = (
            models.JobHostSummary.objects.filter(host=host, job_id__in=list(last_ids))
            .select_related('job__unified_job_template')
            .only(
                'job_id',
                'failed',
                'job__id',
                'job__name',
                'job__status',
                'job__finished',
                'job__failed',
                'job__unified_job_template__id',
                'job__unified_job_template__name',
            )
            .order_by('-job_id')
        )
        result = []
        for s in summaries:
            template = s.job.unified_job_template
            result.append(
                {
                    'job_template': {'id': template.id, 'name': template.name},
                    'job': {
                        'id': s.job.id,
                        'name': s.job.name,
                        'status': s.job.status,
                        'finished': s.job.finished,
                        'failed': s.job.failed,
                    },
                    'host_failed': s.failed,
                }
            )
        return result

    def _recent_jobs(self, host, limit):
        if limit == 0:
            return []
        fields = ('id', 'name', 'status', 'started', 'finished', 'failed', 'created')
        job_ids = models.JobHostSummary.objects.filter(host=host).values('job_id')
        jobs = models.Job.objects.filter(id__in=job_ids).order_by('-created', '-id').values(*fields)[:limit]
        ad_hoc = models.AdHocCommand.objects.filter(id__in=host.ad_hoc_commands.values('id')).order_by('-created', '-id').values(*fields)[:limit]
        items = [dict(j, type='job') for j in jobs] + [dict(a, type='ad_hoc_command') for a in ad_hoc]
        items.sort(key=lambda j: (j['created'], j['id']), reverse=True)
        return items[:limit]
