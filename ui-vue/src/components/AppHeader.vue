<template>
  <header
    class="sticky top-0 z-40 bg-white border-b border-slate-200 h-16 app-titlebar"
    @mousedown="$emit('titlebar-mouse-down', $event)"
    @dblclick="$emit('titlebar-double-click', $event)"
  >
    <div class="w-full h-full flex items-center justify-between px-4 sm:px-6">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 bg-primary rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/30">
          <AppIcon name="view_in_ar" class="text-white" :size="20" />
        </div>
        <span class="text-xl font-bold tracking-tight text-slate-900">{{ appTitle }}</span>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-xs text-slate-400 hidden sm:block">{{ tagline }}</div>
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
            :aria-label="languageLabel"
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
            :aria-label="languageLabel"
          >
            <div class="p-1.5 space-y-0.5">
              <button
                v-for="option in localeOptions"
                :key="option.value"
                class="w-full text-left flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors"
                :class="
                  locale === option.value
                    ? 'text-primary bg-blue-50'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                "
                type="button"
                role="menuitem"
                @click="selectLocale(option.value)"
              >
                <span>{{ option.label }}</span>
                <AppIcon v-if="locale === option.value" name="check" :size="18" />
              </button>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 window-controls">
          <button class="window-btn" @click="$emit('window-minimize')" @dblclick.stop :title="minimizeTitle">
            <AppIcon name="remove" :size="18" />
          </button>
          <button class="window-btn" @click="$emit('window-maximize-restore')" @dblclick.stop :title="maximizeRestoreTitle">
            <AppIcon name="crop_square" :size="18" />
          </button>
          <button class="window-btn window-btn-close" @click="$emit('window-close')" @dblclick.stop :title="closeTitle">
            <AppIcon name="close" :size="18" />
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script>
import AppIcon from "./AppIcon.vue";

export default {
  name: "AppHeader",
  components: { AppIcon },
  props: {
    appTitle: {
      type: String,
      default: "StencilForge",
    },
    tagline: {
      type: String,
      default: "",
    },
    locale: {
      type: String,
      default: "zh-CN",
    },
    localeOptions: {
      type: Array,
      default: () => [],
    },
    currentLocaleLabel: {
      type: String,
      default: "",
    },
    languageLabel: {
      type: String,
      default: "",
    },
    minimizeTitle: {
      type: String,
      default: "",
    },
    maximizeRestoreTitle: {
      type: String,
      default: "",
    },
    closeTitle: {
      type: String,
      default: "",
    },
  },
  emits: [
    "select-locale",
    "window-minimize",
    "window-maximize-restore",
    "window-close",
    "titlebar-mouse-down",
    "titlebar-double-click",
  ],
  data() {
    return {
      languageMenuOpen: false,
    };
  },
  mounted() {
    document.addEventListener("click", this.onDocumentClick);
    document.addEventListener("keydown", this.onDocumentKeydown);
  },
  beforeUnmount() {
    document.removeEventListener("click", this.onDocumentClick);
    document.removeEventListener("keydown", this.onDocumentKeydown);
  },
  methods: {
    toggleLanguageMenu() {
      this.languageMenuOpen = !this.languageMenuOpen;
    },
    selectLocale(nextLocale) {
      this.$emit("select-locale", nextLocale);
      this.languageMenuOpen = false;
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
  },
};
</script>
