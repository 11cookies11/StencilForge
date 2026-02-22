import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const localesDir = path.resolve(__dirname, "../src/i18n/locales");
const baseLocale = "en";

function readJson(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw);
}

function extractPlaceholders(text) {
  if (typeof text !== "string") return [];
  const matches = text.match(/\{[a-zA-Z0-9_]+\}/g) || [];
  return [...new Set(matches)].sort();
}

function listLocaleFiles(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => entry.name)
    .sort();
}

function main() {
  if (!fs.existsSync(localesDir)) {
    console.error(`[i18n] Locales directory not found: ${localesDir}`);
    process.exit(1);
  }

  const files = listLocaleFiles(localesDir);
  if (files.length === 0) {
    console.error("[i18n] No locale JSON files found.");
    process.exit(1);
  }

  const localeMaps = new Map();
  for (const file of files) {
    const locale = path.basename(file, ".json");
    const filePath = path.join(localesDir, file);
    localeMaps.set(locale, readJson(filePath));
  }

  if (!localeMaps.has(baseLocale)) {
    console.error(`[i18n] Base locale "${baseLocale}" not found.`);
    process.exit(1);
  }

  const base = localeMaps.get(baseLocale);
  const baseKeys = Object.keys(base).sort();
  let hasError = false;

  for (const [locale, messages] of localeMaps.entries()) {
    if (locale === baseLocale) continue;

    const keys = Object.keys(messages).sort();
    const missing = baseKeys.filter((key) => !Object.prototype.hasOwnProperty.call(messages, key));
    const extra = keys.filter((key) => !Object.prototype.hasOwnProperty.call(base, key));

    if (missing.length > 0 || extra.length > 0) {
      hasError = true;
      console.error(`\n[i18n] Locale "${locale}" key mismatch:`);
      if (missing.length > 0) {
        console.error(`  Missing (${missing.length}): ${missing.join(", ")}`);
      }
      if (extra.length > 0) {
        console.error(`  Extra (${extra.length}): ${extra.join(", ")}`);
      }
    }

    for (const key of baseKeys) {
      if (!Object.prototype.hasOwnProperty.call(messages, key)) continue;
      const basePlaceholders = extractPlaceholders(base[key]);
      const localePlaceholders = extractPlaceholders(messages[key]);
      if (basePlaceholders.join("|") !== localePlaceholders.join("|")) {
        hasError = true;
        console.error(`\n[i18n] Locale "${locale}" placeholder mismatch at key "${key}":`);
        console.error(`  ${baseLocale}: [${basePlaceholders.join(", ")}]`);
        console.error(`  ${locale}: [${localePlaceholders.join(", ")}]`);
      }
    }
  }

  if (hasError) {
    process.exit(1);
  }

  console.log(`[i18n] OK. Checked ${localeMaps.size} locales, ${baseKeys.length} keys.`);
}

main();
