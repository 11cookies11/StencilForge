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
            <AppIcon name="view_in_ar" class="text-white" :size="20" />
          </div>
          <span class="text-xl font-bold tracking-tight text-slate-900">StencilForge</span>
        </div>
        <div class="flex items-center gap-4">
          <div class="text-xs text-slate-400 hidden sm:block">{{ t("app.tagline") }}</div>
          <div
            class="relative titlebar-interactive"
            ref="languageMenu"
            @mousedown.stop
            @click.stop
            @dblclick.stop
          >
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium text-slate-900 bg-slate-100 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              type="button"
              :aria-label="t('language.label')"
              :aria-expanded="languageMenuOpen ? 'true' : 'false'"
              @mousedown.stop
              @dblclick.stop
              @click="toggleLanguageMenu"
            >
              <AppIcon name="language" class="text-slate-500" :size="20" />
              <span>{{ currentLocaleLabel }}</span>
              <AppIcon
                name="expand_more"
                class="text-slate-400 transition-transform"
                :class="languageMenuOpen ? 'rotate-180' : ''"
                :size="18"
              />
            </button>
            <div
              v-if="languageMenuOpen"
              class="absolute right-0 mt-2 w-48 origin-top-right rounded-xl bg-white shadow-xl ring-1 ring-black/5 focus:outline-none border border-slate-200 z-50"
              role="menu"
              :aria-label="t('language.label')"
            >
              <div class="p-1.5 space-y-0.5">
                <button
                  class="w-full text-left flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors"
                  :class="
                    locale === 'zh-CN'
                      ? 'text-primary bg-blue-50'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  "
                  type="button"
                  role="menuitem"
                  @click="setLocaleFromMenu('zh-CN')"
                >
                  <span>{{ t("language.zh") }}</span>
                  <AppIcon v-if="locale === 'zh-CN'" name="check" :size="18" />
                </button>
                <button
                  class="w-full text-left flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors"
                  :class="
                    locale === 'en'
                      ? 'text-primary bg-blue-50'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  "
                  type="button"
                  role="menuitem"
                  @click="setLocaleFromMenu('en')"
                >
                  <span>{{ t("language.en") }}</span>
                  <AppIcon v-if="locale === 'en'" name="check" :size="18" />
                </button>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2 window-controls">
            <button class="window-btn" @click="windowMinimize" @dblclick.stop :title="t('window.minimize')">
              <AppIcon name="remove" :size="18" />
            </button>
            <button class="window-btn" @click="windowMaximizeRestore" @dblclick.stop :title="t('window.maximizeRestore')">
              <AppIcon name="crop_square" :size="18" />
            </button>
            <button class="window-btn window-btn-close" @click="windowClose" @dblclick.stop :title="t('window.close')">
              <AppIcon name="close" :size="18" />
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="flex-1 w-full max-w-7xl mx-auto px-6 md:px-8 py-10 pt-12 pb-32">
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

      <section v-show="currentTab === 'config'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">{{ t("config.title") }}</h1>
          <p class="text-slate-500">{{ t("config.subtitle") }}</p>
        </div>
        <div class="grid md:grid-cols-2 gap-6">
          <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-5 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <label class="text-xs font-semibold text-slate-600">{{ t("config.thickness") }}
                <input
                  v-model.number="config.thickness_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.01"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">{{ t("config.outputMode") }}
                <select
                  v-model="config.output_mode"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                >
                  <option value="solid_with_cutouts">{{ t("config.outputModeSolid") }}</option>
                  <option value="holes_only">{{ t("config.outputModeHoles") }}</option>
                </select>
              </label>
              <label class="text-xs font-semibold text-slate-600">{{ t("config.pasteOffset") }}
                <input
                  v-model.number="config.paste_offset_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.01"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">{{ t("config.outlineMargin") }}
                <input
                  v-model.number="config.outline_margin_mm"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="0.1"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">{{ t("config.arcSteps") }}
                <input
                  v-model.number="config.arc_steps"
                  @change="updateConfig"
                  class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  type="number"
                  step="1"
                />
              </label>
              <label class="text-xs font-semibold text-slate-600">{{ t("config.curveResolution") }}
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
                {{ t("config.locatorEnabled") }}
              </label>
              <div class="grid grid-cols-2 gap-4">
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorMode") }}
                  <select
                    v-model="config.locator_mode"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    <option value="step">{{ t("config.locatorModeStep") }}</option>
                    <option value="wall">{{ t("config.locatorModeWall") }}</option>
                  </select>
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorHeight") }}
                  <input
                    v-model.number="config.locator_height_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorWidth") }}
                  <input
                    v-model.number="config.locator_width_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorClearance") }}
                  <input
                    v-model.number="config.locator_clearance_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.05"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorStepHeight") }}
                  <input
                    v-model.number="config.locator_step_height_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorStepWidth") }}
                  <input
                    v-model.number="config.locator_step_width_mm"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                    type="number"
                    step="0.1"
                    min="0"
                  />
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorOpenSide") }}
                  <select
                    v-model="config.locator_open_side"
                    @change="updateConfig"
                    class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    <option value="none">{{ t("config.locatorOpenSideNone") }}</option>
                    <option value="top">{{ t("config.locatorOpenSideTop") }}</option>
                    <option value="right">{{ t("config.locatorOpenSideRight") }}</option>
                    <option value="bottom">{{ t("config.locatorOpenSideBottom") }}</option>
                    <option value="left">{{ t("config.locatorOpenSideLeft") }}</option>
                  </select>
                </label>
                <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorOpenWidth") }}
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
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">{{ t("config.pasteRules") }}</div>
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
                    <AppIcon name="close" :size="18" />
                  </button>
                </div>
              </div>
              <button
                class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                @click="addPattern('paste')"
              >
                <AppIcon name="add_circle" :size="16" />
                {{ t("config.addRule") }}
              </button>
            </div>
            <div>
              <div class="text-xs font-semibold text-slate-500 uppercase mb-2">{{ t("config.outlineRules") }}</div>
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
                    <AppIcon name="close" :size="18" />
                  </button>
                </div>
              </div>
              <button
                class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                @click="addPattern('outline')"
              >
                <AppIcon name="add_circle" :size="16" />
                {{ t("config.addRule") }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-show="currentTab === 'preview'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">{{ t("preview.title") }}</h1>
          <p class="text-slate-500">{{ t("preview.subtitle") }}</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 space-y-4">
          <div class="text-sm text-slate-500">{{ t("preview.popupNote") }}</div>
          <div class="text-xs text-slate-500">
            {{ t("preview.currentStl", { value: outputPath || t("preview.notSet") }) }}
          </div>
          <div class="flex flex-wrap gap-3">
            <button class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold" @click="runJob">
              {{ t("preview.generate") }}
            </button>
            <button
              class="px-4 py-2 rounded-lg bg-white border border-slate-200 text-sm font-bold text-slate-600"
              @click="openPreview"
            >
              {{ t("preview.open") }}
            </button>
          </div>
          <div class="flex items-center justify-between">
            <div class="text-xs font-semibold text-slate-500 uppercase">{{ t("preview.status") }}</div>
            <div class="text-sm font-bold text-primary">{{ statusLabel }}</div>
          </div>
          <div class="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
            {{ log.split("\n").slice(-1)[0] || log }}
          </div>
        </div>
      </section>

      <section v-show="currentTab === 'export'" class="space-y-6">
        <div class="text-center space-y-2">
          <h1 class="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">{{ t("export.title") }}</h1>
          <p class="text-slate-500">{{ t("export.subtitle") }}</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-soft p-6 flex items-center justify-between">
          <div class="text-sm text-slate-500">{{ t("export.output", { value: outputPath || t("export.notSet") }) }}</div>
          <button class="px-5 py-2 rounded-lg bg-primary text-white font-bold">{{ t("export.download") }}</button>
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
        <button :class="navClass('export')" @click="setTab('export')">
          <AppIcon name="download" class="text-2xl mb-0.5" :size="24" />
          <span class="nav-label">{{ t("tabs.export") }}</span>
        </button>
      </div>
    </nav>
  </div>
</template>

<script>
import AppIcon from "./components/AppIcon.vue";
const DEFAULT_LOCALE = "en";
const MESSAGES = {
  "zh-CN": {
    "app.tagline": "PCB 钢网与治具生成",
    "language.label": "语言",
    "language.zh": "简体中文",
    "language.en": "English",
    "window.minimize": "最小化",
    "window.maximizeRestore": "最大化/还原",
    "window.close": "关闭",
    "tabs.upload": "上传",
    "tabs.config": "配置",
    "tabs.preview": "预览",
    "tabs.export": "导出",
    "upload.title": "上传 PCB 文件",
    "upload.subtitle": "选择 Gerber 目录与输出 STL 路径。",
    "upload.inputLabel": "输入目录 / ZIP",
    "upload.inputPlaceholder": "Gerber 目录或 ZIP...",
    "upload.inputFolder": "文件夹",
    "upload.inputZip": "ZIP",
    "upload.outputLabel": "输出 STL",
    "upload.outputPlaceholder": "输出文件...",
    "upload.browse": "浏览",
    "upload.configLabel": "配置（可选）",
    "upload.configPick": "选择",
    "upload.generate": "生成 STL",
    "upload.detectedTitle": "检测到的文件",
    "upload.detectedEmpty": "暂无文件，请选择目录或导入 ZIP。",
    "upload.detectedSome": "已检测到文件。",
    "config.title": "配置",
    "config.subtitle": "调整钢网生成参数。",
    "config.thickness": "厚度 (mm)",
    "config.outputMode": "输出模式",
    "config.outputModeSolid": "Solid With Cutouts",
    "config.outputModeHoles": "Holes Only",
    "config.pasteOffset": "焊膏偏移 (mm)",
    "config.outlineMargin": "外形边距 (mm)",
    "config.arcSteps": "圆弧步数",
    "config.curveResolution": "曲线分辨率",
    "config.locatorEnabled": "启用 PCB 定位",
    "config.locatorMode": "定位结构",
    "config.locatorModeStep": "台阶",
    "config.locatorModeWall": "外框墙",
    "config.locatorHeight": "外框高度 (mm)",
    "config.locatorWidth": "外框宽度 (mm)",
    "config.locatorClearance": "定位间隙 (mm)",
    "config.locatorStepHeight": "台阶高度 (mm)",
    "config.locatorStepWidth": "台阶宽度 (mm)",
    "config.locatorOpenSide": "开口方向",
    "config.locatorOpenSideNone": "无",
    "config.locatorOpenSideTop": "上",
    "config.locatorOpenSideRight": "右",
    "config.locatorOpenSideBottom": "下",
    "config.locatorOpenSideLeft": "左",
    "config.locatorOpenWidth": "开口宽度 (mm)",
    "config.pasteRules": "焊膏层规则",
    "config.outlineRules": "外形层规则",
    "config.addRule": "添加规则",
    "preview.title": "预览",
    "preview.subtitle": "查看生成进度与日志。",
    "preview.popupNote": "3D 预览在独立的 VTK 弹窗中打开。",
    "preview.currentStl": "当前 STL: {value}",
    "preview.notSet": "未设置",
    "preview.generate": "生成",
    "preview.open": "打开预览",
    "preview.status": "状态",
    "export.title": "导出",
    "export.subtitle": "下载生成的 STL 文件。",
    "export.output": "输出: {value}",
    "export.notSet": "未设置",
    "export.download": "下载 STL",
    "progress.title": "正在生成 STL 文件...",
    "progress.subtitle": "正在处理 PCB 层级数据并构建 3D 模型，请不要关闭窗口。",
    "progress.running": "进行中",
    "progress.processing": "处理中",
    "progress.eta": "预计剩余时间：计算中",
    "progress.cancel": "取消",
    "status.ready": "就绪",
    "status.running": "生成中",
    "status.success": "完成",
    "status.error": "错误",
    "log.idle": "空闲。",
    "log.qtUnavailable": "Qt WebChannel 不可用。",
    "log.needInput": "需要输入目录和输出 STL。",
    "log.done": "完成: {value}",
    "log.error": "错误: {value}",
    "log.noOutput": "未设置输出 STL。",
  },
  en: {
    "app.tagline": "PCB stencil and fixture generator",
    "language.label": "Language",
    "language.zh": "中文",
    "language.en": "English",
    "window.minimize": "Minimize",
    "window.maximizeRestore": "Maximize/Restore",
    "window.close": "Close",
    "tabs.upload": "Upload",
    "tabs.config": "Config",
    "tabs.preview": "Preview",
    "tabs.export": "Export",
    "upload.title": "Upload PCB files",
    "upload.subtitle": "Choose a Gerber folder and output STL path.",
    "upload.inputLabel": "Input folder / ZIP",
    "upload.inputPlaceholder": "Gerber folder or ZIP...",
    "upload.inputFolder": "Folder",
    "upload.inputZip": "ZIP",
    "upload.outputLabel": "Output STL",
    "upload.outputPlaceholder": "Output file...",
    "upload.browse": "Browse",
    "upload.configLabel": "Config (optional)",
    "upload.configPick": "Choose",
    "upload.generate": "Generate STL",
    "upload.detectedTitle": "Detected files",
    "upload.detectedEmpty": "No files yet. Select a folder or import a ZIP.",
    "upload.detectedSome": "Files detected.",
    "config.title": "Config",
    "config.subtitle": "Adjust stencil generation parameters.",
    "config.thickness": "Thickness (mm)",
    "config.outputMode": "Output mode",
    "config.outputModeSolid": "Solid With Cutouts",
    "config.outputModeHoles": "Holes Only",
    "config.pasteOffset": "Paste offset (mm)",
    "config.outlineMargin": "Outline margin (mm)",
    "config.arcSteps": "Arc steps",
    "config.curveResolution": "Curve resolution",
    "config.locatorEnabled": "Enable PCB locating",
    "config.locatorMode": "Locator type",
    "config.locatorModeStep": "Step",
    "config.locatorModeWall": "Outer wall",
    "config.locatorHeight": "Wall height (mm)",
    "config.locatorWidth": "Wall width (mm)",
    "config.locatorClearance": "Locator clearance (mm)",
    "config.locatorStepHeight": "Step height (mm)",
    "config.locatorStepWidth": "Step width (mm)",
    "config.locatorOpenSide": "Open side",
    "config.locatorOpenSideNone": "None",
    "config.locatorOpenSideTop": "Top",
    "config.locatorOpenSideRight": "Right",
    "config.locatorOpenSideBottom": "Bottom",
    "config.locatorOpenSideLeft": "Left",
    "config.locatorOpenWidth": "Open width (mm)",
    "config.pasteRules": "Paste layer rules",
    "config.outlineRules": "Outline layer rules",
    "config.addRule": "Add rule",
    "preview.title": "Preview",
    "preview.subtitle": "View generation progress and logs.",
    "preview.popupNote": "3D preview opens in a separate VTK window.",
    "preview.currentStl": "Current STL: {value}",
    "preview.notSet": "Not set",
    "preview.generate": "Generate",
    "preview.open": "Open preview",
    "preview.status": "Status",
    "export.title": "Export",
    "export.subtitle": "Download the generated STL file.",
    "export.output": "Output: {value}",
    "export.notSet": "Not set",
    "export.download": "Download STL",
    "progress.title": "Generating STL file...",
    "progress.subtitle": "Processing PCB layers and building the 3D model. Please keep the window open.",
    "progress.running": "Running",
    "progress.processing": "Processing",
    "progress.eta": "ETA: calculating",
    "progress.cancel": "Cancel",
    "status.ready": "Ready",
    "status.running": "Running",
    "status.success": "Done",
    "status.error": "Error",
    "log.idle": "Idle.",
    "log.qtUnavailable": "Qt WebChannel is unavailable.",
    "log.needInput": "Input folder and output STL are required.",
    "log.done": "Done: {value}",
    "log.error": "Error: {value}",
    "log.noOutput": "Output STL is not set.",
  },
};

function getInitialLocale() {
  try {
    const saved = localStorage.getItem("stencilforge-locale");
    if (saved === "en" || saved === "zh-CN") return saved;
  } catch (error) {
    void error;
  }
  if (typeof navigator !== "undefined") {
    const lang = navigator.language || "";
    if (lang.toLowerCase().startsWith("en")) return "en";
  }
  return DEFAULT_LOCALE;
}

export default {
  components: {
    AppIcon,
  },
  data() {
    const locale = getInitialLocale();
    return {
      locale,
      languageMenuOpen: false,
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
      log: (MESSAGES[locale] && MESSAGES[locale]["log.idle"]) || MESSAGES[DEFAULT_LOCALE]["log.idle"],
      logBuffer: [],
      logFlushTimer: null,
      lastProgress: 0,
      pendingProgress: null,
      pendingStatus: null,
      useNativeTitlebar: false,
    };
  },
  computed: {
    currentLocaleLabel() {
      return this.locale === "en" ? this.t("language.en") : this.t("language.zh");
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
    progressPercent() {
      const value = Math.max(0, Math.min(100, this.progressValue || 0));
      return Math.round(value);
    },
  },
  mounted() {
    this.applyLocale(false);
    document.addEventListener("click", this.onDocumentClick);
    document.addEventListener("keydown", this.onDocumentKeydown);
    this.connectBackend();
  },
  beforeUnmount() {
    document.removeEventListener("click", this.onDocumentClick);
    document.removeEventListener("keydown", this.onDocumentKeydown);
  },
  methods: {
    t(key, vars = {}) {
      const table = MESSAGES[this.locale] || MESSAGES[DEFAULT_LOCALE] || {};
      const fallback = MESSAGES[DEFAULT_LOCALE] || {};
      let message = table[key] || fallback[key] || key;
      Object.keys(vars).forEach((name) => {
        message = message.replaceAll(`{${name}}`, vars[name]);
      });
      return message;
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
        document.documentElement.lang = this.locale === "en" ? "en" : "zh-CN";
      }
    },
    setLocale() {
      this.applyLocale(true);
      if (this.backend && this.backend.setLocale) {
        this.backend.setLocale(this.locale);
      }
    },
    setLocaleFromMenu(nextLocale) {
      this.locale = nextLocale;
      this.setLocale();
      this.languageMenuOpen = false;
    },
    toggleLanguageMenu() {
      this.languageMenuOpen = !this.languageMenuOpen;
    },
    onDocumentClick(event) {
      if (!this.languageMenuOpen) return;
      const root = this.$refs.languageMenu;
      if (!root || root.contains(event.target)) return;
      this.languageMenuOpen = false;
    },
    onDocumentKeydown(event) {
      if (event.key === "Escape" && this.languageMenuOpen) {
        this.languageMenuOpen = false;
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
        this.log = this.t("log.needInput");
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
    _startProgressPulse() {},
    _stopProgressPulse() {},
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
