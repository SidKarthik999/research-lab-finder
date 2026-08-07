// Current-user state, shared across the header and every view without a
// framework. app.js calls initSession() once at startup and awaits it
// before the router mounts anything, so getCurrentUser() is safe to call
// synchronously everywhere else. Auth views call setCurrentUser() directly
// with the user object each auth endpoint already returns, rather than
// re-fetching /api/me after every sign-in -- one round trip, not two.

import { getMe } from "./api.js";

let currentUser = null;
const listeners = new Set();

function notify() {
  for (const listener of listeners) listener(currentUser);
}

export async function initSession() {
  currentUser = await getMe();
  notify();
  return currentUser;
}

export function getCurrentUser() {
  return currentUser;
}

export function setCurrentUser(user) {
  currentUser = user;
  notify();
}

// Returns an unsubscribe function.
export function onSessionChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
