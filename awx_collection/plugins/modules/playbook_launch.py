#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}


DOCUMENTATION = '''
---
module: playbook_launch
author: "Belfry project"
short_description: Run a playbook of a project directly, without a job template.
description:
    - Run a playbook of a project as a job, without creating a job template (Belfry).
    - Uses the C(/api/v2/projects/N/launch_playbook/) endpoint. Needs use permission on the project, inventory and credentials,
      the same as creating a job template from them.
    - The setting C(ALLOW_DIRECT_PLAYBOOK_LAUNCH) must be on (default).
options:
    project:
      description:
        - Name or id of the project.
      required: True
      type: str
    organization:
      description:
        - Organization of the project, to look up the project by name.
      type: str
    playbook:
      description:
        - Playbook to run, one of the playbooks of the project.
      required: True
      type: str
    inventory:
      description:
        - Name or id of the inventory to run against.
      required: True
      type: str
    credentials:
      description:
        - Names or ids of the credentials to use (one per type; vault credentials need distinct vault ids).
      type: list
      elements: str
    credential_passwords:
      description:
        - Passwords for credentials which are set to prompt on launch.
      type: dict
    extra_vars:
      description:
        - Extra variables for the playbook.
      type: dict
    limit:
      description:
        - Limit the hosts the playbook runs on.
      type: str
    job_type:
      description:
        - Job type.
      choices: [ 'run', 'check' ]
      type: str
    verbosity:
      description:
        - Verbosity level.
      choices: [ 0, 1, 2, 3, 4, 5 ]
      type: int
    forks:
      description:
        - Number of forks.
      type: int
    job_timeout:
      description:
        - Maximum time in seconds the job may run.
      type: int
    scm_branch:
      description:
        - Branch to use; the project must allow branch override.
      type: str
    execution_environment:
      description:
        - Name or id of the execution environment.
      type: str
    instance_groups:
      description:
        - Names or ids of the instance groups to run on.
      type: list
      elements: str
    diff_mode:
      description:
        - Show the changes made by Ansible tasks.
      type: bool
    tags:
      description:
        - Only run plays and tasks tagged with these values.
      type: list
      elements: str
    skip_tags:
      description:
        - Skip plays and tasks tagged with these values.
      type: list
      elements: str
    use_fact_cache:
      description:
        - Use the fact cache.
      type: bool
    become_enabled:
      description:
        - Run the playbook with privilege escalation (like the job template option).
      type: bool
    wait:
      description:
        - Wait for the job to complete.
      default: False
      type: bool
    interval:
      description:
        - The interval to request an update from the controller.
      required: False
      default: 2
      type: float
    timeout:
      description:
        - If waiting for the job to complete this will abort after this
          amount of seconds
      type: int
extends_documentation_fragment: awx.awx.auth
'''

EXAMPLES = '''
- name: Run a playbook of a project
  playbook_launch:
    project: "Demo Project"
    playbook: hello_world.yml
    inventory: "Demo Inventory"
    credentials:
      - "Demo Credential"
    limit: web
    wait: true
'''

RETURN = '''
id:
    description: job id of the newly launched job
    returned: success
    type: int
    sample: 86
status:
    description: status of newly launched job
    returned: success
    type: str
    sample: pending
'''

from ..module_utils.controller_api import ControllerAPIModule


def main():
    argument_spec = dict(
        project=dict(required=True),
        organization=dict(),
        playbook=dict(required=True),
        inventory=dict(required=True),
        credentials=dict(type='list', elements='str'),
        credential_passwords=dict(type='dict', no_log=False),
        extra_vars=dict(type='dict'),
        limit=dict(),
        job_type=dict(choices=['run', 'check']),
        verbosity=dict(type='int', choices=[0, 1, 2, 3, 4, 5]),
        forks=dict(type='int'),
        job_timeout=dict(type='int'),
        scm_branch=dict(),
        execution_environment=dict(),
        instance_groups=dict(type='list', elements='str'),
        diff_mode=dict(type='bool'),
        tags=dict(type='list', elements='str'),
        skip_tags=dict(type='list', elements='str'),
        use_fact_cache=dict(type='bool'),
        become_enabled=dict(type='bool'),
        wait=dict(default=False, type='bool'),
        interval=dict(default=2.0, type='float'),
        timeout=dict(type='int'),
    )
    module = ControllerAPIModule(argument_spec=argument_spec)

    post_data = {'playbook': module.params.get('playbook')}
    for field_name in (
        'credential_passwords',
        'extra_vars',
        'limit',
        'job_type',
        'verbosity',
        'forks',
        'scm_branch',
        'diff_mode',
        'use_fact_cache',
        'become_enabled',
    ):
        if module.params.get(field_name) is not None:
            post_data[field_name] = module.params.get(field_name)
    if module.params.get('job_timeout') is not None:
        post_data['timeout'] = module.params.get('job_timeout')
    if module.params.get('tags') is not None:
        post_data['job_tags'] = ",".join(module.params.get('tags'))
    if module.params.get('skip_tags') is not None:
        post_data['skip_tags'] = ",".join(module.params.get('skip_tags'))

    post_data['inventory'] = module.resolve_name_to_id('inventories', module.params.get('inventory'))
    if module.params.get('execution_environment'):
        post_data['execution_environment'] = module.resolve_name_to_id('execution_environments', module.params.get('execution_environment'))
    for field_name, endpoint in (('credentials', 'credentials'), ('instance_groups', 'instance_groups')):
        if module.params.get(field_name):
            post_data[field_name] = [module.resolve_name_to_id(endpoint, item) for item in module.params.get(field_name)]

    lookup_data = {}
    if module.params.get('organization'):
        lookup_data['organization'] = module.resolve_name_to_id('organizations', module.params.get('organization'))
    project = module.get_one('projects', name_or_id=module.params.get('project'), data=lookup_data)
    if project is None:
        module.fail_json(msg="Unable to find project by name {0}".format(module.params.get('project')))
    url = project['related'].get('launch_playbook')
    if not url:
        module.fail_json(msg="Running playbooks directly from a project is not available (setting ALLOW_DIRECT_PLAYBOOK_LAUNCH, or not a Belfry server)")

    results = module.post_endpoint(url, **{'data': post_data})
    if results['status_code'] != 201:
        module.fail_json(msg="Failed to launch job, see response for details", **{'response': results})

    if module.params.get('wait'):
        results = module.wait_on_url(
            url=results['json']['url'],
            object_name=results['json']['name'],
            object_type='Job',
            timeout=module.params.get('timeout'),
            interval=module.params.get('interval'),
        )

    module.exit_json(
        **{
            'changed': True,
            'id': results['json']['id'],
            'status': results['json']['status'],
        }
    )


if __name__ == '__main__':
    main()
