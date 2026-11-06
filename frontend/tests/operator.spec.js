import { test, expect } from '@playwright/test';

test('live panel, confirmed setpoint, archive and mobile layout', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled();
  await expect(page.getByTestId('Boiler_Temp_01')).not.toHaveText('—°C');
  await page.getByLabel('Новая уставка').fill('82.5');
  await page.getByRole('button', { name: 'Применить', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Уставка применена.', { timeout: 10000 });
  await page.getByLabel('Показатель').selectOption('Temp_Setpoint_01');
  await expect(page.locator('tbody')).toContainText('82,5');
  await page.screenshot({ path: 'test-results/operator-panel.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: 'Температурная уставка' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('server disconnect hides stale values and reconnects automatically', async ({ page, context }) => {
  let connection;
  await page.routeWebSocket('**/ws/tags', route => {
    connection = route;
    route.connectToServer();
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled();
  const other = await context.newPage();
  await other.goto('/');
  await expect(other.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled();
  connection.close();
  await expect(page.getByRole('alert')).toHaveText('Нет связи с сервером.');
  await expect(page.getByTestId('Boiler_Temp_01')).toHaveText('—°C');
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeDisabled();
  await expect(other.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled({ timeout: 8000 });
  await expect(page.getByRole('alert')).toHaveCount(0);
  await other.close();
});

test('PLC loss keeps server connected, disables control and recovers', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled();
  try {
    expect((await page.request.post('/__test/plc/stop')).ok()).toBe(true);
    await expect(page.getByRole('alert')).toHaveText('Показания контроллера недоступны.');
    await expect(page.getByTestId('Boiler_Temp_01')).toHaveText('—°C');
    await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeDisabled();
  } finally {
    await page.request.post('/__test/plc/start');
  }
  await expect(page.getByRole('button', { name: 'Применить', exact: true })).toBeEnabled({ timeout: 10000 });
  await expect(page.getByRole('alert')).toHaveCount(0);
});
