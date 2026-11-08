#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}


DOCUMENTATION = '''
---
module: job_create_template
author: "Jurre van der Gaag - Terpstra (@jterpstra1)"
short_description: Save a job that ran a playbook directly as a job template.
description:
    - Create a job template from a job that ran a playbook directly from a project, without a job template (Belfry),
      for example a job launched with M(awx.awx.playbook_launch).
    - The new job template gets the project, playbook, inventory, credentials, instance groups, extra variables
      and other settings of the job.
    - Uses the C(/api/v2/jobs/N/create_job_template/) endpoint. Needs read access on the job and the permissions
      to create a job template from its project, inventory and credentials.
    - This module always creates a new job template, it does not update one. It fails if a job template with
      the given name already exists in the organization of the project; use M(awx.awx.job_template) to change it.
    - In check mode the job and the name are checked, nothing is created.
options:
    job_id:
      description:
        - ID of the job that ran a playbook directly.
      required: True
      type: int
    name:
      description:
        - Name of the new job template.
      required: True
      type: str
    description:
      description:
        - Description of the new job template.
      type: str
extends_documentation_fragment: awx.awx.auth
'''

EXAMPLES = '''
- name: Run a playbook of a project
  playbook_launch:
    project: "Demo Project"
    playbook: hello_world.yml
    inventory: "Demo Inventory"
    wait: true
  register: run

- name: Save the run as a job template
  job_create_template:
    job_id: "{{ run.id }}"
    name: "Hello world"
    description: "Saved from a direct run"
'''

RETURN = '''
id:
    description: id of the new job template
    returned: success
    type: int
    sample: 42
name:
    description: name of the new job template
    returned: success
    type: str
    sample: Hello world
'''

from ..module_utils.controller_api import ControllerAPIModule


def main():
    argument_spec = dict(
        job_id=dict(type='int', required=True),
        name=dict(required=True),
        description=dict(),
    )
    module = ControllerAPIModule(argument_spec=argument_spec)

    job_id = module.params.get('job_id')
    name = module.params.get('name')

    job = module.get_one('jobs', **{'data': {'id': job_id}})
    if job is None:
        module.fail_json(msg="Unable to find job with id {0}".format(job_id))
    url = job['related'].get('create_job_template')
    if not url:
        module.fail_json(msg="Job {0} did not run a playbook directly from a project (or this is not a Belfry server)".format(job_id))

    project = module.get_one('projects', **{'data': {'id': job['project']}})
    lookup_data = {'name': name}
    if project and project.get('organization'):
        lookup_data['organization'] = project['organization']
    existing = module.get_one('job_templates', **{'data': lookup_data})
    if existing is not None:
        module.fail_json(msg="A job template named {0} already exists (id {1})".format(name, existing['id']))

    post_data = {'name': name}
    if module.params.get('description') is not None:
        post_data['description'] = module.params.get('description')

    # post_endpoint exits with changed=True in check mode
    results = module.post_endpoint(url, **{'data': post_data})
    if results['status_code'] != 201:
        module.fail_json(msg="Failed to create the job template, see response for details", **{'response': results})

    module.exit_json(
        **{
            'changed': True,
            'id': results['json']['id'],
            'name': results['json']['name'],
        }
    )


if __name__ == '__main__':
    main()
