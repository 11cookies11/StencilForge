<template>
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
          <button class="hover:text-primary transition-colors" @click="setTab('upload')">上传</button>
          <button class="hover:text-primary transition-colors" @click="setTab('config')">配置</button>
          <button class="hover:text-primary transition-colors" @click="setTab('preview')">预览</button>
          <button class="hover:text-primary transition-colors" @click="setTab('export')">导出</button>
        </div>
      </div>
    </nav>

    <main class="flex-1 max-w-6xl mx-auto w-full px-4 md:px-8 py-10 space-y-8">
      <section v-show="currentTab === 'upload'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">上传 PCB 文件</h1>
          <p class="text-slate-500">选择 Gerber 目录与输出 STL 路径。</p>
        </div>
        <div class="grid md:grid-cols-2 gap-6">
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-4">
            <label class="text-xs font-semibold text-slate-500 uppercase">输入目录</label>
            <div class="flex items-center gap-2">
              <input v-model="inputDir" @change="scanFiles" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="Gerber 目录..." type="text" />
              <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickInputDir">浏览</button>
            </div>
            <label class="text-xs font-semibold text-slate-500 uppercase">输出 STL</label>
            <div class="flex items-center gap-2">
              <input v-model="outputPath" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="输出文件..." type="text" />
              <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickOutputPath">浏览</button>
            </div>
            <label class="text-xs font-semibold text-slate-500 uppercase">配置（可选）</label>
            <div class="flex items-center gap-2">
              <input v-model="configPath" class="flex-1 h-10 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg" placeholder="config/stencilforge.json" type="text" />
              <button class="px-4 h-10 bg-white border border-slate-200 rounded-lg text-xs font-bold hover:text-primary" @click="pickConfigPath">选择</button>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <button class="h-11 rounded-xl bg-primary hover:bg-primary-dark text-white font-bold shadow-lg shadow-blue-500/20 transition-all" @click="runJob">生成 STL</button>
              <button class="h-11 rounded-xl bg-white border border-slate-200 text-slate-600 font-bold hover:text-primary hover:border-primary transition-colors" @click="importZip">导入 ZIP</button>
            </div>
          </div>
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5">
            <div class="text-xs font-semibold text-slate-500 uppercase mb-3">检测到的文件</div>
            <ul class="text-xs text-slate-500 space-y-1 max-h-64 overflow-y-auto">
              <li v-for="file in files" :key="file">{{ file }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section v-show="currentTab === 'config'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">配置</h1>
          <p class="text-slate-500">调整钢网生成参数。</p>
        </div>
        <div class="grid md:grid-cols-2 gap-6">
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <label class="text-xs font-semibold text-slate-600">厚度 (mm)
                <input v-model.number="config.thickness_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.01" />
              </label>
              <label class="text-xs font-semibold text-slate-600">输出模式
                <select v-model="config.output_mode" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg">
                  <option value="solid_with_cutouts">Solid With Cutouts</option>
                  <option value="holes_only">Holes Only</option>
                </select>
              </label>
              <label class="text-xs font-semibold text-slate-600">焊膏偏移 (mm)
                <input v-model.number="config.paste_offset_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.01" />
              </label>
              <label class="text-xs font-semibold text-slate-600">外形边距 (mm)
                <input v-model.number="config.outline_margin_mm" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="0.1" />
              </label>
              <label class="text-xs font-semibold text-slate-600">圆弧步数
                <input v-model.number="config.arc_steps" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="1" />
              </label>
              <label class="text-xs font-semibold text-slate-600">曲线分辨率
                <input v-model.number="config.curve_resolution" @change="updateConfig" class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg" type="number" step="1" />
              </label>
            </div>
          </div>
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-5">
            <div>
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">焊膏层规则</div>
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
                添加规则
              </button>
            </div>
            <div>
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">外形层规则</div>
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
                添加规则
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-show="currentTab === 'preview'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">预览</h1>
          <p class="text-slate-500">查看生成进度与日志。</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 space-y-4">
          <div class="text-sm text-slate-500">3D 预览在独立的 VTK 弹窗中打开。</div>
          <div class="text-xs text-slate-500">当前 STL: {{ outputPath || "未设置" }}</div>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold" @click="runJob">生成</button>
            <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="stopJob">停止</button>
            <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="openPreview">打开预览</button>
            <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="previewOutput">预览输出</button>
            <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="pickStlForPreview">打开 STL</button>
          </div>
          <div class="flex items-center justify-between">
            <div class="text-xs font-semibold text-slate-500 uppercase">状态</div>
            <div class="text-sm font-bold text-primary">{{ statusLabel }}</div>
          </div>
          <div class="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div class="h-full bg-primary" :style="{ width: progress + '%' }"></div>
          </div>
          <div class="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">{{ log }}</div>
        </div>
      </section>

      <section v-show="currentTab === 'export'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">导出</h1>
          <p class="text-slate-500">下载生成的 STL 文件。</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 flex items-center justify-between">
          <div class="text-sm text-slate-500">输出: {{ outputPath || "未设置" }}</div>
          <button class="px-5 py-2 rounded-lg bg-primary text-white font-bold">下载 STL</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
export default {
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
      log: "空闲。",
      logBuffer: [],
      logFlushTimer: null,
      lastProgress: 0,
      pendingProgress: null,
      pendingStatus: null,
    };
  },
  computed: {
    statusLabel() {
      const map = {
        ready: "就绪",
        running: "生成中",
        success: "完成",
        error: "错误",
      };
      return map[this.status] || this.status;
    },
  },
  mounted() {
    this.connectBackend();
  },
  methods: {
    connectBackend() {
      if (!window.qt || !window.QWebChannel) {
        this.log = "Qt WebChannel 不可用。";
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
        this.log = `完成: ${result.output_stl || ""}`;
        if (result.output_stl) {
          this.outputPath = result.output_stl;
          this.backend.loadPreviewStl(result.output_stl);
        }
      });
      this.backend.jobError.connect((message) => {
        this.status = "error";
        this.log = `错误: ${message}`;
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
    importZip() {
      if (!this.backend) return;
      this.backend.pickZipFile((zipPath) => {
        if (!zipPath) return;
        this.backend.importZip(zipPath, (extracted) => {
          if (extracted) {
            this.inputDir = extracted;
            this.scanFiles();
          }
        });
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
        this.log = "需要输入目录和输出 STL。";
        return;
      }
      this.backend.runJob(this.inputDir, this.outputPath, this.configPath || "");
    },
    stopJob() {
      if (!this.backend) return;
      this.backend.stopJob();
    },
    openPreview() {
      if (!this.backend) return;
      this.backend.openPreview();
    },
    previewOutput() {
      if (!this.backend) return;
      if (!this.outputPath) {
        this.status = "error";
        this.log = "未设置输出 STL。";
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
  },
};
</script>
