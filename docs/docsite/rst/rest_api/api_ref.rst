.. _api_reference:

API Reference Guide
================================

The API Reference Guide documents every endpoint of the Belfry REST API. It is rendered from the OpenAPI 3 schema of the latest Belfry release (`download schema.json <https://github.com/belfry-project/belfry/releases/latest/download/schema.json>`_). The same schema is also available as the :doc:`Belfry OpenAPI Schema <../open_api/index>`.

Using the reference
-------------------

- Type in the **Filter by tag** box to show only matching groups of endpoints, or pick a group from the index below. Groups are collapsed until you open them.
- Every group and operation has its own link: open one and copy the address from the browser to share it.
- Each operation shows its parameters, the request body and the responses, with an example value generated from the schema.

Basics of the API:

- **Authentication**: requests run with the permissions of the user who makes them. Use HTTP basic authentication or the session of a browser that is logged in; see :ref:`api_session_auth` and the other methods in :doc:`authentication`.
- **Pagination**: lists return ``count``, ``next``, ``previous`` and ``results``; use ``page`` and ``page_size`` (at most 200). See :doc:`pagination`.
- **Filtering and sorting**: filter lists with field lookups such as ``?name__icontains=web`` or ``?created__gt=2026-01-01``, and sort with ``order_by``. Hosts also accept ``host_filter``, for example ``?host_filter=name=web01 or groups__name=db``. See :doc:`filtering`, :doc:`searching` and :doc:`sorting`.

Try the API on your own instance
--------------------------------

Every Belfry instance serves an interactive **API explorer** at ``https://<your Belfry server>/api/v2/docs/`` (and the same schema as ReDoc at ``/api/v2/docs/redoc/``). It shows the API of that instance and runs requests with **Try it out**:

- When you are logged in to the web UI or the browsable API in the same browser, requests use your session, with the CSRF token for POST, PUT, PATCH and DELETE.
- Otherwise use **Authorize** to enter a username and password (HTTP basic authentication). The explorer does not keep them after you close or reload the page.
- Requests have exactly the permissions of your user, as with any other API client: what you may not see or change returns 403 or 404.

The :doc:`browsable API <browseable>` at ``/api/v2/`` is the other way to explore an instance: follow the links between resources and send requests with its forms.

Endpoint groups
---------------

.. raw:: html

    <div id="api-tag-index"></div>
    <link rel="stylesheet" href="../_static/swagger-ui.css" type="text/css">
    <link rel="stylesheet" href="../_static/awx-rest-api.css" type="text/css">
    <div id="swagger-ui"></div>
    <script src="../_static/swagger-ui-bundle.js"></script>
    <script src="../_static/api-ref.js"></script>
