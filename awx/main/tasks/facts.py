import datetime
import os
import json
import logging

# Django
from django.conf import settings
from django.utils.encoding import smart_str
from django.utils.timezone import now

# django-ansible-base
from ansible_base.lib.logging.runtime import log_excess_runtime

# AWX
from awx.main.utils.db import bulk_update_sorted_by_id
from awx.main.models import Host

logger = logging.getLogger('awx.main.tasks.facts')
system_tracking_logger = logging.getLogger('awx.analytics.system_tracking')

# ansible-core 2.19 changed the jsonfile fact cache format. Older versions store
# each host's facts as plain JSON in a file named after the host. Newer versions
# use a file named "s1_<host>" holding {"__payload__": "<facts as JSON>"}, where
# values may be wrapped with data tags. The ansible-core version inside the
# execution environment is not known here, so both formats are written and read.
TAGGED_CACHE_PREFIX = 's1_'
TAGGED_CACHE_PAYLOAD_KEY = '__payload__'


def _fact_cache_files(fact_cache_dir, hostname, hostnames):
    """Return (path, tagged) for each cache file that may hold facts for a host.

    The tagged file is left out when its name is also another host's plain file.
    """
    files = [(os.path.join(fact_cache_dir, hostname), False)]
    if TAGGED_CACHE_PREFIX + hostname not in hostnames:
        files.append((os.path.join(fact_cache_dir, TAGGED_CACHE_PREFIX + hostname), True))
    return files


