<template>
  <div class="relative inline-flex">
    <button
      class="inline-flex h-6 w-6 items-center justify-center rounded-full border text-xs font-bold shadow-sm transition hover:bg-opacity-80"
      :class="buttonClass"
      :aria-label="text"
      type="button"
      @mouseenter="show = true"
      @mouseleave="show = false"
      @focus="show = true"
      @blur="show = false"
    >?</button>
    <div
      v-show="show"
      class="pointer-events-none absolute bottom-full right-0 z-30 mb-2 w-64 max-w-[calc(100vw-2rem)] rounded-2xl border bg-white px-3 py-2 text-left text-xs leading-5 text-slate-600 shadow-[0_20px_45px_rgba(15,23,42,0.12)]"
      :class="popoverBorder"
    >
      <span
        class="absolute -bottom-1 right-3 h-2 w-2 rotate-45 border-b border-r bg-white"
        :class="popoverBorder"
        aria-hidden="true"
      ></span>
      {{ text }}
    </div>
  </div>
</template>

<script>
export default {
  name: "HelpTooltip",
  props: {
    text: { type: String, required: true },
    variant: {
      type: String,
      default: "slate",
      validator: (v) => ["slate", "blue"].includes(v),
    },
  },
  data() {
    return { show: false };
  },
  computed: {
    buttonClass() {
      return this.variant === "blue"
        ? "border-blue-200 bg-white text-blue-600 hover:border-blue-300 hover:bg-blue-50"
        : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:bg-slate-50";
    },
    popoverBorder() {
      return this.variant === "blue"
        ? "border-blue-100"
        : "border-slate-200";
    },
  },
};
</script>
