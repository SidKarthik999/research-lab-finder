// Professor detail page (#/professor/:id). Shows the full topic list
// (unlike the search view's top-3 chips), the same contact panel as the
// search card, publications loaded up front rather than behind a toggle,
// and the cached-or-generate AI summary.
//
// The summary section always discloses that it's AI-generated -- see
// CLAUDE.md / docs/ROADMAP.md Phase 5A: absent beats wrong, and a
// confidently-wrong paragraph about a real named academic is the worst
// failure mode this feature can produce.

import { el, mount } from "../dom.js";
import {
  ApiError,
  bookmarkProfessor,
  generateColdEmail,
  generateProfessorSummary,
  getColdEmailDrafts,
  getProfessor,
  getProfessorPublications,
  unbookmarkProfessor,
  updateColdEmailDraft,
} from "../api.js";
import { publicationList, renderContactLine, topicChips, institutionTypeBadge } from "../professor.js";
import { getCurrentUser } from "../session.js";

const AI_DISCLOSURE = "AI-generated from this professor's public research record — may be incomplete or imprecise.";
const EMAIL_DISCLOSURE =
  "AI-drafted from this professor's public research record and your student profile — review and edit before sending. The app drafts; you send.";

export async function renderProfessorDetailView(container, params) {
  const professorId = params.id;
  mount(container, el("p", { class: "empty-state" }, "Loading…"));

  const signedIn = Boolean(getCurrentUser());

  let professor;
  let publications;
  let existingDrafts = [];
  try {
    [professor, publications, existingDrafts] = await Promise.all([
      getProfessor(professorId),
      getProfessorPublications(professorId).then((data) => data.publications),
      // Only fetched when signed in -- the endpoint requires auth, and a
      // signed-out visitor has no drafts to show anyway.
      signedIn ? getColdEmailDrafts(professorId).then((data) => data.drafts) : Promise.resolve([]),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      mount(
        container,
        el("a", { href: "#/", class: "back-link" }, "← Back to search"),
        el("p", { class: "empty-state" }, "Professor not found.")
      );
      return;
    }
    mount(container, el("p", { class: "form-error" }, `Couldn't load this professor: ${err.message}`));
    return;
  }

  const location = [professor.city, professor.state, professor.country_code].filter(Boolean).join(", ");
  const name = professor.professor_name || "Unknown professor";
  const nameInitials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  mount(
    container,
    el("a", { href: "#/", class: "back-link" }, "← Back to search"),
    el(
      "div",
      { class: "detail-hero" },
      el("span", { class: "avatar large", "aria-hidden": "true" }, nameInitials || "?"),
      el(
        "div",
        { class: "detail-hero-text" },
        el("h1", {}, name),
        el("p", { class: "meta" }, professor.institution_name || "Institution unknown"),
        location ? el("p", { class: "meta" }, location) : null,
        institutionTypeBadge(professor.carnegie_classification)
      )
    ),
    signedIn ? renderBookmarkButton(professorId, professor.is_bookmarked) : null,
    topicChips(professor.topics),
    renderContactLine(professor),
    el("div", { class: "card" }, renderSummarySection(professor, professorId)),
    el("div", { class: "card" }, renderColdEmailSection(professorId, existingDrafts[0])),
    el("div", { class: "card" }, el("h2", {}, "Publications"), publicationList(publications))
  );
}

function renderBookmarkButton(professorId, initiallyBookmarked) {
  let bookmarked = initiallyBookmarked;

  const button = el(
    "button",
    { type: "button", class: "secondary bookmark-button" },
    bookmarked ? "★ Bookmarked" : "☆ Bookmark"
  );
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      if (bookmarked) {
        await unbookmarkProfessor(professorId);
        bookmarked = false;
      } else {
        await bookmarkProfessor(professorId);
        bookmarked = true;
      }
      button.textContent = bookmarked ? "★ Bookmarked" : "☆ Bookmark";
    } catch {
      // A failed toggle just leaves the button in its previous state --
      // nothing to report beyond letting the user try again.
    }
    button.disabled = false;
  });

  return button;
}

function summaryBox(text) {
  return [el("div", { class: "summary-box" }, text), el("p", { class: "hint" }, AI_DISCLOSURE)];
}

