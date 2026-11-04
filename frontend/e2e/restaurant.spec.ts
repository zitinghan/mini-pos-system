import { test, expect } from '@playwright/test';

test('first order, incremental kitchen ticket, cash payment and history', async ({ page }, info) => {
  await page.goto('/');
  const setup = await page.request.get('/api/auth/setup-status');
  const required = (await setup.json()).setup_required;
  await page.getByLabel('员工名称').fill('browser-owner');
  await page.getByLabel(required ? '设置 6–12 位数字 PIN' : 'PIN 码').fill('928461');
  if (required) await page.getByLabel('服务器设置令牌').fill('isolated-browser-test-setup-token');
  await page.getByRole('button', { name: required ? '创建管理员并登录' : '登录', exact: true }).click();
  await expect(page.getByRole('heading', { name: '选择桌台' })).toBeVisible();

  const tableName = { 'android-360': 'T05', 'android-390': 'T06', 'android-412': 'T07' }[info.project.name]!;
  await page.getByRole('button', { name: new RegExp(tableName) }).click();
  await page.getByRole('button', { name: /云吞面/ }).click();
  await page.getByRole('button', { name: '辣', exact: true }).click();
  await page.getByRole('button', { name: /加面/ }).click();
  await page.getByRole('button', { name: '增加数量' }).click();
  await page.getByRole('button', { name: '加入草稿 · RM 20.00' }).click();
  const firstResponse = page.waitForResponse(response => response.url().endsWith('/submit') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '确认下单 / 送厨房' }).click();
  const first = await (await firstResponse).json();
  await expect(page.getByRole('heading', { name: '选择桌台' })).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp(tableName) })).toContainText('RM 20.00');

  await page.getByRole('button', { name: new RegExp(tableName) }).click();
  await page.getByRole('button', { name: /面粉糕/ }).click();
  await page.getByRole('button', { name: /^加蛋/ }).click();
  await page.getByRole('button', { name: '加入草稿 · RM 9.00' }).click();
  const secondResponse = page.waitForResponse(response => response.url().endsWith('/submit') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '确认下单 / 送厨房' }).click();
  const second = await (await secondResponse).json();
  await expect(page.getByRole('heading', { name: '选择桌台' })).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp(tableName) })).toContainText('RM 29.00');

  await page.getByRole('link', { name: /订单/ }).click();
  const secondJob = page.locator('section').filter({ hasText: `任务 #${second.print_job_id}` });
  await expect(secondJob).toContainText('已发送至打印机');
  await secondJob.getByRole('button', { name: '查看厨房单' }).click();
  await expect(page.getByRole('img', { name: '厨房订单，无价格' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('kitchen-preview.png'), fullPage: true });
  await page.getByRole('button', { name: '关闭预览' }).click();

  // Read authoritative batch content too: the second job must refer only to the added batch.
  expect(second.batch_id).not.toBe(first.batch_id);
  await page.getByRole('link', { name: /桌台/ }).click();
  await page.getByRole('button', { name: new RegExp(tableName) }).click();
  await page.getByRole('button', { name: '查看账单 / 收款' }).click();
  await page.getByLabel('收到现金 (RM)').fill('50.00');
  await expect(page.getByText('RM 21.00', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('checkout.png'), fullPage: true });
  await page.getByRole('button', { name: '确认收款并清台' }).click();
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('heading', { name: '选择桌台' })).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp(tableName) })).toContainText('空桌');
  await page.getByRole('link', { name: /营业记录/ }).click();
  await expect(page.getByText('RM 29.00', { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
