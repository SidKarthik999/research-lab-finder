// Sign in, sign up, forgot/reset password, and email verification.
// Google's Identity Services script is loaded lazily (only when a view
// that needs it renders) and the client ID comes from
// GET /api/auth/google/client-id rather than being baked into this file,
// so the button degrades to a plain "not configured yet" note instead of
// erroring when GOOGLE_CLIENT_ID isn't set -- see CLAUDE.md Phase 5A.

import { el, mount } from "../dom.js";
import {
  forgotPassword,
  getGoogleClientId,
  logIn,
  resetPassword,
  signInWithGoogle,
  signUp,
  verifyEmail,
} from "../api.js";
import { joinName } from "../name.js";
import { navigate } from "../router.js";
import { setCurrentUser } from "../session.js";

function formField(labelText, inputEl) {
  return el("div", { class: "field" }, el("label", { for: inputEl.id }, labelText), inputEl);
}

function goHome(user) {
  setCurrentUser(user);
  navigate("/");
}

let googleScriptPromise = null;

function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!googleScriptPromise) {
    googleScriptPromise = new Promise((resolve, reject) => {
      const script = el("script", {
        src: "https://accounts.google.com/gsi/client",
        async: true,
        defer: true,
      });
      script.onload = resolve;
      script.onerror = () => reject(new Error("Failed to load Google Sign-In."));
      document.head.append(script);
    });
  }
  return googleScriptPromise;
}

async function renderGoogleButton(mountEl, onSuccess, onError) {
  let clientId;
  try {
    ({ client_id: clientId } = await getGoogleClientId());
  } catch {
    mount(mountEl, el("p", { class: "hint" }, "Couldn't check Google sign-in status."));
    return;
  }

  if (!clientId) {
    mount(mountEl, el("p", { class: "hint" }, "Google sign-in isn't configured for this site yet."));
    return;
  }

  try {
    await loadGoogleScript();
  } catch {
    mount(mountEl, el("p", { class: "hint" }, "Couldn't load Google sign-in."));
    return;
  }

  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: async (response) => {
      try {
        onSuccess(await signInWithGoogle(response.credential));
      } catch (err) {
        onError(err);
      }
    },
  });

  const buttonMount = el("div", {});
  mount(mountEl, buttonMount);
  window.google.accounts.id.renderButton(buttonMount, { type: "standard" });
}

export function renderSignInView(container) {
  const emailInput = el("input", { type: "email", id: "signin-email", name: "email", required: true });
  const passwordInput = el("input", { type: "password", id: "signin-password", name: "password", required: true });
  const errorEl = el("p", { class: "form-error", hidden: true });
  const googleMount = el("div", {});

  const form = el(
    "form",
    { class: "form" },
    formField("Email", emailInput),
    formField("Password", passwordInput),
    errorEl,
    el("button", { type: "submit" }, "Sign in")
  );

  const showError = (err) => {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    try {
      goHome(await logIn(emailInput.value, passwordInput.value));
    } catch (err) {
      showError(err);
    }
  });

  mount(
    container,
    el(
      "div",
      { class: "auth-page" },
      el("h1", {}, "Sign in"),
      el(
        "div",
        { class: "auth-card" },
        form,
        el("div", { class: "auth-divider" }, "or"),
        googleMount,
        el(
          "div",
          { class: "auth-footer" },
          el("p", {}, "New here? ", el("a", { href: "#/signup" }, "Create an account")),
          el("p", {}, el("a", { href: "#/forgot-password" }, "Forgot your password?"))
        )
      )
    )
  );

  renderGoogleButton(googleMount, goHome, showError);
}

export function renderSignUpView(container) {
  const firstNameInput = el("input", { type: "text", id: "signup-first-name", name: "first_name", required: true });
  const lastNameInput = el("input", { type: "text", id: "signup-last-name", name: "last_name", required: true });
  const emailInput = el("input", { type: "email", id: "signup-email", name: "email", required: true });
  const passwordInput = el("input", {
    type: "password",
    id: "signup-password",
    name: "password",
    required: true,
    minlength: 8,
  });
  const errorEl = el("p", { class: "form-error", hidden: true });
  const successEl = el("p", { class: "form-success", hidden: true });
  const googleMount = el("div", {});

  const form = el(
    "form",
    { class: "form" },
    formField("First name", firstNameInput),
    formField("Last name", lastNameInput),
    formField("Email", emailInput),
    formField("Password (at least 8 characters)", passwordInput),
    errorEl,
    el("button", { type: "submit" }, "Create account")
  );

  const showError = (err) => {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    try {
      const result = await signUp(emailInput.value, passwordInput.value, joinName(firstNameInput.value, lastNameInput.value));
      form.hidden = true;
      successEl.textContent = result.message;
      successEl.hidden = false;
    } catch (err) {
      showError(err);
    }
  });

  mount(
    container,
    el(
      "div",
      { class: "auth-page" },
      el("h1", {}, "Create an account"),
      el(
        "div",
        { class: "auth-card" },
        form,
        successEl,
        el("div", { class: "auth-divider" }, "or"),
        googleMount,
        el("div", { class: "auth-footer" }, el("p", {}, "Already have an account? ", el("a", { href: "#/signin" }, "Sign in")))
      )
    )
  );

  renderGoogleButton(googleMount, goHome, showError);
}

export function renderForgotPasswordView(container) {
  const emailInput = el("input", { type: "email", id: "forgot-email", name: "email", required: true });
  const errorEl = el("p", { class: "form-error", hidden: true });
  const successEl = el("p", { class: "form-success", hidden: true });

  const form = el(
    "form",
    { class: "form" },
    formField("Email", emailInput),
    errorEl,
    el("button", { type: "submit" }, "Send reset link")
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    try {
      const result = await forgotPassword(emailInput.value);
      successEl.textContent = result.message;
      successEl.hidden = false;
      form.hidden = true;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  mount(container, el("div", { class: "auth-page" }, el("h1", {}, "Reset your password"), form, successEl));
}

export function renderResetPasswordView(container, params, query) {
  const token = query.token;
  if (!token) {
    mount(container, el("p", { class: "form-error" }, "This reset link is missing its token."));
    return;
  }

  const passwordInput = el("input", {
    type: "password",
    id: "reset-password",
    name: "password",
    required: true,
    minlength: 8,
  });
  const errorEl = el("p", { class: "form-error", hidden: true });

  const form = el(
    "form",
    { class: "form" },
    formField("New password", passwordInput),
    errorEl,
    el("button", { type: "submit" }, "Set new password")
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    try {
      goHome(await resetPassword(token, passwordInput.value));
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  mount(container, el("div", { class: "auth-page" }, el("h1", {}, "Set a new password"), form));
}

export async function renderVerifyEmailView(container, params, query) {
  const token = query.token;
  if (!token) {
    mount(container, el("p", { class: "form-error" }, "This verification link is missing its token."));
    return;
  }

  mount(container, el("p", { class: "empty-state" }, "Verifying…"));
  try {
    setCurrentUser(await verifyEmail(token));
    mount(
      container,
      el("p", { class: "form-success" }, "Your email is verified and you're signed in."),
      el("a", { href: "#/", class: "back-link" }, "Continue to search")
    );
  } catch (err) {
    mount(container, el("p", { class: "form-error" }, `Couldn't verify this link: ${err.message}`));
  }
}
