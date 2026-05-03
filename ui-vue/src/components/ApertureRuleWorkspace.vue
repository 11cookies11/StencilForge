<template>
  <section :class="embedded ? 'space-y-2' : 'space-y-6'">
    <div :class="embedded ? 'space-y-2' : 'rounded-3xl border border-slate-200 bg-white p-6 md:p-8 shadow-soft'">
      <div v-if="!embedded" class="flex flex-wrap items-start justify-between gap-4">
        <div class="space-y-2">
          <p class="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600">
            {{ t("config.apertureEyebrow") }}
          </p>
          <div class="space-y-1">
            <h2 class="text-2xl md:text-3xl font-bold tracking-tight text-slate-900">
              {{ t("config.apertureStudioTitle") }}
            </h2>
            <p class="max-w-3xl text-sm md:text-base leading-6 text-slate-500">
              {{ t("config.apertureStudioSubtitle") }}
            </p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span class="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700">
            <AppIcon name="auto_awesome" :size="14" />
            {{ t("config.apertureRecommendedBadge") }}
          </span>
          <span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600">
            <AppIcon name="layers" :size="14" />
            {{ profileName }}
          </span>
        </div>
      </div>

      <div v-if="embedded" class="mt-2 flex flex-wrap items-center gap-4 border-b border-slate-200 pb-2">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          class="inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-2 text-sm font-medium transition-all"
          :class="studioTab === tab.value ? 'border-blue-600 text-blue-600' : 'text-slate-500 hover:text-slate-900'"
          type="button"
          @click="studioTab = tab.value"
        >
          <AppIcon :name="tab.icon" :size="16" />
          <span>{{ tab.label }}</span>
        </button>
      </div>
      <div v-else class="mt-6 inline-flex max-w-full flex-wrap items-center gap-2 rounded-2xl bg-slate-100 p-1">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          class="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all"
          :class="studioTab === tab.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
          type="button"
          @click="studioTab = tab.value"
        >
          <AppIcon :name="tab.icon" :size="18" />
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <div :class="embedded ? 'mt-2' : 'mt-6'">
        <div v-if="studioTab === 'basic'" class="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 md:p-6 space-y-5">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 class="text-lg font-bold text-slate-900">{{ t("config.apertureBasicTitle") }}</h3>
                <p class="text-sm text-slate-500">{{ t("config.apertureBasicHint") }}</p>
              </div>
              <span class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-500">
                {{ t("config.apertureThicknessFromAbove", { value: thicknessLabel }) }}
              </span>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureProfileName") }}</span>
                <input
                  v-model="profileName"
                  class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  type="text"
                />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureTransferRatio") }}</span>
                <input
                  v-model.number="transferRatio"
                  class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  min="0.5"
                  max="1.5"
                  step="0.01"
                  type="number"
                />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureStrategy") }}</span>
                <AppSelect v-model="strategy" :options="strategyOptions" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureAllowAsymmetric") }}</span>
                <button
                  class="flex h-10 w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  type="button"
                  @click="allowAsymmetric = !allowAsymmetric"
                >
                  <span>{{ allowAsymmetric ? t("config.apertureYes") : t("config.apertureNo") }}</span>
                  <span
                    class="inline-flex h-5 w-9 items-center rounded-full p-0.5 transition"
                    :class="allowAsymmetric ? 'bg-blue-600 justify-end' : 'bg-slate-300 justify-start'"
                  >
                    <span class="block h-4 w-4 rounded-full bg-white shadow-sm"></span>
                  </span>
                </button>
              </label>
            </div>

            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-2">
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureMinOpen") }}</span>
                <input
                  v-model.number="minApertureMm"
                  class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  min="0"
                  step="0.01"
                  type="number"
                />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureMaxOpen") }}</span>
                <input
                  v-model.number="maxApertureMm"
                  class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  min="0"
                  step="0.01"
                  type="number"
                />
              </label>
              <div
                class="relative rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 pr-10"
              >
                <div class="text-xs font-semibold uppercase tracking-wide text-blue-600">
                  {{ t("config.apertureSummaryThickness") }}
                </div>
                <div class="mt-2 flex items-center justify-between gap-3">
                  <div class="whitespace-nowrap text-base font-semibold text-slate-900">{{ thicknessValue.toFixed(2) }} <span class="text-xs font-medium text-slate-500">mm</span></div>
                </div>
                <div class="absolute right-2 top-2 z-30">
                  <HelpTooltip :text="t('config.apertureSummaryThicknessHint')" variant="blue" />
                </div>
              </div>
              <div
                class="relative rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 pr-10"
              >
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {{ t("config.apertureSummaryRatio") }}
                </div>
                <div class="mt-2 flex items-center justify-between gap-3">
                  <div class="whitespace-nowrap text-base font-semibold text-slate-900">{{ percentLabel(transferRatio) }}</div>
                </div>
                <div class="absolute right-2 top-2 z-30">
                  <HelpTooltip :text="t('config.apertureSummaryRatioHint')" variant="slate" />
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div class="flex items-center justify-between gap-2">
                <div>
                  <h3 class="text-lg font-bold text-slate-900">{{ t("config.apertureProcessTitle") }}</h3>
                  <p class="text-sm text-slate-500">{{ t("config.apertureProcessHint") }}</p>
                </div>
                <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                  {{ t(`config.apertureStrategy${strategyKey}`) }}
                </span>
              </div>

              <div class="mt-4 space-y-3">
                <div class="relative rounded-2xl bg-slate-50 p-4 pr-10">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-sm font-semibold text-slate-600">{{ t("config.apertureRecommendedVolume") }}</span>
                    <span class="text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatVolume(recommendedVolumeMm3) }}</span>
                  </div>
                  <div class="absolute right-3 top-3">
                    <HelpTooltip :text="t('config.apertureRecommendedVolumeHint')" variant="slate" />
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="rounded-2xl border border-slate-200 bg-white p-3.5">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePadArea") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatArea(padAreaMm2) }}</div>
                  </div>
                  <div class="rounded-2xl border border-slate-200 bg-white p-3.5">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureTargetArea") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatArea(targetOpenAreaMm2) }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600">
                  {{ t("config.apertureFormulaLabel") }}
                </div>
                <HelpTooltip :text="t('config.aperturePreviewSummaryHint')" variant="slate" />
              </div>
              <div class="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                {{ t("config.apertureFormulaLine1") }}
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="studioTab === 'rules'" class="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 md:p-6">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 class="text-lg font-bold text-slate-900">{{ t("config.apertureRulesTitle") }}</h3>
                <p class="text-sm text-slate-500">{{ t("config.apertureRulesHint") }}</p>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                  type="button"
                  @click="importRulesFromBackend"
                >
                  <AppIcon name="upload" :size="16" />
                  {{ t("config.apertureImportRules") }}
                </button>
                <button
                  class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                  type="button"
                  @click="exportRulesToBackend"
                >
                  <AppIcon name="download" :size="16" />
                  {{ t("config.apertureExportRules") }}
                </button>
                <button
                  class="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
                  type="button"
                  @click="addRule"
                >
                  <AppIcon name="add_circle" :size="16" />
                  {{ t("config.apertureAddRule") }}
                </button>
              </div>
            </div>

            <div class="mt-5">
              <div class="mb-3 flex items-center justify-between gap-3">
                <div class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {{ t("config.apertureRuleGroupsTitle") }}
                </div>
                <button
                  class="text-xs font-semibold text-blue-600 transition hover:text-blue-700"
                  type="button"
                  @click="selectAllRuleGroups"
                >
                  {{ t("config.apertureAllGroups") }}
                </button>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="group in ruleGroups"
                  :key="group.key"
                  class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold transition"
                  :class="activeRuleGroupKey === group.key ? 'border-blue-200 bg-blue-50 text-blue-700 shadow-sm' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'"
                  type="button"
                  @click="selectRuleGroup(group.key)"
                >
                  <span>{{ group.label }}</span>
                  <span class="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-bold text-slate-500">
                    {{ group.ruleCount }}
                  </span>
                </button>
              </div>
              <div v-if="showingAllRuleGroups" class="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
                {{ t("config.apertureAllGroups") }}
              </div>
            </div>

            <div class="mt-5 space-y-3">
              <button
                v-for="rule in filteredRules"
                :key="rule.id"
                class="w-full rounded-2xl border px-4 py-4 text-left transition"
                :class="selectedRuleId === rule.id ? 'border-blue-200 bg-white shadow-sm ring-4 ring-blue-50' : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'"
                type="button"
                @click="selectRule(rule)"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div class="flex items-center gap-3">
                    <span
                      class="flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-bold"
                      :class="rule.enabled ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-400'"
                    >
                      {{ rule.priority }}
                    </span>
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="font-semibold text-slate-900">{{ rule.name }}</span>
                        <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide" :class="rule.enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'">
                          {{ rule.enabled ? t("config.apertureEnabled") : t("config.apertureDisabled") }}
                        </span>
                      </div>
                      <div class="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span class="rounded-full bg-slate-100 px-2 py-1">{{ describeMatch(rule) }}</span>
                        <span class="rounded-full bg-blue-50 px-2 py-1 text-blue-700">{{ describeAction(rule) }}</span>
                      </div>
                    </div>
                  </div>
                  <AppIcon name="chevron_right" :size="18" class="text-slate-400" />
                </div>
              </button>
              <div v-if="!filteredRules.length" class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                {{ t("config.apertureNoRulesInGroup") }}
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 class="text-lg font-bold text-slate-900">{{ activeRule.name }}</h3>
                  <p class="text-sm text-slate-500">{{ t("config.apertureRuleEditorHint") }}</p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700" type="button" @click="duplicateRule">
                    <AppIcon name="content_copy" :size="16" />
                    {{ t("config.apertureDuplicateRule") }}
                  </button>
                  <button class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-600" type="button" @click="removeSelectedRule">
                    <AppIcon name="delete" :size="16" />
                    {{ t("config.apertureDeleteRule") }}
                  </button>
                </div>
              </div>

              <div class="mt-4 grid gap-4 md:grid-cols-2">
                <label class="space-y-2 md:col-span-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleName") }}</span>
                  <input
                    v-model="activeRule.name"
                    class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                    type="text"
                  />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRulePriority") }}</span>
                  <input
                    v-model.number="activeRule.priority"
                    class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                    min="0"
                    step="1"
                    type="number"
                  />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleEnabled") }}</span>
                  <button
                    class="flex h-10 w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                    type="button"
                    @click="activeRule.enabled = !activeRule.enabled"
                  >
                    <span>{{ activeRule.enabled ? t("config.apertureYes") : t("config.apertureNo") }}</span>
                    <span class="inline-flex h-5 w-9 items-center rounded-full p-0.5 transition" :class="activeRule.enabled ? 'bg-blue-600 justify-end' : 'bg-slate-300 justify-start'">
                      <span class="block h-4 w-4 rounded-full bg-white shadow-sm"></span>
                    </span>
                  </button>
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRulePackage") }}</span>
                  <AppSelect v-model="activeRule.match.package" :options="packageOptions" />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRulePadType") }}</span>
                  <AppSelect v-model="activeRule.match.padType" :options="padTypeOptions" />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRulePadSize") }}</span>
                  <input
                    v-model="activeRule.match.padSize"
                    class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                    type="text"
                  />
                </label>
                <label class="space-y-2 md:col-span-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleAction") }}</span>
                  <AppSelect v-model="activeRule.action.mode" :options="actionOptions" />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleDelta") }}</span>
                  <input
                    v-model.number="activeRule.action.deltaMm"
                    class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                    step="0.01"
                    type="number"
                  />
                </label>
                <label class="space-y-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleScale") }}</span>
                  <input
                    v-model.number="activeRule.action.scale"
                    class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                    min="0.5"
                    max="1.5"
                    step="0.01"
                    type="number"
                  />
                </label>
                <label class="space-y-2 md:col-span-2">
                  <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleNote") }}</span>
                  <textarea
                    v-model="activeRule.note"
                    class="min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  />
                </label>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleMatchSummary") }}</div>
                <div class="mt-2 text-sm font-semibold text-slate-900">{{ describeMatch(activeRule) }}</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleActionSummary") }}</div>
                <div class="mt-2 text-sm font-semibold text-slate-900">{{ describeAction(activeRule) }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="studioTab === 'calculator'" class="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
          <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 md:p-6">
            <div class="space-y-1">
              <h3 class="text-lg font-bold text-slate-900">{{ t("config.apertureCalculatorTitle") }}</h3>
              <p class="text-sm text-slate-500">{{ t("config.apertureCalculatorHint") }}</p>
            </div>

            <div class="mt-5 grid gap-4 md:grid-cols-2">
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePadArea") }}</span>
                <input v-model.number="padAreaMm2" class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" step="0.01" type="number" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePadWidth") }}</span>
                <input v-model.number="padWidthMm" class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" step="0.01" type="number" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePadHeight") }}</span>
                <input v-model.number="padHeightMm" class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" step="0.01" type="number" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePackageType") }}</span>
                <AppSelect v-model="packageType" :options="packageTypeOptions" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePadType") }}</span>
                <AppSelect v-model="padType" :options="padTypeOptions" />
              </label>
              <label class="space-y-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureTargetVolume") }}</span>
                <input v-model.number="targetVolumeMm3" class="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" step="0.001" type="number" />
              </label>
            </div>

            <div class="mt-5 rounded-2xl border border-blue-100 bg-blue-50/70 p-4">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-wide text-blue-600">{{ t("config.apertureGeneratedRule") }}</div>
                  <p class="mt-1 text-sm text-slate-600">{{ t("config.apertureGeneratedRuleHint") }}</p>
                </div>
                <button
                  class="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
                  type="button"
                  @click="syncTargetToRecommended"
                >
                  {{ t("config.apertureUseRecommended") }}
                </button>
              </div>

              <div class="mt-4 grid gap-3 md:grid-cols-3">
                <div class="rounded-2xl bg-white p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureTheoreticalVolume") }}</div>
                  <div class="mt-2 text-2xl font-bold text-slate-900 whitespace-nowrap">{{ formatVolume(theoreticalVolumeMm3) }}</div>
                </div>
                <div class="rounded-2xl bg-white p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRecommendedVolume") }}</div>
                  <div class="mt-2 text-2xl font-bold text-slate-900 whitespace-nowrap">{{ formatVolume(recommendedVolumeMm3) }}</div>
                </div>
                <div class="rounded-2xl bg-white p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureEffectiveVolume") }}</div>
                  <div class="mt-2 text-2xl font-bold text-slate-900 whitespace-nowrap">{{ formatVolume(effectiveTargetVolumeMm3) }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div class="flex items-center justify-between gap-2">
                <h3 class="text-lg font-bold text-slate-900">{{ t("config.apertureCalculatorOutput") }}</h3>
                <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="calculatorStatus === 'warning' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'">
                  {{ calculatorStatusLabel }}
                </span>
              </div>

              <div class="mt-4 space-y-4">
                <div class="grid gap-3 md:grid-cols-2">
                  <div class="rounded-2xl bg-slate-50 p-4">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureTargetArea") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatArea(targetOpenAreaMm2) }}</div>
                  </div>
                  <div class="rounded-2xl bg-slate-50 p-4">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureScaleRatio") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatScale(recommendedScale) }}</div>
                  </div>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-white p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureDelta") }}</div>
                  <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatDelta(recommendedDeltaMm) }}</div>
                </div>
                <div class="rounded-2xl bg-slate-900 p-4 text-white">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-blue-200">{{ t("config.apertureRulePreviewLine") }}</div>
                  <div class="mt-2 font-mono text-xs leading-5 text-slate-200">
                    {{ generatedRulePreview }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
          <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-5 md:p-6">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 class="text-lg font-bold text-slate-900">{{ t("config.aperturePreviewTitle") }}</h3>
                <p class="text-sm text-slate-500">{{ t("config.aperturePreviewHint") }}</p>
              </div>
              <span class="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                {{ t("config.aperturePreviewActive") }}
              </span>
            </div>

            <div class="mt-5 grid gap-4 sm:grid-cols-3">
              <div class="rounded-2xl border border-slate-200 bg-white p-4">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePreviewRawPad") }}</div>
                <div class="mt-4 flex h-36 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
                  <div class="rounded-xl bg-slate-400/20 ring-1 ring-slate-300 transition-all duration-300" :style="previewVisualStyle(1, 'raw')"></div>
                </div>
                <div class="mt-3 text-xs text-slate-500">{{ t("config.aperturePreviewRawPadHint") }}</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePreviewRecommendedLabel") }}</div>
                <div class="mt-4 flex h-36 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
                  <div class="rounded-xl bg-blue-500/15 ring-1 ring-blue-200 transition-all duration-300" :style="previewVisualStyle(recommendedScale, 'recommended')"></div>
                </div>
                <div class="mt-3 text-xs text-slate-500">{{ t("config.aperturePreviewRecommendedHint") }}</div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-4">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.aperturePreviewRuleEffect") }}</div>
                <div class="mt-4 flex h-36 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50">
                  <div class="rounded-xl bg-purple-600/15 ring-1 ring-purple-300 transition-all duration-300" :style="previewVisualStyle(matchedRuleEffectScale, 'rule')"></div>
                </div>
                <div class="mt-3 text-xs text-slate-500">{{ t("config.aperturePreviewRuleEffectHint") }}</div>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 class="text-lg font-bold text-slate-900">{{ t("config.aperturePreviewSummary") }}</h3>
                  <p class="text-sm text-slate-500">{{ t("config.aperturePreviewSummaryHint") }}</p>
                </div>
                <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  {{ describeAction(matchedRule) }}
                </span>
              </div>

              <div class="mt-4 grid gap-3">
                <div class="rounded-2xl bg-slate-50 p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleGroupSummary") }}</div>
                  <div class="mt-2 text-base font-semibold text-slate-900">{{ matchedRuleGroupSummary }}</div>
                </div>
                <div class="rounded-2xl bg-slate-50 p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleMatchSummary") }}</div>
                  <div class="mt-2 text-base font-semibold text-slate-900">{{ describeMatch(matchedRule) }}</div>
                </div>
                <div class="rounded-2xl bg-slate-50 p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureEstimatedVolume") }}</div>
                  <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatVolume(effectiveTargetVolumeMm3) }}</div>
                </div>
                <div class="rounded-2xl bg-slate-50 p-4">
                  <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureRuleEffectSummary") }}</div>
                  <div class="mt-2 text-base font-semibold text-slate-900">{{ matchedRuleActionSummary }}</div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="rounded-2xl border border-slate-200 bg-white p-4">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureDifference") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900 whitespace-nowrap">{{ formatVolume(effectiveTargetVolumeMm3 - recommendedVolumeMm3) }}</div>
                  </div>
                  <div class="rounded-2xl border border-slate-200 bg-white p-4">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("config.apertureStatus") }}</div>
                    <div class="mt-2 text-base font-semibold text-slate-900">{{ previewStatusLabel }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import AppIcon from "./AppIcon.vue";
import AppSelect from "./AppSelect.vue";
import HelpTooltip from "./HelpTooltip.vue";
import { t as translate } from "../i18n";

function cloneRule(rule) {
  return JSON.parse(JSON.stringify(rule));
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

// Keep in sync with src/stencilforge/aperture_workspace.py
const PACKAGE_FACTOR_MAP = {
  QFN: 0.94,
  BGA: 0.92,
  IC: 1.0,
  Power: 1.04,
};

const PAD_TYPE_FACTOR_MAP = {
  SMD: 1.0,
  BGA: 0.92,
  Thermal: 0.96,
  THT: 1.04,
};

const STRATEGY_FACTOR_MAP = {
  balanced: 1.0,
  conservative: 0.95,
  aggressive: 1.05,
};

export default {
  name: "ApertureRuleWorkspace",
  components: { AppIcon, AppSelect, HelpTooltip },
  props: {
    backend: {
      type: Object,
      default: null,
    },
    locale: {
      type: String,
      default: "en",
    },
    embedded: {
      type: Boolean,
      default: false,
    },
    stencilThicknessMm: {
      type: Number,
      default: 0.12,
    },
  },
  data() {
    return {
      studioTab: "basic",
      profileName: "Balanced default",
      transferRatio: 0.88,
      strategy: "balanced",
      minApertureMm: 0.1,
      maxApertureMm: 0,
      allowAsymmetric: false,
      padAreaMm2: 0.84,
      padWidthMm: 0.45,
      padHeightMm: 0.4,
      packageType: "Any",
      padType: "SMD",
      targetVolumeMm3: 0.062,
      selectedRuleId: "rule_default",
      selectedRuleGroupKey: null,
      workspaceHydrating: false,
      workspaceSnapshot: null,
      workspaceSyncTimer: null,
      workspaceSignalConnected: false,
      workspaceLastSignature: "",
      rules: [],
    };
  },
  mounted() {
    this.connectWorkspaceBackend(this.backend);
  },
  beforeUnmount() {
    if (this.workspaceSyncTimer) {
      clearTimeout(this.workspaceSyncTimer);
      this.workspaceSyncTimer = null;
    }
  },
  watch: {
    backend: {
      immediate: true,
      handler(nextBackend, previousBackend) {
        this.connectWorkspaceBackend(nextBackend, previousBackend);
      },
    },
    workspaceDraftSignature: {
      immediate: true,
      handler(nextSignature) {
        if (this.workspaceHydrating) return;
        if (!this.backend || typeof this.backend.setApertureWorkspace !== "function") return;
        if (nextSignature === this.workspaceLastSignature) return;
        this.workspaceLastSignature = nextSignature;
        if (this.workspaceSyncTimer) {
          clearTimeout(this.workspaceSyncTimer);
        }
        this.workspaceSyncTimer = setTimeout(() => {
          if (!this.backend || typeof this.backend.setApertureWorkspace !== "function") return;
          this.backend.setApertureWorkspace(this.exportWorkspaceState());
        }, 150);
      },
    },
  },
  computed: {
    tabs() {
      return [
        { value: "basic", label: this.t("config.apertureTabBasic"), icon: "tune" },
        { value: "rules", label: this.t("config.apertureTabRules"), icon: "rule" },
        { value: "calculator", label: this.t("config.apertureTabCalculator"), icon: "calculate" },
        { value: "preview", label: this.t("config.apertureTabPreview"), icon: "visibility" },
      ];
    },
    workspaceDraftSignature() {
      return JSON.stringify(this.exportWorkspaceState());
    },
    thicknessValue() {
      const value = Number(this.stencilThicknessMm);
      return Number.isFinite(value) && value > 0 ? value : 0.12;
    },
    thicknessLabel() {
      return `${this.thicknessValue.toFixed(2)} mm`;
    },
    currentThicknessFactor() {
      const backendValue = this.workspaceSnapshot?.currentThicknessFactor;
      if (Number.isFinite(backendValue)) return backendValue;
      return this.thicknessValue * this.transferRatio;
    },
    theoreticalVolumeMm3() {
      const backendValue = this.workspaceSnapshot?.theoreticalVolumeMm3;
      if (Number.isFinite(backendValue)) return backendValue;
      return this.padAreaMm2 * this.currentThicknessFactor;
    },
    recommendedVolumeMm3() {
      const backendValue = this.workspaceSnapshot?.recommendedVolumeMm3;
      if (Number.isFinite(backendValue)) return backendValue;
      return this.theoreticalVolumeMm3 * this.packageFactor * this.padTypeFactor * this.strategyFactor;
    },
    effectiveTargetVolumeMm3() {
      const backendValue = this.workspaceSnapshot?.effectiveTargetVolumeMm3;
      if (Number.isFinite(backendValue)) return backendValue;
      const value = Number(this.targetVolumeMm3);
      return Number.isFinite(value) && value > 0 ? value : this.recommendedVolumeMm3;
    },
    targetOpenAreaMm2() {
      const backendValue = this.workspaceSnapshot?.targetOpenAreaMm2;
      if (Number.isFinite(backendValue)) return backendValue;
      if (this.currentThicknessFactor <= 0) return 0;
      return this.effectiveTargetVolumeMm3 / this.currentThicknessFactor;
    },
    recommendedScale() {
      const backendValue = this.workspaceSnapshot?.recommendedScale;
      if (Number.isFinite(backendValue)) return backendValue;
      if (this.padAreaMm2 <= 0 || this.targetOpenAreaMm2 <= 0) return 1;
      return Math.sqrt(Math.max(0.0001, this.targetOpenAreaMm2 / this.padAreaMm2));
    },
    recommendedDeltaMm() {
      const backendValue = this.workspaceSnapshot?.recommendedDeltaMm;
      if (Number.isFinite(backendValue)) return backendValue;
      return this.solveDeltaForRectangle(this.padWidthMm, this.padHeightMm, this.targetOpenAreaMm2);
    },
    calculatorStatus() {
      const backendValue = this.workspaceSnapshot?.calculatorStatus;
      if (backendValue) return backendValue;
      if (!Number.isFinite(this.recommendedDeltaMm)) return "warning";
      if (this.minApertureMm > 0 && this.recommendedDeltaMm < -Math.abs(this.minApertureMm)) return "warning";
      if (this.maxApertureMm > 0 && this.recommendedDeltaMm > this.maxApertureMm) return "warning";
      return "ok";
    },
    calculatorStatusLabel() {
      return this.calculatorStatus === "warning" ? this.t("config.apertureStatusWarning") : this.t("config.apertureStatusOk");
    },
    previewStatusLabel() {
      const backendValue = this.workspaceSnapshot?.previewStatus;
      if (backendValue === "above") {
        return this.t("config.aperturePreviewAbove");
      }
      if (backendValue === "recommended") {
        return this.t("config.aperturePreviewRecommended");
      }
      if (backendValue === "below") {
        return this.t("config.aperturePreviewBelow");
      }
      const effective = this.effectiveTargetVolumeMm3;
      const recommended = this.recommendedVolumeMm3;
      if (effective > recommended * 1.005) return this.t("config.aperturePreviewAbove");
      if (effective < recommended * 0.995) return this.t("config.aperturePreviewBelow");
      return this.t("config.aperturePreviewRecommended");
    },
    matchedRuleActionSummary() {
      const backendValue = this.workspaceSnapshot?.matchedRuleActionSummary;
      if (backendValue) return backendValue;
      return this.describeAction(this.matchedRule);
    },
    matchedRuleEffectScale() {
      const rule = this.matchedRule;
      if (!rule || !rule.action) return 1;
      if (rule.action.mode === "scale") {
        return Number(rule.action.scale) || 1;
      }
      const delta = Number(rule.action.deltaMm) || 0;
      const w = Number(this.padWidthMm);
      const h = Number(this.padHeightMm);
      if (w <= 0 || h <= 0) return 1;
      const newW = w + 2 * delta;
      const newH = h + 2 * delta;
      if (newW <= 0 || newH <= 0) return 0.01;
      const areaRatio = (newW * newH) / (w * h);
      return Math.sqrt(Math.max(0.01, areaRatio));
    },
    matchedRuleEffectDelta() {
      const rule = this.matchedRule;
      if (!rule || !rule.action) return 0;
      return Number(rule.action.deltaMm) || 0;
    },
    activeRule() {
      return this.rules.find((rule) => rule.id === this.selectedRuleId) || this.rules[0];
    },
    matchedRule() {
      if (this.workspaceSnapshot?.matchedRule) {
        return this.workspaceSnapshot.matchedRule;
      }
      return this.activeRule;
    },
    matchedRuleGroupKey() {
      return this.ruleGroupKeyFromRule(this.matchedRule);
    },
    activeRuleGroupKey() {
      if (this.selectedRuleGroupKey === "__all__") return "";
      if (this.selectedRuleGroupKey) return this.selectedRuleGroupKey;
      return this.matchedRuleGroupKey || "";
    },
    showingAllRuleGroups() {
      return this.selectedRuleGroupKey === "__all__";
    },
    ruleGroups() {
      const backendGroups = this.workspaceSnapshot?.ruleGroups;
      if (Array.isArray(backendGroups) && backendGroups.length) {
        return backendGroups;
      }
      return this.buildRuleGroupsFromRules(this.rules);
    },
    filteredRules() {
      const groupKey = this.activeRuleGroupKey;
      if (!groupKey) return this.rules;
      return this.rules.filter((rule) => this.ruleGroupKeyFromRule(rule) === groupKey);
    },
    matchedRuleGroupSummary() {
      const backendValue = this.workspaceSnapshot?.matchedRuleGroupSummary;
      if (backendValue) return backendValue;
      return this.describeRuleGroup(this.matchedRule);
    },
    packageOptions() {
      return [
        { value: "Any", label: this.t("config.apertureAny") },
        { value: "QFN", label: "QFN" },
        { value: "BGA", label: this.t("config.aperturePadTypeBga") },
        { value: "Power", label: this.t("config.aperturePackagePower") },
        { value: "IC", label: "IC" },
      ];
    },
    packageTypeOptions() {
      return [
        { value: "Any", label: this.t("config.apertureAny") },
        { value: "QFN", label: "QFN" },
        { value: "BGA", label: "BGA" },
        { value: "IC", label: "IC" },
        { value: "Power", label: this.t("config.aperturePackagePower") },
      ];
    },
    padTypeOptions() {
      return [
        { value: "Any", label: this.t("config.apertureAny") },
        { value: "SMD", label: this.t("config.aperturePadTypeSmd") },
        { value: "BGA", label: "BGA" },
        { value: "Thermal", label: this.t("config.aperturePadTypeThermal") },
        { value: "THT", label: this.t("config.aperturePadTypeTht") },
      ];
    },
    strategyOptions() {
      return [
        { value: "balanced", label: this.t("config.apertureStrategyBalanced") },
        { value: "conservative", label: this.t("config.apertureStrategyConservative") },
        { value: "aggressive", label: this.t("config.apertureStrategyAggressive") },
      ];
    },
    actionOptions() {
      return [
        { value: "delta", label: this.t("config.apertureActionDelta") },
        { value: "scale", label: this.t("config.apertureActionScale") },
      ];
    },
    generatedRulePreview() {
      const backendValue = this.workspaceSnapshot?.generatedRulePreview;
      if (backendValue) return backendValue;
      const delta = Number.isFinite(this.recommendedDeltaMm) ? this.recommendedDeltaMm.toFixed(3) : "0.000";
      return `match: { package: "${this.packageType}", padType: "${this.padType}" }
action: { deltaMm: ${delta}, scale: ${this.recommendedScale.toFixed(3)} }
priority: 100`;
    },
    strategyKey() {
      const backendValue = this.workspaceSnapshot?.strategy;
      if (backendValue) return this.capitalize(backendValue);
      return this.capitalize(this.strategy);
    },
    packageFactor() {
      const backendValue = this.workspaceSnapshot?.packageFactor;
      if (Number.isFinite(backendValue)) return backendValue;
      return PACKAGE_FACTOR_MAP[this.packageType] || 1;
    },
    padTypeFactor() {
      const backendValue = this.workspaceSnapshot?.padTypeFactor;
      if (Number.isFinite(backendValue)) return backendValue;
      return PAD_TYPE_FACTOR_MAP[this.padType] || 1;
    },
    strategyFactor() {
      const backendValue = this.workspaceSnapshot?.strategyFactor;
      if (Number.isFinite(backendValue)) return backendValue;
      return STRATEGY_FACTOR_MAP[this.strategy] || 1;
    },
  },
  methods: {
    t(key, vars = {}) {
      return translate(this.locale, key, vars);
    },
    connectWorkspaceBackend(nextBackend, previousBackend = null) {
      if (previousBackend === nextBackend) {
        return;
      }
      if (!nextBackend || typeof nextBackend !== "object") {
        this.workspaceSnapshot = null;
        return;
      }
      this.workspaceHydrating = true;
      if (!this.workspaceSignalConnected && nextBackend.apertureWorkspaceChanged && nextBackend.apertureWorkspaceChanged.connect) {
        nextBackend.apertureWorkspaceChanged.connect((snapshot) => {
          this.applyWorkspaceSnapshot(snapshot || {});
        });
        this.workspaceSignalConnected = true;
      }
      if (typeof nextBackend.getApertureWorkspace === "function") {
        nextBackend.getApertureWorkspace((snapshot) => {
          if (snapshot && Array.isArray(snapshot.rules) && snapshot.rules.length > 0) {
            this.applyWorkspaceSnapshot(snapshot);
          } else if (typeof nextBackend.getDefaultApertureWorkspace === "function") {
            nextBackend.getDefaultApertureWorkspace((defaults) => {
              this.applyWorkspaceSnapshot(defaults || {});
            });
          } else {
            this.workspaceHydrating = false;
          }
        });
      } else {
        this.workspaceHydrating = false;
      }
    },
    applyWorkspaceSnapshot(snapshot) {
      if (!snapshot || typeof snapshot !== "object") {
        return;
      }
      this.workspaceHydrating = true;
      this.workspaceSnapshot = snapshot;
      const fields = [
        "profileName",
        "transferRatio",
        "strategy",
        "minApertureMm",
        "maxApertureMm",
        "allowAsymmetric",
        "padAreaMm2",
        "padWidthMm",
        "padHeightMm",
        "packageType",
        "padType",
        "targetVolumeMm3",
        "selectedRuleId",
        "selectedRuleGroupKey",
        "rules",
      ];
      for (const field of fields) {
        if (field in snapshot) {
          this[field] = deepClone(snapshot[field]);
        }
      }
      this.$nextTick(() => {
        this.workspaceHydrating = false;
        this.workspaceLastSignature = JSON.stringify(this.exportWorkspaceState());
      });
    },
    exportWorkspaceState() {
      return {
        profileName: this.profileName,
        transferRatio: Number(this.transferRatio),
        strategy: this.strategy,
        minApertureMm: Number(this.minApertureMm),
        maxApertureMm: Number(this.maxApertureMm),
        allowAsymmetric: !!this.allowAsymmetric,
        padAreaMm2: Number(this.padAreaMm2),
        padWidthMm: Number(this.padWidthMm),
        padHeightMm: Number(this.padHeightMm),
        packageType: this.packageType,
        padType: this.padType,
        targetVolumeMm3: Number(this.targetVolumeMm3),
        selectedRuleId: this.selectedRuleId,
        selectedRuleGroupKey: this.selectedRuleGroupKey || "",
        rules: deepClone(this.rules),
        stencilThicknessMm: Number(this.thicknessValue),
      };
    },
    formatVolume(value) {
      const next = Number(value);
      return `${(Number.isFinite(next) ? next : 0).toFixed(3)} mm³`;
    },
    formatArea(value) {
      const next = Number(value);
      return `${(Number.isFinite(next) ? next : 0).toFixed(3)} mm²`;
    },
    formatScale(value) {
      const next = Number(value);
      return `x ${(Number.isFinite(next) ? next : 1).toFixed(3)}`;
    },
    formatDelta(value) {
      const next = Number(value);
      const normalized = Number.isFinite(next) ? next : 0;
      return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(3)} mm`;
    },
    percentLabel(value) {
      const next = Number(value);
      return `${((Number.isFinite(next) ? next : 0) * 100).toFixed(0)}%`;
    },
    solveDeltaForRectangle(width, height, targetArea) {
      const w = Number(width);
      const h = Number(height);
      const area = Number(targetArea);
      if (!Number.isFinite(w) || !Number.isFinite(h) || !Number.isFinite(area) || w <= 0 || h <= 0 || area <= 0) {
        return 0;
      }
      const root = Math.sqrt(Math.max(0, (w - h) * (w - h) + 4 * area));
      return (-w - h + root) / 4;
    },
    previewVisualStyle(scale, variant) {
      const nextScale = Math.max(0.38, Math.min(1.08, Number(scale) || 1));
      const baseSize = variant === "raw" ? 72 : variant === "recommended" ? 80 : 88;
      const size = Math.round(baseSize * nextScale);
      return {
        width: `${size}px`,
        height: `${size}px`,
      };
    },
    describeMatch(rule) {
      if (!rule) return "";
      const parts = [];
      if (rule.match.package && rule.match.package !== "Any") parts.push(rule.match.package);
      if (rule.match.padType && rule.match.padType !== "Any") parts.push(rule.match.padType);
      if (rule.match.padSize) parts.push(rule.match.padSize);
      return parts.length ? parts.join(" / ") : this.t("config.apertureAny");
    },
    describeRuleGroup(group) {
      if (!group) return this.t("config.apertureAny");
      const label = String(group.label || "").trim();
      if (label) return label;
      const parts = [];
      if (group.package && group.package !== "Any") parts.push(group.package);
      if (group.padType && group.padType !== "Any") parts.push(group.padType);
      return parts.length ? parts.join(" / ") : this.t("config.apertureAny");
    },
    selectAllRuleGroups() {
      this.selectedRuleGroupKey = "__all__";
    },
    selectRuleGroup(groupKey) {
      this.selectedRuleGroupKey = groupKey || null;
      const nextRule = this.filteredRules[0];
      if (nextRule) {
        this.selectedRuleId = nextRule.id;
      }
    },
    selectRule(rule) {
      this.selectedRuleId = rule.id;
    },
    buildRuleGroupsFromRules(rules) {
      const groups = new Map();
      (rules || []).forEach((rule, index) => {
        const key = this.ruleGroupKeyFromRule(rule);
        if (!groups.has(key)) {
          groups.set(key, {
            key,
            label: this.describeRuleGroup(rule?.match ? this.ruleGroupDescriptorFromRule(rule) : null),
            package: String(rule?.match?.package || "Any"),
            padType: String(rule?.match?.padType || "Any"),
            ruleCount: 0,
            enabledRuleCount: 0,
            _order: index,
          });
        }
        const group = groups.get(key);
        group.ruleCount += 1;
        if (rule && rule.enabled !== false) {
          group.enabledRuleCount += 1;
        }
      });
      return Array.from(groups.values())
        .sort((left, right) => {
          if (left._order !== right._order) return left._order - right._order;
          return String(left.label).localeCompare(String(right.label));
        })
        .map((group) => {
          const next = { ...group };
          delete next._order;
          return next;
        });
    },
    ruleGroupDescriptorFromRule(rule) {
      return {
        package: String(rule?.match?.package || "Any"),
        padType: String(rule?.match?.padType || "Any"),
      };
    },
    ruleGroupKeyFromRule(rule) {
      const match = rule && rule.match ? rule.match : {};
      const packageType = String(match.package || "Any").trim() || "Any";
      const padType = String(match.padType || "Any").trim() || "Any";
      return `${packageType.toLowerCase()}::${padType.toLowerCase()}`;
    },
    describeAction(rule) {
      if (!rule) return "";
      if (rule.action.mode === "scale") {
        return `${this.t("config.apertureActionScale")} ${this.formatScale(rule.action.scale)}`;
      }
      return `${this.t("config.apertureActionDelta")} ${this.formatDelta(rule.action.deltaMm)}`;
    },
    newRule() {
      return {
        id: `rule_${Date.now()}`,
        name: this.t("config.apertureNewRule"),
        enabled: true,
        priority: 50,
        match: { package: "Any", padType: "Any", padSize: "0.20-0.80 mm" },
        action: { mode: "scale", deltaMm: 0.0, scale: 1.0 },
        note: "",
      };
    },
    addRule() {
      const next = this.newRule();
      this.rules.unshift(next);
      this.selectedRuleId = next.id;
      this.selectedRuleGroupKey = "__all__";
    },
    duplicateRule() {
      if (!this.activeRule) return;
      const next = cloneRule(this.activeRule);
      next.id = `rule_${Date.now()}`;
      next.name = `${next.name} ${this.t("config.apertureCopySuffix")}`;
      this.rules.splice(this.rules.indexOf(this.activeRule) + 1, 0, next);
      this.selectedRuleId = next.id;
    },
    removeSelectedRule() {
      if (this.rules.length <= 1 || !this.activeRule) return;
      const index = this.rules.indexOf(this.activeRule);
      this.rules.splice(index, 1);
      this.selectedRuleId = this.rules[Math.max(0, index - 1)].id;
    },
    importRulesFromBackend() {
      if (!this.backend || typeof this.backend.importApertureWorkspace !== "function") return;
      this.backend.importApertureWorkspace((resultPath) => {
        if (!resultPath) {
          return;
        }
        if (typeof this.backend.getApertureWorkspace === "function") {
          this.backend.getApertureWorkspace((snapshot) => {
            this.applyWorkspaceSnapshot(snapshot || {});
          });
        }
      });
    },
    exportRulesToBackend() {
      if (!this.backend || typeof this.backend.exportApertureWorkspace !== "function") return;
      this.backend.exportApertureWorkspace((resultPath) => {
        if (!resultPath) {
          return;
        }
        if (typeof this.backend.getApertureWorkspace === "function") {
          this.backend.getApertureWorkspace((snapshot) => {
            this.applyWorkspaceSnapshot(snapshot || {});
          });
        }
      });
    },
    syncTargetToRecommended() {
      this.targetVolumeMm3 = Number(this.recommendedVolumeMm3.toFixed(3));
    },
    capitalize(value) {
      const text = String(value || "");
      return text.charAt(0).toUpperCase() + text.slice(1);
    },
  },
};
</script>
