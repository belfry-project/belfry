#!/usr/bin/python
# coding: utf-8 -*-

# Copyright (c) Belfry contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}


DOCUMENTATION = '''
---
module: host_overview
author: "Belfry contributors"
short_description: Get an overview of a host.
description:
    - Get a host with its variables, direct and inherited groups, facts, the last job per job template
      and its most recent jobs and ad hoc commands in one call (C(/api/v2/hosts/{id}/overview/)).
    - This module only reads; it never changes anything.
options:
    name:
      description:
        - The name or id of the host.
      required: True
      type: str
    inventory:
      description:
        - Name or id of the inventory of the host. Needed when the name is used in more than one inventory.
      type: str
    facts:
      description:
        - Only return these top-level facts. All facts are returned when omitted.
      type: list
      elements: str
    jobs:
      description:
        - Number of recent jobs and ad hoc commands to return (0 to 50).
      type: int
      default: 5
extends_documentation_fragment: awx.awx.auth
'''


EXAMPLES = '''
- name: Get the overview of a host
  awx.awx.host_overview:
    name: web1.example.com
    inventory: Production
    facts:
      - ansible_distribution
      - ansible_distribution_version
    jobs: 10
  register: overview

- name: Show the last result per job template
  ansible.builtin.debug:
    msg: "{{ item.job_template.name }}: {{ item.job.status }}"
  loop: "{{ overview.last_job_per_template }}"
'''

RETURN = '''
host:
    description: The host (id, name, description, enabled, instance_id, inventory, created, modified).
    returned: success
    type: dict
variables:
    description: The host variables, parsed.
    returned: success
    type: dict
groups:
    description: The groups the host is directly in (C(direct)) and all groups including inherited ones (C(all)), with id and name.
    returned: success
    type: dict
facts:
    description: The cached facts, or the requested subset.
    returned: success
    type: dict
ansible_facts_modified:
    description: When the facts were last updated.
    returned: success
    type: str
last_job_per_template:
    description: The last job of each job template that ran on the host, with the job's status and whether it failed on this host.
    returned: success
    type: list
recent_jobs:
    description: The most recent jobs and ad hoc commands that ran on the host, newest first.
    returned: success
    type: list
'''


from ..module_utils.controller_api import ControllerAPIModule


def main():
    argument_spec = dict(
        name=dict(required=True),
        inventory=dict(),
        facts=dict(type='list', elements='str'),
        jobs=dict(type='int', default=5),
    )

    module = ControllerAPIModule(argument_spec=argument_spec, supports_check_mode=True)

    name = module.params.get('name')
    inventory = module.params.get('inventory')
    facts = module.params.get('facts')
    jobs = module.params.get('jobs')

    lookup_data = {}
    if inventory:
        lookup_data['inventory'] = module.resolve_name_to_id('inventories', inventory)
    host = module.get_one('hosts', name_or_id=name, allow_none=False, **{'data': lookup_data})

    query = {'jobs': jobs}
    if facts is not None:
        query['facts'] = ','.join(facts)
    response = module.get_endpoint('hosts/{0}/overview/'.format(host['id']), **{'data': query})
    if response['status_code'] != 200:
        module.fail_json(msg='Unable to get the overview of host {0}: {1}'.format(name, response['json']), status_code=response['status_code'])

    module.exit_json(changed=False, **response['json'])


if __name__ == '__main__':
    main()
