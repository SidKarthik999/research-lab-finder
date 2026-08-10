// Admin dashboard (#/admin): flagged-issue queue + basic usage metrics.
// Gated client-side on the current user's is_admin flag (from /api/me, see
// backend/auth.py's _user_public) purely so a non-admin who lands here
// directly gets a clean "access denied" message instead of a raw 403 --
// the actual enforcement is server-side, in backend/admin.py's
// require_admin, which every /api/admin/* route depends on regardless of
// what this page does.

import { el, mount } from "../dom.js";
import { ApiError, deleteAdminFlag, getAdminFlags, getAdminMetrics, setAdminFlagResolved } from "../api.js";
import { getCurrentUser } from "../session.js";

function statCard(label, value, hint) {
  return el(
    "div",
    { class: "stat-card" },
    el("p", { class: "stat-value" }, String(value)),
    el("p", { class: "stat-label" }, label),
    hint ? el("p", { class: "hint" }, hint) : null
  );
}

function pct(part, total) {
  if (!total) return "0%";
  return `${Math.round((part / total) * 100)}%`;
}

function sparkline(daily) {
  const max = Math.max(1, ...daily.map((d) => d.count));
  return el(
    "div",
    { class: "sparkline" },
    ...daily.map((d) =>
      el("div", {
        class: "sparkline-bar",
        style: `height: ${Math.max(4, (d.count / max) * 100)}%`,
        // "title" is the accessible/fallback tooltip (screen readers, and
        // browsers where the CSS ::after tooltip below doesn't fire); the
        // data-tooltip attribute drives that CSS tooltip, which shows
        // instantly on hover instead of the browser's ~1s native delay.
        title: `${d.date}: ${d.count}`,
        "data-tooltip": `${d.date}: ${d.count}`,
      })
    )
  );
}

function renderMetrics(metrics) {
  const { signups, ai_usage, bookmarks, data_coverage } = metrics;

  return el(
    "div",
    { class: "admin-metrics" },
    el(
      "div",
      { class: "card" },
      el("h2", {}, "Signups"),
      el(
        "div",
        { class: "stat-row" },
        statCard("Total accounts", signups.total),
        statCard("Verified", `${signups.verified} (${pct(signups.verified, signups.total)})`)
      ),
      el("p", { class: "hint" }, "Signups per day, last 30 days"),
      sparkline(signups.daily_last_30_days)
    ),
    el(
      "div",
      { class: "card" },
      el("h2", {}, "Cold email usage"),
      // AI summaries are deliberately not shown here -- they're generated
      // once per professor and cached forever (see ai_summary caching in
      // backend/main.py's professor_summary), so a summary count doesn't
      // track ongoing usage or cost the way cold email (regenerated fresh
      // on every request) does. Still logged in LlmUsage either way, in
      // case that changes.
      el(
        "div",
        { class: "stat-row" },
        statCard("Cold emails (all time)", ai_usage.total_by_kind.cold_email || 0),
        statCard("Cold emails (7 days)", ai_usage.last_7_days_by_kind.cold_email || 0)
      )
    ),
    el(
      "div",
      { class: "card" },
      el("h2", {}, "Bookmarks"),
      el("div", { class: "stat-row" }, statCard("Total bookmarks", bookmarks.total)),
      bookmarks.top_professors.length
        ? el(
            "div",
            { class: "admin-table-wrap" },
            el(
              "table",
              { class: "admin-table" },
              el(
                "thead",
                {},
                el("tr", {}, el("th", {}, "Professor"), el("th", {}, "Institution"), el("th", {}, "Bookmarks"))
              ),
              el(
                "tbody",
                {},
                ...bookmarks.top_professors.map((p) =>
                  el(
                    "tr",
                    {},
                    el("td", {}, el("a", { href: `#/professor/${p.professor_id}` }, p.professor_name || "Unknown")),
                    el("td", {}, p.institution_name || "—"),
                    el("td", {}, String(p.bookmark_count))
                  )
                )
              )
            )
          )
        : el("p", { class: "empty-state" }, "No bookmarks yet.")
    ),
    el(
      "div",
      { class: "card" },
      el("h2", {}, "Data coverage"),
      el(
        "div",
        { class: "stat-row" },
        statCard("Institutions", data_coverage.institutions),
        statCard("Professors", data_coverage.professors),
        statCard("Publications", data_coverage.publications)
      ),
      el(
        "div",
        { class: "stat-row" },
        statCard(
          "With ORCID",
          pct(data_coverage.professors_with_orcid, data_coverage.professors),
          `${data_coverage.professors_with_orcid} professors`
        ),
        statCard(
          "With email",
          pct(data_coverage.professors_with_email, data_coverage.professors),
          `${data_coverage.professors_with_email} professors`
        ),
        statCard(
          "With topics",
          pct(data_coverage.professors_with_topics, data_coverage.professors),
          `${data_coverage.professors_with_topics} professors`
        ),
        statCard(
          "With publications",
          pct(data_coverage.professors_with_publications, data_coverage.professors),
          `${data_coverage.professors_with_publications} professors`
        ),
        // A running total, not a rate -- a summary is cached forever once
        // generated (see backend/main.py's professor_summary), so this
        // reads as "how much of the catalog has one so far".
        statCard(
          "With AI summary",
          pct(data_coverage.professors_with_ai_summary, data_coverage.professors),
          `${data_coverage.professors_with_ai_summary} professors`
        )
      )
    )
  );
}

