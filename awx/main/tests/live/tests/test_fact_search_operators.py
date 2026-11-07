"""host_filter fact search operators (Belfry), evaluated on PostgreSQL."""

import pytest

from awx.main.models import Organization, Inventory, Host
from awx.main.utils.filters import SmartFilter

FACTS = {
    'fsA': {
        'ansible_distribution': 'RedHat',
        'ansible_distribution_version': '9.2',
        'ansible_kernel': '5.14.0-362.el9.x86_64',
        'ansible_memtotal_mb': 16000,
        'ansible_processor_vcpus': 8,
        'ansible_python': {'version': {'major': 3, 'minor': 9}, 'version_info': [3, 9, 18]},
        'opt': None,
    },
    'fsB': {
        'ansible_distribution': 'Ubuntu',
        'ansible_distribution_version': '22.04',
        'ansible_memtotal_mb': 2048,
        'ansible_processor_vcpus': '2',
        'ansible_python': {'version': {'major': 3, 'minor': 10}, 'version_info': [3, 10, 12]},
    },
    'fsC': {
        'ansible_distribution': 'CentOS',
        'ansible_distribution_version': '9.10',
        'ansible_memtotal_mb': 'unknown',
        'ansible_processor_vcpus': True,
    },
    'fsD': {'ansible_distribution': 'redhat', 'ansible_distribution_version': '9'},
    'fsE': {},
}


@pytest.fixture
def fact_hosts():
    org, _ = Organization.objects.get_or_create(name='fact-search-org')
    inv, _ = Inventory.objects.get_or_create(name='fact-search-inv', organization=org)
    inv.hosts.all().delete()
    hosts = [Host.objects.create(name=name, inventory=inv, ansible_facts=facts) for name, facts in FACTS.items()]
    yield inv
    for inv_ in Inventory.objects.filter(name__startswith='fact-search-smart'):
        inv_.delete()
    for host in hosts:
        host.delete()
    inv.delete()
    org.delete()


def names(filter_string):
    qs = SmartFilter.query_from_string(filter_string).filter(name__startswith='fs')
    return sorted(set(qs.values_list('name', flat=True)))


@pytest.mark.django_db
@pytest.mark.parametrize(
    'filter_string, expected',
    [
        ('ansible_facts__ansible_distribution__icontains=hat', ['fsA', 'fsD']),
        ('ansible_facts__ansible_distribution__iexact=REDHAT', ['fsA', 'fsD']),
        ('ansible_facts__ansible_distribution__startswith=Red', ['fsA']),
        ('ansible_facts__ansible_distribution__istartswith=red', ['fsA', 'fsD']),
        ('ansible_facts__ansible_distribution__endswith=OS', ['fsC']),
        ('ansible_facts__ansible_distribution__iendswith=tu', ['fsB']),
        ('ansible_facts__ansible_distribution__in=RedHat,CentOS', ['fsA', 'fsC']),
        ('ansible_facts__ansible_distribution__in="RedHat,Ubuntu"', ['fsA', 'fsB']),
        ('ansible_facts__ansible_processor_vcpus__in=8,2', ['fsA', 'fsB']),
        ('ansible_facts__ansible_kernel__isnull=true', ['fsB', 'fsC', 'fsD', 'fsE']),
        ('ansible_facts__ansible_kernel__isnull=false', ['fsA']),
        ('ansible_facts__opt__isnull=true', ['fsA', 'fsB', 'fsC', 'fsD', 'fsE']),
        ('ansible_facts__opt__exists=true', ['fsA']),
        ('ansible_facts__opt__exists=false', ['fsB', 'fsC', 'fsD', 'fsE']),
        ('ansible_facts__ansible_python__version__exists=true', ['fsA', 'fsB']),
        ('ansible_facts__ansible_python__version__minor__exists=false', ['fsC', 'fsD', 'fsE']),
        ('ansible_facts__ansible_memtotal_mb__gt=4096', ['fsA']),
        ('ansible_facts__ansible_memtotal_mb__lte=2048', ['fsB']),
        ('ansible_facts__ansible_memtotal_mb__lt=100000', ['fsA', 'fsB']),
        ('ansible_facts__ansible_processor_vcpus__gte=2', ['fsA', 'fsB']),
        ('ansible_facts__ansible_distribution_version__gte=9.2', ['fsA', 'fsB']),
        ('ansible_facts__ansible_python__version__minor__gte=10', ['fsB']),
        ('ansible_facts__ansible_python__version_info__2__gt=12', ['fsA']),
        ('ansible_facts__ansible_distribution_version__vgte=9.2', ['fsA', 'fsB', 'fsC']),
        ('ansible_facts__ansible_distribution_version__vgt=9.9', ['fsB', 'fsC']),
        ('ansible_facts__ansible_distribution_version__vlt=9.2', ['fsD']),
        ('ansible_facts__ansible_distribution_version__vlte=9.0', ['fsD']),
        ('ansible_facts__ansible_distribution_version__vgte=9.0.0', ['fsA', 'fsB', 'fsC', 'fsD']),
        ('ansible_facts__ansible_kernel__vgt=1', []),
        ('ansible_facts__ansible_distribution__icontains=hat and ansible_facts__ansible_memtotal_mb__gt=1', ['fsA']),
        ('ansible_facts__ansible_distribution=Ubuntu or ansible_facts__ansible_distribution_version__vgt=9.9', ['fsB', 'fsC']),
        ('name=fsE or ansible_facts__ansible_distribution__startswith=Cent', ['fsC', 'fsE']),
        ("ansible_facts__ansible_distribution__icontains=\"x' OR 1=1 --\"", []),
    ],
)
def test_fact_operators(fact_hosts, filter_string, expected):
    assert names(filter_string) == expected


@pytest.mark.django_db
def test_smart_inventory_with_fact_operators(fact_hosts):
    smart = Inventory.objects.create(
        name='fact-search-smart',
        kind='smart',
        organization=fact_hosts.organization,
        host_filter='ansible_facts__ansible_distribution_version__vgte=9.2 and ansible_facts__ansible_memtotal_mb__gt=1000',
    )
    assert sorted(smart.hosts.values_list('name', flat=True)) == ['fsA', 'fsB']
