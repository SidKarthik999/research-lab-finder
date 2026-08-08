// Rendering helpers shared between the search results view and the
// professor detail page -- the contact-link logic and publication list
// only exist once. See CLAUDE.md's contact-panel notes for why the
// Scholar/directory links are built exactly this way (query-string
// construction, quoting rules) before changing anything here.

import { el, mount } from "./dom.js";

// Only ~78% of institutions have a Carnegie Classification match (see
// src/ingestion/carnegie.py) -- returns null rather than a placeholder
// badge for the rest, same "absent beats wrong" convention as the rest of
// this project rather than implying "uncategorized" is itself a category.
export function institutionTypeBadge(classification) {
  if (!classification) return null;
  return el("span", { class: "institution-type-badge" }, classification);
}

export function institutionDomain(url) {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

// Google Scholar has no public "look up this exact person" API, so this is
// a search link, same idea as the institution site-search link below: it
// reliably gets a student *to* a place to look, even without a direct URL
// stored -- neither link is a guaranteed direct hit.
//
// Appending the institution to narrow ambiguous names was tried and
// reverted: Scholar's mauthors match appears to check the query against
// the profile's own listed affiliation text, so if that doesn't literally
// match what's passed (an abbreviation, an old affiliation, etc.) it
// filters the person out entirely instead of narrowing correctly. Name
// alone is the version known to work -- don't add institution back
// without a way to verify it doesn't regress a real profile.
export function scholarSearchUrl(name) {
  const params = new URLSearchParams({ view_op: "search_authors", mauthors: name });
  return `https://scholar.google.com/citations?${params}`;
}

// The name must be quoted, or Google treats the tokens as independent
// keywords anywhere on the site instead of requiring them together, which
// badly hurts precision.
export function directorySearchUrl(domain, name) {
  const params = new URLSearchParams({ q: `site:${domain} "${name}"` });
  return `https://www.google.com/search?${params}`;
}

// Returns a <p class="contact-line"> of pill-styled contact links, or null
// if there's nothing to show -- both viable directly as an el() child.
export function renderContactLine(professor) {
  const name = professor.professor_name || "";
  const domain = institutionDomain(professor.institution_website);
  const links = [];

  if (professor.email) {
    links.push(el("a", { href: `mailto:${professor.email}` }, "Email"));
  }
  if (professor.website) {
    links.push(el("a", { href: professor.website, target: "_blank", rel: "noopener" }, "Website"));
  }
  if (professor.orcid) {
    links.push(el("a", { href: professor.orcid, target: "_blank", rel: "noopener" }, "ORCID"));
  }
  if (name) {
    links.push(
      el("a", { href: scholarSearchUrl(name), target: "_blank", rel: "noopener" }, "Find on Google Scholar")
    );
  }
  if (domain && name) {
    links.push(
      el(
        "a",
        { href: directorySearchUrl(domain, name), target: "_blank", rel: "noopener" },
        `Search for ${name} on ${professor.institution_name || "institution"}'s site`
      )
    );
  }

  if (links.length === 0) return null;
  return el("p", { class: "contact-line" }, ...links);
}

// topics may be an array of plain strings (the /api/search response's
// top-3 chip list) or an array of {name, ...} objects (the professor
// detail endpoint's full topic list) -- handle both rather than making
// callers normalize first.
export function topicChips(topics) {
  if (!topics || topics.length === 0) return null;
  return el(
    "p",
    { class: "topics" },
    topics.map((topic) => el("span", { class: "topic-chip" }, typeof topic === "string" ? topic : topic.name))
  );
}

// Clicking a paper's title expands it in place to show the abstract (built
// lazily on first expand, cached on the DOM node after that) plus a link
// out to the paper itself where one is on file -- the title toggles the
// abstract, the link is a separate, explicit "go there" action.
function renderPublicationItem(pub) {
  const year = pub.publication_date ? pub.publication_date.slice(0, 4) : "";
  const meta = [pub.journal, year].filter(Boolean).join(", ");
  const abstractBox = el("div", { class: "publication-abstract", hidden: true });

  const titleButton = el(
    "button",
    { type: "button", class: "publication-title", "aria-expanded": "false" },
    pub.title || "(untitled)"
  );
  titleButton.addEventListener("click", () => {
    const expanded = titleButton.getAttribute("aria-expanded") === "true";
    if (expanded) {
      abstractBox.hidden = true;
      titleButton.setAttribute("aria-expanded", "false");
      return;
    }
    if (!abstractBox.dataset.loaded) {
      mount(
        abstractBox,
        el("p", {}, pub.abstract || "No abstract on file for this paper."),
        pub.url
          ? el("a", { href: pub.url, target: "_blank", rel: "noopener", class: "publication-link" }, "Read the full paper ↗")
          : null
      );
      abstractBox.dataset.loaded = "true";
    }
    abstractBox.hidden = false;
    titleButton.setAttribute("aria-expanded", "true");
  });

  return el("li", {}, titleButton, meta ? el("span", { class: "meta" }, ` — ${meta}`) : null, abstractBox);
}

export function publicationList(publications) {
  if (publications.length === 0) {
    return el("p", { class: "meta empty-state" }, "No publications on file.");
  }
  return el("ul", { class: "publication-list" }, publications.map(renderPublicationItem));
}
