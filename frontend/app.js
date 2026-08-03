const form = document.getElementById("search-form");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const prevBtn = document.getElementById("prev-page");
const nextBtn = document.getElementById("next-page");
const pageLabel = document.getElementById("page-label");

const LIMIT = 20;
let currentPage = 1;

function setupAutocomplete(inputId, datalistId, apiPath, extraParams = () => ({})) {
  const input = document.getElementById(inputId);
  const datalist = document.getElementById(datalistId);
  let debounceTimer;

  function fetchSuggestions() {
    clearTimeout(debounceTimer);
    const value = input.value.trim();
    if (!value) {
      datalist.innerHTML = "";
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: value, limit: 10, ...extraParams() });
        const response = await fetch(`${apiPath}?${params}`);
        if (!response.ok) return;
        const data = await response.json();
        const options = data.institutions || data.topics || [];
        datalist.innerHTML = options.map((name) => `<option value="${escapeHtml(name)}"></option>`).join("");
      } catch {
        // Autocomplete is a convenience, not critical -- fail silently.
      }
    }, 200);
  }

  input.addEventListener("input", fetchSuggestions);
  return fetchSuggestions;
}

setupAutocomplete("institution", "institution-options", "/api/institutions");

const refreshTopicSuggestions = setupAutocomplete("topic", "topic-options", "/api/topics", () => {
  const field = document.getElementById("field").value;
  return field ? { field } : {};
});

// Re-scope suggestions immediately if the user picks a field after already
// typing a topic, rather than waiting for their next keystroke.
document.getElementById("field").addEventListener("change", refreshTopicSuggestions);

async function loadFieldOptions() {
  const select = document.getElementById("field");
  try {
    const response = await fetch("/api/fields");
    if (!response.ok) return;
    const data = await response.json();
    for (const name of data.fields) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.appendChild(option);
    }
  } catch {
    // Field is a nice-to-have filter -- leave it as "Any field" on failure.
  }
}

loadFieldOptions();

function currentFilters() {
  const data = new FormData(form);
  const filters = {};
  for (const [key, value] of data.entries()) {
    if (value.trim()) filters[key] = value.trim();
  }
  return filters;
}

async function runSearch(page = 1) {
  currentPage = page;
  statusEl.textContent = "Searching...";
  resultsEl.innerHTML = "";

  const params = new URLSearchParams({ ...currentFilters(), page, limit: LIMIT });

  let data;
  try {
    const response = await fetch(`/api/search?${params}`);
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    data = await response.json();
  } catch (err) {
    statusEl.textContent = `Something went wrong: ${err.message}`;
    return;
  }

  renderResults(data.results);
  updatePagination(data.results.length);
}

