/* Swagger UI setup for the manual's API reference (rest_api/api_ref). */
window.addEventListener('load', function () {
  'use strict';
  var methodOrder = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'];

  // Deep links without Swagger UI's "escaping deep link whitespace with `_`" console error,
  // which Belfry's tags and operation ids (they contain underscores) triggered on every deep link.
  // Same as awx/static/api/explorer.js in the API explorer of a Belfry instance.
  function BelfryDeepLinking() {
    return {
      statePlugins: {
        layout: {
          actions: {
            parseDeepLinkHash: function (rawHash) {
              return function (system) {
                if (!system.getConfigs().deepLinking || !rawHash) {
                  return;
                }
                var hash = rawHash.slice(1);
                if (hash.charAt(0) === '!') hash = hash.slice(1);
                if (hash.charAt(0) === '/') hash = hash.slice(1);
                var key = system.layoutSelectors.isShownKeyFromUrlHashArray(hash.split('/').map(function (s) { return s || ''; }));
                if (key[0] === 'operations') {
                  system.layoutActions.show(system.layoutSelectors.isShownKeyFromUrlHashArray([key[1] || '']), true);
                }
                system.layoutActions.show(key, true);
                system.layoutActions.scrollTo(key);
                if (system.layoutActions.scrollToVirtualizedOperation) {
                  system.layoutActions.scrollToVirtualizedOperation(key);
                }
              };
            },
          },
        },
      },
    };
  }

  // Tag index: one link per tag with its number of operations; a link opens the tag.
  function buildTagIndex(ui) {
    var index = document.getElementById('api-tag-index');
    if (!index) {
      return;
    }
    var tags = ui.specSelectors.taggedOperations().map(function (tag) { return tag.get('operations').size; }).toJS();
    var names = Object.keys(tags).sort(function (a, b) { return a.localeCompare(b); });
    index.textContent = '';
    names.forEach(function (name) {
      var link = document.createElement('a');
      link.href = '#/' + encodeURIComponent(name);
      link.textContent = name + ' (' + tags[name] + ')';
      link.addEventListener('click', function (event) {
        event.preventDefault();
        history.replaceState(null, '', '#/' + encodeURIComponent(name));
        ui.layoutActions.show(['operations-tag', name], true);
        ui.layoutActions.scrollTo(['operations-tag', name]);
      });
      index.appendChild(link);
    });
  }

  var ui = SwaggerUIBundle({
    url: '../_static/schema.json',
    dom_id: '#swagger-ui',
    deepLinking: true,
    filter: true,
    docExpansion: 'none',
    defaultModelsExpandDepth: 0,
    displayOperationId: true,
    validatorUrl: null,
    // Reference only: no "Try it out", as there is no server behind this page
    supportedSubmitMethods: [],
    tagsSorter: 'alpha',
    // Sort by path, then by method
    operationsSorter: function (a, b) {
      var compared = a.get('path').localeCompare(b.get('path'));
      return compared !== 0 ? compared : methodOrder.indexOf(a.get('method')) - methodOrder.indexOf(b.get('method'));
    },
    presets: [SwaggerUIBundle.presets.apis],
    plugins: [BelfryDeepLinking],
    layout: 'BaseLayout',
    onComplete: function () { buildTagIndex(window.ui); },
  });
  window.ui = ui;
});
