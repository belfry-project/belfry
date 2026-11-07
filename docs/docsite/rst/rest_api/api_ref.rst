.. _api_reference:

API Reference Guide
================================

The API Reference Guide documents every endpoint of the Belfry REST API. It is rendered from the OpenAPI 3 schema of the latest Belfry release (`download schema.json <https://github.com/belfry-project/belfry/releases/latest/download/schema.json>`_). The same schema is also available as the :doc:`Belfry OpenAPI Schema <../open_api/index>`.

.. raw:: html

    <link rel="stylesheet" href="../_static/swagger-ui.css" type="text/css">
    <link rel="stylesheet" href="../_static/awx-rest-api.css" type="text/css">
    <div id="swagger-ui"></div>
    <script src="../_static/swagger-ui-bundle.js"></script>
    <script>
    window.addEventListener('load', function() {
      var methodOrder = ['get', 'post', 'put', 'patch', 'delete'];
      window.ui = SwaggerUIBundle({
        url: '../_static/schema.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        validatorUrl: null,
        // Reference only: no "Try it out", as there is no server behind this page
        supportedSubmitMethods: [],
        tagsSorter: 'alpha',
        // Sort by path, then by method
        operationsSorter: function(a, b) {
          var compared = a.get('path').localeCompare(b.get('path'));
          if (compared !== 0) {
            return compared;
          }
          return methodOrder.indexOf(a.get('method')) - methodOrder.indexOf(b.get('method'));
        },
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout'
      });
    });
    </script>