const CHECK_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
const REOPEN_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>';
const TRASH_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';

function iconButton(html, label, extraClass) {
  return el(
    "button",
    { type: "button", class: `ghost icon-button ${extraClass || ""}`, "aria-label": label, title: label },
    // Same "html" escape hatch as the search button's icon in
    // frontend/views/search.js -- fixed, trusted SVG strings, never
    // user-controlled data.
    el("span", { class: "btn-icon", html })
  );
}

// Open reports first, most recent within each group next -- mirrors
// get_recent_flags()'s ORDER BY in src/database.py, so toggling a flag's
// resolved state client-side (no full dashboard refetch, same as delete)
// re-sorts consistently with what a fresh page load would show.
function sortFlags(list) {
  return [...list].sort((a, b) => {
    const aOpen = a.resolved_at ? 1 : 0;
    const bOpen = b.resolved_at ? 1 : 0;
    if (aOpen !== bOpen) return aOpen - bOpen;
    return new Date(b.created_at) - new Date(a.created_at);
  });
}

// Stateful (unlike the pure statCard/sparkline/renderMetrics helpers above)
// because deleting/resolving a flag needs to update what's on screen
// without re-fetching the whole dashboard -- same shape as
// renderBookmarkList in frontend/views/bookmarks.js, including no
// confirm() prompt before deleting, consistent with that same "Remove
// bookmark" button.
function renderFlagsSection(container, flags) {
  flags = sortFlags(flags);

  function render() {
    if (flags.length === 0) {
      mount(container, el("p", { class: "empty-state" }, "No flags reported yet."));
      return;
    }

    mount(
      container,
      el(
        "div",
        { class: "admin-table-wrap" },
        el(
          "table",
          { class: "admin-table" },
          el(
            "thead",
            {},
            el(
              "tr",
              {},
              el("th", {}, "Professor"),
              el("th", {}, "Reported issues"),
              el("th", {}, "Details"),
              el("th", {}, "Reported by"),
              el("th", {}, "When"),
              el("th", {}, "Status"),
              el("th", {})
            )
          ),
          el("tbody", {}, ...flags.map(renderRow))
        )
      )
    );
  }

  function renderRow(flag) {
    const resolveBtn = iconButton(
      flag.resolved_at ? REOPEN_ICON : CHECK_ICON,
      flag.resolved_at ? "Mark as open" : "Mark as resolved"
    );
    resolveBtn.addEventListener("click", async () => {
      resolveBtn.disabled = true;
      try {
        const result = await setAdminFlagResolved(flag.id, !flag.resolved_at);
        flag.resolved_at = result.resolved_at;
        flags = sortFlags(flags);
        render();
      } catch {
        resolveBtn.disabled = false;
      }
    });

    const deleteBtn = iconButton(TRASH_ICON, "Delete this flag", "delete-icon");
    deleteBtn.addEventListener("click", async () => {
      deleteBtn.disabled = true;
      try {
        await deleteAdminFlag(flag.id);
        flags = flags.filter((f) => f.id !== flag.id);
        render();
      } catch {
        deleteBtn.disabled = false;
      }
    });

    return el(
      "tr",
      {},
      el(
        "td",
        {},
        el("a", { href: `#/professor/${flag.professor_id}` }, flag.professor_name || "Unknown"),
        flag.institution_name ? el("div", { class: "hint" }, flag.institution_name) : null
      ),
      el("td", {}, flag.reason_labels.length ? flag.reason_labels.join("; ") : "—"),
      el("td", {}, flag.details || "—"),
      el("td", {}, flag.reporter_email || "Anonymous"),
      el("td", {}, new Date(flag.created_at).toLocaleString()),
      el(
        "td",
        {},
        el("span", { class: `status-badge ${flag.resolved_at ? "resolved" : "open"}` }, flag.resolved_at ? "Resolved" : "Open")
      ),
      el("td", { class: "admin-row-actions" }, resolveBtn, deleteBtn)
    );
  }

  render();
}

export async function renderAdminView(container) {
  const user = getCurrentUser();
  if (!user || !user.is_admin) {
    mount(
      container,
      el("h1", {}, "Admin"),
      el("p", { class: "empty-state" }, "You don't have access to this page."),
      el("a", { href: "#/", class: "back-link" }, "← Back to search")
    );
    return;
  }

  mount(container, el("h1", {}, "Admin"), el("p", { class: "empty-state" }, "Loading…"));

  let flagsData;
  let metricsData;
  try {
    [flagsData, metricsData] = await Promise.all([getAdminFlags(), getAdminMetrics()]);
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? "You don't have access to this page."
        : `Couldn't load the admin dashboard: ${err.message}`;
    mount(
      container,
      el("h1", {}, "Admin"),
      el("p", { class: "empty-state" }, message),
      el("a", { href: "#/", class: "back-link" }, "← Back to search")
    );
    return;
  }

  const flagsListEl = el("div", { class: "admin-flags-list" });
  mount(
    container,
    el("h1", {}, "Admin"),
    renderMetrics(metricsData),
    el("div", { class: "card" }, el("h2", {}, "Flagged issues"), flagsListEl)
  );
  renderFlagsSection(flagsListEl, flagsData.flags);
}
