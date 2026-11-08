from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from awx.main.models import JobTemplate


def _direct_run(run_module, admin_user, project, inventory, machine_credential):
    result = run_module(
        'playbook_launch',
        dict(project=project.name, playbook='helloworld.yml', inventory=inventory.name, credentials=[machine_credential.name], limit='web'),
        admin_user,
    )
    assert not result.get('failed', False), result.get('msg', result)
    return result['id']


@pytest.mark.django_db
def test_job_create_template(run_module, admin_user, project, inventory, machine_credential):
    job_id = _direct_run(run_module, admin_user, project, inventory, machine_credential)
    result = run_module('job_create_template', dict(job_id=job_id, name='saved', description='from a run'), admin_user)
    assert not result.get('failed', False), result.get('msg', result)
    assert result['changed']
    jt = JobTemplate.objects.get(id=result['id'])
    assert (jt.name, jt.description, jt.playbook, jt.limit, jt.project, jt.inventory) == ('saved', 'from a run', 'helloworld.yml', 'web', project, inventory)
    assert list(jt.credentials.all()) == [machine_credential]


@pytest.mark.django_db
def test_job_create_template_check_mode(run_module, admin_user, project, inventory, machine_credential):
    job_id = _direct_run(run_module, admin_user, project, inventory, machine_credential)
    result = run_module('job_create_template', dict(job_id=job_id, name='saved', _ansible_check_mode=True), admin_user)
    assert not result.get('failed', False), result.get('msg', result)
    assert result['changed']
    assert not JobTemplate.objects.exists()


@pytest.mark.django_db
def test_job_create_template_name_exists(run_module, admin_user, project, inventory, machine_credential):
    job_id = _direct_run(run_module, admin_user, project, inventory, machine_credential)
    JobTemplate.objects.create(name='saved', project=project, inventory=inventory, playbook='helloworld.yml')
    result = run_module('job_create_template', dict(job_id=job_id, name='saved'), admin_user)
    assert result.get('failed', False)
    assert 'already exists' in result['msg']
    assert JobTemplate.objects.count() == 1


@pytest.mark.django_db
def test_job_create_template_not_direct(run_module, admin_user, job_template):
    job = job_template.create_unified_job()
    result = run_module('job_create_template', dict(job_id=job.id, name='saved'), admin_user)
    assert result.get('failed', False)
    assert 'did not run a playbook directly' in result['msg']
