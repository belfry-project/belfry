# Belfry: running a playbook of a project directly (POST /api/v2/projects/N/launch_playbook/)
import pytest

from django.test.utils import override_settings

from awx.api.versioning import reverse
from awx.main.models import ActivityStream, Job


def url(project):
    return reverse('api:project_launch_playbook', kwargs={'pk': project.pk})


@pytest.fixture
def launcher(rando, project, inventory, machine_credential):
    """A user with exactly the access needed to create a job template from these resources."""
    project.use_role.members.add(rando)
    inventory.use_role.members.add(rando)
    machine_credential.use_role.members.add(rando)
    return rando


def payload(inventory, machine_credential, **kwargs):
    data = dict(playbook='helloworld.yml', inventory=inventory.pk, credentials=[machine_credential.pk])
    data.update(kwargs)
    return data


@pytest.mark.django_db
def test_get_describes_playbooks(get, project, launcher):
    r = get(url(project), launcher, expect=200)
    assert r.data['playbooks'] == ['helloworld.yml', 'alt-helloworld.yml']
    assert r.data['project_data']['id'] == project.pk


@pytest.mark.django_db
def test_related_link(get, project, admin_user):
    r = get(reverse('api:project_detail', kwargs={'pk': project.pk}), admin_user, expect=200)
    assert r.data['related']['launch_playbook'] == url(project)


@pytest.mark.django_db
def test_launch_creates_job(post, get, project, inventory, machine_credential, launcher):
    data = payload(inventory, machine_credential, limit='web', extra_vars={'a': 1}, job_type='check', verbosity=2, diff_mode=True, use_fact_cache=True)
    r = post(url(project), data, launcher, expect=201)
    job = Job.objects.get(pk=r.data['job'])
    assert job.job_template is None
    assert job.launch_type == 'manual'
    assert job.name == 'test-proj / helloworld.yml'
    assert job.organization == project.organization
    assert job.created_by == launcher
    assert (job.limit, job.job_type, job.verbosity, job.diff_mode, job.use_fact_cache) == ('web', 'check', 2, True, True)
    assert job.extra_vars_dict == {'a': 1}
    assert list(job.credentials.all()) == [machine_credential]
    assert job.status == 'pending'
    assert ActivityStream.objects.filter(job=job, operation='create').exists()
    # the launching user sees the job in the lists and in detail
    assert job.id in [j['id'] for j in get(reverse('api:job_list'), launcher, expect=200).data['results']]
    assert job.id in [j['id'] for j in get(reverse('api:unified_job_list'), launcher, expect=200).data['results']]
    get(reverse('api:job_detail', kwargs={'pk': job.pk}), launcher, expect=200)


@pytest.mark.django_db
def test_org_admin_sees_job_other_user_does_not(post, get, project, inventory, machine_credential, launcher, org_admin, alice):
    r = post(url(project), payload(inventory, machine_credential), launcher, expect=201)
    get(reverse('api:job_detail', kwargs={'pk': r.data['job']}), org_admin, expect=200)
    get(reverse('api:job_detail', kwargs={'pk': r.data['job']}), alice, expect=403)


@pytest.mark.django_db
@pytest.mark.parametrize('missing', ['project', 'inventory', 'credential', 'execution_environment', 'instance_group'])
def test_launch_permission_denied(post, project, inventory, machine_credential, launcher, missing, instance_group, organization):
    from awx.main.models import ExecutionEnvironment

    ee = ExecutionEnvironment.objects.create(name='private-ee', image='quay.io/x/y', organization=organization)
    data = payload(inventory, machine_credential, execution_environment=ee.pk, instance_groups=[instance_group.pk])
    if missing != 'execution_environment':
        organization.member_role.members.add(launcher)  # members can read the org's EEs
    if missing != 'instance_group':
        instance_group.use_role.members.add(launcher)
    if missing == 'project':
        project.use_role.members.remove(launcher)
    elif missing == 'inventory':
        inventory.use_role.members.remove(launcher)
    elif missing == 'credential':
        machine_credential.use_role.members.remove(launcher)
    post(url(project), data, launcher, expect=403)
    assert not Job.objects.exists()


