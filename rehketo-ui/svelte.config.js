import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// SPA fallback to index.html — SvelteKit does client-side routing
		// for any path the server doesn't have a real file for. Must match
		// the backend's UI_STATIC_DIR SPA fallback behavior.
		adapter: adapter({ fallback: 'index.html' })
	}
};

export default config;
