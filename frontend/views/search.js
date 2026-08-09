// The original single-page search UI, refactored into a router view.
// Behavior is unchanged from the pre-Phase-5A app.js -- same debounced
// autocomplete, same field-scoped topic suggestions, same advanced-search
// fields, same lazy-loaded publications toggle -- only the DOM
// construction changed, from innerHTML template literals to el().

import { mount, el } from "../dom.js";
import {
  searchProfessors,
  listInstitutions,
  listTopics,
  listFields,
  listInstitutionTypes,
  getProfessorPublications,
} from "../api.js";
import { renderContactLine, topicChips, publicationList, institutionTypeBadge } from "../professor.js";

const LIMIT = 20;

export function renderSearchView(container) {
  let currentPage = 1;

  const fieldSelect = el("select", { id: "field", name: "field" }, el("option", { value: "" }, "Any field"));
  const institutionTypeSelect = el(
    "select",
    { id: "institution_type", name: "institution_type" },
    el("option", { value: "" }, "Any institution type")
  );
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
  const recentOnlyInput = el("input", { type: "checkbox", id: "recent_only", name: "recent_only" });

  const hero = el(
    "div",
    { class: "search-hero" },
    el("h1", {}, "Find a research lab"),
    el("p", { class: "hero-subtitle" }, "Search professors by research field, topic, institution, or location.")
  );

  // Preset labels only -- values are matched with ILIKE '%...%' against
  // Institution.city/state (see build_search_query in backend/main.py), and
  // are drawn from cities/states that actually have meaningful institution
  // counts in the current data (checked against the DB, not guessed) so a
  // click doesn't land on an empty result page.
  const LOCATION_PRESETS = [
    { label: "New York, NY", city: "New York", state: "New York" },
    { label: "Chicago, IL", city: "Chicago", state: "Illinois" },
    { label: "Los Angeles, CA", city: "Los Angeles", state: "California" },
    { label: "Boston, MA", city: "Boston", state: "Massachusetts" },
    { label: "Philadelphia, PA", city: "Philadelphia", state: "Pennsylvania" },
  ];

  function applyLocationPreset(preset) {
    cityInput.value = preset.city;
    stateInput.value = preset.state;
    countryInput.value = "";
    advancedDetails.open = true;
    runSearch(1);
  }

  const locationPresetsEl = el(
    "div",
    { class: "quick-locations" },
    el("span", { class: "quick-locations-label" }, "Near:"),
    ...LOCATION_PRESETS.map((preset) =>
      el(
        "button",
        { type: "button", class: "chip-button", onClick: () => applyLocationPreset(preset) },
        preset.label
      )
    )
  );

  const advancedDetails = el(
    "details",
    { id: "advanced-search" },
    el("summary", {}, "Advanced search"),
    el(
      "div",
      { class: "advanced-fields" },
      el("div", { class: "field" }, el("label", { for: "name" }, "Professor name"), nameInput),
      el("div", { class: "field" }, el("label", { for: "text" }, "Search publication names"), textInput),
      el(
        "div",
        { class: "field" },
        el("label", { for: "institution_type" }, "Institution type"),
        institutionTypeSelect
      ),
      el(
        "div",
        { class: "location-fields" },
        el("div", { class: "field" }, el("label", { for: "city" }, "City"), cityInput),
        el("div", { class: "field" }, el("label", { for: "state" }, "State"), stateInput),
        el("div", { class: "field" }, el("label", { for: "country" }, "Country"), countryInput)
      ),
      el(
        "div",
        { class: "checkbox-field" },
        el(
          "label",
          { for: "recent_only" },
          recentOnlyInput,
          "Only show recently active researchers (published in the last few years)"
        ),
        el(
          "p",
          { class: "hint" },
          "Publication data is still being filled in for many professors, so this may hide people who are actually active."
        )
      )
    )
  );

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
    locationPresetsEl,
    advancedDetails,
    el(
      "button",
      { type: "submit", class: "search-submit" },
      // el() builds nodes via createElement, which can't create real SVG
      // elements -- this is the documented "html" escape hatch for a fixed,
      // trusted string this codebase wrote itself (see dom.js).
      el("span", {
        class: "btn-icon",
        html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
      }),
      "Search"
    )
  );

  const statusEl = el("p", { id: "status", "aria-live": "polite" });
  const resultsEl = el("ul", { id: "results" });
  const prevBtn = el("button", { id: "prev-page", type: "button", disabled: true }, "Previous");
  const pageLabel = el("span", { id: "page-label" });
  const nextBtn = el("button", { id: "next-page", type: "button", disabled: true }, "Next");
  const pagination = el("div", { id: "pagination" }, prevBtn, pageLabel, nextBtn);

  mount(container, hero, el("div", { class: "search-panel" }, form), statusEl, resultsEl, pagination);

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

  (async () => {
    try {
      const data = await listInstitutionTypes();
      for (const type of data.types) {
        institutionTypeSelect.append(el("option", { value: type }, type));
      }
    } catch {
      // Same as the field dropdown -- leave it as "Any institution type" on failure.
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
      institutionTypeBadge(professor.institution_type),
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
