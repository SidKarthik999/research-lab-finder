// One function per backend endpoint, so no view constructs a fetch() call
// or a query string by hand. request() centralizes credentials, JSON
// encoding/decoding, and error shape -- a failed request throws ApiError
// with the HTTP status attached, so callers can branch on e.g. 503
// ("not configured yet") without string-matching a message.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function toQueryString(params) {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null || value === "") continue;
    usp.set(key, value);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

async function parseJsonResponse(response) {
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const message = (data && data.detail) || `Request failed: ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return data;
}

async function request(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return parseJsonResponse(response);
}

// Separate from request() -- a file upload sends multipart/form-data, not
// JSON, and the browser has to set that Content-Type header itself (it
// includes a boundary value request() has no way to generate), so this
// can't just be another `body` shape through the same function.
async function uploadFile(path, file, fieldName) {
  const formData = new FormData();
  formData.append(fieldName, file);
  const response = await fetch(path, { method: "POST", credentials: "include", body: formData });
  return parseJsonResponse(response);
}

// --- search ---

export function searchProfessors(params) {
  return request(`/api/search${toQueryString(params)}`);
}

export function listInstitutions(q, limit = 10) {
  return request(`/api/institutions${toQueryString({ q, limit })}`);
}

export function listTopics(q, field, limit = 10) {
  return request(`/api/topics${toQueryString({ q, field, limit })}`);
}

export function listFields() {
  return request("/api/fields");
}

export function listInstitutionTypes() {
  return request("/api/institution-types");
}

export function listMetroAreas() {
  return request("/api/metro-areas");
}

// --- professors ---

export function getProfessor(id) {
  return request(`/api/professors/${id}`);
}

export function getProfessorPublications(id) {
  return request(`/api/professors/${id}/publications`);
}

export function generateProfessorSummary(id) {
  return request(`/api/professors/${id}/summary`, { method: "POST" });
}

export function generateColdEmail(id) {
  return request(`/api/professors/${id}/cold-email`, { method: "POST" });
}

export function getColdEmailDrafts(id) {
  return request(`/api/professors/${id}/cold-email`);
}

export function updateColdEmailDraft(id, draftId, body) {
  return request(`/api/professors/${id}/cold-email`, { method: "PUT", body: { draft_id: draftId, body } });
}

export function listFlagReasons() {
  return request("/api/flag-reasons");
}

export function flagProfessor(id, { reasons, details }) {
  return request(`/api/professors/${id}/flag`, { method: "POST", body: { reasons, details } });
}

export function bookmarkProfessor(id) {
  return request(`/api/professors/${id}/bookmark`, { method: "POST" });
}

export function unbookmarkProfessor(id) {
  return request(`/api/professors/${id}/bookmark`, { method: "DELETE" });
}

// --- auth ---

export function getGoogleClientId() {
  return request("/api/auth/google/client-id");
}

export function signInWithGoogle(idToken) {
  return request("/api/auth/google", { method: "POST", body: { id_token: idToken } });
}

export function signUp(email, password, name) {
  return request("/api/auth/signup", { method: "POST", body: { email, password, name } });
}

export function verifyEmail(token) {
  return request("/api/auth/verify-email", { method: "POST", body: { token } });
}

export function logIn(email, password) {
  return request("/api/auth/login", { method: "POST", body: { email, password } });
}

export function forgotPassword(email) {
  return request("/api/auth/forgot", { method: "POST", body: { email } });
}

export function resetPassword(token, password) {
  return request("/api/auth/reset", { method: "POST", body: { token, password } });
}

export function logOut() {
  return request("/api/auth/logout", { method: "POST" });
}

// A signed-out visitor hitting /api/me is the normal case, not an error --
// swallow the 401 here so every caller doesn't have to.
export async function getMe() {
  try {
    return await request("/api/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function updateName(name) {
  return request("/api/me", { method: "PUT", body: { name } });
}

export function getProfile() {
  return request("/api/me/profile");
}

export function updateProfile(data) {
  return request("/api/me/profile", { method: "PUT", body: data });
}

export function getBookmarks() {
  return request("/api/me/bookmarks");
}

export function importResume(file) {
  return uploadFile("/api/me/resume", file, "file");
}
