// General contact form (#/contact) -- backs POST /api/contact. Separate
// from the per-professor "Flag an issue" dialog in professorDetail.js:
// that one always names a specific Professor row and is reachable from
// that professor's own page; this is the catch-all the privacy policy
// points at for anything else, including a professor asking to have
// their listing removed or a general privacy question. See
// docs/ROADMAP.md Phase 6.5.

import { el, mount } from "../dom.js";
import { ApiError, submitContact } from "../api.js";
import { getCurrentUser } from "../session.js";

export async function renderContactView(container) {
  const user = getCurrentUser();

  const nameInput = el("input", { type: "text", id: "contact-name", name: "name", value: user?.name || "" });
  const emailInput = el("input", {
    type: "email",
    id: "contact-email",
    name: "email",
    value: user?.email || "",
    required: true,
  });
  const messageInput = el("textarea", { id: "contact-message", name: "message", rows: "6", required: true });

  const errorEl = el("p", { class: "form-error", hidden: true });
  const successEl = el("p", { class: "form-success", hidden: true });
  const submitButton = el("button", { type: "submit" }, "Send");

  const form = el(
    "form",
    { class: "form form-wide" },
    el("div", { class: "field" }, el("label", { for: "contact-name" }, "Name (optional)"), nameInput),
    el(
      "div",
      { class: "field" },
      el("label", { for: "contact-email" }, "Your email"),
      emailInput,
      el("p", { class: "hint" }, "So we can reply. We don't use this for anything else.")
    ),
    el(
      "div",
      { class: "field" },
      el("label", { for: "contact-message" }, "Message"),
      messageInput,
      el(
        "p",
        { class: "hint" },
        "If this is about a specific professor's listing, mention their name or paste the page link."
      )
    ),
    errorEl,
    successEl,
    submitButton
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    successEl.hidden = true;
    submitButton.disabled = true;
    try {
      await submitContact({
        name: nameInput.value.trim() || null,
        email: emailInput.value.trim() || null,
        message: messageInput.value.trim(),
      });
      successEl.textContent = "Message sent -- thanks, we'll get back to you.";
      successEl.hidden = false;
      form.reset();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        errorEl.textContent = "The contact form isn't set up yet -- sorry about that.";
      } else if (err instanceof ApiError && err.status === 429) {
        errorEl.textContent = "Too many messages sent from here recently -- please try again later.";
      } else {
        errorEl.textContent = err.message;
      }
      errorEl.hidden = false;
    }
    submitButton.disabled = false;
  });

  mount(
    container,
    el("h1", {}, "Contact us"),
    el(
      "p",
      { class: "hint" },
      "Data corrections, removal requests, or anything else. If you have an issue with a specific professor's listing, " +
        "you can also use the \"Flag an issue\" button on their page."
    ),
    form
  );
}
