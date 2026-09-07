// A "search and select from a fixed vocabulary" multi-value input: type to
// get suggestions, pick one to add it as a removable chip, and you can
// only ever hold values that came from the suggestion list -- no free
// text. Built for the profile page's Research interests field (options
// come from /api/topics, i.e. real ResearchTopic name/field/subfield
// values) so a saved interest is always something matching can actually
// match against; the location dropdowns on the same page exist for the
// same reason.
//
// Returns { element, getValues }. getValues() is the array of selected
// strings, in the order they were added.

import { el } from "./dom.js";

export function createTagInput({ initial = [], fetchSuggestions, placeholder = "" } = {}) {
  const selected = [...initial];

  const chipsRow = el("div", { class: "tag-input-chips" });
  const textInput = el("input", {
    type: "text",
    class: "tag-input-text",
    placeholder,
    autocomplete: "off",
    "aria-label": placeholder || "Add an item",
  });
  const suggestionList = el("ul", { class: "autocomplete-list", hidden: true });
  const field = el(
    "div",
    { class: "tag-input" },
    chipsRow,
    el("div", { class: "autocomplete" }, textInput, suggestionList)
  );

  let suggestions = [];
  let activeIndex = -1;
  let debounceTimer;

  function renderChips() {
    chipsRow.replaceChildren(
      ...selected.map((value) =>
        el(
          "span",
          { class: "tag-chip" },
          value,
          el(
            "button",
            {
              type: "button",
              class: "tag-chip-remove",
              "aria-label": `Remove ${value}`,
              onClick: () => remove(value),
            },
            "×"
          )
        )
      )
    );
  }

  function closeSuggestions() {
    suggestionList.hidden = true;
    activeIndex = -1;
  }

  function renderSuggestions() {
    // Anything already picked is filtered out so it can't be added twice.
    const available = suggestions.filter((s) => !selected.includes(s));
    suggestionList.replaceChildren(
      ...available.map((value, i) =>
        el(
          "li",
          {
            class: i === activeIndex ? "active" : null,
            // mousedown, not click: fires before the input's blur so the
            // value is added before the blur handler closes the list.
            onMousedown: (event) => {
              event.preventDefault();
              add(value);
            },
          },
          value
        )
      )
    );
    suggestionList.hidden = available.length === 0;
  }

  function add(value) {
    if (!selected.includes(value)) selected.push(value);
    textInput.value = "";
    suggestions = [];
    closeSuggestions();
    renderChips();
    textInput.focus();
  }

  function remove(value) {
    const i = selected.indexOf(value);
    if (i !== -1) selected.splice(i, 1);
    renderChips();
    textInput.focus();
  }

  textInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = textInput.value.trim();
    if (!q) {
      suggestions = [];
      closeSuggestions();
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        suggestions = await fetchSuggestions(q);
        activeIndex = -1;
        renderSuggestions();
      } catch {
        suggestions = [];
        closeSuggestions();
      }
    }, 200);
  });

  textInput.addEventListener("keydown", (event) => {
    const available = suggestions.filter((s) => !selected.includes(s));
    if (event.key === "Backspace" && !textInput.value && selected.length) {
      remove(selected[selected.length - 1]);
      return;
    }
    if (suggestionList.hidden || available.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = (activeIndex + 1) % available.length;
      renderSuggestions();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = (activeIndex - 1 + available.length) % available.length;
      renderSuggestions();
    } else if (event.key === "Enter") {
      // Only ever commits a real suggestion -- a plain typed string with
      // no match does nothing, which is the whole point of this control.
      event.preventDefault();
      if (activeIndex >= 0) add(available[activeIndex]);
    } else if (event.key === "Escape") {
      closeSuggestions();
    }
  });

  textInput.addEventListener("blur", () => setTimeout(closeSuggestions, 120));

  renderChips();

  return {
    element: field,
    getValues: () => [...selected],
  };
}
