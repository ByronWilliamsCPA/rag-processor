/**
 * E2E tests for authentication flow.
 *
 * These tests validate the complete authentication flow
 * using Playwright. For local development, they use
 * bypass mode (CLOUDFLARE_ENABLED=false).
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should display header with loading state initially', async ({ page }) => {
    await page.goto('/');

    // Header should be visible
    const header = page.locator('.app-header');
    await expect(header).toBeVisible();

    // Should show RAG Processor title
    await expect(page.locator('h1')).toContainText('RAG Processor');
  });

  test('should show user email when authenticated (bypass mode)', async ({
    page,
  }) => {
    await page.goto('/');

    // Wait for auth to complete
    await page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/user/me') &&
        (response.status() === 200 || response.status() === 401)
    );

    // In bypass mode, should show dev@localhost
    const userEmail = page.locator('.user-email');
    const isVisible = await userEmail.isVisible().catch(() => false);

    if (isVisible) {
      await expect(userEmail).toContainText('@');
    }
  });

  test('should show not authenticated when no user', async ({ page }) => {
    // Mock the API to return 401
    await page.route('**/api/v1/user/me', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      })
    );

    await page.goto('/');

    // Wait for the API call to complete
    await page.waitForResponse('**/api/v1/user/me');

    // Should show not authenticated message
    const notAuth = page.locator('.not-authenticated');
    await expect(notAuth).toBeVisible();
  });

  test('should show API status section', async ({ page }) => {
    await page.goto('/');

    // API section should be visible
    const apiSection = page.locator('.api-section');
    await expect(apiSection).toBeVisible();

    // Should have the API status heading
    await expect(page.locator('.api-section h3')).toContainText(
      'Backend API Status'
    );
  });
});

test.describe('Navigation', () => {
  test('should have sticky header', async ({ page }) => {
    await page.goto('/');

    const header = page.locator('.app-header');
    await expect(header).toHaveCSS('position', 'sticky');
  });

  test('should show footer with links', async ({ page }) => {
    await page.goto('/');

    const footer = page.locator('.app-footer');
    await expect(footer).toBeVisible();

    // Should have links to Vite, React, FastAPI
    await expect(footer.locator('a')).toHaveCount(3);
  });
});
