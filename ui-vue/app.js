(() => {
  const { createApp } = Vue;

  createApp({
    data() {
      return {
        currentTab: "upload",
        backend: null,
        config: {
          paste_patterns: ["*gtp*", "*paste*top*"],
          outline_patterns: ["*gko*", "*outline*", "*edge*cuts*"],
          thickness_mm: 0.12,
          paste_offset_mm: -0.05,
          outline_margin_mm: 5.0,
          output_mode: "solid_with_cutouts",
          arc_steps: 64,
          curve_resolution: 16,
        },
        inputDir: "",
        outputPath: "",
        configPath: "",
        files: [],
        status: "ready",
        progress: 0,
        log: "Idle.",
      };
    },
    computed: {
      statusLabel() {
        return this.status.toUpperCase();
      },
    },
    mounted() {
      this.connectBackend();
    },
    methods: {
      connectBackend() {
        if (!window.qt || !window.QWebChannel) {
          this.log = "Qt WebChannel not available.";
          return;
        }
        new QWebChannel(qt.webChannelTransport, (channel) => {
          this.backend = channel.objects.backend;
          this.wireBackendSignals();
          const cfg = this.backend.getConfig();
          if (cfg) {
            this.config = cfg;
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
          this.status = status || "ready";
        });
        this.backend.jobProgress.connect((value) => {
          this.progress = value || 0;
        });
        this.backend.jobLog.connect((line) => {
          this.log = line || "";
        });
        this.backend.jobDone.connect((result) => {
          this.status = "success";
          this.log = `Done: ${result.output_stl || ""}`;
        });
        this.backend.jobError.connect((message) => {
          this.status = "error";
          this.log = `Error: ${message}`;
        });
      },
      setTab(tab) {
        this.currentTab = tab;
      },
      pickInputDir() {
        if (!this.backend) return;
        const picked = this.backend.pickDirectory();
        if (picked) {
          this.inputDir = picked;
          this.scanFiles();
        }
      },
      pickOutputPath() {
        if (!this.backend) return;
        const picked = this.backend.pickSaveFile("stencil.stl");
        if (picked) {
          this.outputPath = picked;
        }
      },
      pickConfigPath() {
        if (!this.backend) return;
        const picked = this.backend.pickConfigFile();
        if (picked) {
          this.configPath = picked;
          this.backend.loadConfig(picked);
        }
      },
      scanFiles() {
        if (!this.backend || !this.inputDir) return;
        this.backend.scanFiles(this.inputDir);
      },
      updateConfig() {
        if (!this.backend) return;
        this.backend.setConfig({ ...this.config });
      },
      addPattern(type) {
        const key = type === "paste" ? "paste_patterns" : "outline_patterns";
        this.config[key].push("*");
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
          this.log = "Input directory and output STL are required.";
          return;
        }
        this.backend.runJob(this.inputDir, this.outputPath, this.configPath || "");
      },
      stopJob() {
        if (!this.backend) return;
        this.backend.stopJob();
      },
    },
    template: `
      <div class="min-h-screen flex flex-col">
        <nav class="border-b border-slate-200 bg-white/90 backdrop-blur-md sticky top-0 z-50">
          <div class="max-w-7xl mx-auto px-6 md:px-8 py-3 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="bg-primary text-white size-9 rounded-lg flex items-center justify-center shadow-lg shadow-blue-600/20">
                <span class="material-symbols-outlined !text-[20px]">view_in_ar</span>
              </div>
              <h2 class="text-lg font-bold tracking-tight text-slate-900">StencilForge</h2>
            </div>
            <div class="flex items-center gap-3 text-xs font-semibold text-slate-500">
              <button class="hover:text-primary transition-colors" @click="setTab('upload')">Upload</button>
              <button class="hover:text-primary transition-colors" @click="setTab('config')">Config</button>
              <button class="hover:text-primary transition-colors" @click="setTab('preview')">Preview</button>
              <button class="hover:text-primary transition-colors" @click="setTab('export')">Export</button>
            </div>
          </div>
        </nav>

        <main class="flex-1 max-w-6xl mx-auto w-full px-4 md:px-8 py-10 space-y-8">
          <section v-show="currentTab === 'upload'" class="space-y-6">
            <div class="text-center space-y-2">
              <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">Upload PCB Files</h1>
              <p class="text-slate-500">Select your Gerber folder and output STL path.</p>
            </div>
            <div class="grid md:grid-cols-2 gap-6">
              <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-4">
                <label class="text-xs font-semibold text-slate-500 uppercase">Input Directory</label>
                <div class="flex items-center gap-2">
                  <input v-model="inputDir" @change="scanFiles" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="Gerber folder..." type="text" />
                  <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickInputDir">Browse</button>
                </div>
                <label class="text-xs font-semibold text-slate-500 uppercase">Output STL</label>
                <div class="flex items-center gap-2">
                  <input v-model="outputPath" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="Output file..." type="text" />
                  <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickOutputPath">Browse</button>
                </div>
                <label class="text-xs font-semibold text-slate-500 uppercase">Config (optional)</label>
                <div class="flex items-center gap-2">
                  <input v-model="configPath" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="config/stencilforge.json" type="text" />
                  <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickConfigPath">Select</button>
                </div>
                <button class="w-full h-11 rounded-xl bg-primary hover:bg-primary-dark text-white font-bold shadow-lg shadow-blue-500/20 transition-all" @click="runJob">Generate STL</button>
              </div>
              <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5">
                <div class="text-xs font-semibold text-slate-500 uppercase mb-3">Detected Files</div>
                <ul class="text-xs text-slate-500 space-y-1 max-h-64 overflow-y-auto">
                  <li v-for="file in files" :key="file">{{ file }}</li>
                </ul>
              </div>
            </div>
          </section>

          <section v-show="currentTab === 'config'" class="space-y-6">
            <div class="text-center space-y-2">
              <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">Configuration</h1>
              <p class="text-slate-500">Tune stencil generation parameters.</p>
            </div>
            <div class="grid md:grid-cols-2 gap-6">
              <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-4">
                <div class="grid grid-cols-2 gap-4">
                  <label class="text-xs font-semibold text-slate-600">Thickness (mm)
                    <input v-model.number="config.thickness_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.01" />
                  </label>
                  <label class="text-xs font-semibold text-slate-600">Output Mode
                    <select v-model="config.output_mode" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg">
                      <option value="solid_with_cutouts">Solid With Cutouts</option>
                      <option value="holes_only">Holes Only</option>
                    </select>
                  </label>
                  <label class="text-xs font-semibold text-slate-600">Paste Offset (mm)
                    <input v-model.number="config.paste_offset_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.01" />
                  </label>
                  <label class="text-xs font-semibold text-slate-600">Outline Margin (mm)
                    <input v-model.number="config.outline_margin_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.1" />
                  </label>
                  <label class="text-xs font-semibold text-slate-600">Arc Steps
                    <input v-model.number="config.arc_steps" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="1" />
                  </label>
                  <label class="text-xs font-semibold text-slate-600">Curve Resolution
                    <input v-model.number="config.curve_resolution" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="1" />
                  </label>
                </div>
              </div>
              <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-5">
                <div>
                  <div class="text-xs font-semibold text-slate-500 uppercase mb-2">Paste Patterns</div>
                  <div class="space-y-2">
                    <div class="flex gap-2" v-for="(pattern, index) in config.paste_patterns" :key="'paste-' + index">
                      <input v-model="config.paste_patterns[index]" @change="updateConfig" class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono" type="text" />
                      <button class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded" @click="removePattern('paste', index)">
                        <span class="material-symbols-outlined text-[18px]">close</span>
                      </button>
                    </div>
                  </div>
                  <button class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1" @click="addPattern('paste')">
                    <span class="material-symbols-outlined text-[16px]">add_circle</span>
                    Add Rule
                  </button>
                </div>
                <div>
                  <div class="text-xs font-semibold text-slate-500 uppercase mb-2">Outline Patterns</div>
                  <div class="space-y-2">
                    <div class="flex gap-2" v-for="(pattern, index) in config.outline_patterns" :key="'outline-' + index">
                      <input v-model="config.outline_patterns[index]" @change="updateConfig" class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono" type="text" />
                      <button class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded" @click="removePattern('outline', index)">
                        <span class="material-symbols-outlined text-[18px]">close</span>
                      </button>
                    </div>
                  </div>
                  <button class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1" @click="addPattern('outline')">
                    <span class="material-symbols-outlined text-[16px]">add_circle</span>
                    Add Rule
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section v-show="currentTab === 'preview'" class="space-y-6">
            <div class="text-center space-y-2">
              <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">Preview</h1>
              <p class="text-slate-500">Monitor generation progress and logs.</p>
            </div>
            <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 space-y-4">
              <div class="flex items-center justify-between">
                <div class="text-xs font-semibold text-slate-500 uppercase">Status</div>
                <div class="text-sm font-bold text-primary">{{ statusLabel }}</div>
              </div>
              <div class="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full bg-primary" :style="{ width: progress + '%' }"></div>
              </div>
              <div class="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">{{ log }}</div>
              <div class="flex gap-3">
                <button class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold" @click="runJob">Generate</button>
                <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="stopJob">Stop</button>
              </div>
            </div>
          </section>

          <section v-show="currentTab === 'export'" class="space-y-6">
            <div class="text-center space-y-2">
              <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">Export</h1>
              <p class="text-slate-500">Download the generated STL.</p>
            </div>
            <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 flex items-center justify-between">
              <div class="text-sm text-slate-500">Output: {{ outputPath || 'Not set' }}</div>
              <button class="px-5 py-2 rounded-lg bg-primary text-white font-bold">Download STL</button>
            </div>
          </section>
        </main>
      </div>
    `,
  }).mount("#app");
})();
