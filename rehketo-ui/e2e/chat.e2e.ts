// Canonical happy path: login (devonly) → create chat → send message →
// see the streamed reply assembled in the UI's assistant bubble (NOT in
// the sidebar conversation list — they both show "Hello world!" once a
// title is generated, so scope the assertion to the bubble).

import { test, expect, assistantBubble, setBifrostProfile } from './fixtures/auth';

test('login + send message + see streamed reply', async ({ page, loggedInRequest }) => {
	await setBifrostProfile(loggedInRequest, 'default'); // 3 chunks: "Hello ", "world", "!"

	await page.goto('/');
	await expect(page.getByRole('button', { name: /new chat/i })).toBeVisible();

	await page.getByRole('button', { name: /new chat/i }).click();
	await expect(page).toHaveURL(/\/c\//);

	const composer = page.getByPlaceholder('Message Rehketo…');
	await composer.fill('hi');
	await page.getByRole('button', { name: 'Send' }).click();

	// Scope to the assistant bubble — "Hello world!" can also appear in the
	// sidebar as the conversation title once title-gen runs.
	await expect(assistantBubble(page).getByText('Hello world!')).toBeVisible();
});
