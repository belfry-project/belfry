.. _api_launch_playbook:

Running a playbook directly from a project
==========================================

Belfry can run a playbook of a project without a job template. This is handy for
one-off runs and automation that would otherwise create and delete a job template
for each run.

``GET /api/v2/projects/<id>/launch_playbook/`` lists the playbooks of the project
(``playbooks``) and, through ``OPTIONS``, the accepted fields.

``POST /api/v2/projects/<id>/launch_playbook/`` creates and starts a job:

.. code-block:: bash

    curl -u admin -H 'Content-Type: application/json' \
      -d '{"playbook": "hello_world.yml", "inventory": 1, "credentials": [1], "limit": "web", "extra_vars": {"greeting": "hi"}}' \
      https://belfry.example.com/api/v2/projects/8/launch_playbook/

Accepted fields: ``playbook`` and ``inventory`` (required), ``credentials``,
``credential_passwords``, ``extra_vars``, ``limit``, ``job_type`` (``run`` or ``check``),
``verbosity``, ``forks``, ``timeout``, ``execution_environment``, ``instance_groups``,
``diff_mode``, ``job_tags``, ``skip_tags``, ``use_fact_cache``, ``become_enabled`` and
``scm_branch`` (only when the project allows branch override).

The response is the new job (``job`` holds its id). It is a normal job named
``<project> / <playbook>`` without a job template, with output, events, activity stream,
cancel and relaunch. Notifications of the project and its organization apply.
Variables given at launch are not trusted for Jinja templating, like prompted variables
of a job template (setting ``ALLOW_JINJA_IN_EXTRA_VARS``).

Permissions
-----------

Running a playbook directly needs the same access as creating a job template from the
same resources: *use* on the project, the inventory, the credentials and the instance
groups, and *read* on the execution environment. The user who launched the job, system
administrators and auditors, and administrators and auditors of the project's organization
see the job. Relaunching needs the same access as launching.

Turning it off
--------------

The feature is on by default. Set ``ALLOW_DIRECT_PLAYBOOK_LAUNCH`` to ``false`` in the Jobs
settings (``/api/v2/settings/jobs/``) to turn it off. The endpoint then answers 403 and the
``launch_playbook`` link is no longer shown in the project's ``related`` fields.

Collection and CLI
------------------

The ``awx.awx.playbook_launch`` module and the ``awx projects launch_playbook`` CLI command
use this endpoint:

.. code-block:: bash

    awx projects launch_playbook "Demo Project" --playbook hello_world.yml --inventory 1 --wait
