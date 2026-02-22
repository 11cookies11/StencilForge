import en from "./locales/en.json";
import de from "./locales/de.json";
import es from "./locales/es.json";
import ja from "./locales/ja.json";
import zhCN from "./locales/zh-CN.json";

export const DEFAULT_LOCALE = "en";
export const SUPPORTED_LOCALES = ["zh-CN", "en", "ja", "de", "es"];

const MESSAGES = {
  "zh-CN": zhCN,
  en,
  ja,
  de,
  es,
};

export function normalizeLocale(locale) {
  if (SUPPORTED_LOCALES.includes(locale)) return locale;
  if (typeof locale === "string") {
    const lowered = locale.toLowerCase();
    if (lowered.startsWith("en")) return "en";
    if (lowered.startsWith("ja")) return "ja";
    if (lowered.startsWith("de")) return "de";
    if (lowered.startsWith("es")) return "es";
  }
  return "zh-CN";
}

export function getInitialLocale() {
  try {
    const saved = localStorage.getItem("stencilforge-locale");
    if (SUPPORTED_LOCALES.includes(saved)) return saved;
  } catch (error) {
    void error;
  }
  if (typeof navigator !== "undefined") {
    const lang = navigator.language || "";
    return normalizeLocale(lang);
  }
  return DEFAULT_LOCALE;
}

export function t(locale, key, vars = {}) {
  const normalized = normalizeLocale(locale);
  const table = MESSAGES[normalized] || MESSAGES[DEFAULT_LOCALE] || {};
  const fallback = MESSAGES[DEFAULT_LOCALE] || {};
  let message = table[key] || fallback[key] || key;
  Object.keys(vars).forEach((name) => {
    message = message.replaceAll(`{${name}}`, vars[name]);
  });
  return message;
}
