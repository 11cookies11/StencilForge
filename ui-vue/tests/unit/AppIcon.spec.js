import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import AppIcon from "../../src/components/AppIcon.vue";

describe("AppIcon", () => {
  it("renders an SVG with correct size", () => {
    const wrapper = mount(AppIcon, { props: { name: "close" } });
    const svg = wrapper.find("svg");
    expect(svg.exists()).toBe(true);
    expect(svg.attributes("width")).toBe("20");
    expect(svg.attributes("height")).toBe("20");
  });

  it("renders custom size as number", () => {
    const wrapper = mount(AppIcon, { props: { name: "close", size: 32 } });
    expect(wrapper.find("svg").attributes("width")).toBe("32");
  });

  it("renders custom size as string", () => {
    const wrapper = mount(AppIcon, { props: { name: "close", size: "1.5em" } });
    expect(wrapper.find("svg").attributes("width")).toBe("1.5em");
  });

  it("renders multiple paths for known icons", () => {
    const wrapper = mount(AppIcon, { props: { name: "language" } });
    const paths = wrapper.findAll("path");
    expect(paths.length).toBeGreaterThanOrEqual(1);
  });

  it("falls back to description icon for unknown name", () => {
    const wrapper = mount(AppIcon, { props: { name: "nonexistent" } });
    const paths = wrapper.findAll("path");
    // description has 3 paths
    expect(paths.length).toBe(3);
  });

  it("marks SVG as aria-hidden", () => {
    const wrapper = mount(AppIcon, { props: { name: "check" } });
    expect(wrapper.find("svg").attributes("aria-hidden")).toBe("true");
  });

  it("renders known icons correctly", () => {
    const knownIcons = [
      "view_in_ar", "language", "expand_more", "check", "remove",
      "crop_square", "close", "description", "add_circle", "autorenew",
      "cloud_upload", "settings", "visibility", "download",
    ];
    for (const name of knownIcons) {
      const wrapper = mount(AppIcon, { props: { name } });
      expect(wrapper.find("svg").exists()).toBe(true);
    }
  });
});