function renderSummarySection(professor, professorId) {
  const wrapper = el("div", {}, el("h2", {}, "AI summary"));

  if (professor.ai_summary) {
    wrapper.append(...summaryBox(professor.ai_summary));
    return wrapper;
  }

  const statusEl = el("p", { class: "hint" });
  const button = el(
    "button",
    {
      type: "button",
      class: "secondary",
      onClick: async () => {
        button.disabled = true;
        statusEl.textContent = "Generating…";
        try {
          const result = await generateProfessorSummary(professorId);
          if (result.summary) {
            wrapper.replaceChildren(el("h2", {}, "AI summary"), ...summaryBox(result.summary));
            return;
          }
          statusEl.textContent = "Not enough public data on file yet to generate a summary for this professor.";
        } catch (err) {
          statusEl.textContent =
            err instanceof ApiError && err.status === 503
              ? "AI summaries aren't turned on for this site yet."
              : `Couldn't generate a summary: ${err.message}`;
        }
        button.disabled = false;
      },
    },
    "Generate AI summary"
  );

  wrapper.append(button, statusEl);
  return wrapper;
}

function renderColdEmailSection(professorId, existingDraft) {
  const wrapper = el("div", {}, el("h2", {}, "Draft a cold email"));

  const user = getCurrentUser();
  if (!user) {
    wrapper.append(
      el(
        "p",
        { class: "hint" },
        "Sign in to draft a personalized email to this professor — ",
        el("a", { href: "#/signin" }, "sign in"),
        "."
      )
    );
    return wrapper;
  }

  const statusEl = el("p", { class: "hint" });

  const draftAction = async () => {
    button.disabled = true;
    button.textContent = "Regenerate draft";
    statusEl.textContent = "Drafting…";
    try {
      const result = await generateColdEmail(professorId);
      if (result.draft) {
        statusEl.textContent = "";
        renderDraft(result.draft, result.draft_id);
        return;
      }
      statusEl.textContent = "Not enough public data on file yet to draft an email for this professor.";
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        statusEl.replaceChildren(
          "Complete your student profile first — ",
          el("a", { href: "#/profile" }, "fill it out here"),
          "."
        );
      } else if (err instanceof ApiError && err.status === 503) {
        statusEl.textContent = "Email drafting isn't turned on for this site yet.";
      } else {
        statusEl.textContent = `Couldn't draft an email: ${err.message}`;
      }
    }
    button.disabled = false;
  };

  const button = el(
    "button",
    { type: "button", class: "secondary", onClick: draftAction },
    existingDraft ? "Regenerate draft" : "Draft an email"
  );

  function renderDraft(body, draftId) {
    // savedBody tracks whatever's actually persisted server-side, so the
    // save button's visibility reflects "does the box differ from what's
    // saved", not just "has this textarea ever been touched".
    let savedBody = body;

    const textarea = el("textarea", { rows: "12" });
    textarea.value = body;

    const saveStatusEl = el("p", { class: "hint save-status" });
    const saveBtn = el("button", { type: "button", class: "save-draft-button", hidden: true }, "Save changes");
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveStatusEl.textContent = "Saving…";
      try {
        await updateColdEmailDraft(professorId, draftId, textarea.value);
        savedBody = textarea.value;
        saveBtn.hidden = true;
        saveStatusEl.textContent = "Saved.";
      } catch (err) {
        saveStatusEl.textContent = `Couldn't save: ${err.message}`;
      }
      saveBtn.disabled = false;
    });
    textarea.addEventListener("input", () => {
      saveBtn.hidden = textarea.value === savedBody;
      if (saveStatusEl.textContent === "Saved.") saveStatusEl.textContent = "";
    });

    wrapper.replaceChildren(
      el("h2", {}, "Draft a cold email"),
      textarea,
      el("p", { class: "hint" }, EMAIL_DISCLOSURE),
      el("div", { class: "draft-actions" }, button, saveBtn),
      statusEl,
      saveStatusEl
    );
  }

  // A previously-saved draft (see GET /api/professors/{id}/cold-email) shows
  // immediately instead of starting from just a "Draft an email" button --
  // otherwise a generated draft was effectively invisible again the moment
  // you navigated away and back, since it was only ever written to the DB,
  // never read back anywhere in the UI until now.
  if (existingDraft) {
    renderDraft(existingDraft.body, existingDraft.id);
    return wrapper;
  }

  wrapper.append(button, statusEl);
  return wrapper;
}
