// Hash-based routing (#/professor/123, #/signin, ...). Deliberately not
// history-API routing: the hash never leaves the browser, so
// StaticFiles(html=True) only ever needs to serve index.html for "/" --
// no server-side catch-all route is needed for a page refresh or a direct
// link to work. This is also why the verification/reset-password email
// links in backend/auth.py point at /#/verify-email?token=... rather than
// a bare server path -- see CLAUDE.md Phase 5A.
//
// A route's view function has the signature
// (container, params, query) => cleanup?. The optional returned cleanup
// function runs before the next route renders (e.g. to unsubscribe from
// session.onSessionChange).

const routes = [];

export function registerRoute(pattern, view) {
  const paramNames = [];
  const regexStr = pattern
    .split("/")
    .map((segment) => {
      if (segment.startsWith(":")) {
        paramNames.push(segment.slice(1));
        return "([^/]+)";
      }
      return segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    })
    .join("/");
  routes.push({ regex: new RegExp(`^${regexStr}$`), paramNames, view });
}

function parseHash() {
  let hash = window.location.hash.slice(1);
  if (!hash.startsWith("/")) hash = `/${hash}`;
  const [path, queryString] = hash.split("?");
  const query = Object.fromEntries(new URLSearchParams(queryString || ""));
  return { path: path || "/", query };
}

function matchRoute(path) {
  for (const route of routes) {
    const match = path.match(route.regex);
    if (match) {
      const params = {};
      route.paramNames.forEach((name, i) => {
        params[name] = match[i + 1];
      });
      return { view: route.view, params };
    }
  }
  return null;
}

let container = null;
let notFoundView = null;
let currentCleanup = null;

async function render() {
  if (typeof currentCleanup === "function") {
    currentCleanup();
  }
  currentCleanup = null;

  const { path, query } = parseHash();
  const matched = matchRoute(path);

  // A fresh child node per navigation, not the shared #app element itself.
  // A view with an in-flight fetch (e.g. the professor detail page) that
  // the user navigates away from before it resolves will still call
  // mount() on what it was given -- but by then this node has been
  // detached from the document, so the stale write lands somewhere
  // invisible instead of clobbering whatever's now on screen.
  const viewContainer = document.createElement("div");
  container.replaceChildren(viewContainer);

  if (!matched) {
    if (notFoundView) currentCleanup = await notFoundView(viewContainer, {}, query);
    return;
  }
  currentCleanup = await matched.view(viewContainer, matched.params, query);
}

export function initRouter(mountEl, { notFound } = {}) {
  container = mountEl;
  notFoundView = notFound;
  window.addEventListener("hashchange", render);
  render();
}

export function navigate(path) {
  window.location.hash = path.startsWith("/") ? path : `/${path}`;
}
