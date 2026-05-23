<script lang="ts">
	import { page } from '$app/state';

	// Map the auth_error code the backend puts in ?auth_error=<code> to
	// user-facing copy. Keep in sync with rehketo-api spec §6 vocabulary.
	const authErrorCopy: Record<string, string> = {
		invalid_grant: 'Sign-in expired. Please try again.',
		invalid_client: 'Backend is misconfigured (client credentials rejected). Contact the admin.',
		invalid_request: 'Sign-in request was malformed. Please try again.',
		unauthorized_client: "This app isn't authorized to sign in. Contact the admin.",
		unsupported_grant_type: 'Backend is misconfigured. Contact the admin.',
		consent_required:
			'Additional consent is needed. Contact the admin to approve the app for your account.',
		interaction_required: 'Please sign in again.',
		token_exchange_failed: "We couldn't complete sign-in. Please try again."
	};

	let authError = $derived(page.url.searchParams.get('auth_error'));
	let errorMessage = $derived.by(() => {
		if (!authError) return null;
		const copy = authErrorCopy[authError];
		if (!copy) {
			console.warn('unknown auth_error code:', authError);
			return 'Sign-in failed — please try again.';
		}
		return copy;
	});

	let next = $derived(page.url.searchParams.get('next'));
	let signInHref = $derived(`/auth/login${next ? `?next=${encodeURIComponent(next)}` : ''}`);
</script>

<section class="flex min-h-screen items-center justify-center bg-bg px-6">
	<div
		class="w-full max-w-sm rounded-lg border border-border bg-surface p-8 shadow-lg shadow-black/20"
	>
		<h1 class="mb-1 text-xl font-semibold text-text">Rehketo</h1>
		<p class="mb-6 text-sm text-muted">Sign in with your work account to continue.</p>

		{#if errorMessage}
			<div
				class="mb-4 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
				role="alert"
			>
				{errorMessage}
			</div>
		{/if}

		<a
			href={signInHref}
			class="block w-full rounded-md bg-accent px-4 py-2 text-center text-sm font-medium text-white transition-colors hover:bg-accent-hover"
		>
			Sign in with Entra
		</a>
	</div>
</section>
