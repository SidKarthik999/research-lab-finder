// AppUser.name stays a single column (Google sign-in already only gives one
// combined name string, so splitting storage into first_name/last_name
// would mean reconstructing one from the other there anyway) -- these are
// presentation-only helpers shared between the signup form and the profile
// page's "Account" section, so the split/join convention stays consistent
// between the two places it's used.

export function splitName(fullName) {
  const trimmed = (fullName || "").trim();
  if (!trimmed) return { first: "", last: "" };
  const spaceIndex = trimmed.indexOf(" ");
  // No space -- a single-word name (e.g. "Cher", or a partial entry mid-
  // typing) goes entirely into "first" rather than splitting a word in half.
  if (spaceIndex === -1) return { first: trimmed, last: "" };
  // Everything after the first space is "last", not just the next word --
  // "Mary Jane Smith" becomes first="Mary", last="Jane Smith" rather than
  // silently dropping "Smith". Common convention for collapsing a
  // multi-word name into exactly two fields.
  return { first: trimmed.slice(0, spaceIndex), last: trimmed.slice(spaceIndex + 1).trim() };
}

export function joinName(first, last) {
  return [first, last].map((part) => part.trim()).filter(Boolean).join(" ");
}
