window.LabComposer = (function () {
  'use strict';

  var currentWorkflow = null;
  var currentTab = 'quick-start';
  var models = [];
  var composerCapabilities = null;
  var modelLoadError = false;
  var DEFERRED_COMPOSER_ROUTES = [
    '/api/lab/composer/recipe/export',
    '/api/lab/composer/recipe/import'
  ];

  function text(key) {
    return typeof T === 'function' ? T(key) : key;
  }

  function composerLabels() {
    if (typeof T !== 'function') {
      return {
        quickStart: 'Quick Start',
        templates: 'Templates',
        customize: 'Customize',
        runWorkflow: 'Run Workflow',
        exportPackage: 'Export Package',
        validationBlocked: 'Workflow validation blocked'
      };
    }
    return {
      quickStart: T('Quick Start'),
      templates: T('Templates'),
      customize: T('Customize'),
      runWorkflow: T('Run Workflow'),
      exportPackage: T('Export Package'),
      validationBlocked: T('Workflow validation blocked')
    };
  }

  function isBlocked(validation) {
    return !validation || validation.status !== "ready";
  }

  function make(tag, className, value) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined && value !== null) element.textContent = value;
    return element;
  }

  function clear(element) {
    if (element) element.textContent = '';
  }

  function root() {
    return document.getElementById('lab-flow-root');
  }

  function isRunnable(model) {
    return !!(model && model.model_exists && (model.cpp_sync || model.py_sync));
  }

  function selectionFor(model) {
    return {
      name: model.name,
      category: model.category,
      model_file: model.model_file
    };
  }

  function labelFor(model) {
    return model.name + ' · ' + model.category;
  }

  async function request(path, payload) {
    if (window.LabPortal && typeof window.LabPortal.request === 'function') {
      return window.LabPortal.request(path, payload);
    }
    return postJ(path, payload);
  }

  async function loadModels() {
    if (models.length) return models;
    modelLoadError = false;
    try {
      var response = await fetch('/api/models');
      if (!response.ok) throw new Error('models_http_' + response.status);
      var data = await response.json();
      models = Array.isArray(data) ? data.filter(isRunnable) : [];
    } catch (err) {
      models = [];
      modelLoadError = true;
    }
    return models;
  }

  function loadCapabilities() {
    if (window.LabPortal && typeof window.LabPortal.capabilities === 'function') {
      composerCapabilities = window.LabPortal.capabilities();
    }
    return composerCapabilities && composerCapabilities.composer ? composerCapabilities.composer : null;
  }

  function setStatus(message, kind) {
    var status = document.getElementById('lab-status');
    if (!status) return;
    status.textContent = message;
    status.className = 'lab-status lab-status-' + (kind || 'info');
  }

  function appendOption(select, value, label) {
    var option = make('option', '', label);
    option.value = value;
    select.appendChild(option);
  }

  function selectedModel(select) {
    var index = Number(select.value);
    return Number.isInteger(index) && index >= 0 ? models[index] : null;
  }

  function appendModelSelect(parent, id) {
    var field = make('div', 'fg');
    var label = make('label', '', text('Model'));
    label.setAttribute('for', id);
    var select = make('select', 'input');
    select.id = id;
    appendOption(select, '', text('Select Model'));
    models.forEach(function (model, index) {
      appendOption(select, String(index), labelFor(model));
    });
    field.appendChild(label);
    field.appendChild(select);
    parent.appendChild(field);
    return select;
  }

  function setWorkflow(response) {
    if (!response || !response.workflow || !response.manifest_id) {
      renderError(response && response.error ? response.error : text('Workflow validation blocked'));
      return;
    }
    currentWorkflow = {
      manifest_id: response.manifest_id,
      workflow: response.workflow,
      validation: response.validation || response.workflow.validation || {},
      status: response.status
    };
    render();
    var blocked = isBlocked(currentWorkflow.validation);
    setStatus(
      blocked ? composerLabels().validationBlocked : text('Workflow ready'),
      blocked ? 'err' : 'ok'
    );
  }

  function renderError(message) {
    var result = document.getElementById('lab-composer-result');
    if (!result) return;
    clear(result);
    result.appendChild(make('p', 'lab-composer-error', message));
    setStatus(message, 'err');
  }

  function renderValidation(parent, validation) {
    if (!validation) return;
    var blocked = isBlocked(validation);
    parent.appendChild(make(
      'p',
      blocked ? 'lab-composer-validation lab-composer-validation-blocked' : 'lab-composer-validation lab-composer-validation-ready',
      blocked ? composerLabels().validationBlocked : text('Workflow ready')
    ));
    var blockers = Array.isArray(validation.blockers) ? validation.blockers : [];
    if (blockers.length) {
      var list = make('ul', 'lab-composer-blockers');
      blockers.forEach(function (blocker) {
        list.appendChild(make('li', '', blocker.node_id + ': ' + blocker.code));
      });
      parent.appendChild(list);
    }
    var warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
    if (warnings.length) {
      var warningList = make('ul', 'lab-composer-warnings');
      warnings.forEach(function (warning) {
        warningList.appendChild(make('li', '', warning.node_id ? warning.node_id + ': ' + warning.code : String(warning)));
      });
      parent.appendChild(warningList);
    }
  }

  function renderWorkflowSummary(parent) {
    if (!currentWorkflow || !currentWorkflow.workflow) return;
    var workflow = currentWorkflow.workflow;
    var model = workflow.model || {};
    var input = workflow.input || {};
    var summary = make('section', 'lab-composer-summary');
    summary.appendChild(make('h3', '', text('Workflow Preview')));
    var details = make('dl', 'lab-composer-summary-details');
    var modelIdentity = [model.name, model.category].filter(Boolean).join(' · ');
    var inputIdentity = [input.kind, input.path].filter(Boolean).join(' · ');
    [
      [text('Model'), modelIdentity || text('Unavailable')],
      [text('Input'), inputIdentity || text('Unavailable')]
    ].forEach(function (item) {
      details.appendChild(make('dt', '', item[0]));
      details.appendChild(make('dd', '', item[1]));
    });
    summary.appendChild(details);
    parent.appendChild(summary);
  }

  function renderGraph(parent) {
    var graph = make('section', 'lab-composer-graph');
    graph.id = 'lab-composer-graph';
    graph.hidden = !currentWorkflow;
    graph.setAttribute("aria-hidden", String(!currentWorkflow));
    graph.appendChild(make('h3', '', composerLabels().customize));
    if (!currentWorkflow) {
      graph.appendChild(make('p', 'txt-dim', text('Choose a model to create a workflow first.')));
      parent.appendChild(graph);
      return;
    }
    var names = {
      input: 'Input',
      builtin_preprocess: 'Preprocess',
      inference: 'Inference',
      builtin_postprocess: 'Postprocess',
      builtin_visualizer: 'Visualize'
    };
    var nodes = currentWorkflow.workflow && Array.isArray(currentWorkflow.workflow.nodes)
      ? currentWorkflow.workflow.nodes : [];
    var chain = make('div', 'lab-composer-node-chain');
    nodes.forEach(function (node, index) {
      if (!node || !node.enabled || !names[node.kind]) return;
      if (chain.childNodes.length) chain.appendChild(make('span', 'lab-composer-arrow', '→'));
      var card = make('div', 'lab-composer-node');
      card.appendChild(make('strong', '', names[node.kind]));
      card.appendChild(make('span', 'txt-dim txt-sm', node.kind));
      card.setAttribute('data-node-index', String(index));
      chain.appendChild(card);
    });
    graph.appendChild(chain);
    parent.appendChild(graph);
  }

  function renderResult(parent) {
    var result = make('section', 'lab-composer-result');
    result.id = 'lab-composer-result';
    result.appendChild(make('h3', '', text('Workflow Result')));
    if (!currentWorkflow) {
      result.appendChild(make('p', 'txt-dim', text('Run a ready workflow to view visual output.')));
    }
    parent.appendChild(result);
  }

  function appendActionButton(parent, className, label, handler) {
    var button = make('button', 'btn ' + className, label);
    button.type = 'button';
    button.addEventListener('click', handler);
    parent.appendChild(button);
    return button;
  }

  function renderActions(parent) {
    var actions = make('div', 'lab-composer-actions');
    var validation = currentWorkflow && currentWorkflow.validation ? currentWorkflow.validation : {};
    var blocked = !currentWorkflow || isBlocked(validation);
    var runButton = appendActionButton(actions, 'btn-acc', composerLabels().runWorkflow, runWorkflow);
    runButton.disabled = blocked;
    var exportButton = appendActionButton(actions, 'btn-blue', composerLabels().exportPackage, exportPackage);
    exportButton.disabled = blocked;
    parent.appendChild(actions);
  }

  async function createQuickStart(model) {
    if (!model) {
      renderError(text('Select Model'));
      return;
    }
    setStatus(text('Creating workflow'), 'info');
    var result = await request('/api/lab/composer/quick_start', { selection: selectionFor(model) });
    setWorkflow(result);
  }

  async function createTemplate(templateId, model) {
    setStatus(text('Creating workflow'), 'info');
    var payload = { template_id: templateId };
    if (model) payload.selection = selectionFor(model);
    var result = await request('/api/lab/composer/template', payload);
    setWorkflow(result);
  }

  function renderQuickStart(parent) {
    var panel = make('section', 'lab-composer-panel');
    panel.appendChild(make('h3', '', composerLabels().quickStart));
    panel.appendChild(make('p', 'txt-dim txt-sm', text('Select a runnable model and let Lab choose a compatible input.')));
    var select = appendModelSelect(panel, 'lab-composer-model');
    if (modelLoadError) {
      panel.appendChild(make('p', 'lab-composer-empty', text('Unable to load runnable models. Check the Lab connection and try again.')));
    } else if (!models.length) {
      panel.appendChild(make('p', 'lab-composer-empty', text('No runnable models are installed. Download a DXNN model before creating a workflow.')));
    }
    select.addEventListener('change', function () {
      createQuickStart(selectedModel(select));
    });
    parent.appendChild(panel);
  }

  function renderTemplates(parent) {
    var panel = make('section', 'lab-composer-panel');
    panel.appendChild(make('h3', '', composerLabels().templates));
    panel.appendChild(make('p', 'txt-dim txt-sm', text('Start with a supported task and a compatible runnable model.')));
    var modelSelect = appendModelSelect(panel, 'lab-composer-template-model');
    var templateGrid = make('div', 'lab-composer-template-grid');
    var composer = loadCapabilities();
    var templates = composer && composer.templates ? composer.templates : {};
    Object.keys(templates).forEach(function (templateId) {
      var button = make('button', 'lab-composer-template', templateId.replace(/_/g, ' '));
      button.type = 'button';
      button.addEventListener('click', function () {
        createTemplate(templateId, selectedModel(modelSelect));
      });
      templateGrid.appendChild(button);
    });
    if (!templateGrid.childNodes.length) {
      templateGrid.appendChild(make('p', 'txt-dim', text('Templates are unavailable until the Lab session is ready.')));
    }
    panel.appendChild(templateGrid);
    parent.appendChild(panel);
  }

  function renderTabs(parent) {
    var tabs = make('div', 'lab-composer-tabs');
    [
      { id: 'quick-start', label: composerLabels().quickStart },
      { id: 'templates', label: composerLabels().templates }
    ].forEach(function (tab) {
      var button = make('button', 'lab-composer-tab' + (currentTab === tab.id ? ' active' : ''), tab.label);
      button.type = 'button';
      button.setAttribute('aria-selected', String(currentTab === tab.id));
      button.addEventListener('click', function () {
        currentTab = tab.id;
        render();
      });
      tabs.appendChild(button);
    });
    parent.appendChild(tabs);
  }

  function render() {
    var container = root();
    if (!container) return;
    clear(container);
    var shell = make('section', 'lab-composer');
    shell.appendChild(make('h2', 'lab-composer-title', text('DX App Composer')));
    renderTabs(shell);
    if (currentTab === 'templates') renderTemplates(shell);
    else renderQuickStart(shell);
    renderWorkflowSummary(shell);
    if (currentWorkflow) renderValidation(shell, currentWorkflow.validation);
    renderGraph(shell);
    renderActions(shell);
    renderResult(shell);
    container.appendChild(shell);
  }

  function safeOutputUrl(value) {
    return typeof value === 'string' && value.indexOf('/outputs/') === 0 ? value : '';
  }

  function renderRunResult(data) {
    var result = document.getElementById('lab-composer-result');
    if (!result) return;
    clear(result);
    result.appendChild(make('h3', '', text('Workflow Result')));
    if (!data || data.error) {
      result.appendChild(make('p', 'lab-composer-error', (data && data.error) || text('Workflow run failed')));
      return;
    }
    var image = data.result_image;
    var imageUrl = safeOutputUrl(data.result_image_url);
    var videoUrl = safeOutputUrl(data.result_video_url);
    if (typeof image === 'string' && image) {
      var imageElement = document.createElement('img');
      imageElement.className = 'res-img';
      imageElement.alt = text('Workflow Result');
      imageElement.src = 'data:image/jpeg;base64,' + image;
      result.appendChild(imageElement);
    } else if (imageUrl) {
      var outputImage = document.createElement('img');
      outputImage.className = 'res-img';
      outputImage.alt = text('Workflow Result');
      outputImage.src = imageUrl;
      result.appendChild(outputImage);
    } else if (videoUrl) {
      var video = document.createElement('video');
      video.className = 'res-img';
      video.controls = true;
      video.src = videoUrl;
      result.appendChild(video);
    } else {
      result.appendChild(make('p', 'txt-dim', text('Workflow completed without a visual output.')));
    }
    ['exit_code', 'fps', 'latency_ms'].forEach(function (key) {
      if (data[key] !== undefined && data[key] !== null) {
        result.appendChild(make('p', 'txt-sm', key + ': ' + String(data[key])));
      }
    });
  }

  async function runWorkflow() {
    if (!currentWorkflow) return;
    setStatus(text('Running workflow'), 'info');
    var result = await request(
      "/api/lab/composer/run",
      { manifest_id: currentWorkflow.manifest_id }
    );
    renderRunResult(result);
    setStatus(result && result.error ? result.error : text('Workflow completed'), result && result.error ? 'err' : 'ok');
  }

  async function exportPackage() {
    if (!currentWorkflow) return;
    var result = await request('/api/lab/composer/export', {
      manifest_id: currentWorkflow.manifest_id,
      package_type: 'run'
    });
    var output = document.getElementById('lab-composer-result');
    if (!output) return;
    var archiveUrl = result && result.download ? safeOutputUrl(result.download.url) : '';
    if (!result || result.error || !result.download || !archiveUrl || !result.download.name) {
      renderError((result && result.error) || text('Package export failed'));
      return;
    }
    clear(output);
    output.appendChild(make('h3', '', text('Export Package')));
    var link = make('a', 'btn btn-acc', result.download.name);
    link.href = archiveUrl;
    link.download = result.download.name;
    output.appendChild(link);
    setStatus(text('Package export completed'), 'ok');
  }

  async function open() {
    await loadModels();
    loadCapabilities();
    render();
  }

  return { open: open };
})();
