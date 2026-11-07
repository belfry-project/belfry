from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from awx.main.models import Job


@pytest.mark.django_db
def test_playbook_launch(run_module, admin_user, project, inventory, machine_credential):
    result = run_module(
        'playbook_launch',
        dict(project=project.name, playbook='helloworld.yml', inventory=inventory.name, credentials=[machine_credential.name], limit='web', tags=['a', 'b']),
        admin_user,
    )
    assert not result.get('failed', False), result.get('msg', result)
    assert result['changed']
    job = Job.objects.get(id=result['id'])
    assert job.job_template is None
    assert (job.playbook, job.limit, job.job_tags) == ('helloworld.yml', 'web', 'a,b')
    assert list(job.credentials.all()) == [machine_credential]


@pytest.mark.django_db
def test_playbook_launch_bad_playbook(run_module, admin_user, project, inventory):
    result = run_module('playbook_launch', dict(project=project.name, playbook='missing.yml', inventory=inventory.name), admin_user)
    assert result.get('failed', False)
    assert not Job.objects.exists()


@pytest.mark.django_db
def test_playbook_launch_turned_off(run_module, admin_user, project, inventory, settings):
    settings.ALLOW_DIRECT_PLAYBOOK_LAUNCH = False
    result = run_module('playbook_launch', dict(project=project.name, playbook='helloworld.yml', inventory=inventory.name), admin_user)
    assert result.get('failed', False)
    assert 'ALLOW_DIRECT_PLAYBOOK_LAUNCH' in result['msg']
