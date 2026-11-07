/* Belfry browsable API (/api/): JSON viewer, links, and sending the forms. No libraries. */
(function () {
  'use strict';

  var csrf = {};
  try { csrf = JSON.parse(document.getElementById('drf_csrf').textContent); } catch (e) { /* no forms */ }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Strings that are API paths become links: "/api/v2/hosts/1/", also with a query.
  var apiPath = /^\/api\/[^\s"]*$/;

  // Render a JSON value; "comma" adds the separator after it, also after a closing bracket.
  function renderValue(value, depth, comma) {
    var node = renderNode(value, depth, comma ? ',' : '');
    if (comma && node.tagName !== 'DETAILS') {
      var wrap = el('span');
      wrap.appendChild(node);
      wrap.appendChild(el('span', 'p', ','));
      return wrap;
    }
    return node;
  }

  function renderNode(value, depth, suffix) {
    if (value === null) return el('span', 'z', 'null');
    if (typeof value === 'string') {
      var span = el('span', 's');
      if (apiPath.test(value)) {
        var a = el('a', '', JSON.stringify(value));
        a.href = value;
        span.appendChild(a);
      } else {
        span.textContent = JSON.stringify(value);
      }
      return span;
    }
    if (typeof value === 'number') return el('span', 'n', String(value));
    if (typeof value === 'boolean') return el('span', 'b', String(value));
    var isArray = Array.isArray(value);
    var keys = isArray ? value : Object.keys(value);
    var open = isArray ? '[' : '{', close = isArray ? ']' : '}';
    if (keys.length === 0) return el('span', 'p', open + close);
    close += suffix;
    var details = el('details');
    details.open = depth < 3 || (depth < 4 && !isArray);
    var summary = el('summary', 'p', open);
    summary.setAttribute('data-size', ' ' + keys.length + (isArray ? ' items ' : ' keys ') + close);
    details.appendChild(summary);
    var children = el('div', 'children');
    keys.forEach(function (item, i) {
      var line = el('div');
      if (!isArray) {
        line.appendChild(el('span', 'k', JSON.stringify(item)));
        line.appendChild(el('span', 'p', ': '));
      }
      line.appendChild(renderValue(isArray ? item : value[item], depth + 1, i < keys.length - 1));
      children.appendChild(line);
    });
    details.appendChild(children);
    details.appendChild(el('span', 'p', close));
    return details;
  }

  var pre = document.getElementById('response-content');
  var rawText = pre ? pre.textContent : '';
  var tree = null;
  if (pre) {
    try {
      var data = JSON.parse(rawText);
      if (data !== null && typeof data === 'object') {
        tree = el('div', 'json');
        tree.appendChild(renderValue(data, 0, false));
        pre.textContent = '';
        pre.appendChild(tree);
      }
    } catch (e) {
      // Not JSON (text, YAML, HTML stdout): link API paths only.
      pre.innerHTML = pre.innerHTML.replace(/"(\/api\/[^\s"<>]*)"/g, '"<a href="$1">$1</a>"');
    }
  }

  document.querySelectorAll('[data-tree]').forEach(function (button) {
    if (!tree) { button.hidden = true; return; }
    button.addEventListener('click', function () {
      var action = button.getAttribute('data-tree');
      if (action === 'raw') {
        var showRaw = !pre.classList.contains('raw');
        pre.classList.toggle('raw', showRaw);
        pre.textContent = '';
        if (showRaw) { pre.textContent = rawText; } else { pre.appendChild(tree); }
        button.textContent = showRaw ? 'Tree' : 'Raw';
        return;
      }
      tree.querySelectorAll('details').forEach(function (d) { d.open = action === 'expand'; });
    });
  });

  // Forms: send PUT, PATCH, DELETE, OPTIONS and the raw-data POST with fetch, as DRF's
  // ajax-form.js does, with the CSRF header; then show the response page.
  function replaceDocument(html, url) {
    document.open();
    document.write(html);
    document.close();
    try { history.replaceState({}, '', url); window.scrollTo(0, 0); } catch (e) { window.location = url; }
  }

  document.querySelectorAll('form[data-method]').forEach(function (form) {
    var clicked = null;
    form.addEventListener('click', function (event) {
      if (event.target.closest('button')) clicked = event.target.closest('button');
    });
    form.addEventListener('submit', function (event) {
      var method = ((clicked && clicked.getAttribute('data-method')) || form.getAttribute('data-method') || 'POST').toUpperCase();
      clicked = null;
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      var headers = { Accept: 'text/html; q=1.0, */*' };
      var body;
      var typeField = form.querySelector('[data-override="content-type"]');
      var contentField = form.querySelector('[data-override="content"]');
      if (typeField && contentField) {
        headers['Content-Type'] = typeField.value;
        body = contentField.value;
      }
      if (!/^(GET|HEAD|OPTIONS|TRACE)$/.test(method) && csrf.csrfHeaderName) {
        headers[csrf.csrfHeaderName] = csrf.csrfToken;
      }
      var url = form.getAttribute('action');
      fetch(url, { method: method, headers: headers, body: body, credentials: 'same-origin' }).then(function (response) {
        var type = response.headers.get('content-type') || '';
        if (type.toLowerCase().indexOf('text/html') === 0) {
          return response.text().then(function (html) { replaceDocument(html, url); });
        }
        window.location = url;
      }, function (error) {
        window.alert('Request failed: ' + error);
      });
    });
  });
})();
