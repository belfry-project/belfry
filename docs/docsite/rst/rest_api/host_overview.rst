.. _api_host_overview:

Host overview
=============

``GET /api/v2/hosts/<id>/overview/`` returns in one call what otherwise takes a request to the host, its groups, its facts, its job host summaries and its ad hoc commands.
Anyone who can read the host can read its overview.

Query parameters:

- ``facts=key1,key2``: only return these top-level facts. Without it, all facts are returned.
- ``jobs=N``: the number of recent jobs and ad hoc commands to return, from 0 to 50 (default 5).

The response has these keys:

``host``
    ``id``, ``type``, ``url``, ``name``, ``description``, ``enabled``, ``instance_id``, ``inventory`` (``id``, ``name``, ``kind``), ``created`` and ``modified``.
``variables``
    The host variables, parsed from YAML or JSON.
``groups``
    ``direct``: the groups the host is a member of; ``all``: those and all their parent groups. Each group has ``id`` and ``name``, sorted by name.
``facts``, ``ansible_facts_modified``
    The cached facts (for a host of a constructed inventory, the facts of the host it was constructed from) and when they were last updated.
``last_job_per_template``
    For each job template that has run on the host, its last job that has a result for the host: ``job_template`` (``id``, ``name``), ``job`` (``id``, ``name``, ``status``, ``finished``, ``failed``) and ``host_failed``, whether the job failed on this host. Newest first.
``recent_jobs``
    The most recent jobs with a result for the host and ad hoc commands that ran on it, newest first, each with ``id``, ``type`` (``job`` or ``ad_hoc_command``), ``name``, ``status``, ``created``, ``started``, ``finished`` and ``failed``. Ad hoc commands are listed as soon as they report an event for the host, so running ones are included; jobs appear when they have finished on the host.

Example:

::

    GET /api/v2/hosts/12/overview/?facts=ansible_distribution,ansible_distribution_version&jobs=3

The ``awx.awx.host_overview`` module and ``awx hosts overview <id or name> [--facts a,b] [--jobs N]`` return the same data.
