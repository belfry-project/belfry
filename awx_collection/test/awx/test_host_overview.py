from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from awx.main.models import Group, Host, Inventory, Organization


@pytest.mark.django_db
def test_host_overview(run_module, admin_user):
    org = Organization.objects.create(name='overview-org')
    inv = Inventory.objects.create(name='overview-inv', organization=org)
    host = Host.objects.create(name='web1', inventory=inv, variables='role: web', ansible_facts={'a': 1, 'b': 2})
    Group.objects.create(name='web', inventory=inv).hosts.add(host)

    result = run_module('host_overview', dict(name='web1', inventory='overview-inv', facts=['a'], jobs=3), admin_user)
    assert not result.get('failed', False), result.get('msg', result)
    assert result['changed'] is False
    assert result['host']['id'] == host.id
    assert result['variables'] == {'role': 'web'}
    assert result['facts'] == {'a': 1}
    assert [g['name'] for g in result['groups']['all']] == ['web']
    assert result['recent_jobs'] == []


@pytest.mark.django_db
def test_host_overview_missing_host(run_module, admin_user):
    result = run_module('host_overview', dict(name='nope'), admin_user)
    assert result.get('failed', False)
