// Tiny toast queue. Auto-dismiss after 5s unless `pinned: true`.

import { SvelteDate } from 'svelte/reactivity';

export type ToastVariant = 'error' | 'info';

export type Toast = {
	id: string;
	variant: ToastVariant;
	message: string;
};

let items = $state<Toast[]>([]);

function nextId(): string {
	return `t-${new SvelteDate().getTime()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const toasts = {
	get items(): Toast[] {
		return items;
	},
	push(toast: { variant: ToastVariant; message: string; pinned?: boolean }): string {
		const id = nextId();
		items = [...items, { id, variant: toast.variant, message: toast.message }];
		if (!toast.pinned) {
			setTimeout(() => this.dismiss(id), 5000);
		}
		return id;
	},
	dismiss(id: string): void {
		items = items.filter((t) => t.id !== id);
	}
};
