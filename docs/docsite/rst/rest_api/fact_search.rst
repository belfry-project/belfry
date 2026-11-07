.. _api_fact_search:

Searching hosts by facts
========================

The ``host_filter`` query parameter of ``/api/v2/hosts/`` (and of an inventory's ``hosts/``), and the ``host_filter`` of a smart inventory, can search the facts cached for each host (``ansible_facts``).
Keys in the fact path are separated by ``__`` and ``[]`` traverses a JSON array. Without an operator, the fact must be equal to the value:

::

    ?host_filter=ansible_facts__ansible_distribution=RedHat
    ?host_filter=ansible_facts__ansible_lo__ipv6[]__scope=host

Operators
---------

Belfry adds operators that are written after the fact path, like Django lookups: ``ansible_facts__<path>__<operator>=<value>``.
They can be combined with ``and``, ``or`` and parentheses like every other ``host_filter`` term, also in smart inventories.

.. list-table::
   :header-rows: 1

   * - Operator
     - Matches hosts where the fact
   * - ``iexact``, ``icontains``
     - equals or contains the value, ignoring case
   * - ``startswith``, ``istartswith``, ``endswith``, ``iendswith``
     - starts or ends with the value (``i``: ignoring case)
   * - ``in``
     - equals one of a comma-separated list of values: ``__in=RedHat,CentOS`` or ``__in="Red Hat,CentOS"``
   * - ``isnull``
     - ``true``: is missing or ``null``; ``false``: has a value that is not ``null``
   * - ``exists``
     - ``true``: the key exists (even with a ``null`` value); ``false``: it does not
   * - ``gt``, ``gte``, ``lt``, ``lte``
     - is a number greater than, greater than or equal to, less than, less than or equal to the value
   * - ``vgt``, ``vgte``, ``vlt``, ``vlte``
     - is a version greater than, ... the value

Examples:

::

    ?host_filter=ansible_facts__ansible_distribution__in=RedHat,Rocky,AlmaLinux
    ?host_filter=ansible_facts__ansible_distribution_version__vgte=9.2
    ?host_filter=ansible_facts__ansible_memtotal_mb__gt=8000 and ansible_facts__ansible_kernel__startswith=5.14
    ?host_filter=ansible_facts__ansible_python__version_info__0__gte=3
    ?host_filter=ansible_facts__ansible_local__exists=false

Semantics
---------

- The text operators (``iexact`` to ``iendswith``) and ``in`` compare the text form of the fact: strings as they are, numbers and booleans as written in JSON (``8``, ``true``). So ``__in=8,16`` matches the number 8 and the string ``"8"``.
- A numeric key in the path also indexes a JSON array (``version_info__0`` is the first element). ``[]`` cannot be combined with an operator.
- ``gt``, ``gte``, ``lt`` and ``lte`` compare as numbers. They match facts that are JSON numbers or strings that look like a number (``"9.2"``); other facts (other strings, booleans, objects) never match. The value must be a number.
- ``vgt``, ``vgte``, ``vlt`` and ``vlte`` compare versions made of dot-separated non-negative integers (``9``, ``9.2``, ``5.14.0``) component by component as integers, so ``9.10`` is greater than ``9.9`` (as a number it is smaller). Trailing zero components are ignored: ``9``, ``9.0`` and ``9.0.0`` are equal. Facts that are not such a version, for example ``5.14.0-362.el9.x86_64`` or ``22.04 LTS``, never match; compare a part of them with ``startswith`` instead. The value must be such a version.
- Operators are evaluated by PostgreSQL. Equality without an operator can use the index on ``ansible_facts``; the operators read the facts of the hosts that the rest of the filter leaves, so combine them with selective terms (inventory, group, name, equality) on large installations.
- A key named like an operator (for example a fact called ``in``) at the end of a path is read as the operator.
- Other Django lookups, such as ``regex`` or ``has_keys``, are not supported on facts. A smart inventory refuses them; on ``/api/v2/hosts/`` they are treated as part of the fact path, as before.
