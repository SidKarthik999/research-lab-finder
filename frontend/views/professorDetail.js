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
import { ApiError, generateProfessorSummary, getProfessor, getProfessorPublications } from "../api.js";
import { publicationList, renderContactLine, topicChips } from "../professor.js";

const AI_DISCLOSURE = "AI-generated from this professor's public research record — may be incomplete or imprecise.";

export async function renderProfessorDetailView(container, params) {
  const professorId = params.id;
  mount(container, el("p", { class: "empty-state" }, "Loading…"));

  let professor;
  let publications;
  try {
    [professor, publications] = await Promise.all([
      getProfessor(professorId),
      getProfessorPublications(professorId).then((data) => data.publications),
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

  mount(
    container,
    el("a", { href: "#/", class: "back-link" }, "← Back to search"),
    el("h1", {}, professor.professor_name || "Unknown professor"),
    el("p", { class: "meta" }, professor.institution_name || "Institution unknown"),
    location ? el("p", { class: "meta" }, location) : null,
    topicChips(professor.topics),
    renderContactLine(professor),
    el("div", { class: "card" }, renderSummarySection(professor, professorId)),
    el("div", { class: "card" }, el("h2", {}, "Publications"), publicationList(publications))
  );
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
