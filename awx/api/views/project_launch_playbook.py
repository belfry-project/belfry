# Belfry: run a playbook of a project directly, without a job template.
#
# Kept in its own module (view and serializer) to ease merges from upstream.

import json
from collections import OrderedDict

from django.conf import settings
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from ansible_base.lib.utils.schema import extend_schema_if_available

from awx.api.fields import VerbatimField
from awx.api.generics import RetrieveAPIView
from awx.api.serializers import BaseSerializer, JobSerializer
from awx.main.models import Credential, ExecutionEnvironment, InstanceGroup, Inventory, Job, Project
from awx.main.models.base import NEW_JOB_TYPE_CHOICES, VERBOSITY_CHOICES
from awx.main.utils import parse_yaml_or_json
from awx.main.validators import vars_validate_or_raise

DISABLED_MESSAGE = _('Running playbooks directly from a project is turned off (ALLOW_DIRECT_PLAYBOOK_LAUNCH).')

# Job fields copied from the validated launch data as they are
SIMPLE_FIELDS = ('playbook', 'inventory', 'scm_branch', 'limit', 'job_type', 'verbosity', 'forks', 'timeout', 'execution_environment')
SIMPLE_FIELDS += ('diff_mode', 'job_tags', 'skip_tags', 'use_fact_cache', 'become_enabled')


