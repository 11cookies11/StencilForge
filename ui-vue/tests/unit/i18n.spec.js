import { afterEach, describe, expect, it, vi } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getInitialLocale, normalizeLocale, t } from "../../src/i18n/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(__dirname, "../../src");

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
    expect(t("ja", "upload.title")).toBe("PCB \u30d5\u30a1\u30a4\u30eb\u3092\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9");
    expect(t("de", "upload.title")).toBe("PCB-Dateien hochladen");
    expect(t("es", "upload.title")).toBe("Subir archivos PCB");
  });

  it("supports placeholder replacement", () => {
    expect(t("en", "log.done", { value: "out.stl" })).toBe("Done: out.stl");
    expect(t("zh-CN", "log.done", { value: "out.stl" })).toBe("\u5b8c\u6210: out.stl");
  });

  it("falls back to default locale keys and finally key name", () => {
    expect(t("fr", "upload.title")).toBe("\u4e0a\u4f20 PCB \u6587\u4ef6");
    expect(t("en", "missing.key.example")).toBe("missing.key.example");
  });

  it("keeps Japanese UI copy localized beyond the top-level page", () => {
    expect(t("ja", "config.apertureStudioTitle")).toBe("\u958b\u53e3\u30eb\u30fc\u30eb\u3068\u30cf\u30f3\u30c0\u91cf");
    expect(t("ja", "progress.cancel")).toBe("\u30ad\u30e3\u30f3\u30bb\u30eb");
  });

  it("keeps German and Spanish UI copy localized beyond the top-level page", () => {
    expect(t("de", "config.apertureStudioTitle")).toBe("Aperturregeln und Lotvolumen");
    expect(t("de", "progress.cancel")).toBe("Abbrechen");
    expect(t("es", "config.apertureStudioTitle")).toBe("Reglas de abertura y volumen de soldadura");
    expect(t("es", "progress.cancel")).toBe("Cancelar");
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

describe("frontend i18n coverage", () => {
  it("keeps Vue templates free of static user-facing copy", () => {
    const files = [
      "App.vue",
      "components/AppHeader.vue",
      "components/AppSelect.vue",
      "components/BasicConfigForm.vue",
      "components/ApertureRuleWorkspace.vue",
      "components/HelpTooltip.vue",
    ];
    const textNodePattern = />\s*([^<>{}\n][^<>{}]*)\s*</g;
    const staticAttrPattern = /(?<![:\w-])(?:aria-label|title|placeholder)="([^"]*[A-Za-z\u4e00-\u9fff\u3040-\u30ff][^"]*)"/g;
    const offenders = [];

    for (const file of files) {
      const source = fs.readFileSync(path.join(srcDir, file), "utf8");
      const template = source.match(/<template>([\s\S]*?)<\/template>/)?.[1] || "";
      for (const match of template.matchAll(textNodePattern)) {
        const value = match[1].replace(/\s+/g, " ").trim();
        if (value && /[A-Za-z\u4e00-\u9fff\u3040-\u30ff]/.test(value)) {
          offenders.push(`${file}: text "${value}"`);
        }
      }
      for (const match of template.matchAll(staticAttrPattern)) {
        offenders.push(`${file}: static attr "${match[1]}"`);
      }
    }

    expect(offenders).toEqual([]);
  });
});
