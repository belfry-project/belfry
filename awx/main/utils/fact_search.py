"""Operators on ansible_facts paths in host_filter (Belfry).

``ansible_facts__<path>__<operator>=<value>`` is turned into a Q object that
PostgreSQL evaluates with JSONB path operators (``#>``, ``#>>``, ``?``), regular
expressions and casts. Key names and values are always passed as query
parameters, never formatted into SQL.

Semantics (see docs/docsite/rst/rest_api/fact_search.rst):

- The fact path is a list of keys separated by ``__``. A numeric key also
  indexes into a JSON array. ``[]`` cannot be combined with an operator.
- ``iexact``, ``icontains``, ``startswith``, ``istartswith``, ``endswith``,
  ``iendswith`` and ``in`` compare the text form of the fact (strings as is,
  numbers and booleans as in JSON, e.g. ``8`` or ``true``). ``in`` takes a
  comma-separated list.
- ``isnull=true`` matches hosts where the fact is missing or JSON null,
  ``isnull=false`` the opposite. ``exists=true`` matches hosts that have the
  key (even with a null value), ``exists=false`` the opposite.
- ``gt``, ``gte``, ``lt``, ``lte`` compare numerically. They match facts that
  are JSON numbers or strings that look like a number; other values never
  match.
- ``vgt``, ``vgte``, ``vlt``, ``vlte`` compare versions made of dot-separated
  non-negative integers (``9``, ``9.2``, ``5.14.0``), component by component
  as integers, so ``9.10`` is greater than ``9.9``. Trailing zero components
  are ignored (``9`` equals ``9.0``). Facts that are not such a version (for
  example ``5.14.0-362.el9``) never match.
"""

import re

from django.contrib.postgres.fields import ArrayField
from django.db.models import BigIntegerField, F, FloatField, Func, Q, TextField, Value
from django.db.models.expressions import Case, When
from django.db.models.fields.json import HasKey, KeyTextTransform, KeyTransform
from django.db.models.functions import Cast
from django.db.models.lookups import (
    EndsWith,
    GreaterThan,
    GreaterThanOrEqual,
    IContains,
    IEndsWith,
    IExact,
    In,
    IsNull,
    IStartsWith,
    LessThan,
    LessThanOrEqual,
    Regex,
    StartsWith,
)

FACTS_FIELD = 'ansible_facts'

TEXT_OPERATORS = {
    'iexact': IExact,
    'icontains': IContains,
    'startswith': StartsWith,
    'istartswith': IStartsWith,
    'endswith': EndsWith,
    'iendswith': IEndsWith,
}
NUMERIC_OPERATORS = {'gt': GreaterThan, 'gte': GreaterThanOrEqual, 'lt': LessThan, 'lte': LessThanOrEqual}
VERSION_OPERATORS = {'v' + k: v for k, v in NUMERIC_OPERATORS.items()}
OPERATORS = frozenset(TEXT_OPERATORS) | frozenset(NUMERIC_OPERATORS) | frozenset(VERSION_OPERATORS) | {'in', 'isnull', 'exists'}

# Patterns used in SQL (constants, passed as parameters).
NUMBER_RE = r'^[-+]?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$'
VERSION_RE = r'^[0-9]{1,18}(\.[0-9]{1,18})*$'
TRAILING_ZEROS_RE = r'(\.0+)+$'


class FactSearchError(RuntimeError):
    pass


def split_operator(key):
    """Return (path, operator) if key is ansible_facts__<path>__<operator>, else None."""
    prefix = FACTS_FIELD + '__'
    if not key.startswith(prefix):
        return None
    pieces = key[len(prefix) :].split('__')
    if len(pieces) < 2 or pieces[-1] not in OPERATORS:
        return None
    path, operator = pieces[:-1], pieces[-1]
    for piece in path:
        if not piece:
            raise FactSearchError('Invalid fact path in %s' % key)
        if piece.endswith('[]'):
            raise FactSearchError('host_filter: __%s cannot be used on a fact path with [] (%s); use a numeric index instead' % (operator, key))
    return path, operator


def _json(path):
    expr = F(FACTS_FIELD)
    for piece in path:
        expr = KeyTransform(piece, expr)
    return expr


def _text(path):
    return KeyTextTransform(path[-1], _json(path[:-1]))


def _bool(operator, value):
    if value in ('true', 'True', True):
        return True
    if value in ('false', 'False', False):
        return False
    raise FactSearchError('host_filter: __%s expects true or false, got %r' % (operator, value))


def _version_tuple(operator, value):
    if not re.match(VERSION_RE, value):
        raise FactSearchError('host_filter: __%s expects a version of dot-separated integers such as 9.2, got %r' % (operator, value))
    parts = [int(p) for p in value.split('.')]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return parts


def fact_q(path, operator, value):
    """Build a Q object for an operator on a fact path. value is the unquoted string."""
    text = _text(path)
    if operator in TEXT_OPERATORS:
        return Q(TEXT_OPERATORS[operator](text, value))
    if operator == 'in':
        values = [v.strip() for v in value.split(',')]
        values = [v[1:-1] if len(v) > 1 and v.startswith('"') and v.endswith('"') else v for v in values]
        if not value or not all(values):
            raise FactSearchError('host_filter: __in expects a comma-separated list of values')
        return Q(In(text, values))
    if operator == 'isnull':
        return Q(IsNull(text, _bool(operator, value)))
    if operator == 'exists':
        parent = _json(path[:-1]) if len(path) > 1 else F(FACTS_FIELD)
        has_key = Q(HasKey(parent, path[-1]))
        if _bool(operator, value):
            return has_key
        if len(path) > 1:
            # A missing parent makes `parent ? key` NULL rather than false.
            return ~has_key | Q(IsNull(_json(path[:-1]), True))
        return ~has_key
    if operator in NUMERIC_OPERATORS:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise FactSearchError('host_filter: __%s expects a number, got %r' % (operator, value))
        numeric = Case(When(Regex(text, NUMBER_RE), then=Cast(text, FloatField())), default=None, output_field=FloatField())
        return Q(NUMERIC_OPERATORS[operator](numeric, Value(number, output_field=FloatField())))
    if operator in VERSION_OPERATORS:
        array_type = ArrayField(BigIntegerField())
        parts = _version_tuple(operator, value)
        normalized = Func(text, Value(TRAILING_ZEROS_RE), Value(''), function='regexp_replace')
        components = Func(normalized, Value('.'), function='string_to_array', output_field=ArrayField(TextField()))
        version = Case(When(Regex(text, VERSION_RE), then=Cast(components, array_type)), default=None, output_field=array_type)
        return Q(VERSION_OPERATORS[operator](version, Value(parts, output_field=array_type)))
    raise FactSearchError('host_filter: unsupported operator __%s' % operator)  # pragma: no cover


__all__ = ['OPERATORS', 'FactSearchError', 'split_operator', 'fact_q']
