import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/unit/**/*.spec.js"],
    environment: "node",
    reporters: ["default"],
  },
});
