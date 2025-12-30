<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(path, index) in iconPaths" :key="index" :d="path" />
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 20 },
});

const icons = {
  view_in_ar: [
    "M4 7l8-4 8 4-8 4-8-4Z",
    "M4 7v10l8 4 8-4V7",
    "M12 11v10",
  ],
  language: [
    "M12 2a10 10 0 100 20a10 10 0 000-20Z",
    "M2 12h20",
    "M12 2c-3 3-3 15 0 20",
    "M12 2c3 3 3 15 0 20",
  ],
  expand_more: ["M6 9l6 6 6-6"],
  check: ["M5 13l4 4 10-10"],
  remove: ["M5 12h14"],
  crop_square: ["M6 6h12v12H6z"],
  close: ["M6 6l12 12", "M18 6l-12 12"],
  description: ["M6 3h9l3 3v15H6z", "M8 11h8", "M8 15h8"],
  add_circle: ["M12 2a10 10 0 100 20a10 10 0 000-20Z", "M12 8v8", "M8 12h8"],
  autorenew: ["M4 12a8 8 0 0113.5-4.5", "M17.5 3.5h3v3", "M20 12a8 8 0 01-13.5 4.5", "M6.5 20.5h-3v-3"],
  cloud_upload: ["M7 18a4 4 0 010-8 5 5 0 019.5-1.5A4 4 0 0117 18H7z", "M12 10v6", "M9 13l3-3 3 3"],
  settings: [
    "M4 6h16",
    "M4 12h16",
    "M4 18h16",
    "M8 6a2 2 0 100-4 2 2 0 000 4",
    "M14 12a2 2 0 100-4 2 2 0 000 4",
    "M10 18a2 2 0 100-4 2 2 0 000 4",
  ],
  visibility: ["M2 12s4-6 10-6 10 6-4 6-10 6-10-6Z", "M12 12a3 3 0 100-6 3 3 0 000 6"],
  download: ["M12 4v10", "M8 10l4 4 4-4", "M4 18h16"],
};

const iconPaths = computed(() => icons[props.name] || icons.description);
</script>
