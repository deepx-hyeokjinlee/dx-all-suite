/* ── Home working view ────────────────────────────────────────
 *
 * Runs an agent from the front door without leaving the page.
 *
 * It adds no way to run an agent. The launcher already reverse proxies
 * dx_agent_dev at /agent/, so this calls the endpoints the module itself calls
 * — same adapters, same effort levels, same targets. If the module's API moves,
 * this follows for free. What is new is only the layout.
 *
 * The stream is already typed, and the types say where each event belongs:
 *
 *   message  → left, as prose
 *   status   → left, as a status line
 *   command  → right as the line, left as a +1 on the activity summary
 *   log      → right
 *   session  → left footer (the artefact)
 *   done     → both settle
 *   error    → left, with the raw text kept in the terminal
 *   ping     → nowhere; it is a keepalive
 */
(function () {
  'use strict';

  var ns = window.DXLauncher = window.DXLauncher || {};

  var _running = false;
  var _follow = true;
  var _started = 0;
  var _tick = null;
  var _turn = null;          // { block, summary, commands, files, other }
  var _sessionDir = '';

  function $(id) { return document.getElementById(id); }
  function _t(key) {
    return (window.DXI18n && window.DXI18n.T) ? window.DXI18n.T(key) : key;
  }
  function _show(el, on) {
    if (!el) return;
    if (on) el.removeAttribute('hidden'); else el.setAttribute('hidden', '');
  }

  /* ── left: narration ─────────────────────────────────────── */

  function _newTurn() {
    var host = $('workNarration');
    if (!host) return null;
    var block = document.createElement('div');
    block.className = 'work-turn';
    var body = document.createElement('p');
    body.className = 'turn-text';
    var summary = document.createElement('p');
    summary.className = 'turn-activity';
    summary.hidden = true;
    block.appendChild(body);
    block.appendChild(summary);
    host.appendChild(block);
    return { block: block, body: body, summary: summary, commands: 0, files: 0, other: 0 };
  }

  function _say(text) {
    if (!_turn || !_turn.body.textContent) {
      _turn = _newTurn();
    }
    if (!_turn) return;
    _turn.body.textContent = text;
  }

  /* The adapter formats shell lines as `$ cmd` and file tools as `✓ action: path`.
     We own both ends, so counting by prefix is a contract, not a heuristic — and
     anything unrecognised falls back to a plain total rather than a wrong label. */
  function _countActivity(text) {
    if (!_turn) _turn = _newTurn();
    if (!_turn) return;
    var line = String(text || '');
    if (line.indexOf('$ ') === 0) _turn.commands += 1;
    else if (line.indexOf('✓') === 0) _turn.files += 1;
    else _turn.other += 1;

    var parts = [];
    if (_turn.files) parts.push(_turn.files + ' ' + _t('files'));
    if (_turn.commands) parts.push(_turn.commands + ' ' + _t('commands'));
    if (!parts.length) {
      var n = _turn.other;
      parts.push(n + ' ' + _t('activity'));
    }
    _turn.summary.hidden = false;
    _turn.summary.textContent = '⤷ ' + parts.join(' · ');
  }

  function _status(text) {
    var el = $('workStatus');
    if (el) el.textContent = text || '';
  }

  function _error(text) {
    var host = $('workNarration');
    if (!host) return;
    var el = document.createElement('p');
    el.className = 'turn-error';
    el.textContent = text;
    host.appendChild(el);
  }

  /* ── right: terminal ─────────────────────────────────────── */

  function _termLine(text, kind) {
    var out = $('workTerminalOut');
    if (!out) return;
    _show($('workTerminal'), true);
    var line = document.createElement('div');
    line.className = 'term-line' + (kind ? ' is-' + kind : '');
    line.textContent = text;
    out.appendChild(line);
    if (_follow) out.scrollTop = out.scrollHeight;
  }

  /* ── the stream ──────────────────────────────────────────── */

  function renderEvent(ev) {
    if (!ev || ev.type === 'ping' || ev.hidden) return;
    switch (ev.type) {
      case 'message':
        _turn = null;              // a new turn starts on the next message
        _say(ev.text || '');
        break;
      case 'status':
        if (ev.text) _status(ev.text);
        break;
      case 'command':
        _termLine(ev.text || '', 'cmd');
        _countActivity(ev.text || '');
        break;
      case 'log':
        _termLine(ev.text || '', 'log');
        _countActivity(ev.text || '');
        break;
      case 'session':
        if (ev.session_dir) _sessionDir = ev.session_dir;
        break;
      case 'error':
        _error(ev.text || '');
        _termLine(ev.text || '', 'err');
        break;
      case 'done':
        if (ev.session_dir) _sessionDir = ev.session_dir;
        _finish(true);
        break;
      default:
        break;
    }
  }

  /* ── run ─────────────────────────────────────────────────── */

  function _elapsed() {
    var s = Math.floor((Date.now() - _started) / 1000);
    return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }

  function _setBusy(on) {
    _running = on;
    var view = $('homeWork');
    if (view) view.classList.toggle('is-running', on);
    var badge = $('workBadge');
    if (badge) badge.classList.toggle('is-running', on);
    if (on) {
      _started = Date.now();
      _tick = setInterval(function () {
        if (badge) badge.textContent = _t('Working') + ' · ' + _elapsed();
      }, 1000);
    } else if (_tick) {
      clearInterval(_tick);
      _tick = null;
    }
  }

  /* The last thing on the left is the thing you can execute. "Done" is not a
     result; a session folder with a Run control is. */
  function _finish(ok) {
    _setBusy(false);
    var badge = $('workBadge');
    if (badge) badge.textContent = ok ? _t('Completed') : _t('Stopped');
    var foot = $('workArtefact');
    if (foot && _sessionDir) {
      $('workSessionPath').textContent = _sessionDir;
      _show(foot, true);
    }
  }

  function start(prompt) {
    if (_running || !prompt) return;
    var view = $('homeWork');
    if (!view) return;
    _show($('homeAnswer'), false);
    _show(view, true);
    $('workAsk').textContent = prompt;
    $('workNarration').innerHTML = '';
    $('workTerminalOut').innerHTML = '';
    _show($('workArtefact'), false);
    _turn = null;
    _sessionDir = '';
    _follow = true;
    _setBusy(true);

    fetch('/agent/api/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        lang: (window.DXI18n && window.DXI18n.lang) || 'en',
        agent: $('workAgent') ? $('workAgent').value : undefined,
        model: $('workModel') ? $('workModel').value : undefined,
        effort: $('workEffort') ? $('workEffort').value : undefined
      })
    }).then(function (resp) {
      if (!resp.ok || !resp.body) {
        _error(_t('Could not reach DX Agent Dev') + ' (HTTP ' + resp.status + ')');
        _finish(false);
        return;
      }
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      (function pump() {
        reader.read().then(function (chunk) {
          if (chunk.done) { _finish(true); return; }
          buffer += decoder.decode(chunk.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop() || '';
          lines.forEach(function (line) {
            if (line.indexOf('data: ') !== 0) return;
            var frag = line.slice(6);
            if (frag === '[DONE]') return;
            try { renderEvent(JSON.parse(frag)); } catch (e) { /* partial frame */ }
          });
          pump();
        }).catch(function () { _finish(false); });
      })();
    }).catch(function () {
      _error(_t('Could not reach DX Agent Dev'));
      _finish(false);
    });
  }

  function stop() {
    fetch('/agent/api/agent/cancel', { method: 'POST' }).catch(function () {});
    _finish(false);
  }

  /* ── setup chips ─────────────────────────────────────────── */

  function _loadOptions() {
    fetch('/agent/api/agent/models').then(function (r) { return r.json(); })
      .then(function (data) {
        var agents = (data && data.agents) || [];
        var sel = $('workAgent');
        if (sel && agents.length) {
          sel.innerHTML = agents.map(function (a) {
            var id = a.id || a.name || a;
            return '<option value="' + id + '">' + id + '</option>';
          }).join('');
        }
      }).catch(function () { /* no agent CLI here — the view still explains itself */ });
  }

  function init() {
    var view = $('homeWork');
    if (!view) return;

    var out = $('workTerminalOut');
    if (out) {
      /* Auto-follow, but scrolling up pins it. A log that yanks itself to the
         bottom while you are reading is a log nobody reads. */
      out.addEventListener('scroll', function () {
        var atBottom = out.scrollHeight - out.scrollTop - out.clientHeight < 40;
        _follow = atBottom;
        var btn = $('workFollow');
        if (btn) btn.classList.toggle('is-on', _follow);
      });
    }
    var follow = $('workFollow');
    if (follow) {
      follow.addEventListener('click', function () {
        _follow = true;
        follow.classList.add('is-on');
        if (out) out.scrollTop = out.scrollHeight;
      });
    }
    var collapse = $('workCollapse');
    if (collapse) {
      collapse.addEventListener('click', function () {
        var split = $('workSplit');
        if (split) split.classList.toggle('is-collapsed');
      });
    }
    var edit = $('workSetupEdit');
    if (edit) {
      edit.addEventListener('click', function () {
        view.classList.toggle('setup-open');
      });
    }
    var stopBtn = $('workStop');
    if (stopBtn) stopBtn.addEventListener('click', stop);
    var openModule = $('workOpenModule');
    if (openModule) {
      openModule.addEventListener('click', function () {
        window.location.href = '/agent/#ask=' +
          encodeURIComponent($('workAsk').textContent || '');
      });
    }
    _loadOptions();
  }

  ns.homeAgentStart = start;
  ns.initHomeConsole = init;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
