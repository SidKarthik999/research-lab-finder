// #/guide -- a short "how this works / how to approach a professor" page
// (docs/ROADMAP.md Phase 6.8). Static content, same shape as legal.js.
//
// Shown once automatically to a newly-signed-in account: app.js redirects
// to #/guide?welcome=1 on the first signed-in landing on root, and the
// email-verification view sends new password accounts here. The
// rf_seen_guide localStorage flag set on render is what makes it "once".

import { el, mount } from "../dom.js";

const SEEN_GUIDE_KEY = "rf_seen_guide";

export function markGuideSeen() {
  try {
    localStorage.setItem(SEEN_GUIDE_KEY, "1");
  } catch {
    // Private-mode / storage-disabled browsers just get the guide again on
    // their next root visit -- harmless.
  }
}

export function hasSeenGuide() {
  try {
    return localStorage.getItem(SEEN_GUIDE_KEY) === "1";
  } catch {
    return false;
  }
}

function section(heading, ...body) {
  return el("section", { class: "card" }, el("h2", {}, heading), ...body);
}

export async function renderGuideView(container, _params, query) {
  markGuideSeen();

  const welcome = query.welcome === "1";

  mount(
    container,
    el(
      "div",
      { class: "legal-page" },
      el("h1", {}, welcome ? "Welcome — here's how to get started" : "How Research Finder works"),
      welcome
        ? el(
            "p",
            { class: "hint" },
            "Your account is ready. This page is a one-time overview — you can always reach it again from “How it works” in the header."
          )
        : null,

      section(
        "What a search returns",
        el(
          "p",
          {},
          "Results are individual professors (principal investigators), each at one institution — not a curated directory of labs. " +
            "The data comes from public sources (OpenAlex and ORCID); see the "
        ),
        el("p", {}, el("a", { href: "#/about" }, "About & data provenance"), " page for exactly where each field comes from."
        ),
        el(
          "p",
          {},
          "Search by a research area (a broad field like “neuroscience” or a specific topic like “optogenetics” — both work), " +
            "plus optional institution and location filters. The example chips on the home page are real searches you can start from."
        )
      ),

      section(
        "Finding a way to contact someone",
        el(
          "p",
          {},
          "Most professors don't have a public email address on file — that's expected, not a gap in your search. " +
            "Every result has a contact panel with what is known (a personal or lab site, ORCID) plus two search links: " +
            "“Find on Google Scholar” and a search of the institution's own site for the professor's name. " +
            "Those get you to a page where their real contact details usually live."
        )
      ),

      section(
        "Writing a first email that gets a reply",
        el(
          "ul",
          {},
          el("li", {}, "Keep it short — a few sentences. A busy PI skims."),
          el(
            "li",
            {},
            "Name a specific paper or project of theirs and say what caught your interest. This is the whole difference between a real email and a mass one."
          ),
          el(
            "li",
            {},
            "Say who you are in one line (year, school, relevant coursework or skills) and what you're actually asking for — a few hours a week this term, a summer position, remote or in person."
          ),
          el("li", {}, "Ask one clear question and make it easy to say yes or no. Attach a short CV if you have one.")
        )
      ),

      section(
        "If you make an account",
        el(
          "p",
          {},
          "Signing in lets you save a student profile once (level, coursework, skills, what you're looking for), " +
            "bookmark professors, and generate a draft email grounded in both your profile and the professor's recent work. " +
            "The draft is always yours to edit, and you send it yourself — the app never emails anyone on your behalf."
        )
      ),

      el("p", { class: "back-link-row" }, el("a", { href: "#/", class: "back-link" }, "← Start searching"))
    )
  );
}