@pytest.mark.django_db
def test_launch_validation(post, project, inventory, machine_credential, admin_user, credential, vault_credential):
    r = post(url(project), payload(inventory, machine_credential, playbook='missing.yml'), admin_user, expect=400)
    assert 'playbook' in r.data
    r = post(url(project), dict(playbook='helloworld.yml'), admin_user, expect=400)
    assert 'inventory' in r.data
    r = post(url(project), payload(inventory, machine_credential, scm_branch='other'), admin_user, expect=400)
    assert 'scm_branch' in r.data
    r = post(url(project), payload(inventory, machine_credential, extra_vars='[not a dict'), admin_user, expect=400)
    assert 'extra_vars' in r.data
    from awx.main.models import Credential

    second = Credential.objects.create(credential_type=machine_credential.credential_type, name='m2', inputs={'username': 'u'})
    r = post(url(project), dict(payload(inventory, machine_credential), credentials=[machine_credential.pk, second.pk]), admin_user, expect=400)
    assert 'credentials' in r.data
    ask = Credential.objects.create(credential_type=machine_credential.credential_type, name='ask', inputs={'username': 'u', 'password': 'ASK'})
    r = post(url(project), dict(payload(inventory, machine_credential), credentials=[ask.pk]), admin_user, expect=400)
    assert r.data['passwords_needed_to_start'] == ['ssh_password']
    post(url(project), dict(payload(inventory, machine_credential), credentials=[ask.pk], credential_passwords={'ssh_password': 'x'}), admin_user, expect=201)


@pytest.mark.django_db
def test_failed_project_refused(post, project, inventory, machine_credential, admin_user):
    project.scm_update_on_launch = False
    project.save()
    project.__class__.objects.filter(pk=project.pk).update(status='failed')
    project.refresh_from_db()
    r = post(url(project), payload(inventory, machine_credential), admin_user, expect=400)
    assert 'playbook' in r.data


@pytest.mark.django_db
def test_setting_off(get, post, project, inventory, machine_credential, admin_user):
    with override_settings(ALLOW_DIRECT_PLAYBOOK_LAUNCH=False):
        r = post(url(project), payload(inventory, machine_credential), admin_user, expect=403)
        assert 'ALLOW_DIRECT_PLAYBOOK_LAUNCH' in str(r.data['detail'])
        get(url(project), admin_user, expect=403)
        r = get(reverse('api:project_detail', kwargs={'pk': project.pk}), admin_user, expect=200)
        assert 'launch_playbook' not in r.data['related']
    assert not Job.objects.exists()


@pytest.mark.django_db
def test_setting_in_settings_api(get, admin_user):
    r = get(reverse('api:setting_singleton_detail', kwargs={'category_slug': 'jobs'}), admin_user, expect=200)
    assert r.data['ALLOW_DIRECT_PLAYBOOK_LAUNCH'] is True


@pytest.mark.django_db
def test_relaunch_and_cancel(post, get, project, inventory, machine_credential, launcher, alice):
    r = post(url(project), payload(inventory, machine_credential), launcher, expect=201)
    job = Job.objects.get(pk=r.data['job'])
    # another user without access can neither relaunch nor cancel
    post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, alice, expect=403)
    post(reverse('api:job_cancel', kwargs={'pk': job.pk}), {}, alice, expect=403)
    r = post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {'job_type': 'check'}, launcher, expect=201)
    new_job = Job.objects.get(pk=r.data['id'])
    assert new_job.job_template is None and new_job.launch_type == 'relaunch'
    assert new_job.job_type == 'check' and new_job.playbook == 'helloworld.yml'
    assert list(new_job.credentials.all()) == [machine_credential]
    assert new_job.task_impact > 0
    post(reverse('api:job_cancel', kwargs={'pk': job.pk}), {}, launcher, expect=202)
    # after losing use on the inventory, relaunch is refused
    inventory.use_role.members.remove(launcher)
    post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, launcher, expect=403)
    with override_settings(ALLOW_DIRECT_PLAYBOOK_LAUNCH=False):
        inventory.use_role.members.add(launcher)
        post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, launcher, expect=403)


@pytest.mark.django_db
def test_relaunch_keeps_instance_groups(post, project, inventory, machine_credential, launcher, instance_group, default_instance_group):
    instance_group.use_role.members.add(launcher)
    r = post(url(project), payload(inventory, machine_credential, instance_groups=[instance_group.pk]), launcher, expect=201)
    job = Job.objects.get(pk=r.data['job'])
    assert job.preferred_instance_groups_cache == [instance_group.pk]
    assert job.direct_launch_instance_groups() == [instance_group]
    r = post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, launcher, expect=201)
    relaunched = Job.objects.get(pk=r.data['id'])
    assert relaunched.preferred_instance_groups_cache == [instance_group.pk]
    # and again from the relaunched job
    r = post(reverse('api:job_relaunch', kwargs={'pk': relaunched.pk}), {}, launcher, expect=201)
    assert Job.objects.get(pk=r.data['id']).preferred_instance_groups_cache == [instance_group.pk]
    # relaunch needs use on the instance group, like launching
    instance_group.use_role.members.remove(launcher)
    post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, launcher, expect=403)


