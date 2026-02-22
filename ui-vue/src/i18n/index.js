import en from "./locales/en.json";
import zhCN from "./locales/zh-CN.json";

export const DEFAULT_LOCALE = "en";
export const SUPPORTED_LOCALES = ["zh-CN", "en"];

const MESSAGES = {
  "zh-CN": zhCN,
  en,
};

export function normalizeLocale(locale) {
  if (locale === "zh-CN" || locale === "en") return locale;
  if (typeof locale === "string" && locale.toLowerCase().startsWith("en")) return "en";
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
    if (lang.toLowerCase().startsWith("en")) return "en";
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
