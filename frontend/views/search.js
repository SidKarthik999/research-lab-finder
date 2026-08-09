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
  listMetroAreas,
  getProfessorPublications,
} from "../api.js";
import { renderContactLine, topicChips, publicationList, institutionTypeBadge } from "../professor.js";

const LIMIT = 20;

// Module-level, not inside renderSearchView -- the router mounts a fresh
// child <div> on every navigation (see router.js), so any state that needs
// to survive "go to a professor, then come back" has to live outside that
// per-mount closure. A plain module-scoped variable does that for free: the
// module itself is only ever imported/evaluated once, so this persists for
// the life of the page exactly like the router intends currentCleanup to.
// Holds the last-rendered filters/page/results/scroll position, or null
// before the first search of the session.
let savedSearchState = null;

export function renderSearchView(container) {
  let currentPage = 1;
  // Set by a "Near" preset click; cleared as soon as the user edits
  // city/state/country by hand, so a stale preset never silently narrows a
  // manual search the user thinks they fully control.
  let activeMetro = null;
  // The exact result rows currently on screen -- kept alongside filters/page
  // so navigating back can redisplay them directly rather than re-running
  // the search (which could return different results if the data changed
  // in between, and would defeat the point of "still there" restoration).
  let lastResults = [];

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

  // Each preset expands server-side to a curated metro-area city list (see
  // backend/metro_areas.py) rather than a single city -- "Near NYC" means
  // the boroughs and inner suburbs too, not just literally the city named
  // "New York". Fetched, not hardcoded, so the frontend never risks drifting
  // out of sync with the backend's metro id <-> label mapping (same pattern
  // as the Field/Institution type dropdowns below).
  function applyLocationPreset(metroId) {
    activeMetro = metroId;
    cityInput.value = "";
    stateInput.value = "";
    countryInput.value = "";
    // Deliberately does NOT open the advanced-search accordion -- a "Near"
    // click is meant to be a one-click shortcut, not a detour into a form
    // section the user never asked to see.
    runSearch(1);
  }

  const locationPresetsEl = el(
    "div",
    { class: "quick-locations" },
    el("span", { class: "quick-locations-label" }, "Near:")
  );

  (async () => {
    try {
      const data = await listMetroAreas();
      for (const area of data.areas) {
        locationPresetsEl.append(
          el(
            "button",
            { type: "button", class: "chip-button", onClick: () => applyLocationPreset(area.id) },
            area.label
          )
        );
      }
    } catch {
      // Presets are a convenience shortcut -- leave the row label-only on failure.
    }
  })();

  // A manual edit to any location field should drop a stale preset rather
  // than silently keep narrowing results to it underneath what's now typed.
  for (const input of [cityInput, stateInput, countryInput]) {
    input.addEventListener("input", () => {
      activeMetro = null;
    });
  }

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
      // A saved field selection can only be applied once its <option> exists
      // -- restoreSearchState() (below) runs before this fetch resolves.
      if (savedSearchState) fieldSelect.value = savedSearchState.filters.field;
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
      if (savedSearchState) institutionTypeSelect.value = savedSearchState.filters.institution_type;
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
    if (activeMetro) filters.metro = activeMetro;
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

    lastResults = data.results;
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

  // Coming back from a professor page (via the "Back to search" link or the
  // browser back button -- both just change the hash, so both land here the
  // same way) should restore exactly what was on screen, not start a new
  // search from a blank form. Redisplays the saved results directly rather
  // than re-fetching, so a page click + a data change elsewhere can't make
  // "back" show something different from what was actually there.
  if (savedSearchState) {
    const { filters, page, results, scrollY, advancedOpen } = savedSearchState;
    nameInput.value = filters.name;
    textInput.value = filters.text;
    topicInput.value = filters.topic;
    institutionInput.value = filters.institution;
    cityInput.value = filters.city;
    stateInput.value = filters.state;
    countryInput.value = filters.country;
    recentOnlyInput.checked = filters.recent_only;
    activeMetro = filters.metro;
    advancedDetails.open = advancedOpen;
    // fieldSelect/institutionTypeSelect are restored separately, above,
    // once their options actually exist to select.

    currentPage = page;
    lastResults = results;
    renderResults(results);
    updatePagination(results.length);
    // The saved scroll position only makes sense once the restored results
    // have actually given the page the height to scroll to -- results are
    // synchronous above, but the browser needs a paint before scrollTo lands
    // correctly for content added in the same tick.
    requestAnimationFrame(() => window.scrollTo(0, scrollY));
  } else {
    runSearch(1);
  }

  return function cleanup() {
    savedSearchState = {
      filters: {
        name: nameInput.value,
        text: textInput.value,
        topic: topicInput.value,
        institution: institutionInput.value,
        city: cityInput.value,
        state: stateInput.value,
        country: countryInput.value,
        recent_only: recentOnlyInput.checked,
        field: fieldSelect.value,
        institution_type: institutionTypeSelect.value,
        metro: activeMetro,
      },
      page: currentPage,
      results: lastResults,
      scrollY: window.scrollY,
      advancedOpen: advancedDetails.open,
    };
  };
}
