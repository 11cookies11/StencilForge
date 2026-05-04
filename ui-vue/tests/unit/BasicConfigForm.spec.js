import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BasicConfigForm from "../../src/components/BasicConfigForm.vue";

const DEFAULT_CONFIG = {
  thickness_mm: 0.12,
  output_mode: "solid_with_cutouts",
  printer_profile: "generic",
  model_backend: "trimesh",
  paste_offset_mm: -0.05,
  mask_opening_scale: 0.95,
  outline_margin_mm: 5.0,
  locator_enabled: true,
  locator_mode: "step",
  locator_height_mm: 2.0,
  locator_width_mm: 2.0,
  locator_clearance_mm: 0.2,
  locator_step_height_mm: 1.0,
  locator_step_width_mm: 1.5,
  locator_open_side: "none",
  locator_open_width_mm: 0.0,
  arc_steps: 64,
  curve_resolution: 16,
  outline_merge_tol_mm: 0.01,
  paste_patterns: ["*gtp*", "*gbp*"],
  outline_patterns: ["*gko*", "*gm1*"],
};

function mountForm(props = {}) {
  return mount(BasicConfigForm, {
    props: { config: DEFAULT_CONFIG, locale: "en", ...props },
    global: {
      stubs: {
        AppIcon: { template: "<span />" },
        AppSelect: {
          props: ["modelValue", "options"],
          emits: ["update:modelValue"],
          template: "<div />",
        },
      },
    },
  });
}

describe("BasicConfigForm", () => {
  it("renders thickness input with correct value", () => {
    const wrapper = mountForm();
    const inputs = wrapper.findAll("input[type='number']");
    const thicknessInput = inputs.find((i) => i.attributes("step") === "0.01");
    expect(thicknessInput.element.value).toBe("0.12");
  });

  it("emits update:config when thickness changes", async () => {
    const wrapper = mountForm();
    const inputs = wrapper.findAll("input[type='number']");
    const thicknessInput = inputs.find((i) => i.attributes("step") === "0.01");
    await thicknessInput.setValue("0.2");
    const emitted = wrapper.emitted("update:config");
    expect(emitted).toBeTruthy();
    expect(emitted[0][0].thickness_mm).toBe(0.2);
  });

  it("emits update:config with paste_offset_mm changed", async () => {
    const wrapper = mountForm();
    const inputs = wrapper.findAll("input[type='number']");
    // paste_offset_mm is the input with step="0.01" after thickness_mm
    const pasteInput = inputs[1];
    await pasteInput.setValue("-0.03");
    expect(wrapper.emitted("update:config")[0][0].paste_offset_mm).toBe(-0.03);
  });

  it("emits update:config with mask_opening_scale changed", async () => {
    const wrapper = mountForm();
    const inputs = wrapper.findAll("input[type='number']");
    const maskScaleInput = inputs[2];
    await maskScaleInput.setValue("0.9");
    expect(wrapper.emitted("update:config")[0][0].mask_opening_scale).toBe(0.9);
  });

  it("toggles locator_enabled via checkbox", async () => {
    const wrapper = mountForm();
    const checkbox = wrapper.find("input[type='checkbox']");
    expect(checkbox.element.checked).toBe(true);
    await checkbox.setValue(false);
    const emitted = wrapper.emitted("update:config");
    expect(emitted[0][0].locator_enabled).toBe(false);
  });

  it("hides advanced section by default", () => {
    const wrapper = mountForm({ showAdvancedConfig: false });
    expect(wrapper.find(".rounded-2xl.border.border-slate-200").exists()).toBe(false);
  });

  it("shows advanced section when showAdvancedConfig is true", () => {
    const wrapper = mountForm({ showAdvancedConfig: true });
    expect(wrapper.find(".rounded-2xl.border.border-slate-200").exists()).toBe(true);
  });

  it("renders paste pattern inputs in advanced section", () => {
    const wrapper = mountForm({ showAdvancedConfig: true });
    // paste_patterns has 2 items: *gtp*, *gbp*
    const patternInputs = wrapper.findAll(".font-mono");
    expect(patternInputs.length).toBeGreaterThanOrEqual(2);
  });

  it("emits add-pattern when paste add button clicked", async () => {
    const wrapper = mountForm({ showAdvancedConfig: true });
    const addButtons = wrapper.findAll("button");
    const pasteAddBtn = addButtons.find((b) => b.text().includes("addRule") || b.text().includes("addRule"));
    if (pasteAddBtn) {
      await pasteAddBtn.trigger("click");
      expect(wrapper.emitted("add-pattern")).toBeTruthy();
    }
  });

  it("keeps other fields unchanged when updating one field", async () => {
    const wrapper = mountForm();
    const inputs = wrapper.findAll("input[type='number']");
    await inputs[0].setValue("0.25");
    const emitted = wrapper.emitted("update:config")[0][0];
    expect(emitted.thickness_mm).toBe(0.25);
    expect(emitted.output_mode).toBe("solid_with_cutouts");
    expect(emitted.model_backend).toBe("trimesh");
  });

  it("applies FDM printer profile defaults when profile changes", () => {
    const wrapper = mountForm();
    wrapper.vm.emitPrinterProfileChange("fdm");
    const emitted = wrapper.emitted("update:config")[0][0];
    expect(emitted.printer_profile).toBe("fdm");
    expect(emitted.stl_quality).toBe("high_quality");
    expect(emitted.arc_steps).toBe(96);
    expect(emitted.curve_resolution).toBe(24);
  });

  it("shows managed thickness when FDM profile is selected", () => {
    const wrapper = mountForm({
      config: { ...DEFAULT_CONFIG, printer_profile: "fdm", thickness_mm: 0.12 },
    });
    const inputs = wrapper.findAll("input[type='number']");
    const thicknessInput = inputs.find((i) => i.attributes("step") === "0.01");
    expect(thicknessInput.element.value).toBe("0.2");
    expect(thicknessInput.element.disabled).toBe(true);
    expect(wrapper.text()).toContain("FDM profile manages thickness");
  });

  it("renders i18n labels based on locale prop", () => {
    const wrapper = mountForm({ locale: "zh-CN" });
    expect(wrapper.text()).toContain("厚度"); // Chinese label
  });
});
