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
          "Every search returns individual professors whose work matches your search terms — not a curated list of labs. " +
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
          "Most professors don't have a public email address on file. " +
            "Every result has a contact panel with what is known and verified (a personal or lab site, ORCID) plus two search links: " +
            "“Find on Google Scholar” and a search of the institution's own site for the professor's name. " +
            "Those usually get you to a page where their contact details are listed."
        )
      ),

      section(
        "Writing a cold email",
        el(
          "ul",
          {},
          el("li", {}, "Keep it short. PIs get a lot of email and skim most of it."),
          el(
            "li",
            {},
            "Name a specific paper or project of theirs and say what part of it you're interested in."
          ),
          el(
            "li",
            {},
            "Say who you are in a line or two (year, school, relevant coursework or skills) and what you're actually asking for — a few hours a week this term, a summer position, remote or in person."
          ),
          el("li", {}, "Ask one clear question and make it easy to say yes or no. Attach a short CV if you have one."),
          el(
            "li",
            {},
            "The generated draft is a starting point — read it and edit it before sending. If you don't hear back in a week or so feel free to follow-up."
          )
        )
      ),

      section(
        "If you make an account",
        el(
          "p",
          {},
          "Signing in lets you save your student profile once (level, coursework, skills, what you're looking for), " +
            "bookmark professors, and generate draft emails grounded in both your profile and the professor's recent work. " +
            "The draft is always yours to edit, and you send it yourself — the app never emails anyone on your behalf."
        )
      ),

      el("p", { class: "back-link-row" }, el("a", { href: "#/", class: "back-link" }, "← Start searching"))
    )
  );
}
