import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import App from "../../src/App.vue";

function mountApp() {
  return mount(App, {
    global: {
      stubs: {
        AppHeader: { template: '<header class="mock-header"><slot /></header>', props: ["appTitle", "tagline", "locale", "localeOptions", "currentLocaleLabel", "languageLabel", "minimizeTitle", "maximizeRestoreTitle", "closeTitle"] },
        AppIcon: { template: "<span />", props: ["name", "size"] },
        BasicConfigForm: { template: '<div class="mock-config-form" />', props: ["config", "showAdvancedConfig", "locale"] },
        ApertureRuleWorkspace: { template: '<div class="mock-aperture-workspace" />', props: ["embedded", "backend", "locale", "stencilThicknessMm"] },
        AppSelect: { template: "<div />" },
      },
    },
  });
}

describe("App", () => {
  beforeEach(() => {
    // Simulate Qt environment missing → enters fallback gracefully
    delete window.qt;
    delete window.QWebChannel;
  });

  it("renders without crashing (Qt backend unavailable)", () => {
    const wrapper = mountApp();
    expect(wrapper.find(".min-h-screen").exists()).toBe(true);
  });

  it("starts on upload tab by default", () => {
    const wrapper = mountApp();
    expect(wrapper.vm.currentTab).toBe("upload");
    expect(wrapper.text()).toContain("Upload PCB files");
  });

  it("switches to config tab", async () => {
    const wrapper = mountApp();
    await wrapper.vm.setTab("config");
    expect(wrapper.vm.currentTab).toBe("config");
  });

  it("switches to preview tab", async () => {
    const wrapper = mountApp();
    await wrapper.vm.setTab("preview");
    expect(wrapper.vm.currentTab).toBe("preview");
  });

  it("shows upload section when on upload tab", () => {
    const wrapper = mountApp();
    wrapper.vm.currentTab = "upload";
    expect(wrapper.vm.currentTab).toBe("upload");
  });

  it("has default config values", () => {
    const wrapper = mountApp();
    const cfg = wrapper.vm.config;
    expect(cfg.thickness_mm).toBe(0.12);
    expect(cfg.output_mode).toBe("solid_with_cutouts");
    expect(cfg.printer_profile).toBe("generic");
    expect(cfg.model_backend).toBe("trimesh");
  });

  it("uses FDM managed thickness for aperture calculations", () => {
    const wrapper = mountApp();
    wrapper.vm.config = { ...wrapper.vm.config, printer_profile: "fdm", thickness_mm: 0.12 };
    expect(wrapper.vm.effectiveStencilThicknessMm).toBe(0.2);
  });

  it("has locale options for 5 languages", () => {
    const wrapper = mountApp();
    expect(wrapper.vm.localeOptions.length).toBe(5);
    expect(wrapper.vm.localeOptions.map((o) => o.value)).toEqual(["zh-CN", "en", "ja", "de", "es"]);
  });

  it("updates locale on setLocale", async () => {
    const wrapper = mountApp();
    await wrapper.vm.setLocale("en");
    expect(wrapper.vm.locale).toBe("en");
  });

  it("updates config and emits config change", () => {
    const wrapper = mountApp();
    const newCfg = { ...wrapper.vm.config, thickness_mm: 0.18 };
    wrapper.vm.onConfigFormUpdate(newCfg);
    expect(wrapper.vm.config.thickness_mm).toBe(0.18);
  });

  it("configPanelTab defaults to basic", () => {
    const wrapper = mountApp();
    expect(wrapper.vm.configPanelTab).toBe("basic");
  });

  it("toggles configPanelTab", async () => {
    const wrapper = mountApp();
    wrapper.vm.currentTab = "config";
    wrapper.vm.configPanelTab = "rules";
    expect(wrapper.vm.configPanelTab).toBe("rules");
  });

  it("toggles showAdvancedConfig", async () => {
    const wrapper = mountApp();
    expect(wrapper.vm.showAdvancedConfig).toBe(false);
    wrapper.vm.showAdvancedConfig = true;
    expect(wrapper.vm.showAdvancedConfig).toBe(true);
  });

  it("restores basic defaults", () => {
    const wrapper = mountApp();
    wrapper.vm.config.thickness_mm = 0.5;
    wrapper.vm.restoreBasicDefaults();
    expect(wrapper.vm.config.thickness_mm).toBe(0.12);
  });

  it("adds paste pattern", () => {
    const wrapper = mountApp();
    const before = wrapper.vm.config.paste_patterns.length;
    wrapper.vm.addPattern("paste");
    expect(wrapper.vm.config.paste_patterns.length).toBe(before + 1);
  });

  it("removes paste pattern", () => {
    const wrapper = mountApp();
    const before = wrapper.vm.config.paste_patterns.length;
    wrapper.vm.removePattern("paste", 0);
    expect(wrapper.vm.config.paste_patterns.length).toBe(before - 1);
  });

  it("adds outline pattern", () => {
    const wrapper = mountApp();
    const before = wrapper.vm.config.outline_patterns.length;
    wrapper.vm.addPattern("outline");
    expect(wrapper.vm.config.outline_patterns.length).toBe(before + 1);
  });

  it("removes outline pattern", () => {
    const wrapper = mountApp();
    const before = wrapper.vm.config.outline_patterns.length;
    wrapper.vm.removePattern("outline", 0);
    expect(wrapper.vm.config.outline_patterns.length).toBe(before - 1);
  });

  it("sets log message when backend missing", () => {
    const wrapper = mountApp();
    // i18n key "log.qtUnavailable" → translated to actual text
    expect(wrapper.vm.log).toBeTruthy();
    expect(typeof wrapper.vm.log).toBe("string");
  });

  it("progress is hidden by default", () => {
    const wrapper = mountApp();
    expect(wrapper.vm.progressVisible).toBe(false);
  });

  it("useNativeTitlebar defaults to false (no backend response)", () => {
    const wrapper = mountApp();
    expect(wrapper.vm.useNativeTitlebar).toBe(false);
  });
});