function institutionDomain(url) {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

// Derived links -- computed on the fly from data already on hand, not
// scraped or guessed. Google Scholar has no public "look up this exact
// person" API, so this is a search link, same idea as the institution
// site-search link: it reliably gets a student *to* a place to look, even
// when we don't have a direct URL stored. Neither one is a guaranteed
// direct hit -- both still require a click to find the right result.
function scholarSearchUrl(name) {
  // Tried appending the institution to narrow ambiguous names, but Scholar's
  // mauthors match appears to check it against the profile's own listed
  // affiliation text -- if that doesn't literally match what we pass (an
  // abbreviation, an old affiliation, etc.), it filters the person out
  // entirely instead of narrowing correctly. Name alone is the version
  // known to actually work; don't add institution back without a way to
  // verify it doesn't regress real profiles like this one.
  const params = new URLSearchParams({ view_op: "search_authors", mauthors: name });
  return `https://scholar.google.com/citations?${params}`;
}

function directorySearchUrl(domain, name) {
  // The name must be quoted -- otherwise Google treats "Jeffrey" and
  // "Tyner" as two independent keywords anywhere on the site instead of
  // requiring them together, which noticeably hurts precision.
  const params = new URLSearchParams({ q: `site:${domain} "${name}"` });
  return `https://www.google.com/search?${params}`;
}

function renderResults(results) {
  if (results.length === 0) {
    statusEl.textContent = "No professors found. Try broadening your search.";
    return;
  }
  statusEl.textContent = `${results.length} result${results.length === 1 ? "" : "s"} on this page.`;

  for (const professor of results) {
    const li = document.createElement("li");
    li.className = "result-card";

    const location = [professor.city, professor.state, professor.country_code]
      .filter(Boolean)
      .join(", ");

    const topics = professor.topics || [];
    const topicsHtml = topics.length
      ? `<p class="topics">${topics.map((topic) => `<span class="topic-chip">${escapeHtml(topic)}</span>`).join("")}</p>`
      : "";

    const professorName = professor.professor_name || "";
    const domain = institutionDomain(professor.institution_website);

    const contactLinks = [
      professor.email && `<a href="mailto:${escapeHtml(professor.email)}">Email</a>`,
      professor.website && `<a href="${escapeHtml(professor.website)}" target="_blank" rel="noopener">Website</a>`,
      professor.orcid && `<a href="${escapeHtml(professor.orcid)}" target="_blank" rel="noopener">ORCID</a>`,
      professorName &&
        `<a href="${escapeHtml(scholarSearchUrl(professorName))}" target="_blank" rel="noopener">Find on Google Scholar</a>`,
      domain &&
        professorName &&
        `<a href="${escapeHtml(directorySearchUrl(domain, professorName))}" target="_blank" rel="noopener">Search for ${escapeHtml(professorName)} on ${escapeHtml(professor.institution_name || "institution")}'s site</a>`,
    ]
      .filter(Boolean)
      .join(" &middot; ");

    li.innerHTML = `
      <h2>${escapeHtml(professor.professor_name || "Unknown professor")}</h2>
      <p class="meta">${professor.institution_name ? escapeHtml(professor.institution_name) : "Institution unknown"}</p>
      ${location ? `<p class="meta">${escapeHtml(location)}</p>` : ""}
      ${topicsHtml}
      <p class="meta">${contactLinks}</p>
      <button type="button" class="publications-toggle" data-professor-id="${professor.id}">Show publications</button>
      <div class="publications" hidden></div>
    `;
    resultsEl.appendChild(li);
  }
}

async function togglePublications(button) {
  const container = button.nextElementSibling;

  if (!container.hidden) {
    container.hidden = true;
    button.textContent = "Show publications";
    return;
  }

  if (!container.dataset.loaded) {
    button.disabled = true;
    try {
      const response = await fetch(`/api/professors/${button.dataset.professorId}/publications`);
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      const data = await response.json();
      renderPublications(container, data.publications);
      container.dataset.loaded = "true";
    } catch (err) {
      container.innerHTML = `<p class="meta">Couldn't load publications: ${escapeHtml(err.message)}</p>`;
    }
    button.disabled = false;
  }

  container.hidden = false;
  button.textContent = "Hide publications";
}

function renderPublications(container, publications) {
  if (publications.length === 0) {
    container.innerHTML = `<p class="meta">No publications on file.</p>`;
    return;
  }

  container.innerHTML = `<ul class="publication-list">${publications
    .map((pub) => {
      const year = pub.publication_date ? pub.publication_date.slice(0, 4) : "";
      const title = pub.url
        ? `<a href="${escapeHtml(pub.url)}" target="_blank" rel="noopener">${escapeHtml(pub.title)}</a>`
        : escapeHtml(pub.title);
      const meta = [pub.journal, year].filter(Boolean).join(", ");
      return `<li>${title}${meta ? `<span class="meta"> &mdash; ${escapeHtml(meta)}</span>` : ""}</li>`;
    })
    .join("")}</ul>`;
}

function updatePagination(resultCount) {
  pageLabel.textContent = `Page ${currentPage}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = resultCount < LIMIT;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runSearch(1);
});

prevBtn.addEventListener("click", () => runSearch(currentPage - 1));
nextBtn.addEventListener("click", () => runSearch(currentPage + 1));

resultsEl.addEventListener("click", (event) => {
  const button = event.target.closest(".publications-toggle");
  if (button) togglePublications(button);
});

runSearch(1);
