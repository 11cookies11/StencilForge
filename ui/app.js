(() => {
  const state = {
    backend: null,
    config: null,
    inputDir: "",
    outputPath: "",
    configPath: "",
  };

  const fieldMap = {
    ThicknessInput: "thickness_mm",
    PasteOffsetInput: "paste_offset_mm",
    OutlineMarginInput: "outline_margin_mm",
    OutputModeSelect: "output_mode",
    ArcStepsInput: "arc_steps",
    CurveResolutionInput: "curve_resolution",
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function connectBackend() {
    if (!window.qt || !window.QWebChannel) {
      return;
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
      state.backend = channel.objects.backend;
      wireBackendSignals();
      initializeUI();
      requestConfig();
    });
  }

  function wireBackendSignals() {
    const backend = state.backend;
    if (!backend) return;
    backend.configChanged.connect((cfg) => {
      state.config = cfg;
      applyConfigToUI(cfg);
    });
    backend.filesScanned.connect((payload) => {
      updateFileList(payload.files || []);
    });
    backend.jobStatus.connect((status) => {
      updateStatus(status);
    });
    backend.jobProgress.connect((value) => {
      updateProgress(value);
    });
    backend.jobLog.connect((line) => {
      appendLog(line);
    });
    backend.jobDone.connect((result) => {
      updateStatus("success");
      appendLog(`Done: ${result.output_stl || ""}`);
    });
    backend.jobError.connect((message) => {
      updateStatus("error");
      appendLog(`Error: ${message}`);
    });
  }

  function initializeUI() {
    wirePickers();
    wireConfigInputs();
    wireRunControls();
  }

  function requestConfig() {
    if (!state.backend) return;
    const cfg = state.backend.getConfig();
    if (cfg) {
      state.config = cfg;
      applyConfigToUI(cfg);
    }
  }

  function wirePickers() {
    const inputDir = byId("InputDirPicker");
    const outputPath = byId("OutputPathPicker");
    const configPath = byId("ConfigPathPicker");
    const browseInput = byId("BrowseInputButton");
    const browseOutput = byId("BrowseOutputButton");
    const browseConfig = byId("BrowseConfigButton");
    const fileInput = byId("InputFileInput");
    const fileButton = byId("InputFileButton");

    if (browseInput) {
      browseInput.addEventListener("click", () => {
        if (!state.backend) return;
        const picked = state.backend.pickDirectory();
        if (picked && inputDir) {
          inputDir.value = picked;
          state.inputDir = picked;
          scanFiles(picked);
        }
      });
    }
    if (browseOutput) {
      browseOutput.addEventListener("click", () => {
        if (!state.backend) return;
        const picked = state.backend.pickSaveFile("stencil.stl");
        if (picked && outputPath) {
          outputPath.value = picked;
          state.outputPath = picked;
        }
      });
    }
    if (browseConfig) {
      browseConfig.addEventListener("click", () => {
        if (!state.backend) return;
        const picked = state.backend.pickConfigFile();
        if (picked && configPath) {
          configPath.value = picked;
          state.configPath = picked;
          state.backend.loadConfig(picked);
        }
      });
    }
    if (fileButton && fileInput) {
      fileButton.addEventListener("click", () => fileInput.click());
    }
    if (fileInput) {
      fileInput.addEventListener("change", () => {
        const files = Array.from(fileInput.files || []);
        updateFileList(files.map((f) => f.name));
        if (files.length && files[0].path && inputDir) {
          const path = files[0].path;
          const dir = path.replace(/[\\/][^\\/]+$/, "");
          inputDir.value = dir;
          state.inputDir = dir;
          scanFiles(dir);
        }
      });
    }

    if (inputDir) {
      inputDir.addEventListener("change", () => {
        state.inputDir = inputDir.value.trim();
        scanFiles(state.inputDir);
      });
    }
    if (outputPath) {
      outputPath.addEventListener("change", () => {
        state.outputPath = outputPath.value.trim();
      });
    }
    if (configPath) {
      configPath.addEventListener("change", () => {
        state.configPath = configPath.value.trim();
        if (state.backend && state.configPath) {
          state.backend.loadConfig(state.configPath);
        }
      });
    }
  }

  function wireConfigInputs() {
    Object.keys(fieldMap).forEach((id) => {
      const el = byId(id);
      if (!el) return;
      el.addEventListener("change", () => {
        const key = fieldMap[id];
        const value = el.type === "number" ? Number(el.value) : el.value;
        updateConfig({ [key]: value });
      });
    });
  }

  function wireRunControls() {
    const runButtons = document.querySelectorAll("[data-action='run']");
    const stopButtons = document.querySelectorAll("[data-action='stop']");
    runButtons.forEach((btn) => {
      btn.addEventListener("click", () => runJob());
    });
    stopButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        if (state.backend) state.backend.stopJob();
      });
    });
  }

  function updateConfig(partial) {
    if (!state.backend) return;
    state.backend.setConfig(partial);
  }

  function applyConfigToUI(cfg) {
    if (!cfg) return;
    Object.keys(fieldMap).forEach((id) => {
      const el = byId(id);
      if (!el) return;
      const key = fieldMap[id];
      if (key in cfg) {
        el.value = cfg[key];
      }
    });
    renderPatternList("PastePatternEditor", cfg.paste_patterns || [], "paste");
    renderPatternList("OutlinePatternEditor", cfg.outline_patterns || [], "outline");
  }

  function renderPatternList(containerId, patterns, type) {
    const container = byId(containerId);
    if (!container) return;
    container.innerHTML = "";
    const list = document.createElement("div");
    list.className = "space-y-2";
    patterns.forEach((pattern, index) => {
      const row = document.createElement("div");
      row.className = "flex gap-2";
      const input = document.createElement("input");
      input.className =
        "flex-1 h-8 px-2 text-sm bg-white border border-gray-200 rounded focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono placeholder-gray-400";
      input.type = "text";
      input.value = pattern;
      input.addEventListener("change", () => {
        patterns[index] = input.value.trim();
        commitPatterns(type, patterns);
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className =
        "size-8 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors";
      remove.innerHTML = "<span class='material-symbols-outlined text-[18px]'>close</span>";
      remove.addEventListener("click", () => {
        patterns.splice(index, 1);
        commitPatterns(type, patterns);
        renderPatternList(containerId, patterns, type);
      });
      row.appendChild(input);
      row.appendChild(remove);
      list.appendChild(row);
    });
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className =
      "mt-2.5 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1.5 px-1 py-0.5 rounded hover:bg-blue-50 transition-colors w-fit";
    addBtn.innerHTML =
      "<span class='material-symbols-outlined text-[16px]'>add_circle</span> Add Rule";
    addBtn.addEventListener("click", () => {
      patterns.push("*");
      commitPatterns(type, patterns);
      renderPatternList(containerId, patterns, type);
    });
    container.appendChild(list);
    container.appendChild(addBtn);
  }

  function commitPatterns(type, patterns) {
    if (type === "paste") {
      updateConfig({ paste_patterns: patterns });
    } else {
      updateConfig({ outline_patterns: patterns });
    }
  }

  function scanFiles(dir) {
    if (!state.backend || !dir) return;
    state.backend.scanFiles(dir);
  }

  function runJob() {
    if (!state.backend) return;
    const inputDir = (byId("InputDirPicker") || {}).value || state.inputDir;
    const outputPath = (byId("OutputPathPicker") || {}).value || state.outputPath;
    const configPath = (byId("ConfigPathPicker") || {}).value || state.configPath;
    if (!inputDir || !outputPath) {
      appendLog("Input directory and output STL are required.");
      updateStatus("error");
      return;
    }
    state.backend.runJob(inputDir, outputPath, configPath || "");
  }

  function updateFileList(files) {
    const container = byId("FileListPreview");
    if (!container) return;
    container.innerHTML = "";
    const list = document.createElement("ul");
    list.className = "text-xs text-slate-500 space-y-1";
    files.forEach((file) => {
      const li = document.createElement("li");
      li.textContent = file;
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  function updateStatus(status) {
    const badge = byId("StatusBadge");
    if (!badge) return;
    badge.textContent = status.toUpperCase();
  }

  function updateProgress(value) {
    const bar = byId("ProgressBar");
    const text = byId("ProgressText");
    if (bar) {
      bar.style.width = `${value}%`;
    }
    if (text) {
      text.textContent = `${value}%`;
    }
  }

  function appendLog(message) {
    const log = byId("LogConsole");
    if (!log) return;
    log.textContent = message;
  }

  window.addEventListener("DOMContentLoaded", connectBackend);
})();
