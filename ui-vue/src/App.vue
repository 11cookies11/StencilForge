<template>
  <div class="min-h-screen flex flex-col bg-slate-50 text-slate-800 pb-32">
    <AppHeader
      :app-title="t('app.title')"
      :tagline="t('app.tagline')"
      :locale="locale"
      :locale-options="localeOptions"
      :current-locale-label="currentLocaleLabel"
      :language-label="t('language.label')"
      :minimize-title="t('window.minimize')"
      :maximize-restore-title="t('window.maximizeRestore')"
      :close-title="t('window.close')"
      @titlebar-mouse-down="onTitlebarMouseDown"
      @titlebar-double-click="onTitlebarDoubleClick"
      @select-locale="setLocale"
      @window-minimize="windowMinimize"
      @window-maximize-restore="windowMaximizeRestore"
      @window-close="windowClose"
    />

    <main class="flex-1 w-full max-w-6xl mx-auto px-6 md:px-8 py-10 pt-12 pb-32">
      <section v-show="currentTab === 'upload'" class="space-y-8">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">{{ t("upload.title") }}</h1>
          <p class="text-slate-500">{{ t("upload.subtitle") }}</p>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <section class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 md:p-8 space-y-6">
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">{{ t("upload.inputLabel") }}</label>
              <div class="flex rounded-md shadow-sm">
                <input
                  v-model="inputDir"
                  @change="scanFiles"
                  class="flex-1 block w-full rounded-none rounded-l-md border-slate-300 bg-white text-slate-900 focus:border-primary focus:ring-primary sm:text-sm py-2.5 px-4"
                  :placeholder="t('upload.inputPlaceholder')"
                  type="text"
                />
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickInputDir"
                >
                  {{ t("upload.inputFolder") }}
                </button>
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-md bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickInputZip"
                >
                  {{ t("upload.inputZip") }}
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">{{ t("upload.outputLabel") }}</label>
              <div class="flex rounded-md shadow-sm">
                <input
                  v-model="outputPath"
                  class="flex-1 block w-full rounded-none rounded-l-md border-slate-300 bg-white text-slate-900 focus:border-primary focus:ring-primary sm:text-sm py-2.5 px-4"
                  :placeholder="t('upload.outputPlaceholder')"
                  type="text"
                />
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-md bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickOutputPath"
                >
                  {{ t("upload.browse") }}
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">{{ t("upload.configLabel") }}</label>
              <div class="flex rounded-md shadow-sm">
                <input
                  v-model="configPath"
                  class="flex-1 block w-full rounded-none rounded-l-md border-slate-300 bg-white text-slate-600 focus:border-primary focus:ring-primary sm:text-sm py-2.5 px-4"
                  placeholder="config/stencilforge.json"
                  type="text"
                />
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-md bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickConfigPath"
                >
                  {{ t("upload.configPick") }}
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 gap-4">
              <button
                class="col-span-1 w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-bold text-white bg-primary hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors"
                @click="runJob"
              >
                {{ t("upload.generate") }}
              </button>
            </div>
          </section>
          <section class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 md:p-8 min-h-[420px]">
            <h3 class="text-sm font-semibold text-slate-700 mb-4">{{ t("upload.detectedTitle") }}</h3>
            <div
              class="w-full h-[calc(100%-2rem)] rounded-lg border-2 border-dashed border-slate-200 bg-slate-50/60 flex flex-col items-center justify-center p-8 text-center"
            >
              <div class="space-y-3">
                <div class="mx-auto w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center">
                  <AppIcon name="description" class="text-slate-400" :size="24" />
                </div>
                <p class="text-sm text-slate-500">
                  {{ files.length ? t("upload.detectedSome") : t("upload.detectedEmpty") }}
                </p>
                <ul v-if="files.length" class="text-xs text-slate-500 space-y-1 max-h-36 overflow-y-auto">
                  <li v-for="file in files" :key="file">{{ file }}</li>
                </ul>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section v-show="currentTab === 'config'" class="space-y-5">
        <div class="max-w-3xl mx-auto space-y-1 text-center">
          <h1 class="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">{{ t("config.title") }}</h1>
          <p class="text-sm md:text-base text-slate-500">{{ t("config.subtitle") }}</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 md:p-6 space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-4">
            <div class="flex flex-wrap items-center gap-2 rounded-2xl bg-slate-100 p-1">
              <button
                class="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all"
                :class="configPanelTab === 'basic' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                type="button"
                @click="configPanelTab = 'basic'"
              >
                <AppIcon name="tune" :size="18" />
                <span>{{ t("config.panelTabProcess") }}</span>
              </button>
              <button
                class="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all"
                :class="configPanelTab === 'rules' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                type="button"
                @click="configPanelTab = 'rules'"
              >
                <AppIcon name="rule" :size="18" />
                <span>{{ t("config.panelTabAperture") }}</span>
              </button>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <button
                class="px-3 h-8 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                @click="restoreBasicDefaults"
              >
                {{ t("config.restoreBasicDefaults") }}
              </button>
              <button
                class="px-3 h-8 rounded-lg border border-slate-200 text-xs font-semibold text-blue-600 hover:bg-blue-50"
                @click="showAdvancedConfig = !showAdvancedConfig"
              >
                {{ showAdvancedConfig ? t("config.hideAdvanced") : t("config.showAdvanced") }}
              </button>
            </div>
          </div>

          <div v-if="configPanelTab === 'basic'" class="space-y-4">
            <BasicConfigForm
              :config="config"
              :show-advanced-config="showAdvancedConfig"
              :locale="locale"
              @update:config="onConfigFormUpdate"
              @add-pattern="addPattern"
              @remove-pattern="removePattern"
            />
          </div>

          <div v-else class="pt-0">
            <ApertureRuleWorkspace
              embedded
              :backend="backend"
              :locale="locale"
              :stencil-thickness-mm="config.thickness_mm"
            />
          </div>
        </div>
      </section>

      <section v-show="currentTab === 'preview'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">{{ t("preview.title") }}</h1>
          <p class="text-slate-500">{{ t("preview.subtitle") }}</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 space-y-5">
          <div class="space-y-4">
            <div class="text-sm text-slate-500">{{ t("preview.popupNote") }}</div>
            <div class="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-2">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ t("preview.stlLabel") }}</div>
              <div class="text-sm text-slate-700 break-all">
                {{ outputPath || t("preview.notSet") }}
              </div>
            </div>
          </div>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="text-xs text-slate-500">{{ t("preview.subtitle") }}</p>
            <div class="flex flex-wrap items-center gap-3">
              <button
                class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-semibold shadow-sm hover:bg-slate-50"
                type="button"
                @click="openPreviewFolder"
              >
                {{ t("preview.openFolder") }}
              </button>
              <button
                class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-bold shadow-sm hover:bg-blue-700"
                type="button"
                @click="previewPrimaryAction"
              >
                {{ t("preview.pickStlAndOpen") }}
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>

    <teleport to="body">
      <div :class="['progress-overlay', { 'is-visible': progressVisible }]" role="dialog" aria-modal="true" aria-labelledby="progress-title">
        <div :class="['progress-backdrop', { 'is-visible': progressVisible }]"></div>
        <div class="progress-shell">
          <div :class="['progress-card', { 'is-visible': progressVisible }]">
            <div class="sm:flex sm:items-start">
              <div class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 sm:mx-0 sm:h-10 sm:w-10">
                <AppIcon name="autorenew" class="text-primary animate-spin" :size="20" />
              </div>
              <div class="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                <h3 id="progress-title" class="text-lg font-semibold leading-6 text-slate-900">{{ t("progress.title") }}</h3>
                <div class="mt-2">
                  <p class="text-sm text-slate-500">{{ t("progress.subtitle") }}</p>
                </div>
                <div class="mt-6">
                  <div class="flex mb-2 items-center justify-between">
                    <span class="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-blue-600 bg-blue-100">
                      {{ t("progress.running") }}
                    </span>
                    <span class="text-xs font-semibold inline-block text-slate-500">{{ t("progress.processing") }}</span>
                  </div>
                  <div class="loader-track">
                    <div class="loader-bar"></div>
                  </div>
                  <p class="text-xs text-slate-400 text-center">{{ t("progress.eta") }}</p>
                </div>
              </div>
            </div>
            <div class="mt-5 sm:mt-6 sm:flex sm:flex-row-reverse">
              <button
                class="inline-flex w-full justify-center rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 sm:mt-0 sm:w-auto transition-colors"
                type="button"
                @click="stopJob"
              >
                {{ t("progress.cancel") }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </teleport>

    <nav class="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 taskbar">
      <div class="flex items-center px-2 py-2 bg-white border border-slate-200/60 rounded-2xl shadow-taskbar ring-1 ring-white/20 taskbar-shell">
        <button :class="navClass('upload')" @click="setTab('upload')">
          <AppIcon name="cloud_upload" class="text-2xl mb-0.5" :size="24" />
          <span class="nav-label">{{ t("tabs.upload") }}</span>
        </button>
        <button :class="navClass('config')" @click="setTab('config')">
          <AppIcon name="settings" class="text-2xl mb-0.5" :size="24" />
          <span class="nav-label">{{ t("tabs.config") }}</span>
        </button>
        <button :class="navClass('preview')" @click="setTab('preview')">
          <AppIcon name="visibility" class="text-2xl mb-0.5" :size="24" />
          <span class="nav-label">{{ t("tabs.preview") }}</span>
        </button>
      </div>
    </nav>
  </div>
</template>

<script>
import AppIcon from "./components/AppIcon.vue";
import AppHeader from "./components/AppHeader.vue";
import ApertureRuleWorkspace from "./components/ApertureRuleWorkspace.vue";
import AppSelect from "./components/AppSelect.vue";
import BasicConfigForm from "./components/BasicConfigForm.vue";
import { getInitialLocale, getLocaleDisplayName, t as translate } from "./i18n";

const LOCALE_OPTIONS = [
  { value: "zh-CN" },
  { value: "en" },
  { value: "ja" },
  { value: "de" },
  { value: "es" },
];

const DEFAULT_CONFIG = {
  paste_patterns: ["*gtp*", "*gbp*", "*paste*top*", "*paste*bottom*", "*cream*"],
  outline_patterns: ["*gko*", "*gm1*", "*boardoutline*", "*outline*", "*edge*cuts*"],
  thickness_mm: 0.12,
  paste_offset_mm: -0.05,
  outline_margin_mm: 5.0,
  outline_merge_tol_mm: 0.01,
  locator_enabled: true,
  locator_height_mm: 2.0,
  locator_width_mm: 2.0,
  locator_clearance_mm: 0.2,
  locator_step_height_mm: 1.0,
  locator_step_width_mm: 1.5,
  locator_mode: "step",
  locator_open_side: "none",
  locator_open_width_mm: 0.0,
  output_mode: "solid_with_cutouts",
  model_backend: "trimesh",
  arc_steps: 64,
  curve_resolution: 16,
};

const BASIC_CONFIG_KEYS = [
  "thickness_mm",
  "output_mode",
  "model_backend",
  "paste_offset_mm",
  "locator_enabled",
  "locator_mode",
  "locator_height_mm",
  "locator_width_mm",
  "locator_clearance_mm",
];

export default {
  components: {
    AppIcon,
    AppHeader,
    ApertureRuleWorkspace,
    AppSelect,
    BasicConfigForm,
  },
  data() {
    const locale = getInitialLocale();
      return {
        locale,
        currentTab: "upload",
        configPanelTab: "basic",
        showAdvancedConfig: false,
        backend: null,
      config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)),
      inputDir: "",
      outputPath: "",
      configPath: "",
      files: [],
      status: "ready",
      progress: 0,
      progressValue: 0,
      progressVisible: false,
      progressStartAt: 0,
      progressHideTimer: null,
      progressPulseTimer: null,
      log: translate(locale, "log.idle"),
      logBuffer: [],
      logFlushTimer: null,
      lastProgress: 0,
      pendingProgress: null,
      pendingStatus: null,
      useNativeTitlebar: false,
    };
  },
  computed: {
    localeOptions() {
      return LOCALE_OPTIONS.map((item) => ({
        ...item,
        label: getLocaleDisplayName(item.value),
      }));
    },
    currentLocaleLabel() {
      return getLocaleDisplayName(this.locale);
    },
    statusLabel() {
      const map = {
        ready: this.t("status.ready"),
        running: this.t("status.running"),
        success: this.t("status.success"),
        error: this.t("status.error"),
      };
      return map[this.status] || this.status;
    },
  },
  mounted() {
    this.applyLocale(false);
    this.connectBackend();
  },
  methods: {
    t(key, vars = {}) {
      return translate(this.locale, key, vars);
    },
    applyLocale(persist = true) {
      if (persist) {
        try {
          localStorage.setItem("stencilforge-locale", this.locale);
        } catch (error) {
          void error;
        }
      }
      if (typeof document !== "undefined" && document.documentElement) {
        document.documentElement.lang = this.locale;
      }
    },
    setLocale(nextLocale = this.locale) {
      this.locale = nextLocale;
      this.applyLocale(true);
      if (this.backend && this.backend.setLocale) {
        this.backend.setLocale(this.locale);
      }
    },
    navClass(tab) {
      const active = this.currentTab === tab;
      return [
        "nav-item group relative flex flex-col items-center justify-center w-16 h-14 rounded-xl transition-all duration-200 mx-1",
        active ? "text-primary bg-slate-100" : "text-slate-500 hover:text-primary hover:bg-slate-100",
      ].join(" ");
    },
    connectBackend() {
      if (!window.qt || !window.QWebChannel) {
        this.log = this.t("log.qtUnavailable");
        return;
      }
      new QWebChannel(qt.webChannelTransport, (channel) => {
        this.backend = channel.objects.backend;
        this.wireBackendSignals();
        this.backend.getConfig((cfg) => {
          if (cfg) {
            this.config = cfg;
          }
        });
        if (!this.outputPath && this.backend.defaultOutputPath) {
          this.backend.defaultOutputPath("stencil.stl", (path) => {
            if (path && !this.outputPath) {
              this.outputPath = path;
            }
          });
        }
        this.backend.windowUsesNativeHitTest((value) => {
          this.useNativeTitlebar = !!value;
        });
        if (this.backend.setLocale) {
          this.backend.setLocale(this.locale);
        }
      });
    },
    wireBackendSignals() {
      if (!this.backend) return;
      this.backend.configChanged.connect((cfg) => {
        this.config = cfg;
      });
      this.backend.filesScanned.connect((payload) => {
        this.files = payload.files || [];
      });
      this.backend.jobStatus.connect((status) => {
        this.pendingStatus = status || "ready";
        if (this.pendingStatus === "running") {
          this.progressValue = 0;
          this.progressStartAt = Date.now();
          this.progressVisible = true;
        }
        if (this.currentTab === "preview") {
          this.status = this.pendingStatus;
        }
      });
      this.backend.jobProgress.connect((value) => {
        const nextValue = value || 0;
        const delta = Math.abs(nextValue - this.lastProgress);
        if (delta >= 2 || nextValue === 0 || nextValue === 100) {
          if (this.currentTab === "preview") {
            this.progress = nextValue;
            this.lastProgress = nextValue;
          } else {
            this.pendingProgress = nextValue;
          }
        }
      });
      this.backend.jobLog.connect((line) => {
        this.queueLog(line || "");
      });
      this.backend.jobDone.connect((result) => {
        this.status = "success";
        this.log = this.t("log.done", { value: result.output_stl || "" });
        this.progressValue = 100;
        this._scheduleProgressHide(300);
        if (result.output_stl) {
          this.outputPath = result.output_stl;
          this.setTab("preview");
          this.backend.loadPreviewStl(result.output_stl);
        }
      });
      this.backend.jobError.connect((message) => {
        this.status = "error";
        this.log = this.t("log.error", { value: message });
        this._scheduleProgressHide(300);
      });
    },
    queueLog(message) {
      if (!message) return;
      this.logBuffer.push(message);
      if (this.logBuffer.length > 300) {
        this.logBuffer.splice(0, this.logBuffer.length - 300);
      }
      if (this.currentTab !== "preview") return;
      if (this.logFlushTimer) return;
      this.logFlushTimer = setTimeout(() => {
        this.log = this.logBuffer.join("\n");
        clearTimeout(this.logFlushTimer);
        this.logFlushTimer = null;
      }, 250);
    },
    flushLog() {
      if (this.logFlushTimer) {
        clearTimeout(this.logFlushTimer);
        this.logFlushTimer = null;
      }
      if (this.logBuffer.length) {
        this.log = this.logBuffer.join("\n");
      }
    },
    setTab(tab) {
      this.currentTab = tab;
      if (tab === "preview") {
        if (this.pendingStatus) {
          this.status = this.pendingStatus;
        }
        if (this.pendingProgress !== null) {
          this.progress = this.pendingProgress;
          this.lastProgress = this.pendingProgress;
          this.pendingProgress = null;
        }
        this.flushLog();
      }
    },
    pickInputDir() {
      if (!this.backend) return;
      this.backend.pickDirectory((picked) => {
        if (picked) {
          this.inputDir = picked;
          this.scanFiles();
        }
      });
    },
    pickInputZip() {
      if (!this.backend) return;
      this.backend.pickZipFile((picked) => {
        if (picked) {
          this.inputDir = picked;
          this.scanFiles();
        }
      });
    },
    pickOutputPath() {
      if (!this.backend) return;
      this.backend.pickSaveFile("stencil.stl", (picked) => {
        if (picked) {
          this.outputPath = picked;
        }
      });
    },
    pickConfigPath() {
      if (!this.backend) return;
      this.backend.pickConfigFile((picked) => {
        if (picked) {
          this.configPath = picked;
          this.backend.loadConfig(picked);
        }
      });
    },
    scanFiles() {
      if (!this.backend || !this.inputDir) return;
      this.backend.scanFiles(this.inputDir);
    },
    updateConfig() {
      if (!this.backend) return;
      this.backend.setConfig({ ...this.config });
    },
    onConfigFormUpdate(newConfig) {
      this.config = newConfig;
      this.updateConfig();
    },
    addPattern(type) {
      const key = type === "paste" ? "paste_patterns" : "outline_patterns";
      this.config[key].push("*");
      this.updateConfig();
    },
    restoreBasicDefaults() {
      for (const key of BASIC_CONFIG_KEYS) {
        if (Object.prototype.hasOwnProperty.call(DEFAULT_CONFIG, key)) {
          this.config[key] = DEFAULT_CONFIG[key];
        }
      }
      this.updateConfig();
    },
    removePattern(type, index) {
      const key = type === "paste" ? "paste_patterns" : "outline_patterns";
      this.config[key].splice(index, 1);
      this.updateConfig();
    },
    runJob() {
      if (!this.backend) return;
      if (!this.inputDir || !this.outputPath) {
        this.status = "error";
        this.log = this.t("log.needInput");
        return;
      }
      this.backend.runJob(this.inputDir, this.outputPath, this.configPath || "");
    },
    stopJob() {
      if (!this.backend) return;
      this.backend.stopJob();
    },
    openPreviewFolder() {
      if (!this.backend) return;
      this.backend.openTargetFolder();
    },
    previewPrimaryAction() {
      if (!this.backend) return;
      this.pickStlForPreview();
    },
    previewOutput() {
      if (!this.backend) return;
      if (!this.outputPath) {
        this.status = "error";
        this.log = this.t("log.noOutput");
        return;
      }
      this.backend.loadPreviewStl(this.outputPath);
    },
    pickStlForPreview() {
      if (!this.backend) return;
      this.backend.pickStlFile((picked) => {
        if (!picked) return;
        this.outputPath = picked;
        this.backend.loadPreviewStl(picked);
      });
    },
    windowMinimize() {
      if (!this.backend) return;
      this.backend.windowMinimize();
    },
    windowMaximizeRestore() {
      if (!this.backend) return;
      this.backend.windowMaximizeRestore();
    },
    windowClose() {
      if (!this.backend) return;
      this.backend.windowClose();
    },
    _scheduleProgressHide(minVisible = 300) {
      const elapsed = Date.now() - this.progressStartAt;
      const remaining = Math.max(0, minVisible - elapsed);
      if (this.progressHideTimer) {
        clearTimeout(this.progressHideTimer);
      }
      this.progressHideTimer = setTimeout(() => {
        this.progressVisible = false;
        this.progressHideTimer = null;
      }, remaining);
    },
    onTitlebarMouseDown(event) {
      if (event.button !== 0) return;
      if (event.target.closest(".window-controls")) return;
      if (event.target.closest(".titlebar-interactive")) return;
      if (this.useNativeTitlebar) return;
      if (!this.backend) return;
      this.backend.windowStartDrag();
    },
    onTitlebarDoubleClick(event) {
      if (event.target.closest(".window-controls")) return;
      if (event.target.closest(".titlebar-interactive")) return;
      if (this.useNativeTitlebar) return;
      this.windowMaximizeRestore();
    },
  },
};
</script>

<style scoped>
.nav-item .nav-label {
  font-size: 10px;
  line-height: 1;
  opacity: 0.65;
}
.nav-item:hover .nav-label,
.nav-item.text-primary .nav-label {
  opacity: 1;
}
.progress-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  pointer-events: none;
}
.progress-overlay.is-visible {
  pointer-events: auto;
}
.progress-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  opacity: 0;
}
.progress-backdrop.is-visible {
  opacity: 1;
}
.progress-shell {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.progress-card {
  width: min(90vw, 520px);
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.25);
  opacity: 0;
}
.progress-card.is-visible {
  opacity: 1;
}
.loader-track {
  position: relative;
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}
.loader-bar {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  width: 35%;
  background: #2563eb;
  transform: translateX(-100%);
  animation: loader-slide 1.1s infinite linear;
}
@keyframes loader-slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(320%);
  }
}
@media (max-height: 740px) {
  .taskbar {
    bottom: 8px;
  }
  .taskbar-shell {
    padding: 6px 6px;
  }
  .nav-item {
    width: 56px;
    height: 48px;
  }
}
</style>
