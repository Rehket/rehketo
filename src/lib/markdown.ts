// Assistant markdown renderer.
//
// Pipeline: marked → highlight.js (for fenced code) → DOMPurify.
//
// Sanitization is MANDATORY — model output is untrusted. DOMPurify strips
// script tags, inline event handlers, javascript: URLs, and other
// injection vectors. Links get rel="noopener noreferrer" + target="_blank"
// via an afterSanitize hook.
//
// User messages MUST NOT flow through this (spec §5.5) — render them as
// plain text so user input can't be interpreted as structure.

import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/common';
import { Marked } from 'marked';

const ALLOWED_LANGS: ReadonlySet<string> = new Set([
	'ts',
	'typescript',
	'js',
	'javascript',
	'py',
	'python',
	'bash',
	'sh',
	'shell',
	'json',
	'yaml',
	'yml',
	'sql',
	'md',
	'markdown'
]);

const marked = new Marked({
	gfm: true,
	breaks: false,
	async: false
});

marked.use({
	walkTokens(token) {
		if (token.type === 'code') {
			const lang = (token.lang ?? '').trim().toLowerCase();
			if (lang && ALLOWED_LANGS.has(lang) && hljs.getLanguage(lang)) {
				try {
					token.text = hljs.highlight(token.text, { language: lang, ignoreIllegals: true }).value;
					(token as unknown as { escaped: boolean }).escaped = true;
				} catch {
					// fall through — renders the raw text
				}
			}
		}
	}
});

// Rewrite anchors to open safely in a new tab. Runs after DOMPurify's
// sanitize pass so we know the tags have already been vetted.
function installAnchorHook(): void {
	DOMPurify.removeAllHooks();
	DOMPurify.addHook('afterSanitizeAttributes', (node: Element) => {
		if (node.nodeName === 'A') {
			node.setAttribute('rel', 'noopener noreferrer');
			node.setAttribute('target', '_blank');
		}
	});
}

installAnchorHook();

export function renderMarkdown(text: string): string {
	const raw = marked.parse(text) as string;
	return DOMPurify.sanitize(raw, {
		ADD_ATTR: ['target', 'rel']
	});
}
