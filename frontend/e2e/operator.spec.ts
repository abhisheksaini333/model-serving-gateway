import { test, expect } from "@playwright/test";
const operator = process.env.GATEWAY_OPERATOR_KEY!;
const tenant = JSON.parse(process.env.GATEWAY_TENANTS_JSON || "{}").alpha
  ?.api_key;
test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Operator credential", { exact: true }).fill(operator);
  await page.getByRole("button", { name: "Connect to gateway" }).click();
  await expect(page.getByText("cpu-a", { exact: true })).toBeVisible();
});
test("operator drains and restores the real model, then runs a streaming probe", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Drain cpu-a" }).click();
  await page.getByRole("button", { name: "Confirm drain" }).click();
  await expect(
    page.getByRole("button", { name: "Enable cpu-a" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Enable cpu-a" }).click();
  await page.getByRole("button", { name: "Confirm enable" }).click();
  await expect(page.getByRole("button", { name: "Drain cpu-a" })).toBeVisible();
  await page.getByLabel("Tenant credential for probe").fill(tenant);
  await page.getByRole("button", { name: "Run streaming probe" }).click();
  await expect(page.getByText(/Complete · \d+ tokens/)).toBeVisible();
  await expect(page.locator(".probe-output")).not.toBeEmpty();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.screenshot({
    path: process.env.GATEWAY_SCREENSHOT || "/tmp/serving-gateway-console.png",
    fullPage: true,
  });
});
test("stream disconnect records actual cancellation and clears capacity", async ({
  page,
  request,
}) => {
  await page.getByLabel("Tenant credential for probe").fill(tenant);
  await page.getByRole("button", { name: "Run streaming probe" }).click();
  await expect(
    page.getByText("Generation in progress", { exact: true })
  ).toBeVisible();
  await page.getByRole("button", { name: "Disconnect stream" }).click();
  await expect(
    page.getByText(/Cancelled · \d+ generated tokens recorded/)
  ).toBeVisible();
  await expect
    .poll(async () => {
      const response = await request.get("/ops/summary", {
        headers: { Authorization: `Bearer ${operator}` },
      });
      return (await response.json()).workers;
    })
    .toBe(0);
});
test("mobile operator controls remain inside the viewport and credentials clear on reload", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Drain cpu-a" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    )
  ).toBe(true);
  await page.reload();
  await expect(
    page.getByLabel("Operator credential", { exact: true })
  ).toHaveValue("");
});
