# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal, single-user Streamlit dashboard (Vietnamese UI) that visualizes focus-session data
exported from the **Forest** app, plus two optional secondary sources: work calendar events (via
CalDAV/iCloud) and reading/watch progress (via Apple Reminders export). It's retrospective only —
no goal-setting, no reminders, just looking back at what Forest already recorded. See the app's
own **Hướng dẫn** (Help) tab for user-facing feature documentation — don't duplicate that content
here.

The entire application lives in one file, `app.py` (~5500 lines). There is no separate
frontend/backend split; Streamlit's script-rerun model *is* the architecture.

## Commands

There is no build step, linter, or test suite in this repo.

```bash
# Syntax-check after every edit (cheap, catches typos before running anything)
python3 -c "import ast; ast.parse(open('app.py').read())"

# Run the app locally (needs .streamlit/secrets.toml populated, see secrets.toml.example)
streamlit run app.py
```

### Verifying a change without hitting Supabase/iCloud

There's no committed test suite, and the sandbox generally can't reach `*.supabase.co` or
`caldav.icloud.com`. The working pattern for verifying changes in this repo is to run the *real*
`app.py` against fakes, then drive it with Playwright:

1. Copy `app.py` to a scratch file and monkeypatch `_get_supabase()` (and `_get_caldav_client()`
   if relevant) to return an in-memory fake client with `.table(name).select/insert/upsert/
   delete().execute()` semantics, seeded with representative sample data.
2. `streamlit run <scratch_app>.py --server.port <N> --server.headless true` in the background.
3. Drive it with `playwright` (`p.chromium.launch(executable_path='/opt/pw-browsers/chromium')`),
   checking `"Traceback" not in page.inner_text('body')` across every top-level nav page as a
   regression sweep, plus targeted checks (bounding boxes, computed styles, screenshots) for the
   specific change.
4. For anything with more than 2-3 branches of logic (date-comparison math, template selection,
   CSV parsing), also write a quick offline Python script that imports/execs just the function
   under test with synthetic `pandas` DataFrames — faster than round-tripping through Streamlit
   for pure-logic bugs.

Regenerate the scratch harness fresh each session rather than assuming one persists — it isn't
committed to the repo.

## Architecture

### Everything is one dispatch function keyed on `st.query_params`

Top-level navigation is a flat dict `NAV` (page name → Material icon) rendered as a
`st.segmented_control`, backed by `st.session_state["nav"]` seeded once per session from
`st.query_params["nav"]` and written back after every change (this is what makes deep-links like
`?nav=Hôm nay&day=2026-07-04` work — session state, not the widget, is the source of truth). The
page body is a long `if nav == "X": ... elif nav == "Y": ...` chain near the bottom of the file.
"Báo cáo" has a second-level `BAOCAO_SUBS` list (Tổng quan/Tuần/Tháng/Năm/Dự án) using the exact
same seed-from-query-param pattern under `?sub=`. `day_picker()` does the same for `?day=`.

When reordering nav items or sub-tabs, the list order in `NAV`/`BAOCAO_SUBS` **is** the display
order — the physical order of the `if/elif` branches doesn't need to match and isn't worth
reshuffling for its own sake.

### Data layer: Supabase-only, one `load_*`/`save_*` pair per table

No local CSV storage — `load_db()`, `load_mapping()`, `load_deleted()`, `load_notes()`,
`load_work_calendar()`, `load_reading_log()`, `load_settings()` each wrap a Supabase table read,
cached with `@st.cache_data`; the matching `save_*`/`sync_*` writes and then calls
`st.cache_data.clear()`. `work_calendar` (CalDAV) and `reading_log` (Reminders CSV import) are
optional secondary sources — code touching them must degrade gracefully (empty DataFrame with the
right columns, not a crash) when the tables are empty or unconfigured, since a real user may not
have set either up. `supabase_schema.sql` is the source of truth for table shape; keep it in sync
with any new `load_*`/`save_*` pair.

`prep_analysis_data()` is the one place that joins/derives the analysis-ready DataFrame (adds
`Tuần`/`Tháng`/`Năm`/`Thứ` columns etc.) that every report page reads from — it must return a
DataFrame with the right columns even when empty, since several pages branch on `df.empty` rather
than crashing.

