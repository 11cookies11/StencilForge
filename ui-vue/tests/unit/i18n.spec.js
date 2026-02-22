import { afterEach, describe, expect, it, vi } from "vitest";

import { getInitialLocale, normalizeLocale, t } from "../../src/i18n/index.js";

describe("i18n normalizeLocale", () => {
  it("normalizes supported locale aliases", () => {
    expect(normalizeLocale("en-US")).toBe("en");
    expect(normalizeLocale("ja-JP")).toBe("ja");
    expect(normalizeLocale("de-DE")).toBe("de");
    expect(normalizeLocale("es-ES")).toBe("es");
    expect(normalizeLocale("zh-Hans-CN")).toBe("zh-CN");
  });

  it("falls back to zh-CN for unknown locales", () => {
    expect(normalizeLocale("fr-FR")).toBe("zh-CN");
    expect(normalizeLocale("")).toBe("zh-CN");
    expect(normalizeLocale(null)).toBe("zh-CN");
  });
});

describe("i18n t()", () => {
  it("returns localized strings", () => {
    expect(t("en", "upload.title")).toBe("Upload PCB files");
    expect(t("ja", "upload.title")).toBe("PCB ファイルをアップロード");
    expect(t("de", "upload.title")).toBe("PCB-Dateien hochladen");
    expect(t("es", "upload.title")).toBe("Subir archivos PCB");
  });

  it("supports placeholder replacement", () => {
    expect(t("en", "log.done", { value: "out.stl" })).toBe("Done: out.stl");
    expect(t("zh-CN", "log.done", { value: "out.stl" })).toBe("完成: out.stl");
  });

  it("falls back to default locale keys and finally key name", () => {
    expect(t("fr", "upload.title")).toBe("上传 PCB 文件");
    expect(t("en", "missing.key.example")).toBe("missing.key.example");
  });
});

describe("getInitialLocale", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prefers stored locale", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => "de",
    });
    vi.stubGlobal("navigator", { language: "ja-JP" });
    expect(getInitialLocale()).toBe("de");
  });
});
