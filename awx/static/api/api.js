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

  // Theme menu: light, dark or auto (follow the system); remembered in this browser.
  var themeKey = 'belfry-api-theme';
  function currentTheme() {
    try { return localStorage.getItem(themeKey) || 'auto'; } catch (e) { return 'auto'; }
  }
  function applyTheme(theme) {
    if (theme === 'light' || theme === 'dark') {
      document.documentElement.setAttribute('data-theme', theme);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    document.querySelectorAll('[data-theme-set]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-set') === theme));
    });
  }
  applyTheme(currentTheme());
  document.querySelectorAll('[data-theme-set]').forEach(function (button) {
    button.addEventListener('click', function () {
      var theme = button.getAttribute('data-theme-set');
      try { localStorage.setItem(themeKey, theme); } catch (e) { /* not stored */ }
      applyTheme(theme);
      button.closest('details').open = false;
    });
  });

  // Menus (details elements): close when clicking elsewhere or pressing Escape.
  document.addEventListener('click', function (event) {
    document.querySelectorAll('details.menu[open]').forEach(function (menu) {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') document.querySelectorAll('details.menu[open]').forEach(function (menu) { menu.open = false; });
  });

  document.querySelectorAll('[data-dialog]').forEach(function (button) {
    button.addEventListener('click', function () {
      var dialog = document.getElementById(button.getAttribute('data-dialog'));
      if (dialog && dialog.showModal) dialog.showModal();
    });
  });

  // "HTML form": fields generated from the JSON of the raw data form (the defaults Belfry
  // puts there), kept in sync with it. Strings, numbers and booleans get inputs; other
  // values (objects, lists) a small JSON text box. Empty fields that were null stay null.
  function buildForm(form) {
    var fields = form.querySelector('.form-fields');
    var content = form.querySelector('[data-override="content"]');
    var type = form.querySelector('[data-override="content-type"]');
    var data;
    try { data = JSON.parse(content.value || '{}'); } catch (e) { return false; }
    if (data === null || typeof data !== 'object' || Array.isArray(data) || (type && !/json/.test(type.value))) return false;
    fields.textContent = '';
    Object.keys(data).forEach(function (key) {
      var value = data[key];
      var group = el('div', 'form-group');
      var id = 'f-' + Math.random().toString(36).slice(2);
      var input;
      if (typeof value === 'boolean') {
        var label = el('label', 'check');
        input = el('input'); input.type = 'checkbox'; input.checked = value; input.id = id;
        label.appendChild(input); label.appendChild(document.createTextNode(key));
        group.appendChild(label);
      } else {
        var lab = el('label', '', key); lab.htmlFor = id;
        if (value === null) lab.appendChild(el('span', 'null-hint', 'null'));
        group.appendChild(lab);
        if (value !== null && typeof value === 'object') {
          input = el('textarea', 'form-control'); input.value = JSON.stringify(value, null, 2);
        } else {
          input = el('input', 'form-control');
          input.type = typeof value === 'number' ? 'number' : 'text';
          input.value = value === null ? '' : String(value);
        }
        input.id = id;
        group.appendChild(input);
      }
      input.setAttribute('data-key', key);
      input.setAttribute('data-kind', value === null ? 'null' : Array.isArray(value) ? 'json' : typeof value === 'object' ? 'json' : typeof value);
      fields.appendChild(group);
    });
    return true;
  }

  function formToJson(form) {
    var content = form.querySelector('[data-override="content"]');
    var data = {};
    form.querySelectorAll('.form-fields [data-key]').forEach(function (input) {
      var kind = input.getAttribute('data-kind'), key = input.getAttribute('data-key'), v = input.value;
      if (kind === 'boolean') data[key] = input.checked;
      else if (kind === 'number') data[key] = v === '' ? null : Number(v);
      else if (kind === 'json') { try { data[key] = JSON.parse(v); } catch (e) { data[key] = v; } }
      else if (kind === 'null') {
        if (v === '') data[key] = null;
        else { try { data[key] = JSON.parse(v); } catch (e) { data[key] = v; } }
      } else data[key] = v;
    });
    content.value = JSON.stringify(data, null, 4);
  }

  function showView(form, view) {
    var fields = form.querySelector('.form-fields'), raw = form.querySelector('.raw-fields');
    if (view === 'form') {
      if (!buildForm(form)) view = 'raw';
    } else if (!fields.hidden) {
      formToJson(form);
    }
    fields.hidden = view !== 'form';
    raw.hidden = view === 'form';
    form.querySelectorAll('.pill').forEach(function (p) {
      var active = p.getAttribute('data-view') === view;
      p.classList.toggle('active', active);
      p.setAttribute('aria-selected', String(active));
    });
  }

  document.querySelectorAll('form.data-form').forEach(function (form) {
    form.querySelectorAll('.pill').forEach(function (pill) {
      pill.addEventListener('click', function () { showView(form, pill.getAttribute('data-view')); });
    });
    showView(form, 'form');
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
      var formFields = form.querySelector('.form-fields');
      if (formFields && !formFields.hidden) formToJson(form);
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