@pytest.mark.django_db
def test_relaunch_without_instance_groups_uses_defaults(post, project, inventory, machine_credential, launcher, instance_group, default_instance_group):
    r = post(url(project), payload(inventory, machine_credential), launcher, expect=201)
    job = Job.objects.get(pk=r.data['job'])
    assert job.direct_launch_instance_groups() == []
    inventory.instance_groups.add(instance_group)  # defaults are computed again on relaunch
    r = post(reverse('api:job_relaunch', kwargs={'pk': job.pk}), {}, launcher, expect=201)
    assert Job.objects.get(pk=r.data['id']).preferred_instance_groups_cache[0] == instance_group.pk


def jt_url(job):
    return reverse('api:job_create_job_template', kwargs={'pk': job.pk})


@pytest.mark.django_db
def test_create_job_template_from_job(post, get, project, inventory, machine_credential, launcher, instance_group):
    from awx.main.models import JobTemplate

    instance_group.use_role.members.add(launcher)
    data = payload(inventory, machine_credential, limit='web', extra_vars={'a': 1}, job_type='check', verbosity=2, instance_groups=[instance_group.pk])
    job = Job.objects.get(pk=post(url(project), data, launcher, expect=201).data['job'])
    r = get(reverse('api:job_detail', kwargs={'pk': job.pk}), launcher, expect=200)
    assert r.data['related']['create_job_template'] == jt_url(job)
    assert get(jt_url(job), launcher, expect=200).data['can_create_job_template'] is True

    post(jt_url(job), {}, launcher, expect=400)  # name is required
    r = post(jt_url(job), {'name': 'saved run', 'description': 'from a direct run'}, launcher, expect=201)
    jt = JobTemplate.objects.get(pk=r.data['id'])
    assert (jt.name, jt.description, jt.project, jt.inventory, jt.playbook) == ('saved run', 'from a direct run', project, inventory, 'helloworld.yml')
    assert (jt.limit, jt.job_type, jt.verbosity, jt.organization) == ('web', 'check', 2, project.organization)
    assert jt.extra_vars_dict == {'a': 1}
    assert list(jt.credentials.all()) == [machine_credential]
    assert list(jt.instance_groups.all()) == [instance_group]
    # the creator administers the new template, which can be launched and scheduled
    assert launcher in jt.admin_role
    assert ActivityStream.objects.filter(job_template=jt, operation='create').exists()
    # the template name must be unique in the organization
    r = post(jt_url(job), {'name': 'saved run'}, launcher, expect=400)


@pytest.mark.django_db
@pytest.mark.parametrize('missing', ['project', 'inventory', 'credential', 'instance_group'])
def test_create_job_template_permission(post, project, inventory, machine_credential, launcher, instance_group, missing, org_admin):
    from awx.main.models import JobTemplate

    instance_group.use_role.members.add(launcher)
    job = Job.objects.get(pk=post(url(project), payload(inventory, machine_credential, instance_groups=[instance_group.pk]), launcher, expect=201).data['job'])
    if missing == 'project':
        project.use_role.members.remove(launcher)
    elif missing == 'inventory':
        inventory.use_role.members.remove(launcher)
    elif missing == 'credential':
        machine_credential.use_role.members.remove(launcher)
    else:
        instance_group.use_role.members.remove(launcher)
    post(jt_url(job), {'name': 'x'}, launcher, expect=403)
    assert not JobTemplate.objects.exists()


@pytest.mark.django_db
def test_create_job_template_only_for_direct_runs(post, get, job_template, admin_user, alice, project, inventory, machine_credential, launcher):
    job = job_template.create_unified_job()
    assert 'create_job_template' not in get(reverse('api:job_detail', kwargs={'pk': job.pk}), admin_user, expect=200).data['related']
    assert get(jt_url(job), admin_user, expect=200).data['can_create_job_template'] is False
    r = post(jt_url(job), {'name': 'x'}, admin_user, expect=400)
    assert 'directly' in str(r.data['detail'])
    # a user who cannot see the job cannot save it
    direct = post(url(project), payload(inventory, machine_credential), launcher, expect=201).data['job']
    post(reverse('api:job_create_job_template', kwargs={'pk': direct}), {'name': 'x'}, alice, expect=403)
