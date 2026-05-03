<template>
  <div class="space-y-4">
    <div class="grid gap-4 md:grid-cols-2">
      <label class="text-xs font-semibold text-slate-600">{{ t("config.thickness") }}
        <input
          :value="effectiveThicknessValue"
          :disabled="isFsmProfile"
          @input="emitThicknessChange"
          class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg disabled:text-slate-500 disabled:bg-slate-100"
          type="number" step="0.01"
        />
        <span v-if="isFsmProfile" class="mt-1 block text-[11px] font-medium text-slate-500">
          {{ t("config.thicknessFsmManaged") }}
        </span>
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.outputMode") }}
        <AppSelect
          :model-value="config.output_mode"
          @update:model-value="$emit('update:config', { ...config, output_mode: $event })"
          class="mt-1"
          :options="outputModeOptions"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.pasteSide") }}
        <AppSelect
          :model-value="config.paste_side || 'top'"
          @update:model-value="$emit('update:config', { ...config, paste_side: $event })"
          class="mt-1"
          :options="pasteSideOptions"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.printerProfile") }}
        <AppSelect
          :model-value="config.printer_profile || 'generic'"
          @update:model-value="emitPrinterProfileChange"
          class="mt-1"
          :options="printerProfileOptions"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.modelBackend") }}
        <AppSelect
          :model-value="config.model_backend"
          @update:model-value="$emit('update:config', { ...config, model_backend: $event })"
          class="mt-1"
          :options="modelBackendOptions"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.pasteOffset") }}
        <input
          :value="config.paste_offset_mm"
          @input="$emit('update:config', { ...config, paste_offset_mm: Number($event.target.value) })"
          class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
          type="number" step="0.01"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.maskOpeningScale") }}
        <input
          :value="config.mask_opening_scale ?? 0.95"
          @input="$emit('update:config', { ...config, mask_opening_scale: Number($event.target.value) })"
          class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
          type="number" step="0.01" min="0.01"
        />
      </label>
      <label class="text-xs font-semibold text-slate-600">{{ t("config.outlineMargin") }}
        <input
          :value="config.outline_margin_mm"
          @input="$emit('update:config', { ...config, outline_margin_mm: Number($event.target.value) })"
          class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
          type="number" step="0.1"
        />
      </label>
    </div>

    <div class="pt-2 border-t border-slate-100 space-y-3">
      <label class="flex items-center gap-2 text-xs font-semibold text-slate-700">
        <input
          :checked="config.locator_enabled"
          @change="$emit('update:config', { ...config, locator_enabled: $event.target.checked })"
          class="h-4 w-4 text-primary border-slate-300 rounded"
          type="checkbox"
        />
        {{ t("config.locatorEnabled") }}
      </label>
      <div class="grid gap-4 md:grid-cols-2">
        <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorMode") }}
          <AppSelect
            :model-value="config.locator_mode"
            @update:model-value="$emit('update:config', { ...config, locator_mode: $event })"
            class="mt-1"
            :options="locatorModeOptions"
          />
        </label>
        <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorHeight") }}
          <input :value="config.locator_height_mm"
            @input="$emit('update:config', { ...config, locator_height_mm: Number($event.target.value) })"
            class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
            type="number" step="0.1" min="0"
          />
        </label>
        <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorWidth") }}
          <input :value="config.locator_width_mm"
            @input="$emit('update:config', { ...config, locator_width_mm: Number($event.target.value) })"
            class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
            type="number" step="0.1" min="0"
          />
        </label>
        <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorClearance") }}
          <input :value="config.locator_clearance_mm"
            @input="$emit('update:config', { ...config, locator_clearance_mm: Number($event.target.value) })"
            class="mt-1 w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg"
            type="number" step="0.05" min="0"
          />
        </label>
      </div>
    </div>

    <div v-if="showAdvancedConfig" class="space-y-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
      <div>
        <div class="text-xs font-semibold text-slate-500 uppercase mb-2">{{ t("config.advancedSection") }}</div>
        <div class="grid gap-4 md:grid-cols-2">
          <label class="text-xs font-semibold text-slate-600">{{ t("config.outlineMergeTol") }}
            <input :value="config.outline_merge_tol_mm"
              @input="$emit('update:config', { ...config, outline_merge_tol_mm: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="0.01" min="0"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.arcSteps") }}
            <input :value="config.arc_steps"
              @input="$emit('update:config', { ...config, arc_steps: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="1"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.curveResolution") }}
            <input :value="config.curve_resolution"
              @input="$emit('update:config', { ...config, curve_resolution: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="1"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorStepHeight") }}
            <input :value="config.locator_step_height_mm"
              @input="$emit('update:config', { ...config, locator_step_height_mm: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="0.1" min="0"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorStepWidth") }}
            <input :value="config.locator_step_width_mm"
              @input="$emit('update:config', { ...config, locator_step_width_mm: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="0.1" min="0"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorOpenSide") }}
            <AppSelect
              :model-value="config.locator_open_side"
              @update:model-value="$emit('update:config', { ...config, locator_open_side: $event })"
              class="mt-1"
              :options="locatorOpenSideOptions"
            />
          </label>
          <label class="text-xs font-semibold text-slate-600">{{ t("config.locatorOpenWidth") }}
            <input :value="config.locator_open_width_mm"
              @input="$emit('update:config', { ...config, locator_open_width_mm: Number($event.target.value) })"
              class="mt-1 w-full h-9 px-2 text-sm bg-white border border-slate-200 rounded-lg"
              type="number" step="0.1" min="0"
            />
          </label>
        </div>
      </div>
      <div>
        <div class="text-xs font-semibold text-slate-500 uppercase mb-2">{{ t("config.pasteRules") }}</div>
        <div class="space-y-2">
          <div class="flex gap-2" v-for="(pattern, index) in config.paste_patterns" :key="'paste-' + index">
            <input
              :value="pattern"
              @input="emitPatternChange('paste_patterns', index, $event.target.value)"
              class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono"
              type="text"
            />
            <button class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"
              @click="$emit('remove-pattern', 'paste', index)">
              <AppIcon name="close" :size="18" />
            </button>
          </div>
        </div>
        <button class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
          @click="$emit('add-pattern', 'paste')">
          <AppIcon name="add_circle" :size="16" />
          {{ t("config.addRule") }}
        </button>
      </div>
      <div>
        <div class="text-xs font-semibold text-slate-500 uppercase mb-2">{{ t("config.outlineRules") }}</div>
        <div class="space-y-2">
          <div class="flex gap-2" v-for="(pattern, index) in config.outline_patterns" :key="'outline-' + index">
            <input
              :value="pattern"
              @input="emitPatternChange('outline_patterns', index, $event.target.value)"
              class="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded font-mono"
              type="text"
            />
            <button class="size-8 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"
              @click="$emit('remove-pattern', 'outline', index)">
              <AppIcon name="close" :size="18" />
            </button>
          </div>
        </div>
        <button class="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
          @click="$emit('add-pattern', 'outline')">
          <AppIcon name="add_circle" :size="16" />
          {{ t("config.addRule") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import AppIcon from "./AppIcon.vue";
import AppSelect from "./AppSelect.vue";
import { t as translate } from "../i18n";

export default {
  name: "BasicConfigForm",
  components: { AppIcon, AppSelect },
  props: {
    config: { type: Object, required: true },
    showAdvancedConfig: { type: Boolean, default: false },
    locale: { type: String, required: true },
  },
  emits: ["update:config", "add-pattern", "remove-pattern"],
  computed: {
    pasteSideOptions() {
      return [
        { value: "both", label: this.t("config.pasteSideBoth") },
        { value: "top", label: this.t("config.pasteSideTop") },
        { value: "bottom", label: this.t("config.pasteSideBottom") },
      ];
    },
    outputModeOptions() {
      return [
        { value: "solid_with_cutouts", label: this.t("config.outputModeSolid") },
        { value: "holes_only", label: this.t("config.outputModeHoles") },
      ];
    },
    printerProfileOptions() {
      return [
        { value: "generic", label: this.t("config.printerProfileGeneric") },
        { value: "fsm", label: this.t("config.printerProfileFsm") },
      ];
    },
    modelBackendOptions() {
      return [
        { value: "cadquery", label: this.t("config.modelBackendCadquery") },
        { value: "trimesh", label: this.t("config.modelBackendTrimesh") },
      ];
    },
    locatorModeOptions() {
      return [
        { value: "step", label: this.t("config.locatorModeStep") },
        { value: "wall", label: this.t("config.locatorModeWall") },
      ];
    },
    locatorOpenSideOptions() {
      return [
        { value: "none", label: this.t("config.locatorOpenSideNone") },
        { value: "top", label: this.t("config.locatorOpenSideTop") },
        { value: "right", label: this.t("config.locatorOpenSideRight") },
        { value: "bottom", label: this.t("config.locatorOpenSideBottom") },
        { value: "left", label: this.t("config.locatorOpenSideLeft") },
      ];
    },
    isFsmProfile() {
      return (this.config.printer_profile || "generic") === "fsm";
    },
    effectiveThicknessValue() {
      return this.isFsmProfile ? 0.2 : this.config.thickness_mm;
    },
  },
  methods: {
    t(key, vars) { return translate(this.locale, key, vars); },
    emitThicknessChange(event) {
      if (this.isFsmProfile) return;
      this.$emit("update:config", { ...this.config, thickness_mm: Number(event.target.value) });
    },
    printerProfileDefaults(profile) {
      if (profile === "fsm") {
        return {
          stl_quality: "high_quality",
          stl_linear_deflection: 0.02,
          stl_angular_deflection: 0.05,
          arc_steps: 96,
          curve_resolution: 24,
        };
      }
      return {
        stl_quality: "balanced",
        stl_linear_deflection: 0.05,
        stl_angular_deflection: 0.1,
        arc_steps: 64,
        curve_resolution: 16,
      };
    },
    emitPrinterProfileChange(profile) {
      this.$emit("update:config", {
        ...this.config,
        printer_profile: profile,
        ...this.printerProfileDefaults(profile),
      });
    },
    emitPatternChange(patternKey, index, value) {
      const patterns = [...this.config[patternKey]];
      patterns[index] = value;
      this.$emit("update:config", { ...this.config, [patternKey]: patterns });
    },
  },
};
</script>
