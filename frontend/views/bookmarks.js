// Bookmarked professors (#/bookmarks) -- split out from #/profile so
// "things I saved" and "my own info" are two separate pages rather than
// one long scroll, reachable from the account dropdown.

import { el, mount } from "../dom.js";
import { getBookmarks, unbookmarkProfessor } from "../api.js";
import { getCurrentUser } from "../session.js";

const DRAFT_PREVIEW_LENGTH = 160;

function renderBookmarkList(container, bookmarks) {
  function render() {
    if (bookmarks.length === 0) {
      mount(container, el("p", { class: "empty-state" }, "You haven't bookmarked any professors yet."));
      return;
    }
    mount(container, ...bookmarks.map(renderBookmarkItem));
  }

  function renderBookmarkItem(bookmark) {
    const location = [bookmark.city, bookmark.state, bookmark.country_code].filter(Boolean).join(", ");
    const removeBtn = el("button", { type: "button", class: "ghost" }, "Remove bookmark");
    removeBtn.addEventListener("click", async () => {
      removeBtn.disabled = true;
      try {
        await unbookmarkProfessor(bookmark.professor_id);
        bookmarks = bookmarks.filter((b) => b.bookmark_id !== bookmark.bookmark_id);
        render();
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
      { class: "card bookmark-item" },
      el(
        "h2",
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

  render();
}

export async function renderBookmarksView(container) {
  const user = getCurrentUser();
  if (!user) {
    mount(
      container,
      el("h1", {}, "Bookmarked professors"),
      el("p", { class: "empty-state" }, "Sign in to see your bookmarked professors."),
      el("a", { href: "#/signin", class: "back-link" }, "Sign in")
    );
    return;
  }

  mount(container, el("p", { class: "empty-state" }, "Loading…"));

  let bookmarks;
  try {
    bookmarks = (await getBookmarks()).bookmarks;
  } catch (err) {
    mount(container, el("p", { class: "form-error" }, `Couldn't load your bookmarks: ${err.message}`));
    return;
  }

  const listEl = el("div", { class: "bookmark-list" });
  mount(container, el("h1", {}, "Bookmarked professors"), listEl);
  renderBookmarkList(listEl, bookmarks);
}
