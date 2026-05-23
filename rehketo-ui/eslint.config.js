import prettier from 'eslint-config-prettier';
import path from 'node:path';
import { includeIgnoreFile } from '@eslint/compat';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';
import svelteConfig from './svelte.config.js';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	ts.configs.recommended,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: { globals: { ...globals.browser, ...globals.node } },
		rules: {
			// typescript-eslint strongly recommend that you do not use the no-undef lint rule on TypeScript projects.
			// see: https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-there-are-no-typescript-errors
			'no-undef': 'off'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser,
				svelteConfig
			}
		}
	},
	{
		rules: {
			// The backend lives at /auth, /conversations, /runs, /me, etc.
			// These are same-origin routes (Vite proxy in dev, StaticFiles
			// mount in prod) but are NOT SvelteKit-managed — resolve()
			// only knows the UI's own route table. Turn off the rule so
			// backend hrefs and goto()s don't require ceremony.
			'svelte/no-navigation-without-resolve': 'off'
		}
	},
	{
		// Invariant: all data access goes through apiFetch (CSRF, 401/403,
		// envelope). Raw fetch is allowed ONLY in src/lib/api.ts.
		files: ['**/*.ts', '**/*.svelte', '**/*.svelte.ts'],
		rules: {
			'no-restricted-syntax': [
				'error',
				{
					selector: "CallExpression[callee.name='fetch']",
					message: 'Use apiFetch from $lib/api — raw fetch is only allowed in src/lib/api.ts.'
				},
				{
					selector: "CallExpression[callee.property.name='fetch']",
					message: 'Use apiFetch from $lib/api — raw fetch is only allowed in src/lib/api.ts.'
				}
			]
		}
	},
	{
		files: ['src/lib/api.ts'],
		rules: { 'no-restricted-syntax': 'off' }
	},
	{
		// Invariant (spec §5.5): user-authored text is NEVER markdown-rendered.
		// UserBubble renders plain text only.
		files: ['src/lib/components/UserBubble.svelte'],
		rules: {
			'no-restricted-imports': [
				'error',
				{
					patterns: [
						{
							group: ['**/MarkdownView.svelte', '**/markdown', '$lib/markdown'],
							message: 'User text must never be markdown-rendered (spec §5.5).'
						}
					]
				}
			]
		}
	}
);
