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

const accountNavEl = document.getElementById("account-nav");
const appEl = document.getElementById("app");

function initials(user) {
  const source = user.name || user.email || "?";
  const parts = source.trim().split(/\s+/);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}

function renderAccountNav() {
  const user = getCurrentUser();
  if (user) {
    mount(
      accountNavEl,
      el(
        "span",
        { class: "user-name" },
        el("span", { class: "avatar" }, initials(user)),
        user.name || user.email
      ),
      el("a", { href: "#/profile" }, "Profile"),
      el(
        "button",
        {
          type: "button",
          class: "ghost",
          onClick: async () => {
            await logOut();
            setCurrentUser(null);
            navigate("/");
          },
        },
        "Sign out"
      )
    );
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

// Registered before initSession() runs, so its internal notify() call
// already covers the first render -- no separate initial call needed.
onSessionChange(renderAccountNav);

(async () => {
  await initSession();
  initRouter(appEl, { notFound: renderNotFound });
})();
