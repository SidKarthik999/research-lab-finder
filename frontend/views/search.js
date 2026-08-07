// The original single-page search UI, refactored into a router view.
// Behavior is unchanged from the pre-Phase-5A app.js -- same debounced
// autocomplete, same field-scoped topic suggestions, same advanced-search
// fields, same lazy-loaded publications toggle -- only the DOM
// construction changed, from innerHTML template literals to el().

import { mount, el } from "../dom.js";
import { searchProfessors, listInstitutions, listTopics, listFields, getProfessorPublications } from "../api.js";
import { renderContactLine, topicChips, publicationList } from "../professor.js";

const LIMIT = 20;

export function renderSearchView(container) {
  let currentPage = 1;

  const fieldSelect = el("select", { id: "field", name: "field" }, el("option", { value: "" }, "Any field"));
  const topicInput = el("input", {
    type: "text",
    id: "topic",
    name: "topic",
    list: "topic-options",
    placeholder: "e.g. optogenetics",
    autocomplete: "off",
  });
  const topicOptions = el("datalist", { id: "topic-options" });
  const institutionInput = el("input", {
    type: "text",
    id: "institution",
    name: "institution",
    list: "institution-options",
    placeholder: "e.g. Stanford",
    autocomplete: "off",
  });
  const institutionOptions = el("datalist", { id: "institution-options" });

  const nameInput = el("input", { type: "text", id: "name", name: "name", placeholder: "e.g. Smith" });
  const textInput = el("input", {
    type: "text",
    id: "text",
    name: "text",
    placeholder: "e.g. a specific technique or method",
  });
  const cityInput = el("input", { type: "text", id: "city", name: "city" });
  const stateInput = el("input", { type: "text", id: "state", name: "state" });
  const countryInput = el("input", { type: "text", id: "country", name: "country" });

  const form = el(
    "form",
    { id: "search-form" },
    el("div", { class: "field" }, el("label", { for: "field" }, "Field"), fieldSelect),
    el("div", { class: "field" }, el("label", { for: "topic" }, "Research topic"), topicInput, topicOptions),
    el(
      "div",
      { class: "field" },
      el("label", { for: "institution" }, "Institution"),
      institutionInput,
      institutionOptions
    ),
    el(
      "details",
      { id: "advanced-search" },
      el("summary", {}, "Advanced search"),
      el(
        "div",
        { class: "advanced-fields" },
        el("div", { class: "field" }, el("label", { for: "name" }, "Professor name"), nameInput),
        el(
          "div",
          { class: "field" },
          el("label", { for: "text" }, "Search publications"),
          textInput,
          el("p", { class: "hint" }, "Searches actual paper titles and abstracts, not just topic categories.")
        ),
        el("div", { class: "field" }, el("label", { for: "city" }, "City"), cityInput),
        el("div", { class: "field" }, el("label", { for: "state" }, "State"), stateInput),
        el("div", { class: "field" }, el("label", { for: "country" }, "Country"), countryInput)
      )
    ),
    el("button", { type: "submit" }, "Search")
  );

  const statusEl = el("p", { id: "status", "aria-live": "polite" });
  const resultsEl = el("ul", { id: "results" });
  const prevBtn = el("button", { id: "prev-page", type: "button", disabled: true }, "Previous");
  const pageLabel = el("span", { id: "page-label" });
  const nextBtn = el("button", { id: "next-page", type: "button", disabled: true }, "Next");
  const pagination = el("div", { id: "pagination" }, prevBtn, pageLabel, nextBtn);

  mount(container, form, statusEl, resultsEl, pagination);

  function setupAutocomplete(input, datalist, fetchFn) {
    let debounceTimer;
    function fetchSuggestions() {
      clearTimeout(debounceTimer);
      const value = input.value.trim();
      if (!value) {
        datalist.replaceChildren();
        return;
      }
      debounceTimer = setTimeout(async () => {
        try {
          const options = await fetchFn(value);
          datalist.replaceChildren(...options.map((name) => el("option", { value: name })));
        } catch {
          // Autocomplete is a convenience, not critical -- fail silently.
        }
      }, 200);
    }
    input.addEventListener("input", fetchSuggestions);
    return fetchSuggestions;
  }

  setupAutocomplete(institutionInput, institutionOptions, async (value) => {
    const data = await listInstitutions(value, 10);
    return data.institutions;
  });

  // Re-scope suggestions immediately if the user picks a field after
  // already typing a topic, rather than waiting for their next keystroke.
  const refreshTopicSuggestions = setupAutocomplete(topicInput, topicOptions, async (value) => {
    const data = await listTopics(value, fieldSelect.value || undefined, 10);
    return data.topics;
  });
  fieldSelect.addEventListener("change", refreshTopicSuggestions);

  (async () => {
    try {
      const data = await listFields();
      for (const name of data.fields) {
        fieldSelect.append(el("option", { value: name }, name));
      }
    } catch {
      // Field is a nice-to-have filter -- leave it as "Any field" on failure.
    }
  })();

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
    resultsEl.replaceChildren();

    let data;
    try {
      data = await searchProfessors({ ...currentFilters(), page, limit: LIMIT });
    } catch (err) {
      statusEl.textContent = `Something went wrong: ${err.message}`;
      return;
    }

    renderResults(data.results);
    updatePagination(data.results.length);
  }

  function renderResults(results) {
    if (results.length === 0) {
      statusEl.textContent = "No professors found. Try broadening your search.";
      return;
    }
    statusEl.textContent = `${results.length} result${results.length === 1 ? "" : "s"} on this page.`;
    for (const professor of results) {
      resultsEl.append(renderCard(professor));
    }
  }

  function renderCard(professor) {
    const location = [professor.city, professor.state, professor.country_code].filter(Boolean).join(", ");

    const publicationsContainer = el("div", { class: "publications", hidden: true });
    const toggleBtn = el(
      "button",
      {
        type: "button",
        class: "publications-toggle secondary",
        "data-professor-id": professor.id,
        onClick: () => togglePublications(toggleBtn, publicationsContainer, professor.id),
      },
      "Show publications"
    );

    return el(
      "li",
      { class: "result-card" },
      el("h2", {}, el("a", { href: `#/professor/${professor.id}` }, professor.professor_name || "Unknown professor")),
      el("p", { class: "meta" }, professor.institution_name || "Institution unknown"),
      location ? el("p", { class: "meta" }, location) : null,
      topicChips(professor.topics),
      renderContactLine(professor),
      toggleBtn,
      publicationsContainer
    );
  }

  async function togglePublications(button, container, professorId) {
    if (!container.hidden) {
      container.hidden = true;
      button.textContent = "Show publications";
      return;
    }

    if (!container.dataset.loaded) {
      button.disabled = true;
      try {
        const data = await getProfessorPublications(professorId);
        mount(container, publicationList(data.publications));
        container.dataset.loaded = "true";
      } catch (err) {
        mount(container, el("p", { class: "meta" }, `Couldn't load publications: ${err.message}`));
      }
      button.disabled = false;
    }

    container.hidden = false;
    button.textContent = "Hide publications";
  }

  function updatePagination(resultCount) {
    pageLabel.textContent = `Page ${currentPage}`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = resultCount < LIMIT;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch(1);
  });
  prevBtn.addEventListener("click", () => runSearch(currentPage - 1));
  nextBtn.addEventListener("click", () => runSearch(currentPage + 1));

  runSearch(1);
}
