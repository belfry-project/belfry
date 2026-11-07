import pytest

from awx.api.versioning import reverse
from awx.main.models import AdHocCommand, AdHocCommandEvent, Group, Host, Inventory, Job, JobHostSummary, JobTemplate


@pytest.fixture
def overview_host(organization):
    inv = Inventory.objects.create(name='overview-inv', organization=organization)
    parent = Group.objects.create(name='parent', inventory=inv)
    child = Group.objects.create(name='child', inventory=inv)
    Group.objects.create(name='unrelated', inventory=inv)
    parent.children.add(child)
    host = Host.objects.create(
        name='web1',
        inventory=inv,
        variables='ansible_host: 10.0.0.1\nrole: web',
        ansible_facts={'ansible_distribution': 'RedHat', 'ansible_memtotal_mb': 2048, 'ansible_kernel': '5.14'},
    )
    child.hosts.add(host)
    return host


def add_job(host, template, status='successful', host_failed=False):
    job = Job.objects.create(name=template.name, job_template=template, unified_job_template=template, inventory=host.inventory, status=status)
    JobHostSummary.objects.create(job=job, host=host, failures=1 if host_failed else 0, ok=0 if host_failed else 1)
    return job


def add_ad_hoc(host, status='running'):
    ahc = AdHocCommand.objects.create(inventory=host.inventory, module_name='ping', status=status)
    AdHocCommandEvent.objects.create(ad_hoc_command=ahc, host=host, event='runner_on_ok', job_created=ahc.created)
    return ahc


def get_overview(get, host, user, query='', expect=200):
    return get(reverse('api:host_overview', kwargs={'pk': host.pk}) + query, user, expect=expect)


@pytest.mark.django_db
def test_overview_content(get, admin_user, overview_host):
    jt1 = JobTemplate.objects.create(name='deploy')
    jt2 = JobTemplate.objects.create(name='patch')
    add_job(overview_host, jt1, status='failed', host_failed=True)
    last_deploy = add_job(overview_host, jt1)
    last_patch = add_job(overview_host, jt2, status='failed', host_failed=True)
    ahc = add_ad_hoc(overview_host)

    data = get_overview(get, overview_host, admin_user).data

    assert data['host']['id'] == overview_host.id
    assert data['host']['name'] == 'web1'
    assert data['host']['inventory'] == {'id': overview_host.inventory_id, 'name': 'overview-inv', 'kind': ''}
    assert data['variables'] == {'ansible_host': '10.0.0.1', 'role': 'web'}
    assert [g['name'] for g in data['groups']['direct']] == ['child']
    assert [g['name'] for g in data['groups']['all']] == ['child', 'parent']
    assert data['facts'] == overview_host.ansible_facts
    assert 'ansible_facts_modified' in data

    per_template = {e['job_template']['name']: e for e in data['last_job_per_template']}
    assert per_template['deploy']['job']['id'] == last_deploy.id
    assert per_template['deploy']['job']['status'] == 'successful'
    assert per_template['deploy']['host_failed'] is False
    assert per_template['patch']['job']['id'] == last_patch.id
    assert per_template['patch']['job']['status'] == 'failed'
    assert per_template['patch']['host_failed'] is True
    assert per_template['patch']['job_template']['id'] == jt2.id

    recent = data['recent_jobs']
    assert len(recent) == 4
    assert {(j['type'], j['id']) for j in recent} >= {('ad_hoc_command', ahc.id), ('job', last_patch.id)}
    assert {'id', 'type', 'name', 'status', 'started', 'finished', 'failed', 'created'} <= set(recent[0])


@pytest.mark.django_db
def test_overview_parameters(get, admin_user, overview_host):
    jt = JobTemplate.objects.create(name='deploy')
    for _ in range(7):
        add_job(overview_host, jt)

    data = get_overview(get, overview_host, admin_user, '?facts=ansible_distribution,missing,ansible_kernel').data
    assert data['facts'] == {'ansible_distribution': 'RedHat', 'ansible_kernel': '5.14'}
    assert len(data['recent_jobs']) == 5

    assert len(get_overview(get, overview_host, admin_user, '?jobs=2').data['recent_jobs']) == 2
    assert get_overview(get, overview_host, admin_user, '?jobs=0').data['recent_jobs'] == []
    assert len(get_overview(get, overview_host, admin_user, '?jobs=50').data['recent_jobs']) == 7
    for bad in ('51', '-1', 'x'):
        get_overview(get, overview_host, admin_user, '?jobs=' + bad, expect=400)


@pytest.mark.django_db
def test_overview_permissions(get, overview_host, rando, alice):
    get_overview(get, overview_host, rando, expect=403)
    overview_host.inventory.read_role.members.add(alice)
    assert get_overview(get, overview_host, alice).data['host']['id'] == overview_host.id


@pytest.mark.django_db
def test_overview_query_count(get, admin_user, overview_host, django_assert_max_num_queries):
    url = reverse('api:host_overview', kwargs={'pk': overview_host.pk})
    add_job(overview_host, JobTemplate.objects.create(name='first'))
    add_ad_hoc(overview_host)
    get(url, admin_user, expect=200)  # warm up caches (settings, user roles)
    with django_assert_max_num_queries(40) as small:
        get(url, admin_user, expect=200)

    for i in range(10):
        jt = JobTemplate.objects.create(name='jt%d' % i)
        add_job(overview_host, jt)
        add_job(overview_host, jt)
        add_ad_hoc(overview_host, status='successful')
        group = Group.objects.create(name='g%d' % i, inventory=overview_host.inventory)
        group.hosts.add(overview_host)

    with django_assert_max_num_queries(len(small.captured_queries)):
        data = get(url + '?jobs=50', admin_user, expect=200).data
    assert len(data['last_job_per_template']) == 11
    assert len(data['recent_jobs']) == 32
