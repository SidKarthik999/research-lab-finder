// Student profile (#/profile) -- level, school, coursework, skills, prior
// experience, and what they're looking for. Feeds the cold-email drafts
// in a later phase; not shown to professors directly. Bookmarked
// professors live on their own page (#/bookmarks, see views/bookmarks.js)
// rather than here -- kept separate so each page stays focused instead of
// one long scroll mixing "things I saved" with "my own info".

import { el, mount } from "../dom.js";
import {
  ApiError,
  getProfile,
  importResume,
  listLocations,
  listTopics,
  updateName,
  updateProfile,
} from "../api.js";
import { createTagInput } from "../tagInput.js";
import { joinName, splitName } from "../name.js";
import { getCurrentUser, setCurrentUser } from "../session.js";

function formField(labelText, inputEl, hint) {
  const children = [el("label", { for: inputEl.id }, labelText), inputEl];
  if (hint) children.push(el("p", { class: "hint" }, hint));
  return el("div", { class: "field" }, ...children);
}

export async function renderProfileView(container) {
  const user = getCurrentUser();
  if (!user) {
    mount(
      container,
      el("h1", {}, "Your profile"),
      el("p", { class: "empty-state" }, "Sign in to set up your profile."),
      el("a", { href: "#/signin", class: "back-link" }, "Sign in")
    );
    return;
  }

  mount(container, el("p", { class: "empty-state" }, "Loading…"));

  let profile;
  try {
    profile = await getProfile();
  } catch (err) {
    mount(container, el("p", { class: "form-error" }, `Couldn't load your profile: ${err.message}`));
    return;
  }

  const levelSelect = el(
    "select",
    { id: "profile-level", name: "level" },
    el("option", { value: "" }, "Not specified"),
    el("option", { value: "high school" }, "High school"),
    el("option", { value: "undergraduate" }, "Undergraduate"),
    el("option", { value: "graduate" }, "Graduate"),
    el("option", { value: "other" }, "Other")
  );
  if (profile.level) levelSelect.value = profile.level;

  const schoolInput = el("input", {
    type: "text",
    id: "profile-school",
    name: "school",
    value: profile.school || "",
  });
  const gradYearInput = el("input", {
    type: "number",
    id: "profile-grad-year",
    name: "graduation_year",
    value: profile.graduation_year ?? "",
    min: 1950,
    max: 2100,
  });
  // rows sized to what each field realistically holds -- a class list or
  // skills line runs short, prior experience tends to run longest.
  const courseworkInput = el(
    "textarea",
    { id: "profile-coursework", name: "coursework", rows: "3" },
    profile.coursework || ""
  );
  const skillsInput = el(
    "textarea",
    { id: "profile-skills", name: "skills", rows: "3" },
    profile.skills || ""
  );
  const priorExperienceInput = el(
    "textarea",
    { id: "profile-prior-experience", name: "prior_experience", rows: "5" },
    profile.prior_experience || ""
  );
  const lookingForInput = el(
    "textarea",
    { id: "profile-looking-for", name: "looking_for", rows: "4" },
    profile.looking_for || ""
  );

  // interests + location (migration 012, Phase 7): the structured signals
  // Smart search on the search page ranks professors against. Separate
  // from "What you're looking for" above -- that's about the ask (hours a
  // week, summer, remote), this is the subject matter.
  //
  // A search-and-pick tag input, not free text: every value must be a real
  // ResearchTopic name/field/subfield (same suggestions the search page's
  // Research area box uses), so a saved interest is always something
  // matching can actually match. profile.interests is an array now.
  const interestsTagInput = createTagInput({
    initial: Array.isArray(profile.interests) ? profile.interests : [],
    placeholder: "Search a field, subfield, or topic…",
    fetchSuggestions: async (q) => {
      const { topics } = await listTopics(q, undefined, 10);
      return topics;
    },
  });
  // Cascading Country -> State/region -> City dropdowns, populated from
  // real Institution locations (GET /api/locations) so a student can't
  // save a value that doesn't exist in the data. Options load after mount
  // (populateLocationSelects below); until then each shows a placeholder.
  const countrySelect = el(
    "select",
    { id: "profile-country" },
    el("option", { value: "" }, "Not specified")
  );
  const stateSelect = el(
    "select",
    { id: "profile-state", disabled: true },
    el("option", { value: "" }, "Select a country first")
  );
  const citySelect = el(
    "select",
    { id: "profile-city", disabled: true },
    el("option", { value: "" }, "Select a state / region first")
  );

  async function loadStateOptions(country, selected) {
    stateSelect.disabled = !country;
    citySelect.disabled = true;
    citySelect.replaceChildren(el("option", { value: "" }, "Select a state / region first"));
    if (!country) {
      stateSelect.replaceChildren(el("option", { value: "" }, "Select a country first"));
      return;
    }
    let states = [];
    try {
      ({ states } = await listLocations(country));
    } catch {
      // Non-critical -- leave the dropdown empty rather than blocking the form.
    }
    stateSelect.replaceChildren(
      el("option", { value: "" }, states.length ? "Any state / region" : "No regions on file"),
      ...states.map((s) => el("option", { value: s }, s))
    );
    if (selected && states.includes(selected)) stateSelect.value = selected;
  }

  async function loadCityOptions(country, state, selected) {
    const ready = Boolean(country && state);
    citySelect.disabled = !ready;
    if (!ready) {
      citySelect.replaceChildren(el("option", { value: "" }, "Select a state / region first"));
      return;
    }
    let cities = [];
    try {
      ({ cities } = await listLocations(country, state));
    } catch {
      // Non-critical.
    }
    citySelect.replaceChildren(
      el("option", { value: "" }, cities.length ? "Any city" : "No cities on file"),
      ...cities.map((c) => el("option", { value: c }, c))
    );
    if (selected && cities.includes(selected)) citySelect.value = selected;
  }

  async function populateLocationSelects() {
    let countries = [];
    try {
      ({ countries } = await listLocations());
    } catch {
      return; // leave "Not specified" as the only option
    }
    countrySelect.replaceChildren(
      el("option", { value: "" }, "Not specified"),
      ...countries.map((c) => el("option", { value: c.code }, c.name))
    );
    if (profile.country_code) countrySelect.value = profile.country_code;
    await loadStateOptions(countrySelect.value, profile.state);
    await loadCityOptions(countrySelect.value, stateSelect.value, profile.city);
  }

  countrySelect.addEventListener("change", () => {
    loadStateOptions(countrySelect.value);
    loadCityOptions(countrySelect.value, "");
  });
  stateSelect.addEventListener("change", () => {
    loadCityOptions(countrySelect.value, stateSelect.value);
  });

  // Only overwrites a field when the resume actually had something for
  // it -- extract_profile_from_resume() (backend/llm.py) returns null for
  // anything it isn't confident about, and this preserves that: a field
  // the student already filled in manually is left alone rather than
  // blanked out by a resume that simply didn't mention it.
  function applyExtractedProfile(extracted) {
    if (extracted.level) levelSelect.value = extracted.level;
    if (extracted.school) schoolInput.value = extracted.school;
    if (extracted.graduation_year) gradYearInput.value = extracted.graduation_year;
    if (extracted.coursework) courseworkInput.value = extracted.coursework;
    if (extracted.skills) skillsInput.value = extracted.skills;
    if (extracted.prior_experience) priorExperienceInput.value = extracted.prior_experience;
    if (extracted.looking_for) lookingForInput.value = extracted.looking_for;
  }

  const resumeInput = el("input", { type: "file", id: "resume-upload", accept: "application/pdf,.pdf" });
  const resumeStatusEl = el("p", { class: "hint" });
  const resumeImportBtn = el("button", { type: "button", class: "secondary" }, "Fill in from resume");
  resumeImportBtn.addEventListener("click", async () => {
    const file = resumeInput.files[0];
    if (!file) {
      resumeStatusEl.textContent = "Choose a PDF file first.";
      return;
    }
    resumeImportBtn.disabled = true;
    resumeStatusEl.textContent = "Reading your resume…";
    try {
      const extracted = await importResume(file);
      applyExtractedProfile(extracted);
      resumeStatusEl.textContent = "Filled in what we could find below — review it, then save.";
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        resumeStatusEl.textContent = err.message;
      } else if (err instanceof ApiError && err.status === 503) {
        resumeStatusEl.textContent = "Resume import isn't turned on for this site yet.";
      } else {
        resumeStatusEl.textContent = `Couldn't read that resume: ${err.message}`;
      }
    }
    resumeImportBtn.disabled = false;
  });

  // Separate from the StudentProfile form below -- name lives on the
  // account itself (AppUser), not the research-interest form, and is saved
  // through its own PUT /api/me rather than PUT /api/me/profile. Google
  // sign-in already gets a name for free from the profile; this is what
  // lets a password-signup student set theirs, or anyone fix a typo later.
  const { first: initialFirst, last: initialLast } = splitName(user.name);
  const firstNameInput = el("input", { type: "text", id: "account-first-name", name: "first_name", value: initialFirst });
  const lastNameInput = el("input", { type: "text", id: "account-last-name", name: "last_name", value: initialLast });
  const nameErrorEl = el("p", { class: "form-error", hidden: true });
  const nameSuccessEl = el("p", { class: "form-success", hidden: true });
  const nameForm = el(
    "form",
    { class: "form" },
    el(
      "div",
      { class: "name-fields-row" },
      formField("First name", firstNameInput),
      formField("Last name", lastNameInput)
    ),
    nameErrorEl,
    nameSuccessEl,
    el("button", { type: "submit" }, "Save name")
  );
  nameForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    nameErrorEl.hidden = true;
    nameSuccessEl.hidden = true;
    try {
      const updatedUser = await updateName(joinName(firstNameInput.value, lastNameInput.value));
      setCurrentUser(updatedUser);
      nameSuccessEl.textContent = "Name saved.";
      nameSuccessEl.hidden = false;
    } catch (err) {
      nameErrorEl.textContent = err.message;
      nameErrorEl.hidden = false;
    }
  });
  const accountSection = el("div", { class: "card" }, el("h2", {}, "Account"), nameForm);

  const resumeSection = el(
    "div",
    { class: "card" },
    el("h2", {}, "Import from resume"),
    el(
      "p",
      { class: "hint" },
      "Upload a PDF resume and we'll fill in what we can find below from it — nothing is saved until you review it and click Save profile."
    ),
    el("div", { class: "resume-upload-row" }, resumeInput, resumeImportBtn),
    resumeStatusEl
  );

  const errorEl = el("p", { class: "form-error", hidden: true });
  const successEl = el("p", { class: "form-success", hidden: true });

  const form = el(
    "form",
    { class: "form form-wide" },
    el(
      "div",
      { class: "profile-fields-row" },
      formField("Level", levelSelect),
      formField("School", schoolInput),
      formField("Expected graduation year", gradYearInput)
    ),
    formField("Relevant coursework", courseworkInput, "Classes, labs, or projects relevant to research."),
    formField("Skills / techniques", skillsInput, "Programming languages, lab techniques, tools you know."),
    formField("Prior research or work experience", priorExperienceInput),
    formField("What you're looking for", lookingForInput, "Used to help write cold emails that actually fit."),
    formField(
      "Research interests",
      interestsTagInput.element,
      "Type to search, then pick from the list. Add a broad field (“Neuroscience”) or a specific topic (“Optogenetics”) — Smart search on the search page ranks professors by how well they match these."
    ),
    el(
      "div",
      { class: "profile-fields-row" },
      formField("Country", countrySelect),
      formField("State / region", stateSelect),
      formField("City", citySelect)
    ),
    el(
      "p",
      { class: "hint" },
      "Where you can realistically work — Smart search ranks nearby professors higher. Pick a country to narrow the region list, and a region to narrow the cities. Leave any level blank to match anywhere within the one above."
    ),
    errorEl,
    successEl,
    el("button", { type: "submit" }, "Save profile")
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    successEl.hidden = true;
    try {
      await updateProfile({
        level: levelSelect.value || null,
        school: schoolInput.value || null,
        graduation_year: gradYearInput.value ? Number(gradYearInput.value) : null,
        coursework: courseworkInput.value || null,
        skills: skillsInput.value || null,
        prior_experience: priorExperienceInput.value || null,
        looking_for: lookingForInput.value || null,
        interests: interestsTagInput.getValues(),
        city: citySelect.value || null,
        state: stateSelect.value || null,
        country_code: countrySelect.value || null,
      });
      successEl.textContent = "Profile saved.";
      successEl.hidden = false;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  mount(
    container,
    el("h1", {}, "Your profile"),
    accountSection,
    el("h2", {}, "Your info"),
    el(
      "p",
      { class: "hint" },
      "This information personalizes the cold emails you generate and powers Smart search on the search page — it's never shown to professors directly."
    ),
    resumeSection,
    form
  );

  // Fills the location dropdowns and re-selects the student's saved
  // country/state/city -- runs after mount so the form is on screen
  // immediately rather than waiting on three sequential requests.
  populateLocationSelects();
}
