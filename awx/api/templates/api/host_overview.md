# Host Overview

Make a GET request to this resource to get, in one call, the host, its parsed
variables, its groups (`direct` and `all`, including inherited ones), its facts and
when they were last modified, the last job per job template that ran on the host,
and its most recent jobs and ad hoc commands.

Query parameters:

* `facts=key1,key2`: return only these top-level facts (default: all facts).
* `jobs=N`: number of recent jobs and ad hoc commands to return, 0 to 50 (default 5).

Requires read access to the host.
