import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import AppSelect from "../../src/components/AppSelect.vue";

const SAMPLE_OPTIONS = [
  { value: "a", label: "Option A" },
  { value: "b", label: "Option B" },
  { value: "c", label: "Option C" },
];

function mountSelect(props = {}) {
  return mount(AppSelect, {
    props: { options: SAMPLE_OPTIONS, ...props },
    global: {
      stubs: {
        AppIcon: { template: "<span />" },
      },
    },
    attachTo: document.body,
  });
}

// Helper: find dropdown option buttons only (not the trigger)
function dropdownOptions(wrapper) {
  return wrapper.findAll("button").filter((btn) => {
    const text = btn.text();
    return ["Option A", "Option B", "Option C"].some((o) => text.includes(o));
  });
}

describe("AppSelect", () => {
  it("renders placeholder when no value selected", () => {
    const wrapper = mountSelect({ placeholder: "Choose..." });
    expect(wrapper.text()).toContain("Choose...");
  });

  it("renders selected option label", () => {
    const wrapper = mountSelect({ modelValue: "b" });
    expect(wrapper.text()).toContain("Option B");
  });

  it("shows dropdown on button click", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    expect(dropdownOptions(wrapper).length).toBe(3);
  });

  it("hides dropdown by default", () => {
    const wrapper = mountSelect();
    expect(dropdownOptions(wrapper).length).toBe(0);
  });

  it("emits update:modelValue when option selected", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    const opts = dropdownOptions(wrapper);
    await opts[2].trigger("click"); // pick "c"
    expect(wrapper.emitted("update:modelValue")).toBeTruthy();
    expect(wrapper.emitted("update:modelValue")[0]).toEqual(["c"]);
  });

  it("emits change alongside update:modelValue", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    const opts = dropdownOptions(wrapper);
    await opts[0].trigger("click");
    expect(wrapper.emitted("change")).toBeTruthy();
    expect(wrapper.emitted("change")[0]).toEqual(["a"]);
    expect(wrapper.emitted("update:modelValue")).toBeTruthy();
  });

  it("closes dropdown after selection", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    const opts = dropdownOptions(wrapper);
    await opts[0].trigger("click");
    expect(dropdownOptions(wrapper).length).toBe(0);
  });

  it("highlights selected option", async () => {
    const wrapper = mountSelect({ modelValue: "a" });
    await wrapper.find("button").trigger("click");
    const active = wrapper.find(".bg-blue-50");
    expect(active.exists()).toBe(true);
  });

  it("does not open when disabled", async () => {
    const wrapper = mountSelect({ disabled: true });
    await wrapper.find("button").trigger("click");
    expect(dropdownOptions(wrapper).length).toBe(0);
  });

  it("closes on Escape key", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    expect(wrapper.vm.open).toBe(true);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.open).toBe(false);
  });

  it("closes on outside click", async () => {
    const wrapper = mountSelect();
    await wrapper.find("button").trigger("click");
    expect(wrapper.vm.open).toBe(true);
    // Click on body (outside the component)
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.open).toBe(false);
  });
});
