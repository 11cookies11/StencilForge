import { expect, test } from "@playwright/test";

test.describe("language switching", () => {
  test("switches locale among ja/de/es and updates document language", async ({ page }) => {
    await page.goto("/");

    const menuButton = page.locator(".titlebar-interactive > button").first();
    const menuItems = page.getByRole("menuitem");

    await menuButton.click();
    await menuItems.nth(2).click();
    await expect(page.getByText("PCB ファイルをアップロード")).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.lang)).toBe("ja");

    await menuButton.click();
    await menuItems.nth(3).click();
    await expect(page.getByText("PCB-Dateien hochladen")).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.lang)).toBe("de");

    await menuButton.click();
    await menuItems.nth(4).click();
    await expect(page.getByText("Subir archivos PCB")).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.lang)).toBe("es");
  });
});
