// Admin dashboard (#/admin): flagged-issue queue + basic usage metrics.
// Gated client-side on the current user's is_admin flag (from /api/me, see
// backend/auth.py's _user_public) purely so a non-admin who lands here
// directly gets a clean "access denied" message instead of a raw 403 --
// the actual enforcement is server-side, in backend/admin.py's
// require_admin, which every /api/admin/* route depends on regardless of
// what this page does.

import { el, mount } from "../dom.js";
import { ApiError, getAdminFlags, getAdminMetrics } from "../api.js";
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
      el("h2", {}, "AI feature usage"),
      el(
        "div",
        { class: "stat-row" },
        statCard("AI summaries (all time)", ai_usage.total_by_kind.ai_summary || 0),
        statCard("Cold emails (all time)", ai_usage.total_by_kind.cold_email || 0),
        statCard("AI summaries (7 days)", ai_usage.last_7_days_by_kind.ai_summary || 0),
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
        )
      )
    )
  );
}

function renderFlags(flags) {
  if (flags.length === 0) {
    return el("p", { class: "empty-state" }, "No flags reported yet.");
  }

  return el(
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
          el("th", {}, "When")
        )
      ),
      el(
        "tbody",
        {},
        ...flags.map((flag) =>
          el(
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
            el("td", {}, new Date(flag.created_at).toLocaleString())
          )
        )
      )
    )
  );
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

  mount(
    container,
    el("h1", {}, "Admin"),
    renderMetrics(metricsData),
    el("div", { class: "card" }, el("h2", {}, "Flagged issues"), renderFlags(flagsData.flags))
  );
}
