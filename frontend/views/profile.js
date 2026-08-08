// Student profile (#/profile) -- level, school, coursework, skills, prior
// experience, and what they're looking for. Feeds the cold-email drafts
// in a later phase; not shown to professors directly.

import { el, mount } from "../dom.js";
import { getBookmarks, getProfile, unbookmarkProfessor, updateProfile } from "../api.js";
import { getCurrentUser } from "../session.js";

const DRAFT_PREVIEW_LENGTH = 160;

function renderBookmarksSection(bookmarks) {
  const listEl = el("div", { class: "bookmark-list" });

  function renderList() {
    if (bookmarks.length === 0) {
      mount(listEl, el("p", { class: "empty-state" }, "You haven't bookmarked any professors yet."));
      return;
    }
    mount(listEl, ...bookmarks.map(renderBookmarkItem));
  }

  function renderBookmarkItem(bookmark) {
    const location = [bookmark.city, bookmark.state, bookmark.country_code].filter(Boolean).join(", ");
    const removeBtn = el("button", { type: "button", class: "ghost" }, "Remove bookmark");
    removeBtn.addEventListener("click", async () => {
      removeBtn.disabled = true;
      try {
        await unbookmarkProfessor(bookmark.professor_id);
        bookmarks = bookmarks.filter((b) => b.bookmark_id !== bookmark.bookmark_id);
        renderList();
      } catch {
        removeBtn.disabled = false;
      }
    });

    const draftPreview = bookmark.latest_draft_body
      ? bookmark.latest_draft_body.slice(0, DRAFT_PREVIEW_LENGTH) +
        (bookmark.latest_draft_body.length > DRAFT_PREVIEW_LENGTH ? "…" : "")
      : null;

    return el(
      "div",
      { class: "bookmark-item" },
      el(
        "h3",
        {},
        el("a", { href: `#/professor/${bookmark.professor_id}` }, bookmark.professor_name || "Unknown professor")
      ),
      el(
        "p",
        { class: "meta" },
        [bookmark.institution_name, location].filter(Boolean).join(" — ") || "Institution unknown"
      ),
      draftPreview
        ? el(
            "div",
            { class: "bookmark-draft-preview" },
            el("p", { class: "hint" }, "Saved email draft:"),
            el("p", {}, draftPreview)
          )
        : null,
      removeBtn
    );
  }

  renderList();
  return el("div", { class: "card" }, el("h2", {}, "Bookmarked professors"), listEl);
}

function formField(labelText, inputEl, hint) {
  const children = [el("label", { for: inputEl.id }, labelText), inputEl];
  if (hint) children.push(el("p", { class: "hint" }, hint));
  return el("div", { class: "field" }, ...children);
}

export async function renderProfileView(container) {
  const user = getCurrentUser();
  if (!user) {
    mount(
      container,
      el("h1", {}, "Your profile"),
      el("p", { class: "empty-state" }, "Sign in to set up your profile."),
      el("a", { href: "#/signin", class: "back-link" }, "Sign in")
    );
    return;
  }

  mount(container, el("p", { class: "empty-state" }, "Loading…"));

  let profile;
  let bookmarks;
  try {
    [profile, bookmarks] = await Promise.all([getProfile(), getBookmarks().then((data) => data.bookmarks)]);
  } catch (err) {
    mount(container, el("p", { class: "form-error" }, `Couldn't load your profile: ${err.message}`));
    return;
  }

  const levelSelect = el(
    "select",
    { id: "profile-level", name: "level" },
    el("option", { value: "" }, "Not specified"),
    el("option", { value: "high school" }, "High school"),
    el("option", { value: "undergraduate" }, "Undergraduate"),
    el("option", { value: "graduate" }, "Graduate"),
    el("option", { value: "other" }, "Other")
  );
  if (profile.level) levelSelect.value = profile.level;

  const schoolInput = el("input", {
    type: "text",
    id: "profile-school",
    name: "school",
    value: profile.school || "",
  });
  const gradYearInput = el("input", {
    type: "number",
    id: "profile-grad-year",
    name: "graduation_year",
    value: profile.graduation_year ?? "",
    min: 1950,
    max: 2100,
  });
  // rows sized to what each field realistically holds -- a class list or
  // skills line runs short, prior experience tends to run longest.
  const courseworkInput = el(
    "textarea",
    { id: "profile-coursework", name: "coursework", rows: "3" },
    profile.coursework || ""
  );
  const skillsInput = el(
    "textarea",
    { id: "profile-skills", name: "skills", rows: "3" },
    profile.skills || ""
  );
  const priorExperienceInput = el(
    "textarea",
    { id: "profile-prior-experience", name: "prior_experience", rows: "5" },
    profile.prior_experience || ""
  );
  const lookingForInput = el(
    "textarea",
    { id: "profile-looking-for", name: "looking_for", rows: "4" },
    profile.looking_for || ""
  );

  const errorEl = el("p", { class: "form-error", hidden: true });
  const successEl = el("p", { class: "form-success", hidden: true });

  const form = el(
    "form",
    { class: "form form-wide" },
    el(
      "div",
      { class: "profile-fields-row" },
      formField("Level", levelSelect),
      formField("School", schoolInput),
      formField("Expected graduation year", gradYearInput)
    ),
    formField("Relevant coursework", courseworkInput, "Classes, labs, or projects relevant to research."),
    formField("Skills / techniques", skillsInput, "Programming languages, lab techniques, tools you know."),
    formField("Prior research or work experience", priorExperienceInput),
    formField("What you're looking for", lookingForInput, "Used to help write cold emails that actually fit."),
    errorEl,
    successEl,
    el("button", { type: "submit" }, "Save profile")
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    successEl.hidden = true;
    try {
      await updateProfile({
        level: levelSelect.value || null,
        school: schoolInput.value || null,
        graduation_year: gradYearInput.value ? Number(gradYearInput.value) : null,
        coursework: courseworkInput.value || null,
        skills: skillsInput.value || null,
        prior_experience: priorExperienceInput.value || null,
        looking_for: lookingForInput.value || null,
      });
      successEl.textContent = "Profile saved.";
      successEl.hidden = false;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  mount(
    container,
    el("h1", {}, "Your profile"),
    renderBookmarksSection(bookmarks),
    el("h2", {}, "Your info"),
    el(
      "p",
      { class: "hint" },
      "This information is used to personalize the cold emails you generate — it's never shown to professors directly."
    ),
    form
  );
}