class ProjectLaunchPlaybookSerializer(BaseSerializer):
    # Representational fields (GET)
    playbooks = serializers.SerializerMethodField(help_text=_('Playbooks of this project that can be run.'))
    project_data = serializers.SerializerMethodField()

    # Accepted launch fields (POST)
    playbook = serializers.CharField(write_only=True, help_text=_('Playbook to run, one of the playbooks of the project.'))
    inventory = serializers.PrimaryKeyRelatedField(queryset=Inventory.objects.all(), write_only=True)
    credentials = serializers.PrimaryKeyRelatedField(many=True, queryset=Credential.objects.all(), required=False, write_only=True)
    credential_passwords = VerbatimField(required=False, write_only=True)
    extra_vars = serializers.JSONField(required=False, write_only=True)
    scm_branch = serializers.CharField(required=False, write_only=True, allow_blank=True)
    limit = serializers.CharField(required=False, write_only=True, allow_blank=True)
    job_type = serializers.ChoiceField(required=False, choices=NEW_JOB_TYPE_CHOICES, write_only=True)
    verbosity = serializers.ChoiceField(required=False, choices=VERBOSITY_CHOICES, write_only=True)
    forks = serializers.IntegerField(required=False, write_only=True, min_value=0)
    timeout = serializers.IntegerField(required=False, write_only=True)
    execution_environment = serializers.PrimaryKeyRelatedField(queryset=ExecutionEnvironment.objects.all(), required=False, write_only=True)
    instance_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=InstanceGroup.objects.all(), required=False, write_only=True)
    diff_mode = serializers.BooleanField(required=False, write_only=True)
    job_tags = serializers.CharField(required=False, write_only=True, allow_blank=True)
    skip_tags = serializers.CharField(required=False, write_only=True, allow_blank=True)
    use_fact_cache = serializers.BooleanField(required=False, write_only=True)
    become_enabled = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Project
        fields = (
            'playbooks',
            'project_data',
            'playbook',
            'inventory',
            'credentials',
            'credential_passwords',
            'extra_vars',
            'scm_branch',
            'limit',
            'job_type',
            'verbosity',
            'forks',
            'timeout',
            'execution_environment',
            'instance_groups',
            'diff_mode',
            'job_tags',
            'skip_tags',
            'use_fact_cache',
            'become_enabled',
        )

    def get_playbooks(self, obj):
        # same list as /api/v2/projects/N/playbooks/
        return obj.playbook_files if obj.scm_type else obj.playbooks

    def get_project_data(self, obj):
        return dict(id=obj.id, name=obj.name, allow_override=obj.allow_override)

    def validate_extra_vars(self, value):
        return vars_validate_or_raise(value)

    def validate(self, attrs):
        # Mirrors the checks of JobOptionsSerializer (playbook, scm_branch), JobTemplate.clean_forks
        # and JobLaunchSerializer (project state, inventory, credentials, passwords).
        project = self.context['project']
        errors = {}
        playbook = force_str(attrs.get('playbook', ''))
        if not (project.scm_type and project.allow_override) and playbook not in self.get_playbooks(project):
            errors['playbook'] = [_('Playbook not found for project.')]
        failure_reason = project.get_reason_if_failed()
        if failure_reason:
            errors.setdefault('playbook', []).append(failure_reason)
        if attrs.get('scm_branch') and not project.allow_override:
            errors['scm_branch'] = [_('Project does not allow overriding branch.')]
        if settings.MAX_FORKS > 0 and attrs.get('forks', 0) > settings.MAX_FORKS:
            errors['forks'] = [_(f'Maximum number of forks ({settings.MAX_FORKS}) exceeded.')]
        if attrs['inventory'].pending_deletion:
            errors['inventory'] = [_('The provided inventory is being deleted.')]

        distinct_cred_kinds = []
        for cred in attrs.get('credentials', []):
            if cred.unique_hash() in distinct_cred_kinds:
                errors.setdefault('credentials', []).append(_('Cannot assign multiple {} credentials.').format(cred.unique_hash(display=True)))
            if cred.credential_type.kind not in ('ssh', 'vault', 'cloud', 'net', 'kubernetes'):
                errors.setdefault('credentials', []).append(_('Cannot assign a Credential of kind `{}`').format(cred.credential_type.kind))
            distinct_cred_kinds.append(cred.unique_hash())

        passwords = attrs.get('credential_passwords') or {}
        lacking = [p for cred in attrs.get('credentials', []) for p in cred.passwords_needed if not passwords.get(p)]
        if lacking:
            errors['passwords_needed_to_start'] = lacking
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ProjectLaunchPlaybook(RetrieveAPIView):
    model = Project
    serializer_class = ProjectLaunchPlaybookSerializer
    obj_permission_type = 'read'  # POST: read on the project here, the launch permissions in post()
    resource_purpose = 'run a playbook of a project directly'

    def check_enabled(self):
        if not settings.ALLOW_DIRECT_PLAYBOOK_LAUNCH:
            raise PermissionDenied(DISABLED_MESSAGE)

    @extend_schema_if_available(extensions={"x-ai-description": "Describe the fields for running a playbook of a project directly and list its playbooks."})
    def get(self, request, *args, **kwargs):
        self.check_enabled()
        return super().get(request, *args, **kwargs)

    @extend_schema_if_available(extensions={"x-ai-description": "Run a playbook of a project directly, without a job template. Creates and starts a job."})
    def post(self, request, *args, **kwargs):
        self.check_enabled()
        project = self.get_object()  # needs read access on the project
        serializer = self.serializer_class(data=request.data, context={'project': project, 'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        allowed, messages = request.user.can_access_with_errors(Project, 'launch_playbook', project, data)
        if not allowed:
            raise PermissionDenied(messages.get('detail') or messages or None)

        passwords = data.pop('credential_passwords', None) or {}
        job = self.create_job(project, data, request.user)
        result = job.signal_start(**passwords)
        if not result:
            response = dict(passwords_needed_to_start=job.passwords_needed_to_start)
            job.delete()
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        response = OrderedDict(job=job.id)
        response.update(JobSerializer(job, context=self.get_serializer_context()).to_representation(job))
        return Response(response, status=status.HTTP_201_CREATED, headers={'Location': job.get_absolute_url(request)})

    @staticmethod
    def create_job(project, data, user):
        """Create the job like JobTemplate.create_unified_job, without a template."""
        from awx.main.signals import disable_activity_stream, activity_stream_create

        job = Job(
            name='{} / {}'.format(project.name, data['playbook'])[:512],
            launch_type='manual',
            created_by=user,
            modified_by=user,
            project=project,
            organization=project.organization,
            # without a template there is nothing to serialize on; all template-less jobs would block each other
            allow_simultaneous=True,
        )
        for field_name in SIMPLE_FIELDS:
            if data.get(field_name) is not None:
                setattr(job, field_name, data[field_name])
        if data.get('extra_vars'):
            job.extra_vars = json.dumps(parse_yaml_or_json(data['extra_vars']))
        instance_groups = data.get('instance_groups') or []
        if instance_groups:
            job.preferred_instance_groups_cache = [ig.id for ig in instance_groups]
        else:
            job.preferred_instance_groups_cache = job._get_preferred_instance_group_cache()
        job._set_default_dependencies_processed()
        job.task_impact = job._get_task_impact()
        with disable_activity_stream():
            job.save()
            if data.get('credentials'):
                job.credentials.add(*data['credentials'])
        activity_stream_create(None, job, True)
        job.log_lifecycle("created")
        return job
