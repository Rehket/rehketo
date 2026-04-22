// Runs in the `dom` vitest project (jsdom) — DOMPurify needs `window`.

import { describe, expect, test } from 'vitest';

import { renderMarkdown } from './markdown';

describe('renderMarkdown', () => {
	test('strips <script> tags', () => {
		const html = renderMarkdown('Hello\n\n<script>alert(1)</script>');
		expect(html).not.toContain('<script');
		expect(html).not.toContain('alert(1)');
	});

	test('strips inline event handlers on attributes', () => {
		const html = renderMarkdown('<img src="x" onerror="alert(1)">');
		expect(html.toLowerCase()).not.toContain('onerror');
	});

	test('strips javascript: URLs from anchors', () => {
		const html = renderMarkdown('[click](javascript:alert(1))');
		expect(html.toLowerCase()).not.toContain('javascript:');
	});

	test('adds rel=noopener noreferrer and target=_blank to anchors', () => {
		const html = renderMarkdown('[link](https://example.com)');
		expect(html).toContain('rel="noopener noreferrer"');
		expect(html).toContain('target="_blank"');
	});

	test('renders fenced code with hljs classes for allowed languages', () => {
		const html = renderMarkdown('```ts\nconst x = 1;\n```');
		expect(html).toContain('hljs-');
	});

	test('unknown fenced language renders as plain code (no crash, no hljs-)', () => {
		const html = renderMarkdown('```klingon\nHab SoSlI quch\n```');
		expect(html).toContain('<code');
		expect(html).not.toContain('hljs-');
	});

	test('basic markdown (bold, lists, headings) survives sanitization', () => {
		const html = renderMarkdown('# h\n\n- a\n- b\n\n**bold**');
		expect(html).toContain('<h1');
		expect(html).toContain('<ul');
		expect(html).toContain('<strong');
	});

	test('plain text passes through as a paragraph', () => {
		const html = renderMarkdown('just text');
		expect(html).toContain('just text');
		expect(html).toContain('<p');
	});
});
