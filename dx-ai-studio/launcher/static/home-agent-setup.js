/* ── Agent setup ──────────────────────────────────────────────
 *
 * Who is going to build it, with which model, at what effort — and whether it
 * is signed in. Visible before you run, because a control you can only reach
 * after starting is a control you cannot use to decide whether to start.
 *
 * Every value here comes from dx_agent_dev. `GET /api/agent/status` already
 * returns, per detected agent: name, models, default_model, reasoning_efforts,
 * default_effort and authenticated. That is the whole form. Nothing is
 * hard-coded on this side — the effort levels in particular differ per agent
 * (copilot has `none`, codex has `minimal` and no `max`, claude has neither),
 * so a fixed list here would be wrong for two of the five.
 *
 * When no CLI is present the same endpoint returns localized `title`/`detail`
 * and an `installOptions` list. An empty set of dropdowns explains nothing;
 * that guidance does.
 */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};

  var API = '/agent/api/agent';
  var _agents = [];          // [{name, models, default_model, reasoning_efforts, default_effort, authenticated}]
  var _current = null;

  function $(id) { return document.getElementById(id); }
  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }
  function _show(el, on) {
    if (!el) return;
    if (on) el.removeAttribute('hidden'); else el.setAttribute('hidden', '');
  }

  function _fill(sel, values, chosen) {
    if (!sel) return;
    sel.innerHTML = values.map(function (v) {
      return '<option value="' + v + '"' + (v === chosen ? ' selected' : '') + '>' + v + '</option>';
    }).join('');
  }

  /* ── the form ────────────────────────────────────────────── */

  function _byName(name) {
    for (var i = 0; i < _agents.length; i++) {
      if (_agents[i].name === name) return _agents[i];
    }
    return null;
  }

  /* Model and effort belong to the agent, so both are rebuilt whenever the
     agent changes. Keeping the old model selected across a change would post
     a model the new CLI has never heard of. */
  function _selectAgent(name) {
    var a = _byName(name);
    if (!a) return;
    _current = a;
    _fill($('setupModel'), a.models || [], a.default_model);
    _fill($('setupEffort'), a.reasoning_efforts || [], a.default_effort);
    _paintAuth(a);
  }

  function _paintAuth(a) {
    var badge = $('setupAuth');
    var hint = $('setupHint');
    if (!badge) return;
    if (a.authenticated === true) {
      badge.textContent = _t('signed in');
      badge.className = 'setup-auth is-ok';
      _show(hint, false);
      return;
    }
    /* authenticated === null means the adapter could not tell. Saying "signed
       out" then would be a guess, and a wrong one sends people to re-run a
       login they already did. */
    badge.textContent = a.authenticated === false ? _t('not signed in') : _t('sign-in unknown');
    badge.className = 'setup-auth' + (a.authenticated === false ? ' is-off' : '');
    _loadHint(a.name);
  }

  /* The exact command, from the adapter that owns it. Interactive OAuth needs a
     terminal, so the honest help is the command rather than a button that
     cannot finish the job. */
  function _loadHint(name) {
    var hint = $('setupHint');
    if (!hint) return;
    fetch(API + '/login/status?agent=' + encodeURIComponent(name))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.hint || d.authenticated === true) { _show(hint, false); return; }
        hint.querySelector('code').textContent = d.hint;
        _show(hint, true);
      })
      .catch(function () { _show(hint, false); });
  }

  /* ── no CLI at all ───────────────────────────────────────── */

  function _degraded(status) {
    var box = $('setupDegraded');
    var form = $('setupForm');
    _show(form, false);
    if (!box) return;
    box.querySelector('[data-role="title"]').textContent =
      status.title || _t('No coding agent found');
    box.querySelector('[data-role="detail"]').textContent = status.detail || '';
    var list = box.querySelector('[data-role="options"]');
    list.innerHTML = '';
    (status.installOptions || []).forEach(function (o) {
      var li = document.createElement('li');
      var state = o.installed
        ? (o.authenticated === true ? _t('signed in') : _t('not signed in'))
        : _t('not installed');
      li.innerHTML = '<b>' + (o.displayName || o.agent) + '</b><span>' + state + '</span>' +
        (o.loginHint ? '<code>' + o.loginHint + '</code>' : '');
      list.appendChild(li);
    });
    _show(box, true);
  }

  /* ── load ────────────────────────────────────────────────── */

  function load() {
    return fetch(API + '/status').then(function (r) { return r.json(); })
      .then(function (status) {
        if (!status || !status.available) { _degraded(status || {}); return; }
        _agents = status.agents || [];
        if (!_agents.length) { _degraded(status); return; }
        _show($('setupDegraded'), false);
        _show($('setupForm'), true);
        _fill($('setupAgent'), _agents.map(function (a) { return a.name; }), _agents[0].name);
        _selectAgent(_agents[0].name);
      })
      .catch(function () {
        /* The module is not running. The Build section still explains itself;
           it just cannot say who would do the building. */
        _show($('setupForm'), false);
        _show($('setupDegraded'), false);
      });
  }

  /* What the console posts to /api/agent/run. */
  function choice() {
    return {
      agent: $('setupAgent') ? $('setupAgent').value : undefined,
      model: $('setupModel') ? $('setupModel').value : undefined,
      effort: $('setupEffort') ? $('setupEffort').value : undefined
    };
  }

  function init() {
    if (!$('setupForm')) return;
    var agent = $('setupAgent');
    if (agent) {
      agent.addEventListener('change', function () { _selectAgent(agent.value); });
    }
    load();
    if (window.DXI18n && DXI18n.onLangChange) {
      DXI18n.onLangChange(function () { if (_current) _paintAuth(_current); });
    }
  }

  ns.agentChoice = choice;
  ns.reloadAgentSetup = load;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
