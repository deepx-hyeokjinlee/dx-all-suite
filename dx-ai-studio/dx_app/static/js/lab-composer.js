window.LabComposer = (function () {
  'use strict';

  var currentWorkflow = null;
  var currentTab = 'quick-start';
  var models = [];
  var composerCapabilities = null;
  var modelLoadError = false;
  var customizationHistory = [];
  var customizationHistoryIndex = -1;
  var pendingPluginScaffold = null;
  var savedRecipe = null;
  var compatibleAssets = [];
  var compatibleAssetKey = '';
  var MAX_CUSTOMIZATION_HISTORY = 20;
  var PLUGIN_DRAG_MIME = 'application/x-dx-app-composer-plugin';
  var MODEL_DRAG_MIME = 'application/x-dx-app-composer-model';
  var ASSET_DRAG_MIME = 'application/x-dx-app-composer-asset';
  var CORE_NODE_ORDER = [
    'input',
    'builtin_preprocess',
    'inference',
    'builtin_postprocess',
    'builtin_visualizer'
  ];
  var DEFERRED_COMPOSER_ROUTES = [
    '/api/lab/composer/recipe/export',
    '/api/lab/composer/recipe/import'
  ];

  var ComposerState = {
    selectedNodeId: 'input',
    selectedTemplateModelFile: '',
    dragKind: '',
    get workflow() {
      return currentWorkflow && currentWorkflow.workflow;
    }
  };

  var ComposerApi = {
    update: function (updates) {
      return applyCustomization(updates);
    }
  };

  var ComposerRenderer = {
    palette: renderBuilderPalette,
    canvas: renderBuilderCanvas,
    inspector: renderBuilderInspector
  };

  function text(key) {
    return typeof T === 'function' ? T(key) : key;
  }

  function composerLabels() {
    if (typeof T !== 'function') {
      return {
        quickStart: 'Quick Start',
        templates: 'Templates',
        customize: 'Customize',
        undo: 'Undo',
        redo: 'Redo',
        saveOutput: 'Save Output',
        selectInputAsset: 'Select input asset',
        deviceId: 'Device ID',
        invalidDeviceId: 'Device ID must be a non-negative integer',
        pluginPalette: 'Plugin palette',
        dragPlugin: 'Drag a custom plugin to Preprocess or Postprocess',
        customPlugin: 'Custom plugin',
        saveRecipe: 'Save Recipe',
        exportRecipe: 'Export Recipe',
        importRecipe: 'Import Recipe',
        runPackage: 'Run Package',
        developerPackage: 'Developer Package',
        reusableRecipe: 'Reusable Recipe',
        exportPreflight: 'Export Preflight',
        recipeSaved: 'Recipe saved',
        recipeImportFailed: 'Recipe import failed',
        recipeExportFailed: 'Recipe export failed',
        chooseRecipe: 'Choose a recipe JSON file',
        copyOutVerified: 'Copy-out verified',
        plugins: 'Plugins',
        validation: 'Validation',
        addCustomPreprocess: 'Add custom preprocess',
        addCustomPostprocess: 'Add custom postprocess',
        applyPluginScaffold: 'Apply Plugin Scaffold',
        runWorkflow: 'Run Workflow',
        exportPackage: 'Export Package',
        validationBlocked: 'Workflow validation blocked',
        builder: 'Builder',
        runnableModels: 'Runnable Models',
        compatibleAssets: 'Compatible Assets',
        canvas: 'Canvas',
        inspector: 'Inspector',
        dropModelHere: 'Drop model here',
        dropAssetHere: 'Drop asset here',
        builtInFactoryComponent: 'Built-in Factory Component',
        pluginFactoryIntegration: 'Plugin execution requires Factory integration',
        fixedCoreChain: 'The core chain is fixed so the selected DX App Factory and SyncRunner remain executable.'
      };
    }
    return {
      quickStart: T('Quick Start'),
      templates: T('Templates'),
      customize: T('Customize'),
      undo: T('Undo'),
      redo: T('Redo'),
      saveOutput: T('Save Output'),
      selectInputAsset: T('Select input asset'),
      deviceId: T('Device ID'),
      invalidDeviceId: T('Device ID must be a non-negative integer'),
      pluginPalette: T('Plugin palette'),
      dragPlugin: T('Drag a custom plugin to Preprocess or Postprocess'),
      customPlugin: T('Custom plugin'),
      saveRecipe: T('Save Recipe'),
      exportRecipe: T('Export Recipe'),
      importRecipe: T('Import Recipe'),
      runPackage: T('Run Package'),
      developerPackage: T('Developer Package'),
      reusableRecipe: T('Reusable Recipe'),
      exportPreflight: T('Export Preflight'),
      recipeSaved: T('Recipe saved'),
      recipeImportFailed: T('Recipe import failed'),
      recipeExportFailed: T('Recipe export failed'),
      chooseRecipe: T('Choose a recipe JSON file'),
      copyOutVerified: T('Copy-out verified'),
      plugins: T('Plugins'),
      validation: T('Validation'),
      addCustomPreprocess: T('Add custom preprocess'),
      addCustomPostprocess: T('Add custom postprocess'),
      applyPluginScaffold: T('Apply Plugin Scaffold'),
      runWorkflow: T('Run Workflow'),
      exportPackage: T('Export Package'),
      validationBlocked: T('Workflow validation blocked'),
      builder: T('Builder'),
      runnableModels: T('Runnable Models'),
      compatibleAssets: T('Compatible Assets'),
      canvas: T('Canvas'),
      inspector: T('Inspector'),
      dropModelHere: T('Drop model here'),
      dropAssetHere: T('Drop asset here'),
      builtInFactoryComponent: T('Built-in Factory Component'),
      pluginFactoryIntegration: T('Plugin execution requires Factory integration'),
      fixedCoreChain: T('The core chain is fixed so the selected DX App Factory and SyncRunner remain executable.')
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

  function modelForFile(modelFile) {
    return models.find(function (model) {
      return isRunnable(model) && model.model_file === modelFile;
    }) || null;
  }

  function selectedPaletteModel() {
    var workflow = ComposerState.workflow || {};
    var currentModel = workflow.model || {};
    return modelForFile(currentModel.model_file) || modelForFile(ComposerState.selectedTemplateModelFile);
  }

  function applyModelSelection(model) {
    if (!isRunnable(model)) return Promise.resolve();
    ComposerState.selectedTemplateModelFile = model.model_file;
    if (!currentWorkflow) {
      if (currentTab === 'templates') {
        render();
        return Promise.resolve();
      }
      return createQuickStart(model);
    }
    return ComposerApi.update({ model_selection: { model_file: model.model_file } });
  }

  function applyAssetSelection(path) {
    if (!currentWorkflow || typeof path !== 'string' || !path) return Promise.resolve();
    return ComposerApi.update({ input_selection: { path: path } });
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

  function assetKeyFor(workflow) {
    var input = workflow && workflow.input ? workflow.input : {};
    var model = workflow && workflow.model ? workflow.model : {};
    return [input.kind || '', model.category || ''].join(':');
  }

  async function loadCompatibleAssets(workflow) {
    var input = workflow && workflow.input ? workflow.input : {};
    var kind = input.kind;
    var key = assetKeyFor(workflow);
    if (key === compatibleAssetKey) return compatibleAssets;
    compatibleAssetKey = key;
    compatibleAssets = [];
    if (kind !== 'image' && kind !== 'video') return compatibleAssets;
    var url = kind === 'video'
      ? '/api/videos'
      : '/api/images?category=' + encodeURIComponent((workflow.model || {}).category || '');
    try {
      var response = await fetch(url);
      var data = response.ok ? await response.json() : [];
      if (compatibleAssetKey === key) {
        compatibleAssets = Array.isArray(data) ? data.filter(function (asset) {
          return typeof asset === 'string' && asset;
        }) : [];
      }
    } catch (err) {
      if (compatibleAssetKey === key) compatibleAssets = [];
    }
    return compatibleAssets;
  }

  function customizationSnapshot(workflow) {
    var execution = workflow && workflow.execution ? workflow.execution : {};
    var plugins = workflow && Array.isArray(workflow.plugins) ? workflow.plugins : [];
    var model = workflow && workflow.model ? workflow.model : {};
    var input = workflow && workflow.input ? workflow.input : {};
    return {
      model_file: typeof model.model_file === 'string' ? model.model_file : '',
      input_path: typeof input.path === 'string' ? input.path : '',
      execution: {
        device_id: execution.device_id === undefined ? null : execution.device_id,
        save_output: execution.save_output !== false
      },
      plugins: plugins.filter(function (plugin) {
        return plugin && typeof plugin.id === 'string';
      }).map(function (plugin) {
        return { id: plugin.id, enabled: plugin.enabled === true };
      })
    };
  }

  function recordCustomizationState() {
    if (!currentWorkflow || !currentWorkflow.workflow) return;
    var snapshot = customizationSnapshot(currentWorkflow.workflow);
    var current = customizationHistory[customizationHistoryIndex];
    if (current && JSON.stringify(current) === JSON.stringify(snapshot)) return;
    customizationHistory = customizationHistory.slice(0, customizationHistoryIndex + 1);
    customizationHistory.push(snapshot);
    if (customizationHistory.length > MAX_CUSTOMIZATION_HISTORY) customizationHistory.shift();
    customizationHistoryIndex = customizationHistory.length - 1;
  }

  function resetCustomizationHistory() {
    customizationHistory = [];
    customizationHistoryIndex = -1;
    recordCustomizationState();
  }

  function historyPatch(snapshot) {
    var workflow = currentWorkflow && currentWorkflow.workflow ? currentWorkflow.workflow : {};
    var enabledById = {};
    (snapshot.plugins || []).forEach(function (plugin) {
      enabledById[plugin.id] = plugin.enabled;
    });
    var updates = {
      execution: {
        device_id: snapshot.execution.device_id,
        save_output: snapshot.execution.save_output
      },
      plugins: (workflow.plugins || []).filter(function (plugin) {
        return plugin && typeof plugin.id === 'string';
      }).map(function (plugin) {
        return { id: plugin.id, enabled: enabledById[plugin.id] === true };
      })
    };
    if (snapshot.model_file) {
      updates.model_selection = { model_file: snapshot.model_file };
    }
    if (snapshot.input_path) {
      updates.input_selection = { path: snapshot.input_path };
    }
    return updates;
  }

  function setWorkflow(response, historyAction) {
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
    savedRecipe = null;
    if (historyAction === 'record') recordCustomizationState();
    else if (historyAction !== 'preserve') resetCustomizationHistory();
    render();
    loadCompatibleAssets(currentWorkflow.workflow).then(function () {
      if (currentWorkflow && compatibleAssetKey === assetKeyFor(currentWorkflow.workflow)) render();
    });
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

  function nodeBlockers(node) {
    var validation = currentWorkflow && currentWorkflow.validation ? currentWorkflow.validation : {};
    var blockers = Array.isArray(validation.blockers) ? validation.blockers : [];
    return blockers.filter(function (blocker) {
      return blocker && blocker.node_id === node.id;
    });
  }

  function nodeParameterSummary(node) {
    var params = node && node.params && typeof node.params === 'object' ? node.params : {};
    var entries = Object.keys(params).map(function (key) {
      return key + ': ' + String(params[key]);
    });
    return entries.length ? entries.join(', ') : text('Built-in defaults');
  }

  function appendPluginControls(card, stage) {
    var workflow = currentWorkflow && currentWorkflow.workflow ? currentWorkflow.workflow : {};
    var plugins = Array.isArray(workflow.plugins) ? workflow.plugins : [];
    plugins.filter(function (plugin) {
      return plugin && plugin.stage === stage && typeof plugin.id === 'string';
    }).forEach(function (plugin) {
      var toggle = make('label', 'lab-composer-plugin-toggle');
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = plugin.enabled === true;
      checkbox.addEventListener('change', function () {
        applyCustomization({ plugins: [{ id: plugin.id, enabled: checkbox.checked }] });
      });
      toggle.appendChild(checkbox);
      toggle.appendChild(make('span', '', plugin.id));
      card.appendChild(toggle);
    });

    var control = make('div', 'lab-composer-plugin-control');
    var language = make('select', 'input');
    appendOption(language, 'python', 'Python');
    appendOption(language, 'cpp', 'C++');
    var label = stage === 'preprocess'
      ? composerLabels().addCustomPreprocess
      : composerLabels().addCustomPostprocess;
    var button = appendActionButton(control, 'btn-blue', label, function () {
      planPluginScaffold(stage, language.value);
    });
    button.classList.add('lab-composer-plugin-button');
    card.appendChild(control);
  }

  function appendModelCustomization(card, workflow) {
    var field = make('div', 'lab-composer-node-control');
    var label = make('label', '', text('Model'));
    label.setAttribute('for', 'lab-composer-workflow-model');
    var select = make('select', 'input');
    select.id = 'lab-composer-workflow-model';
    appendOption(select, '', text('Select Model'));
    models.forEach(function (model, index) {
      appendOption(select, String(index), labelFor(model));
      if (workflow.model && workflow.model.model_file === model.model_file) select.value = String(index);
    });
    select.addEventListener('change', function () {
      var selected = selectedModel(select);
      if (!selected) return;
      applyCustomization({ model_selection: { model_file: selected.model_file } });
    });
    field.appendChild(label);
    field.appendChild(select);
    card.appendChild(field);
  }

  function appendAssetCustomization(card, workflow) {
    var input = workflow.input || {};
    if (input.kind !== 'image' && input.kind !== 'video') return;
    var field = make('div', 'lab-composer-node-control');
    var label = make('label', '', composerLabels().selectInputAsset);
    label.setAttribute('for', 'lab-composer-input-asset');
    var select = make('select', 'input');
    select.id = 'lab-composer-input-asset';
    var assets = compatibleAssetKey === assetKeyFor(workflow) ? compatibleAssets.slice() : [];
    if (input.path && assets.indexOf(input.path) === -1) assets.unshift(input.path);
    appendOption(select, '', composerLabels().selectInputAsset);
    assets.forEach(function (asset) {
      appendOption(select, asset, asset);
    });
    select.value = input.path || '';
    select.disabled = !assets.length;
    select.addEventListener('change', function () {
      if (!select.value) return;
      applyCustomization({ input_selection: { path: select.value } });
    });
    field.appendChild(label);
    field.appendChild(select);
    card.appendChild(field);
  }

  function appendExecutionControls(card, workflow) {
    var execution = workflow.execution || {};
    var field = make('div', 'lab-composer-node-control');
    var label = make('label', '', composerLabels().deviceId);
    label.setAttribute('for', 'lab-composer-device-id');
    var device = document.createElement('input');
    device.className = 'input';
    device.id = 'lab-composer-device-id';
    device.type = 'number';
    device.min = '0';
    device.step = '1';
    device.value = execution.device_id === null || execution.device_id === undefined ? '' : String(execution.device_id);
    device.addEventListener('change', function () {
      var deviceId = device.value === '' ? null : Number(device.value);
      if (deviceId !== null && (!Number.isInteger(deviceId) || deviceId < 0)) {
        renderError(composerLabels().invalidDeviceId);
        return;
      }
      applyCustomization({ execution: { device_id: deviceId } });
    });
    field.appendChild(label);
    field.appendChild(device);
    card.appendChild(field);
  }

  function appendPluginDropTarget(card, stage) {
    card.classList.add('lab-composer-plugin-drop-target');
    card.setAttribute('data-plugin-drop-stage', stage);
    card.appendChild(make('p', 'lab-composer-drop-hint', composerLabels().dragPlugin));
    card.addEventListener('dragover', function (event) {
      if (!event.dataTransfer || !Array.prototype.includes.call(event.dataTransfer.types, PLUGIN_DRAG_MIME)) return;
      event.preventDefault();
      card.classList.add('lab-composer-plugin-drop-active');
      event.dataTransfer.dropEffect = 'copy';
    });
    card.addEventListener('dragleave', function () {
      card.classList.remove('lab-composer-plugin-drop-active');
    });
    card.addEventListener('drop', function (event) {
      event.preventDefault();
      card.classList.remove('lab-composer-plugin-drop-active');
      var language = event.dataTransfer ? event.dataTransfer.getData(PLUGIN_DRAG_MIME) : '';
      if (language !== 'python' && language !== 'cpp') return;
      planPluginScaffold(stage, language);
    });
  }

  function renderPluginPalette(graph) {
    var palette = make('section', 'lab-composer-plugin-palette');
    palette.appendChild(make('h4', '', composerLabels().pluginPalette));
    palette.appendChild(make('p', 'txt-dim txt-sm', composerLabels().dragPlugin));
    ['python', 'cpp'].forEach(function (language) {
      var chip = make('button', 'lab-composer-plugin-chip', language === 'python' ? 'Python' : 'C++');
      chip.type = 'button';
      chip.draggable = true;
      chip.setAttribute('aria-label', language + ' ' + composerLabels().customPlugin);
      chip.addEventListener('dragstart', function (event) {
        if (!event.dataTransfer) return;
        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData(PLUGIN_DRAG_MIME, language);
      });
      palette.appendChild(chip);
    });
    graph.appendChild(palette);
  }

  function appendChoice(parent, label, className, selected, clickHandler, dragMime, dragValue) {
    var button = make('button', className + (selected ? ' selected' : ''), label);
    button.type = 'button';
    button.setAttribute('aria-pressed', String(selected));
    button.addEventListener('click', clickHandler);
    if (dragMime && typeof dragValue === 'string') {
      button.draggable = true;
      button.addEventListener('dragstart', function (event) {
        if (!event.dataTransfer) return;
        ComposerState.dragKind = dragMime;
        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData(dragMime, dragValue);
      });
    }
    parent.appendChild(button);
    return button;
  }

  function availableAssets() {
    var workflow = ComposerState.workflow || {};
    var input = workflow.input || {};
    var assets = compatibleAssetKey === assetKeyFor(workflow) ? compatibleAssets.slice() : [];
    if (input.path && assets.indexOf(input.path) === -1) assets.unshift(input.path);
    return assets;
  }

  function appendModelChoices(parent) {
    var selected = selectedPaletteModel();
    if (!models.length) {
      parent.appendChild(make('p', 'lab-composer-empty', modelLoadError
        ? text('Unable to load runnable models. Check the Lab connection and try again.')
        : text('No runnable models are installed. Download a DXNN model before creating a workflow.')));
      return;
    }
    models.forEach(function (model) {
      appendChoice(
        parent,
        labelFor(model),
        'lab-composer-palette-item lab-composer-model-choice',
        !!selected && selected.model_file === model.model_file,
        function () { applyModelSelection(model); },
        MODEL_DRAG_MIME,
        model.model_file
      );
    });
  }

  function appendAssetChoices(parent) {
    var workflow = ComposerState.workflow || {};
    var input = workflow.input || {};
    var assets = availableAssets();
    if (!currentWorkflow) {
      parent.appendChild(make('p', 'txt-dim txt-sm', text('Choose a model to create a workflow first.')));
      return;
    }
    if (!assets.length) {
      parent.appendChild(make('p', 'lab-composer-empty', composerLabels().selectInputAsset));
      return;
    }
    assets.forEach(function (asset) {
      appendChoice(
        parent,
        asset,
        'lab-composer-palette-item lab-composer-asset-choice',
        input.path === asset,
        function () { applyAssetSelection(asset); },
        ASSET_DRAG_MIME,
        asset
      );
    });
  }

  function appendSelectionDropTarget(card, kind) {
    var dragMime = kind === 'model' ? MODEL_DRAG_MIME : ASSET_DRAG_MIME;
    var hint = kind === 'model' ? composerLabels().dropModelHere : composerLabels().dropAssetHere;
    card.classList.add('lab-composer-selection-drop-target');
    card.setAttribute('data-drop-kind', kind);
    card.appendChild(make('p', 'lab-composer-drop-hint', hint));
    card.addEventListener('dragover', function (event) {
      if (!event.dataTransfer || !Array.prototype.includes.call(event.dataTransfer.types, dragMime)) return;
      event.preventDefault();
      card.classList.add('lab-composer-drop-active');
      event.dataTransfer.dropEffect = 'copy';
    });
    card.addEventListener('dragleave', function () {
      card.classList.remove('lab-composer-drop-active');
    });
    card.addEventListener('drop', function (event) {
      event.preventDefault();
      card.classList.remove('lab-composer-drop-active');
      var value = event.dataTransfer ? event.dataTransfer.getData(dragMime) : '';
      if (kind === 'model') {
        var model = modelForFile(value);
        if (model) applyModelSelection(model);
        return;
      }
      if (availableAssets().indexOf(value) !== -1) applyAssetSelection(value);
    });
  }

  function nodeLabel(kind) {
    return {
      input: 'Input',
      builtin_preprocess: 'Preprocess',
      inference: 'Inference',
      builtin_postprocess: 'Postprocess',
      builtin_visualizer: 'Visualize'
    }[kind] || kind;
  }

  function nodeIdForKind(kind) {
    return {
      input: 'input',
      builtin_preprocess: 'preprocess',
      inference: 'inference',
      builtin_postprocess: 'postprocess',
      builtin_visualizer: 'visualize'
    }[kind] || kind;
  }

  function fixedBuilderNodes() {
    var workflow = ComposerState.workflow || {};
    var nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
    return CORE_NODE_ORDER.map(function (kind) {
      return nodes.find(function (node) { return node && node.kind === kind; }) || {
        id: nodeIdForKind(kind),
        kind: kind,
        enabled: true,
        params: {}
      };
    });
  }

  function builderNodeSummary(node) {
    var workflow = ComposerState.workflow || {};
    var model = workflow.model || {};
    var input = workflow.input || {};
    if (node.kind === 'input') return input.path || text('Unavailable');
    if (node.kind === 'inference') return model.name ? labelFor(model) : text('Unavailable');
    if (node.kind === 'builtin_preprocess' || node.kind === 'builtin_postprocess') {
      return composerLabels().builtInFactoryComponent;
    }
    if (node.kind === 'builtin_visualizer') return text('Built-in defaults');
    return nodeParameterSummary(node);
  }

  function selectBuilderNode(nodeId) {
    ComposerState.selectedNodeId = nodeId;
    render();
  }

  function renderBuilderPalette(parent) {
    var palette = make('aside', 'lab-composer-palette');
    palette.appendChild(make('h3', '', composerLabels().builder));
    renderTabs(palette);
    if (currentTab === 'templates') {
      palette.appendChild(make('h4', '', composerLabels().runnableModels));
      appendModelChoices(palette);
      palette.appendChild(make('h4', '', composerLabels().templates));
      var composer = loadCapabilities();
      var templates = composer && composer.templates ? composer.templates : {};
      Object.keys(templates).forEach(function (templateId) {
        appendChoice(
          palette,
          templateId.replace(/_/g, ' '),
          'lab-composer-palette-item lab-composer-template-choice',
          false,
          function () { createTemplate(templateId, selectedPaletteModel()); }
        );
      });
      if (!Object.keys(templates).length) {
        palette.appendChild(make('p', 'txt-dim txt-sm', text('Templates are unavailable until the Lab session is ready.')));
      }
    } else {
      palette.appendChild(make('h4', '', composerLabels().runnableModels));
      appendModelChoices(palette);
    }
    palette.appendChild(make('h4', '', composerLabels().compatibleAssets));
    appendAssetChoices(palette);
    renderPluginPalette(palette);
    parent.appendChild(palette);
  }

  function renderBuilderCanvas(parent) {
    var canvas = make('section', 'lab-composer-canvas');
    canvas.appendChild(make('h3', '', composerLabels().canvas));
    canvas.appendChild(make('p', 'txt-dim txt-sm', composerLabels().fixedCoreChain));
    var chain = make('div', 'lab-composer-node-chain');
    fixedBuilderNodes().forEach(function (node, index) {
      if (index) chain.appendChild(make('span', 'lab-composer-arrow', '→'));
      var blockers = nodeBlockers(node);
      var card = make(
        'article',
        'lab-composer-node' + (ComposerState.selectedNodeId === node.id ? ' selected' : '')
      );
      card.tabIndex = 0;
      card.setAttribute('data-node-id', node.id);
      card.setAttribute('aria-label', text(nodeLabel(node.kind)));
      card.addEventListener('click', function () { selectBuilderNode(node.id); });
      card.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectBuilderNode(node.id);
        }
      });
      card.appendChild(make('strong', '', text(nodeLabel(node.kind))));
      card.appendChild(make('span', 'txt-dim txt-sm', node.kind));
      card.appendChild(make(
        'span',
        'lab-composer-node-status ' + (blockers.length ? 'lab-composer-node-blocked' : 'lab-composer-node-ready'),
        blockers.length ? text('Blocked') : text('Ready')
      ));
      card.appendChild(make('p', 'lab-composer-node-params', builderNodeSummary(node)));
      if (node.kind === 'input') appendSelectionDropTarget(card, 'asset');
      if (node.kind === 'inference') appendSelectionDropTarget(card, 'model');
      if (node.kind === 'builtin_preprocess') appendPluginDropTarget(card, 'preprocess');
      if (node.kind === 'builtin_postprocess') appendPluginDropTarget(card, 'postprocess');
      chain.appendChild(card);
    });
    canvas.appendChild(chain);
    parent.appendChild(canvas);
  }

  function selectedBuilderNode() {
    var nodes = fixedBuilderNodes();
    return nodes.find(function (node) { return node.id === ComposerState.selectedNodeId; }) || nodes[0];
  }

  function renderBuilderInspector(parent) {
    var inspector = make('aside', 'lab-composer-inspector');
    var node = selectedBuilderNode();
    inspector.appendChild(make('h3', '', composerLabels().inspector));
    inspector.appendChild(make('h4', '', text(nodeLabel(node.kind))));
    inspector.appendChild(make('p', 'txt-dim txt-sm', builderNodeSummary(node)));
    if (node.kind === 'input') {
      inspector.appendChild(make('h4', '', composerLabels().compatibleAssets));
      appendAssetChoices(inspector);
    } else if (node.kind === 'inference') {
      inspector.appendChild(make('h4', '', composerLabels().runnableModels));
      appendModelChoices(inspector);
    } else if (node.kind === 'builtin_preprocess' || node.kind === 'builtin_postprocess') {
      var stage = node.kind === 'builtin_preprocess' ? 'preprocess' : 'postprocess';
      inspector.appendChild(make('p', 'lab-composer-factory-note', composerLabels().builtInFactoryComponent));
      inspector.appendChild(make('p', 'lab-composer-factory-note', composerLabels().pluginFactoryIntegration));
      if (currentWorkflow) appendPluginControls(inspector, stage);
    } else if (node.kind === 'builtin_visualizer' && currentWorkflow) {
      var workflow = currentWorkflow.workflow || {};
      var saveOutput = make('label', 'lab-composer-plugin-toggle');
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = workflow.execution && workflow.execution.save_output !== false;
      checkbox.addEventListener('change', function () {
        ComposerApi.update({ execution: { save_output: checkbox.checked } });
      });
      saveOutput.appendChild(checkbox);
      saveOutput.appendChild(make('span', '', composerLabels().saveOutput));
      inspector.appendChild(saveOutput);
      appendExecutionControls(inspector, workflow);
    }
    parent.appendChild(inspector);
  }

  function renderHistoryControls(graph) {
    var controls = make('div', 'lab-composer-history');
    var undo = appendActionButton(controls, 'btn-blue', composerLabels().undo, undoCustomization);
    undo.disabled = customizationHistoryIndex <= 0;
    var redo = appendActionButton(controls, 'btn-blue', composerLabels().redo, redoCustomization);
    redo.disabled = customizationHistoryIndex < 0 || customizationHistoryIndex >= customizationHistory.length - 1;
    graph.appendChild(controls);
  }

  function renderPluginScaffoldPreview(graph) {
    if (!pendingPluginScaffold) return;
    var preview = make('section', 'lab-composer-plugin-preview');
    preview.appendChild(make('h4', '', text('Plugin scaffold preview')));
    (pendingPluginScaffold.operations || []).forEach(function (operation) {
      preview.appendChild(make('p', 'txt-sm', operation.path || text('Unavailable')));
    });
    preview.appendChild(appendActionButton(
      preview,
      'btn-acc',
      composerLabels().applyPluginScaffold,
      applyPluginScaffold
    ));
    graph.appendChild(preview);
  }

  function renderGraph(parent) {
    var graph = make('section', 'lab-composer-graph');
    graph.id = 'lab-composer-graph';
    renderHistoryControls(graph);
    var builder = make('div', 'lab-composer-builder');
    ComposerRenderer.palette(builder);
    ComposerRenderer.canvas(builder);
    ComposerRenderer.inspector(builder);
    graph.appendChild(builder);
    renderPluginScaffoldPreview(graph);
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
    var exportButton = appendActionButton(actions, 'btn-blue', composerLabels().exportPackage, function () {
      exportPackage('run');
    });
    exportButton.disabled = blocked;
    parent.appendChild(actions);
  }

  function renderRecipeControls(parent) {
    var validation = currentWorkflow && currentWorkflow.validation ? currentWorkflow.validation : {};
    if (!currentWorkflow || isBlocked(validation)) return;
    var section = make('section', 'lab-composer-recipe-controls');
    section.appendChild(make('h3', '', composerLabels().saveRecipe));
    var actions = make('div', 'lab-composer-recipe-actions');
    appendActionButton(actions, 'btn-blue', composerLabels().saveRecipe, saveRecipe);
    appendActionButton(actions, 'btn-blue', composerLabels().exportRecipe, exportRecipe);
    var importLabel = make('label', 'btn btn-blue', composerLabels().importRecipe);
    importLabel.setAttribute('for', 'lab-composer-recipe-file');
    var importFile = document.createElement('input');
    importFile.id = 'lab-composer-recipe-file';
    importFile.type = 'file';
    importFile.accept = '.json,application/json';
    importFile.className = 'lab-composer-recipe-file';
    importFile.addEventListener('change', function () {
      var file = importFile.files && importFile.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var recipe;
        try {
          recipe = JSON.parse(String(reader.result || ''));
        } catch (err) {
          renderError(composerLabels().recipeImportFailed);
          return;
        }
        if (typeof recipe !== 'object' || recipe === null || Array.isArray(recipe)) {
          renderError(composerLabels().recipeImportFailed);
          return;
        }
        importRecipe(recipe);
      };
      reader.onerror = function () {
        renderError(composerLabels().recipeImportFailed);
      };
      reader.readAsText(file);
      importFile.value = '';
    });
    actions.appendChild(importLabel);
    actions.appendChild(importFile);
    section.appendChild(actions);
    if (savedRecipe) section.appendChild(make('p', 'txt-dim txt-sm', composerLabels().recipeSaved));
    parent.appendChild(section);
  }

  function renderExportPanel(parent) {
    var validation = currentWorkflow && currentWorkflow.validation ? currentWorkflow.validation : {};
    if (!currentWorkflow || isBlocked(validation)) return;
    var workflow = currentWorkflow.workflow || {};
    var model = workflow.model || {};
    var input = workflow.input || {};
    var plugins = Array.isArray(workflow.plugins) ? workflow.plugins : [];
    var section = make('section', 'lab-composer-export-panel');
    section.appendChild(make('h3', '', composerLabels().exportPreflight));
    var summary = make('dl', 'lab-composer-export-summary');
    [
      [text('Model'), [model.name, model.category].filter(Boolean).join(' · ') || text('Unavailable')],
      [text('Input'), [input.kind, input.path].filter(Boolean).join(' · ') || text('Unavailable')],
      [composerLabels().plugins, plugins.length ? plugins.map(function (plugin) { return plugin.id; }).join(', ') : text('Built-in defaults')],
      [composerLabels().validation, validation.status]
    ].forEach(function (item) {
      summary.appendChild(make('dt', '', item[0]));
      summary.appendChild(make('dd', '', item[1]));
    });
    section.appendChild(summary);
    var actions = make('div', 'lab-composer-export-actions');
    [
      ['run', composerLabels().runPackage],
      ['developer', composerLabels().developerPackage],
      ['recipe', composerLabels().reusableRecipe]
    ].forEach(function (choice) {
      appendActionButton(actions, 'btn-blue', choice[1], function () {
        exportPackage(choice[0]);
      });
    });
    section.appendChild(actions);
    parent.appendChild(section);
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

  async function applyCustomization(updates, historyIndex) {
    if (!currentWorkflow) return;
    setStatus(text('Updating workflow'), 'info');
    var result = await request("/api/lab/composer/customize", {
      manifest_id: currentWorkflow.manifest_id,
      updates: updates
    });
    if (!result || result.error) {
      renderError((result && result.error) || text('Workflow validation blocked'));
      return;
    }
    if (typeof historyIndex === 'number') customizationHistoryIndex = historyIndex;
    setWorkflow(result, typeof historyIndex === 'number' ? 'preserve' : 'record');
  }

  async function undoCustomization() {
    if (customizationHistoryIndex <= 0) return;
    var targetIndex = customizationHistoryIndex - 1;
    await applyCustomization(historyPatch(customizationHistory[targetIndex]), targetIndex);
  }

  async function redoCustomization() {
    if (customizationHistoryIndex < 0 || customizationHistoryIndex >= customizationHistory.length - 1) return;
    var targetIndex = customizationHistoryIndex + 1;
    await applyCustomization(historyPatch(customizationHistory[targetIndex]), targetIndex);
  }

  async function planPluginScaffold(stage, language) {
    if (!currentWorkflow) return;
    setStatus(text('Creating Plugin Scaffold'), 'info');
    var result = await request('/api/lab/composer/plugin/dry_run', {
      workflow_manifest_id: currentWorkflow.manifest_id,
      plugin_name: 'custom_' + stage,
      stage: stage,
      language: language
    });
    if (!result || result.error) {
      renderError((result && result.error) || text('Plugin scaffold planning failed'));
      return;
    }
    pendingPluginScaffold = result;
    render();
  }

  async function applyPluginScaffold() {
    if (!pendingPluginScaffold) return;
    var confirmations = {};
    var required = Array.isArray(pendingPluginScaffold.confirmations)
      ? pendingPluginScaffold.confirmations : [];
    for (var index = 0; index < required.length; index += 1) {
      var confirmation = required[index];
      if (typeof window.confirm === 'function' && !window.confirm(confirmation.label)) return;
      confirmations[confirmation.key] = confirmation.expected;
    }
    setStatus(text('Applying Plugin Scaffold'), 'info');
    var result = await request('/api/lab/composer/plugin/apply', {
      plugin_manifest_id: pendingPluginScaffold.id,
      confirmations: confirmations
    });
    if (!result || result.error) {
      renderError((result && result.error) || text('Plugin scaffold apply failed'));
      return;
    }
    pendingPluginScaffold = null;
    setWorkflow(result, 'record');
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
    renderGraph(shell);
    renderWorkflowSummary(shell);
    if (currentWorkflow) renderValidation(shell, currentWorkflow.validation);
    renderActions(shell);
    renderRecipeControls(shell);
    renderExportPanel(shell);
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

  function downloadRecipe(recipe) {
    var blob = new Blob([JSON.stringify(recipe, null, 2) + '\n'], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = 'workflow.recipe.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 0);
  }

  async function saveRecipe() {
    if (!currentWorkflow) return;
    setStatus(composerLabels().saveRecipe, 'info');
    var result = await request('/api/lab/composer/recipe/export', {
      manifest_id: currentWorkflow.manifest_id
    });
    if (!result || result.error || !result.recipe || typeof result.recipe !== 'object') {
      renderError((result && result.error) || composerLabels().recipeExportFailed);
      return;
    }
    savedRecipe = result.recipe;
    render();
    setStatus(composerLabels().recipeSaved, 'ok');
  }

  async function exportRecipe() {
    if (!currentWorkflow) return;
    setStatus(composerLabels().exportRecipe, 'info');
    var result = await request('/api/lab/composer/recipe/export', {
      manifest_id: currentWorkflow.manifest_id
    });
    if (!result || result.error || !result.recipe || typeof result.recipe !== 'object') {
      renderError((result && result.error) || composerLabels().recipeExportFailed);
      return;
    }
    savedRecipe = result.recipe;
    downloadRecipe(savedRecipe);
    render();
    setStatus(composerLabels().recipeSaved, 'ok');
  }

  async function importRecipe(recipe) {
    setStatus(composerLabels().importRecipe, 'info');
    var result = await request('/api/lab/composer/recipe/import', { recipe: recipe });
    if (!result || result.error) {
      renderError((result && result.error) || composerLabels().recipeImportFailed);
      return;
    }
    setWorkflow(result);
  }

  async function exportPackage(packageType) {
    if (!currentWorkflow) return;
    setStatus(composerLabels().exportPreflight, 'info');
    var result = await request('/api/lab/composer/export', {
      manifest_id: currentWorkflow.manifest_id,
      package_type: packageType
    });
    var output = document.getElementById('lab-composer-result');
    if (!output) return;
    var archiveUrl = result && result.download ? safeOutputUrl(result.download.url) : '';
    if (
      !result || result.error || !result.download || !archiveUrl ||
      typeof result.download.name !== 'string' || !result.download.name
    ) {
      renderError((result && result.error) || text('Package export failed'));
      return;
    }
    clear(output);
    output.appendChild(make('h3', '', text('Export Package')));
    var link = make('a', 'btn btn-acc', result.download.name);
    link.href = archiveUrl;
    link.download = result.download.name;
    output.appendChild(link);
    if (result.copy_out_verified) {
      output.appendChild(make('p', 'txt-dim txt-sm', composerLabels().copyOutVerified));
    }
    setStatus(text('Package export completed'), 'ok');
  }

  async function open() {
    await loadModels();
    loadCapabilities();
    render();
  }

  return { open: open };
})();
