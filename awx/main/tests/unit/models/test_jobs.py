# -*- coding: utf-8 -*-
import json
import os
import pytest
from unittest import mock

from awx.main.models import (
    Inventory,
    Host,
)
from awx.main.tasks.facts import start_fact_cache, finish_fact_cache

from django.utils.timezone import now

from datetime import timedelta

import time


@pytest.fixture
def ref_time():
    return now() - timedelta(seconds=5)


@pytest.fixture
def hosts(ref_time):
    inventory = Inventory(id=5)
    return [
        Host(name='host1', ansible_facts={"a": 1, "b": 2}, ansible_facts_modified=ref_time, inventory=inventory),
        Host(name='host2', ansible_facts={"a": 1, "b": 2}, ansible_facts_modified=ref_time, inventory=inventory),
        Host(name='host3', ansible_facts={"a": 1, "b": 2}, ansible_facts_modified=ref_time, inventory=inventory),
        Host(name='Iñtërnâtiônàlizætiøn', ansible_facts={"a": 1, "b": 2}, ansible_facts_modified=ref_time, inventory=inventory),
    ]


def test_start_job_fact_cache(hosts, tmpdir):
    # Create artifacts dir inside tmpdir
    artifacts_dir = tmpdir.mkdir("artifacts")

    # Assign a mock inventory ID
    inventory_id = 42

    # Call the function WITHOUT log_data — the decorator handles it
    start_fact_cache(hosts, artifacts_dir=str(artifacts_dir), timeout=0, inventory_id=inventory_id)

    # Fact files are written into artifacts_dir/fact_cache/
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')

    for host in hosts:
        filepath = os.path.join(fact_cache_dir, host.name)
        assert os.path.exists(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            assert json.load(f) == host.ansible_facts


def test_fact_cache_with_invalid_path_traversal(tmpdir):
    hosts = [
        Host(
            name='../foo',
            ansible_facts={"a": 1, "b": 2},
        ),
    ]
    artifacts_dir = tmpdir.mkdir("artifacts")
    inventory_id = 42

    start_fact_cache(hosts, artifacts_dir=str(artifacts_dir), timeout=0, inventory_id=inventory_id)

    # Fact cache directory (safe location)
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')

    # The bad host name should not produce a file
    assert not os.path.exists(os.path.join(fact_cache_dir, '../foo'))

    # Make sure the fact_cache dir exists and is still empty
    assert os.listdir(fact_cache_dir) == []


def test_start_job_fact_cache_past_timeout(hosts, tmpdir):
    fact_cache = os.path.join(tmpdir, 'facts')
    start_fact_cache(hosts, fact_cache, timeout=2)

    for host in hosts:
        assert not os.path.exists(os.path.join(fact_cache, host.name))
    ret = start_fact_cache(hosts, fact_cache, timeout=2)
    assert ret is None


def test_start_job_fact_cache_within_timeout(hosts, tmpdir):
    artifacts_dir = tmpdir.mkdir("artifacts")

    # The hosts fixture was modified 5s ago, which is less than 7s
    start_fact_cache(hosts, str(artifacts_dir), timeout=7)

    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    for host in hosts:
        filepath = os.path.join(fact_cache_dir, host.name)
        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            assert json.load(f) == host.ansible_facts


def test_finish_job_fact_cache_clear(hosts, mocker, ref_time, tmpdir):
    artifacts_dir = str(tmpdir.mkdir("artifacts"))
    inventory_id = 5

    start_fact_cache(hosts, artifacts_dir=artifacts_dir, timeout=0, inventory_id=inventory_id)

    mocker.patch('awx.main.tasks.facts.bulk_update_sorted_by_id')

    # Remove the fact file for hosts[1] to simulate ansible's clear_facts
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    os.remove(os.path.join(fact_cache_dir, hosts[1].name))

    hosts_qs = mock.MagicMock()
    # The new code calls host_qs.filter(name__in=...).select_related('inventory')
    # Only hosts[1] needs clearing (its file was removed), so return just that host
    hosts_qs.filter.return_value.select_related.return_value = [hosts[1]]

    finish_fact_cache(hosts_qs, artifacts_dir=artifacts_dir, inventory_id=inventory_id)

    # hosts[1] should have had its facts cleared (file was missing, job_created=None)
    assert hosts[1].ansible_facts == {}
    assert hosts[1].ansible_facts_modified > ref_time

    # Other hosts should be unmodified (fact files exist but weren't changed by ansible)
    for host in (hosts[0], hosts[2], hosts[3]):
        assert host.ansible_facts == {"a": 1, "b": 2}
        assert host.ansible_facts_modified == ref_time


def test_finish_job_fact_cache_with_bad_data(hosts, mocker, tmpdir):
    artifacts_dir = str(tmpdir.mkdir("artifacts"))
    inventory_id = 5

    start_fact_cache(hosts, artifacts_dir=artifacts_dir, timeout=0, inventory_id=inventory_id)

    bulk_update = mocker.patch('awx.main.tasks.facts.bulk_update_sorted_by_id')

    # Overwrite fact files with invalid JSON and set future mtime
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    for h in hosts:
        filepath = os.path.join(fact_cache_dir, h.name)
        with open(filepath, 'w') as f:
            f.write('not valid json!')
            f.flush()
            new_modification_time = time.time() + 3600
            os.utime(filepath, (new_modification_time, new_modification_time))

    hosts_qs = mock.MagicMock()

    finish_fact_cache(hosts_qs, artifacts_dir=artifacts_dir, inventory_id=inventory_id)

    # Invalid JSON should be skipped — no hosts updated, bulk_update never called
    bulk_update.assert_not_called()


def _tagged_payload(facts):
    return {'__payload__': json.dumps(facts)}


def _write_future(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    future = time.time() + 3600
    os.utime(filepath, (future, future))


def test_start_job_fact_cache_writes_tagged_format(hosts, tmpdir):
    artifacts_dir = tmpdir.mkdir("artifacts")

    start_fact_cache(hosts, artifacts_dir=str(artifacts_dir), timeout=0, inventory_id=42)

    # ansible-core 2.19 and later read "s1_<host>" with the facts in a JSON payload
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    for host in hosts:
        with open(os.path.join(fact_cache_dir, 's1_' + host.name), 'r', encoding='utf-8') as f:
            assert json.loads(json.load(f)['__payload__']) == host.ansible_facts


def test_start_job_fact_cache_skips_tagged_file_that_collides_with_host(ref_time, tmpdir):
    inventory = Inventory(id=5)
    hosts = [
        Host(name='web', ansible_facts={"host": "web"}, ansible_facts_modified=ref_time, inventory=inventory),
        Host(name='s1_web', ansible_facts={"host": "s1_web"}, ansible_facts_modified=ref_time, inventory=inventory),
    ]
    artifacts_dir = tmpdir.mkdir("artifacts")

    start_fact_cache(hosts, artifacts_dir=str(artifacts_dir), timeout=0, inventory_id=42)

    # "s1_web" is the plain file of host s1_web, so web gets no tagged file
    with open(os.path.join(artifacts_dir, 'fact_cache', 's1_web'), 'r', encoding='utf-8') as f:
        assert json.load(f) == {"host": "s1_web"}


def test_finish_job_fact_cache_reads_tagged_format(hosts, mocker, tmpdir):
    artifacts_dir = str(tmpdir.mkdir("artifacts"))
    start_fact_cache(hosts, artifacts_dir=artifacts_dir, timeout=0, inventory_id=5)
    bulk_update = mocker.patch('awx.main.tasks.facts.bulk_update_sorted_by_id', return_value=1)

    # Simulate ansible-core 2.19+ writing facts, with values wrapped in data tags
    tagged_facts = {
        "a": {"value": 3, "tags": [{"path": "/tmp/play.yml", "line_num": 1, "col_num": 1, "__ansible_type": "Origin"}], "__ansible_type": "_AnsibleTaggedInt"},
        "c": {"value": {"d": [{"value": "x", "tags": [], "__ansible_type": "_AnsibleTaggedStr"}]}, "tags": [], "__ansible_type": "_AnsibleTaggedDict"},
        "plain": "y",
    }
    _write_future(os.path.join(artifacts_dir, 'fact_cache', 's1_' + hosts[0].name), _tagged_payload(tagged_facts))

    hosts_qs = mock.MagicMock()
    hosts_qs.filter.return_value.select_related.return_value.iterator.return_value = [hosts[0]]

    finish_fact_cache(hosts_qs, artifacts_dir=artifacts_dir, inventory_id=5)

    assert hosts[0].ansible_facts == {"a": 3, "c": {"d": ["x"]}, "plain": "y"}
    bulk_update.assert_called_once()
    for host in hosts[1:]:
        assert host.ansible_facts == {"a": 1, "b": 2}


def test_finish_job_fact_cache_clear_tagged_format(hosts, mocker, ref_time, tmpdir):
    artifacts_dir = str(tmpdir.mkdir("artifacts"))
    start_fact_cache(hosts, artifacts_dir=artifacts_dir, timeout=0, inventory_id=5)
    mocker.patch('awx.main.tasks.facts.bulk_update_sorted_by_id')

    # ansible-core 2.19+ clears facts by removing only the file it uses
    os.remove(os.path.join(artifacts_dir, 'fact_cache', 's1_' + hosts[1].name))

    hosts_qs = mock.MagicMock()
    hosts_qs.filter.return_value.select_related.return_value = [hosts[1]]

    finish_fact_cache(hosts_qs, artifacts_dir=artifacts_dir, inventory_id=5)

    assert hosts[1].ansible_facts == {}
    assert hosts[1].ansible_facts_modified > ref_time
    for host in (hosts[0], hosts[2], hosts[3]):
        assert host.ansible_facts == {"a": 1, "b": 2}
        assert host.ansible_facts_modified == ref_time


def test_finish_job_fact_cache_with_bad_tagged_data(hosts, mocker, tmpdir):
    artifacts_dir = str(tmpdir.mkdir("artifacts"))
    start_fact_cache(hosts, artifacts_dir=artifacts_dir, timeout=0, inventory_id=5)
    bulk_update = mocker.patch('awx.main.tasks.facts.bulk_update_sorted_by_id')

    # A tagged file without a payload, and one whose payload is not JSON
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    _write_future(os.path.join(fact_cache_dir, 's1_' + hosts[0].name), {"not": "a payload"})
    _write_future(os.path.join(fact_cache_dir, 's1_' + hosts[1].name), {"__payload__": "not json"})

    hosts_qs = mock.MagicMock()
    hosts_qs.filter.return_value.select_related.return_value.iterator.return_value = hosts[:2]

    finish_fact_cache(hosts_qs, artifacts_dir=artifacts_dir, inventory_id=5)

    bulk_update.assert_not_called()
