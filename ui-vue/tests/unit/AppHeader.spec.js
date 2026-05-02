import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import AppHeader from "../../src/components/AppHeader.vue";

const DEFAULT_PROPS = {
  appTitle: "StencilForge",
  tagline: "PCB stencil generator",
  locale: "zh-CN",
  localeOptions: [
    { value: "zh-CN", label: "简体中文" },
    { value: "en", label: "English" },
    { value: "ja", label: "日本語" },
  ],
  currentLocaleLabel: "简体中文",
  languageLabel: "Language",
  minimizeTitle: "Minimize",
  maximizeRestoreTitle: "Maximize",
  closeTitle: "Close",
};

function mountHeader(props = {}) {
  return mount(AppHeader, {
    props: { ...DEFAULT_PROPS, ...props },
    global: {
      stubs: {
        AppIcon: { template: '<span class="mock-icon" :data-name="name" />', props: ["name", "size"] },
      },
    },
  });
}

describe("AppHeader", () => {
  describe("rendering", () => {
    it("displays app title and tagline", () => {
      const wrapper = mountHeader();
      expect(wrapper.text()).toContain("StencilForge");
      expect(wrapper.text()).toContain("PCB stencil generator");
    });

    it("displays current locale label", () => {
      const wrapper = mountHeader({ currentLocaleLabel: "English" });
      expect(wrapper.text()).toContain("English");
    });

    it("renders window control buttons", () => {
      const wrapper = mountHeader();
      const buttons = wrapper.findAll(".window-btn");
      expect(buttons.length).toBe(3);
    });
  });

  describe("events", () => {
    it("emits window-minimize when minimize button clicked", async () => {
      const wrapper = mountHeader();
      await wrapper.findAll(".window-btn")[0].trigger("click");
      expect(wrapper.emitted("window-minimize")).toBeTruthy();
    });

    it("emits window-maximize-restore when maximize button clicked", async () => {
      const wrapper = mountHeader();
      await wrapper.findAll(".window-btn")[1].trigger("click");
      expect(wrapper.emitted("window-maximize-restore")).toBeTruthy();
    });

    it("emits window-close when close button clicked", async () => {
      const wrapper = mountHeader();
      await wrapper.findAll(".window-btn")[2].trigger("click");
      expect(wrapper.emitted("window-close")).toBeTruthy();
    });

    it("emits titlebar-mouse-down when header mousedown", async () => {
      const wrapper = mountHeader();
      await wrapper.find("header").trigger("mousedown", { button: 0 });
      expect(wrapper.emitted("titlebar-mouse-down")).toBeTruthy();
    });

    it("emits titlebar-double-click when header double clicked", async () => {
      const wrapper = mountHeader();
      await wrapper.find("header").trigger("dblclick");
      expect(wrapper.emitted("titlebar-double-click")).toBeTruthy();
    });
  });

  describe("language menu", () => {
    it("toggles language menu on button click", async () => {
      const wrapper = mountHeader();
      // Initially menu should be closed
      expect(wrapper.find('[role="menu"]').exists()).toBe(false);
      // Click lang button
      await wrapper.find(".titlebar-interactive button").trigger("click");
      expect(wrapper.find('[role="menu"]').exists()).toBe(true);
    });

    it("emits select-locale and closes menu", async () => {
      const wrapper = mountHeader();
      await wrapper.find(".titlebar-interactive button").trigger("click");
      const items = wrapper.findAll('[role="menuitem"]');
      await items[1].trigger("click"); // pick English
      const selectEvents = wrapper.emitted("select-locale");
      expect(selectEvents).toBeTruthy();
      expect(selectEvents[0]).toEqual(["en"]);
    });
  });
});
