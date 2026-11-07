/* Belfry API explorer additions, loaded after swagger-ui-bundle.js and before drf-spectacular's setup script. */
(function () {
  'use strict';
  var methodOrder = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'];

  // Deep links without Swagger UI's "escaping deep link whitespace with `_`" console error:
  // Belfry's tags and operation ids contain underscores, so every deep link triggered it.
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

  // Sort operations by path, then by HTTP method (GET, POST, PUT, PATCH, DELETE).
  function operationsSorter(a, b) {
    var compared = a.get('path').localeCompare(b.get('path'));
    return compared !== 0 ? compared : methodOrder.indexOf(a.get('method')) - methodOrder.indexOf(b.get('method'));
  }

  var original = window.SwaggerUIBundle;
  if (!original) {
    return;
  }
  var wrapped = function (options) {
    options.plugins = (options.plugins || []).concat([BelfryDeepLinking]);
    options.operationsSorter = operationsSorter;
    return original(options);
  };
  Object.keys(original).forEach(function (k) { wrapped[k] = original[k]; });
  window.SwaggerUIBundle = wrapped;
})();
