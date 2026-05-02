import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import HelpTooltip from "../../src/components/HelpTooltip.vue";

describe("HelpTooltip", () => {
  it("renders with required text prop", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "This is help text" } });
    expect(wrapper.text()).toContain("This is help text");
  });

  it("hides tooltip content by default", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help" } });
    const popover = wrapper.find(".pointer-events-none");
    expect(popover.isVisible()).toBe(false);
  });

  it("shows tooltip on mouseenter", async () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help" } });
    await wrapper.find("button").trigger("mouseenter");
    const popover = wrapper.find(".pointer-events-none");
    expect(popover.isVisible()).toBe(true);
  });

  it("hides tooltip on mouseleave", async () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help" } });
    const button = wrapper.find("button");
    // Enter → visible
    await button.trigger("mouseenter");
    expect(wrapper.find(".pointer-events-none").isVisible()).toBe(true);
    // Leave → hidden
    await button.trigger("mouseleave");
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.show).toBe(false);
  });

  it("applies default slate variant style", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help" } });
    expect(wrapper.find("button").attributes("class")).toContain("border-slate-200");
  });

  it("applies blue variant style", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help", variant: "blue" } });
    expect(wrapper.find("button").attributes("class")).toContain("border-blue-200");
  });

  it("renders question mark button", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Help" } });
    expect(wrapper.find("button").text()).toBe("?");
  });

  it("sets aria-label on button", () => {
    const wrapper = mount(HelpTooltip, { props: { text: "Show help" } });
    expect(wrapper.find("button").attributes("aria-label")).toBe("Show help");
  });
});
