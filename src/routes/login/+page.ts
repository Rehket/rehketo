// Login landing is fully static — safe to prerender so a signed-out
// user doesn't need to run JS before seeing the sign-in affordance.
export const prerender = true;
export const ssr = false;
