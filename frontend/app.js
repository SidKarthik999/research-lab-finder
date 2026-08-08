// Bootstrap: wires session state, the header's account nav, and the
// router together. initSession() must resolve before the router mounts
// anything, so every view's getCurrentUser() call is synchronous and
// correct on first render -- see session.js.

import { el, mount } from "./dom.js";
import { logOut } from "./api.js";
import { getCurrentUser, initSession, onSessionChange, setCurrentUser } from "./session.js";
import { initRouter, navigate, registerRoute } from "./router.js";
import { renderSearchView } from "./views/search.js";
import { renderProfessorDetailView } from "./views/professorDetail.js";
import {
  renderForgotPasswordView,
  renderResetPasswordView,
  renderSignInView,
  renderSignUpView,
  renderVerifyEmailView,
} from "./views/auth.js";
import { renderProfileView } from "./views/profile.js";
import { renderBookmarksView } from "./views/bookmarks.js";

const accountNavEl = document.getElementById("account-nav");
const appEl = document.getElementById("app");

function initials(user) {
  const source = user.name || user.email || "?";
  const parts = source.trim().split(/\s+/);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}

// Closes any open account dropdown on a click outside it -- registered once
// at module load (not inside renderAccountNav, which reruns on every
// session change) so repeated sign-in/out cycles don't stack up duplicate
// document-level listeners.
document.addEventListener("click", (event) => {
  const menu = accountNavEl.querySelector(".account-menu");
  if (!menu || menu.hidden) return;
  if (!accountNavEl.contains(event.target)) {
    menu.hidden = true;
    accountNavEl.querySelector(".account-trigger")?.setAttribute("aria-expanded", "false");
  }
});

function renderAccountNav() {
  const user = getCurrentUser();
  if (user) {
    const menu = el(
      "div",
      { class: "account-menu", hidden: true },
      el("a", { href: "#/profile" }, "Profile"),
      el("a", { href: "#/bookmarks" }, "Bookmarks"),
      el(
        "button",
        {
          type: "button",
          onClick: async () => {
            await logOut();
            setCurrentUser(null);
            navigate("/");
          },
        },
        "Sign out"
      )
    );
    // Closes the menu on any click inside it too (a link nav or the sign-out
    // button), not just the outside-click handler above -- otherwise it's
    // left open in the DOM after navigating away, since nothing else
    // re-renders account-nav on a route change (only on session change).
    menu.addEventListener("click", () => {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    });

    const trigger = el(
      "button",
      { type: "button", class: "account-trigger", "aria-expanded": "false" },
      el("span", { class: "avatar" }, initials(user)),
      user.name || user.email
    );
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const opening = menu.hidden;
      menu.hidden = !opening;
      trigger.setAttribute("aria-expanded", String(opening));
    });

    mount(accountNavEl, el("div", { class: "account-dropdown" }, trigger, menu));
  } else {
    mount(accountNavEl, el("a", { href: "#/signin" }, "Sign in"), el("a", { href: "#/signup" }, "Sign up"));
  }
}

function renderNotFound(container) {
  mount(container, el("h1", {}, "Page not found"), el("a", { href: "#/", class: "back-link" }, "← Back to search"));
}

registerRoute("/", renderSearchView);
registerRoute("/professor/:id", renderProfessorDetailView);
registerRoute("/signin", renderSignInView);
registerRoute("/signup", renderSignUpView);
registerRoute("/forgot-password", renderForgotPasswordView);
registerRoute("/reset-password", renderResetPasswordView);
registerRoute("/verify-email", renderVerifyEmailView);
registerRoute("/profile", renderProfileView);
registerRoute("/bookmarks", renderBookmarksView);

// Registered before initSession() runs, so its internal notify() call
// already covers the first render -- no separate initial call needed.
onSessionChange(renderAccountNav);

(async () => {
  await initSession();
  initRouter(appEl, { notFound: renderNotFound });
})();