def _strip_data_tags(value):
    """Replace ansible-core data tag wrappers with the plain values they hold."""
    if isinstance(value, dict):
        if '__ansible_type' in value and 'value' in value:
            return _strip_data_tags(value['value'])
        return {k: _strip_data_tags(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_data_tags(v) for v in value]
    return value


def _read_fact_file(filepath, tagged):
    with open(filepath, 'r', encoding='utf-8', newline='') as f:
        data = json.load(f)
    if tagged:
        data = _strip_data_tags(json.loads(data[TAGGED_CACHE_PAYLOAD_KEY]))
    return data


@log_excess_runtime(logger, debug_cutoff=0.01, msg='Inventory {inventory_id} host facts prepared for {written_ct} hosts, took {delta:.3f} s', add_log_data=True)
def start_fact_cache(hosts, artifacts_dir, timeout=None, inventory_id=None, log_data=None):
    log_data = log_data or {}
    log_data['inventory_id'] = inventory_id
    log_data['written_ct'] = 0
    # Dict mapping host name -> bool (True if a fact file was written)
    hosts_cached = {}

    # Create the fact_cache directory inside artifacts_dir
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')
    os.makedirs(fact_cache_dir, mode=0o700, exist_ok=True)

    if timeout is None:
        timeout = settings.ANSIBLE_FACT_CACHE_TIMEOUT

    last_write_time = None

    hosts = list(hosts)
    hostnames = {host.name for host in hosts}

    for host in hosts:
        if not host.ansible_facts_modified or (timeout and host.ansible_facts_modified < now() - datetime.timedelta(seconds=timeout)):
            hosts_cached[host.name] = False
            continue  # facts are expired - do not write them

        files = _fact_cache_files(fact_cache_dir, host.name, hostnames)
        if not all(os.path.realpath(filepath).startswith(fact_cache_dir) for filepath, _ in files):
            logger.error(f'facts for host {smart_str(host.name)} could not be cached')
            hosts_cached[host.name] = False
            continue

        try:
            for filepath, tagged in files:
                data = {TAGGED_CACHE_PAYLOAD_KEY: json.dumps(host.ansible_facts)} if tagged else host.ansible_facts
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    os.chmod(f.name, 0o600)
                    json.dump(data, f)
                # Backdate the file by 2 seconds so finish_fact_cache can reliably
                # distinguish these reference files from files updated by ansible.
                # This guarantees fact file mtime < summary file mtime even with
                # zipfile's 2-second timestamp rounding during artifact transfer.
                mtime = os.path.getmtime(filepath)
                backdated = mtime - 2
                os.utime(filepath, (backdated, backdated))
                last_write_time = backdated
            log_data['written_ct'] += 1
            hosts_cached[host.name] = True
        except IOError:
            logger.error(f'facts for host {smart_str(host.name)} could not be cached')
            hosts_cached[host.name] = False
            continue

    # Write summary file directly to the artifacts_dir
    if inventory_id is not None:
        summary_file = os.path.join(artifacts_dir, 'host_cache_summary.json')
        summary_data = {
            'last_write_time': last_write_time,
            'hosts_cached': hosts_cached,
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)


@log_excess_runtime(
    logger,
    debug_cutoff=0.01,
    msg='Inventory {inventory_id} host facts: updated {updated_ct}, cleared {cleared_ct}, unchanged {unmodified_ct}, took {delta:.3f} s',
    add_log_data=True,
)
def finish_fact_cache(host_qs, artifacts_dir, job_id=None, inventory_id=None, job_created=None, log_data=None):
    log_data = log_data or {}
    log_data['inventory_id'] = inventory_id
    log_data['updated_ct'] = 0
    log_data['unmodified_ct'] = 0
    log_data['cleared_ct'] = 0
    # The summary file is directly inside the artifacts dir
    summary_path = os.path.join(artifacts_dir, 'host_cache_summary.json')
    if not os.path.exists(summary_path):
        logger.error(f'Missing summary file at {summary_path}')
        return

    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        facts_write_time = os.path.getmtime(summary_path)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f'Error reading summary file at {summary_path}: {e}')
        return

    hosts_cached_map = summary.get('hosts_cached', {})
    fact_cache_dir = os.path.join(artifacts_dir, 'fact_cache')

    # Phase 1: Scan files on disk to discover which hosts have updated or missing facts
    hosts_with_updates = {}  # hostname -> (path, tagged) of the fact file Ansible modified
    hosts_to_clear = []  # hostnames where Ansible removed a fact file we wrote

    for hostname, was_written in hosts_cached_map.items():
        updated = None
        missing = False
        for filepath, tagged in _fact_cache_files(fact_cache_dir, hostname, hosts_cached_map):
            if os.path.islink(filepath):
                logger.error(f'Invalid path for facts file: {filepath}')
                missing = True
                continue
            if not os.path.isfile(filepath):
                missing = True
                continue
            try:
                modified = os.path.getmtime(filepath)
            except OSError as e:
                logger.warning(f'Could not stat facts file {filepath}: {e}')
                continue
            if modified >= facts_write_time and (updated is None or tagged):
                updated = (filepath, tagged)

        if updated:
            hosts_with_updates[hostname] = updated
        elif missing and was_written:
            # Ansible removes the file of the cache format it uses when facts are cleared
            hosts_to_clear.append(hostname)
        else:
            log_data['unmodified_ct'] += 1

    # Phase 2: Stream updated facts to database in batches
    if hosts_with_updates:
        hosts_to_save = []
        total_rows_updated = 0
        for host in host_qs.filter(name__in=list(hosts_with_updates)).select_related('inventory').iterator():
            filepath, tagged = hosts_with_updates[host.name]
            try:
                new_facts = _read_fact_file(filepath, tagged)
            except (ValueError, OSError, KeyError, TypeError):
                continue

            if new_facts != host.ansible_facts:
                host.ansible_facts = new_facts
                host.ansible_facts_modified = now()
                hosts_to_save.append(host)
                logger.info(
                    f'New fact for inventory {smart_str(host.inventory.name)} host {smart_str(host.name)}',
                    extra=dict(
                        inventory_id=host.inventory.id,
                        host_name=host.name,
                        ansible_facts=host.ansible_facts,
                        ansible_facts_modified=host.ansible_facts_modified.isoformat(),
                        job_id=job_id,
                    ),
                )
                log_data['updated_ct'] += 1
            else:
                log_data['unmodified_ct'] += 1

            if len(hosts_to_save) >= 100:
                total_rows_updated += bulk_update_sorted_by_id(Host, hosts_to_save, fields=['ansible_facts', 'ansible_facts_modified'])
                hosts_to_save = []

        if hosts_to_save:
            total_rows_updated += bulk_update_sorted_by_id(Host, hosts_to_save, fields=['ansible_facts', 'ansible_facts_modified'])

        # Mismatch means a concurrent process changed or deleted hosts between our read and bulk update
        if total_rows_updated != log_data['updated_ct']:
            logger.warning(
                f'Fact update for inventory {inventory_id} job {job_id}: expected to update {log_data["updated_ct"]} hosts but {total_rows_updated} rows were changed'
            )

    # Phase 3: Clear facts for hosts whose files were removed by Ansible
    if hosts_to_clear:
        hosts = list(host_qs.filter(name__in=hosts_to_clear).select_related('inventory'))
        clear_hosts = []
        for host in hosts:
            if job_created and host.ansible_facts_modified and host.ansible_facts_modified > job_created:
                logger.warning(
                    f'Skipping fact clear for host {smart_str(host.name)} in job {job_id} '
                    f'inventory {inventory_id}: host ansible_facts_modified '
                    f'({host.ansible_facts_modified.isoformat()}) is after this job\'s '
                    f'created time ({job_created.isoformat()}). '
                    f'A concurrent job likely updated this host\'s facts while this job was running.'
                )
                log_data['unmodified_ct'] += 1
            else:
                host.ansible_facts = {}
                host.ansible_facts_modified = now()
                clear_hosts.append(host)
                logger.info(f'Facts cleared for inventory {smart_str(host.inventory.name)} host {smart_str(host.name)}')
                log_data['cleared_ct'] += 1

        if clear_hosts:
            rows = bulk_update_sorted_by_id(Host, clear_hosts, fields=['ansible_facts', 'ansible_facts_modified'])
            if rows != len(clear_hosts):
                logger.warning(f'Fact clear for inventory {inventory_id} job {job_id}: expected to clear {len(clear_hosts)} hosts but {rows} rows were changed')

    logger.debug(f'Updated {log_data["updated_ct"]} host facts for inventory {inventory_id} in job {job_id}')