### Timezone: always `_today_vn()`, never bare `date.today()`

`APP_TZ = ZoneInfo("Asia/Ho_Chi_Minh")` is fixed regardless of server locale (Streamlit Cloud runs
UTC). `date.today()` on a UTC server is a whole day behind Vietnam for 7 hours every day — this
was a real, previously-shipped bug. Any code that needs "today" (default day, "is this the current
week/month/year" checks, backup-reminder day counting) must go through `_today_vn()`.

### Theming: CSS custom properties driven by `IS_DARK`, not two stylesheets

`IS_DARK` is derived once from `st.context.theme.type` at module load. A block of `--token`
CSS custom properties (`--bg`, `--card`, `--text`, `--text-2/3/4`, `--border`, `--divider`,
`--accent`, `--accent-rgb`, `--accent-dark`) is injected as `:root{...}`, with light/dark values
chosen per `IS_DARK`. The large main CSS block is a *plain string*, not an f-string — don't convert
it to one (hundreds of literal `{`/`}` in CSS rules would all need escaping). Custom accent color
(`ACCENT`, from `ACCENT_PRESETS`, persisted in the `settings` table) flows through the same
`var(--accent...)` tokens plus a few Python-side derived constants (`ACCENT_RGB`, `ACCENT_DARK`)
for places CSS vars can't reach (Altair/Plotly chart colors, the Quill iframe's injected CSS,
which is a separate document and can't see the main page's `:root`).

Any hardcoded hex color added to a new UI element is very likely a dark-mode bug waiting to
happen — prefer the existing `var(--token)` set.

### Numbered `st.expander` sections are a UI convention, not incidental

Report pages (Tổng quan/Tuần/Tháng/Năm/Dự án, Chi tiết ở Sách/Gundam) are built from a sequence of
`st.expander("N. Tên mục", ...)`. When inserting/removing a section, renumber the following ones
in the same page. `render_stat_panel(hero_items, sections, footer, groups, card_style)` is the
shared "hero numbers + labeled chip rows" component reused across nearly every one of these pages
— extend it rather than hand-rolling a new card layout, and use `card_style` for one-off
margin/width overrides instead of touching its shared defaults (they affect every call site).

### Keyboard shortcuts live in one injected JS blob

`_inject_keyboard_shortcuts()` (a big `components.html(js, height=0)` call) handles global
shortcuts (1-7 nav, Shift+1..5 Báo cáo sub-tabs indexed off `BAOCAO_SUBS`, `n`/`f`/`r`/`l`/`/`/`?`/
arrow keys/`[`/`]`). `_inject_note_editor_shortcuts()` is injected separately *inside* the Quill
iframe's own document, because keydowns there don't bubble to the parent frame. Sub-tab shortcuts
are index-driven off the same list used for rendering, so reordering `BAOCAO_SUBS` doesn't require
touching the shortcut handler — only doc/help-text updates.

### The "Hướng dẫn" (Help) tab is user-facing documentation, treat it as content, not code

Don't rewrite its explanatory text as a side effect of an unrelated change; update it deliberately
when a change actually affects what a user sees or how a feature works, and add a `guide_update()`
entry when it's a notable behavior change.

## Git workflow for this repo

Development happens on branch `claude/app-features-overview-pr-h75608` against `famxuannam/
forest-dashboard`. PRs are squash-merged one at a time. **Do not open or merge a PR until the user
explicitly says so** — commit and push to the branch after verifying, then wait.

Because PRs are squashed, the branch's history diverges from `origin/main` after every merge. Before
starting new work (or before committing, if `origin/main` has moved), restart clean:
```bash
git fetch origin main
git checkout -B claude/app-features-overview-pr-h75608 origin/main
# re-apply/cherry-pick any not-yet-merged local work here
git push --force-with-lease -u origin claude/app-features-overview-pr-h75608
```
Clean up any generated sample data files (`database.csv`, `mapping.csv`, `notes.csv`,
`__pycache__`) before committing — they're a byproduct of local testing, not app output.
