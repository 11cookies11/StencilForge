<template>
  <div class="relative" ref="root" v-bind="$attrs">
    <button
      class="w-full h-9 px-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-left flex items-center justify-between gap-2"
      type="button"
      :disabled="disabled"
      @click.stop="toggleOpen"
    >
      <span class="truncate" :class="selectedLabel ? 'text-slate-700' : 'text-slate-400'">
        {{ selectedLabel || placeholder }}
      </span>
      <AppIcon
        name="expand_more"
        :size="18"
        class="text-slate-400 transition-transform"
        :class="open ? 'rotate-180' : ''"
      />
    </button>
    <div
      v-if="open"
      class="absolute left-0 right-0 mt-1 z-40 rounded-lg border border-slate-200 bg-white shadow-lg max-h-56 overflow-y-auto"
    >
      <button
        v-for="item in options"
        :key="String(item.value)"
        class="w-full text-left px-3 py-2 text-sm transition-colors"
        :class="item.value === modelValue ? 'bg-blue-50 text-primary' : 'text-slate-700 hover:bg-slate-50'"
        type="button"
        @click="selectOption(item.value)"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

<script>
import AppIcon from "./AppIcon.vue";

export default {
  name: "AppSelect",
  components: { AppIcon },
  inheritAttrs: false,
  props: {
    modelValue: {
      type: [String, Number],
      default: "",
    },
    options: {
      type: Array,
      default: () => [],
    },
    placeholder: {
      type: String,
      default: "",
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["update:modelValue", "change"],
  data() {
    return {
      open: false,
    };
  },
  computed: {
    selectedLabel() {
      const matched = this.options.find((item) => item.value === this.modelValue);
      return matched ? matched.label : "";
    },
  },
  mounted() {
    document.addEventListener("click", this.onDocumentClick);
    document.addEventListener("keydown", this.onKeydown);
  },
  beforeUnmount() {
    document.removeEventListener("click", this.onDocumentClick);
    document.removeEventListener("keydown", this.onKeydown);
  },
  methods: {
    toggleOpen() {
      if (this.disabled) return;
      this.open = !this.open;
    },
    selectOption(value) {
      this.$emit("update:modelValue", value);
      this.$emit("change", value);
      this.open = false;
    },
    onDocumentClick(event) {
      if (!this.open) return;
      const root = this.$refs.root;
      if (!root || root.contains(event.target)) return;
      this.open = false;
    },
    onKeydown(event) {
      if (event.key === "Escape" && this.open) {
        this.open = false;
      }
    },
  },
};
</script>
