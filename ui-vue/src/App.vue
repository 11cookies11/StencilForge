<template>
  <div class="min-h-screen flex flex-col bg-slate-50 text-slate-800 pb-32">
    <header
      class="sticky top-0 z-40 bg-white border-b border-slate-200 h-16 app-titlebar"
      @mousedown="onTitlebarMouseDown"
      @dblclick="onTitlebarDoubleClick"
    >
      <div class="w-full h-full flex items-center justify-between px-4 sm:px-6">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 bg-primary rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/30">
            <span class="material-symbols-outlined text-white text-[20px]">view_in_ar</span>
          </div>
          <span class="text-xl font-bold tracking-tight text-slate-900">StencilForge</span>
        </div>
        <div class="flex items-center gap-4">
          <div class="text-xs text-slate-400 hidden sm:block">PCB 钢网与治具生成</div>
          <div class="flex items-center gap-2 window-controls">
            <button class="window-btn" @click="windowMinimize" @dblclick.stop title="最小化">
              <span class="material-symbols-outlined text-[18px]">remove</span>
            </button>
            <button class="window-btn" @click="windowMaximizeRestore" @dblclick.stop title="最大化/还原">
              <span class="material-symbols-outlined text-[18px]">crop_square</span>
            </button>
            <button class="window-btn window-btn-close" @click="windowClose" @dblclick.stop title="关闭">
              <span class="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="flex-1 w-full max-w-7xl mx-auto px-6 md:px-8 py-10 pt-12 pb-32">
      <section v-show="currentTab === 'upload'" class="space-y-8">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">上传 PCB 文件</h1>
          <p class="text-slate-500">选择 Gerber 目录与输出 STL 路径。</p>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <section class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 md:p-8 space-y-6">
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">输入目录</label>
              <div class="flex rounded-md shadow-sm">
                <input
                  v-model="inputDir"
                  @change="scanFiles"
                  class="flex-1 block w-full rounded-none rounded-l-md border-slate-300 bg-white text-slate-900 focus:border-primary focus:ring-primary sm:text-sm py-2.5 px-4"
                  placeholder="Gerber 目录..."
                  type="text"
                />
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-md bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickInputDir"
                >
                  浏览
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">输出 STL</label>
              <div class="flex rounded-md shadow-sm">
                <input
                  v-model="outputPath"
                  class="flex-1 block w-full rounded-none rounded-l-md border-slate-300 bg-white text-slate-900 focus:border-primary focus:ring-primary sm:text-sm py-2.5 px-4"
                  placeholder="输出文件..."
                  type="text"
                />
                <button
                  class="inline-flex items-center px-4 py-2 border border-l-0 border-slate-300 rounded-r-md bg-slate-50 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
                  type="button"
                  @click="pickOutputPath"
                >
                  浏览
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">配置（可选）</label>
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
                  选择
                </button>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <button
                class="col-span-1 w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-bold text-white bg-primary hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors"
                @click="runJob"
              >
                生成 STL
              </button>
              <button
                class="col-span-1 w-full flex justify-center py-3 px-4 border border-slate-300 rounded-lg shadow-sm text-sm font-bold text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors"
                @click="importZip"
              >
                导入 ZIP
              </button>
            </div>
          </section>
          <section class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 md:p-8 min-h-[420px]">
            <h3 class="text-sm font-semibold text-slate-700 mb-4">检测到的文件</h3>
            <div
              class="w-full h-[calc(100%-2rem)] rounded-lg border-2 border-dashed border-slate-200 bg-slate-50/60 flex flex-col items-center justify-center p-8 text-center"
            >
              <div class="space-y-3">
                <div class="mx-auto w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center">
                  <span class="material-symbols-outlined text-slate-400 text-[24px]">description</span>
                </div>
                <p class="text-sm text-slate-500">
                  {{ files.length ? "已检测到文件。" : "暂无文件，请选择目录或导入 ZIP。" }}
                </p>
                <ul v-if="files.length" class="text-xs text-slate-500 space-y-1 max-h-36 overflow-y-auto">
                  <li v-for="file in files" :key="file">{{ file }}</li>
                </ul>
              </div>
            </div>
          </section>
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
                <input
                  v-model.number="config.thickness_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.01"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">输出模式
                <select
                  v-model="config.output_mode"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                >
                  <option value="solid_with_cutouts">Solid With Cutouts</option>
                  <option value="holes_only">Holes Only</option>
                </select>
              </label>
              <label class="text-xs font-semibold text-slate-600">焊膏偏移 (mm)
                <input
                  v-model.number="config.paste_offset_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.01"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">外形边距 (mm)
                <input
                  v-model.number="config.outline_margin_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.1"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">圆弧步数
                <input
                  v-model.number="config.arc_steps"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="1"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">曲线分辨率
                <input
                  v-model.number="config.curve_resolution"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="1"
                />
              </label>
            </div>
            <div class="pt-2 border-t border-slate-100 space-y-3">
              <label class="flex items-center gap-2 text-xs font-semibold text-slate-700">
                <input
                  v-model="config.locator_enabled"
                  @change="updateConfig"
                  class="h-4 w-4 text-primary border-slate-300 rounded"
                  type="checkbox"
                />
                启用 PCB 定位
              </label>
              <div class="grid grid-cols-2 gap-4">
                <label class="text-xs font-semibold text-slate-600">定位结构
                  <select
                    v-model="config.locator_mode"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    <option value="step">台阶</option>
                    <option value="wall">外框墙</option>
                  </select>
                </label>
                <label class="text-xs font-semibold text-slate-600">外框高度 (mm)
                  <input
                    v-model.number="config.locator_height_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">外框宽度 (mm)
                  <input
                    v-model.number="config.locator_width_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">定位间隙 (mm)
                  <input
                    v-model.number="config.locator_clearance_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.05"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">台阶高度 (mm)
                  <input
                    v-model.number="config.locator_step_height_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">台阶宽度 (mm)
                  <input
                    v-model.number="config.locator_step_width_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">开口方向
                  <select
                    v-model="config.locator_open_side"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    <option value="none">无</option>
                    <option value="top">上</option>
                    <option value="right">右</option>
                    <option value="bottom">下</option>
                    <option value="left">左</option>
                  </select>
                </label>
                <label class="text-xs font-semibold text-slate-600">开口宽度 (mm)
                  <input
                    v-model.number="config.locator_open_width_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-5">
            <div>
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">焊膏层规则</div>
              <div class="space-y-2">
                <div class="flex gap-2" v-for="(pattern, index) in config.paste_patterns" :key="'paste-' + index">
                  <input
                    v-model="config.paste_patterns[index]"
                    @change="updateConfig"
                    class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono"
                    type="text"
                  />
                  <button
                    class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"
                    @click="removePattern('paste', index)"
                  >
                    <span class="material-symbols-outlined text-[18px]">close</span>
                  </button>
                </div>
              </div>
              <button
                class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                @click="addPattern('paste')"
              >
                <span class="material-symbols-outlined text-[16px]">add_circle</span>
                添加规则
              </button>
            </div>
            <div>
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">外形层规则</div>
              <div class="space-y-2">
                <div class="flex gap-2" v-for="(pattern, index) in config.outline_patterns" :key="'outline-' + index">
                  <input
                    v-model="config.outline_patterns[index]"
                    @change="updateConfig"
                    class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono"
                    type="text"
                  />
                  <button
                    class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"
                    @click="removePattern('outline', index)"
                  >
                    <span class="material-symbols-outlined text-[18px]">close</span>
                  </button>
                </div>
              </div>
              <button
                class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                @click="addPattern('outline')"
              >
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
            <button class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600" @click="openPreview">打开预览</button>
          </div>
          <div class="flex items-center justify-between">
            <div class="text-xs font-semibold text-slate-500 uppercase">状态</div>
            <div class="text-sm font-bold text-primary">{{ statusLabel }}</div>
          </div>
          <div class="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
            {{ log.split("\n").slice(-1)[0] || log }}
          </div>
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

    <teleport to="body">
      <div :class="['progress-overlay', { 'is-visible': progressVisible }]" role="dialog" aria-modal="true" aria-labelledby="progress-title">
        <div :class="['progress-backdrop', { 'is-visible': progressVisible }]"></div>
        <div class="progress-shell">
          <div :class="['progress-card', { 'is-visible': progressVisible }]">
            <div class="sm:flex sm:items-start">
              <div class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 sm:mx-0 sm:h-10 sm:w-10">
                <span class="material-symbols-outlined text-primary animate-spin">autorenew</span>
              </div>
              <div class="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                <h3 id="progress-title" class="text-lg font-semibold leading-6 text-slate-900">正在生成 STL 文件...</h3>
                <div class="mt-2">
                  <p class="text-sm text-slate-500">正在处理 PCB 层级数据并构建 3D 模型，请不要关闭窗口。</p>
                </div>
                <div class="mt-6">
                  <div class="flex mb-2 items-center justify-between">
                    <span class="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-blue-600 bg-blue-100">
                      进行中
                    </span>
                    <span class="text-xs font-semibold inline-block text-slate-500">处理中</span>
                  </div>
                  <div class="loader-track">
                    <div class="loader-bar"></div>
                  </div>
                  <p class="text-xs text-slate-400 text-center">预计剩余时间：计算中</p>
                </div>
              </div>
            </div>
            <div class="mt-5 sm:mt-6 sm:flex sm:flex-row-reverse">
              <button
                class="inline-flex w-full justify-center rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 sm:mt-0 sm:w-auto transition-colors"
                type="button"
                @click="stopJob"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      </div>
    </teleport>

    <nav class="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 taskbar">
      <div class="flex items-center px-2 py-2 bg-white border border-slate-200/60 rounded-2xl shadow-taskbar ring-1 ring-white/20 taskbar-shell">
        <button :class="navClass('upload')" @click="setTab('upload')">
          <span class="material-symbols-outlined text-2xl mb-0.5">cloud_upload</span>
          <span class="nav-label">上传</span>
        </button>
        <button :class="navClass('config')" @click="setTab('config')">
          <span class="material-symbols-outlined text-2xl mb-0.5">settings</span>
          <span class="nav-label">配置</span>
        </button>
        <button :class="navClass('preview')" @click="setTab('preview')">
          <span class="material-symbols-outlined text-2xl mb-0.5">visibility</span>
          <span class="nav-label">预览</span>
        </button>
        <button :class="navClass('export')" @click="setTab('export')">
          <span class="material-symbols-outlined text-2xl mb-0.5">download</span>
          <span class="nav-label">导出</span>
        </button>
      </div>
    </nav>
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
        arc_steps: 64,
        curve_resolution: 16,
      },
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
      log: "空闲。",
      logBuffer: [],
      logFlushTimer: null,
      lastProgress: 0,
      pendingProgress: null,
      pendingStatus: null,
      useNativeTitlebar: false,
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
    progressPercent() {
      const value = Math.max(0, Math.min(100, this.progressValue || 0));
      return Math.round(value);
    },
  },
  mounted() {
    this.connectBackend();
  },
  methods: {
    navClass(tab) {
      const active = this.currentTab === tab;
      return [
        "nav-item group relative flex flex-col items-center justify-center w-16 h-14 rounded-xl transition-all duration-200 mx-1",
        active ? "text-primary bg-slate-100" : "text-slate-500 hover:text-primary hover:bg-slate-100",
      ].join(" ");
    },
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
        this.backend.windowUsesNativeHitTest((value) => {
          this.useNativeTitlebar = !!value;
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
        this.log = `完成: ${result.output_stl || ""}`;
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
        this.log = `错误: ${message}`;
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
    _startProgressPulse() {},
    _stopProgressPulse() {},
    onTitlebarMouseDown(event) {
      if (event.button !== 0) return;
      if (event.target.closest(".window-controls")) return;
      if (this.useNativeTitlebar) return;
      if (!this.backend) return;
      this.backend.windowStartDrag();
    },
    onTitlebarDoubleClick(event) {
      if (event.target.closest(".window-controls")) return;
      if (this.useNativeTitlebar) return;
      this.windowMaximizeRestore();
    },
  },
};
</script>

<style scoped>
.app-titlebar {
  user-select: none;
}
.window-btn {
  width: 34px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  transition: background 0.2s ease, color 0.2s ease;
}
.window-btn:hover {
  background: #f1f5f9;
  color: #1f2937;
}
.window-btn-close:hover {
  background: #fee2e2;
  color: #b91c1c;
}
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
