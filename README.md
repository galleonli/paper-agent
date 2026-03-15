<div align="center">

# 🔥 Paper Agent

**A self-hosted paper inbox for arXiv discovery and Google Scholar alerts.**

_Discover relevant arXiv papers with explainable, interest-aware selection (instead of raw keyword matching).
Keep Google Scholar Alert emails in a separate inbox, then write local notes, daily and weekly digests, related-paper links, and BibTeX/RIS exports._

[**Quick start**](#quick-start) · [**Key features**](#key-features) · [**Raycast at a glance**](#raycast-at-a-glance) · [**Raycast extension**](#raycast-extension) · [**Configuration**](#configuration-user-settings-first) · [**Google Scholar setup**](#google-scholar-setup) · [**Advanced tuning**](#advanced-tuning-legacy-compatibility) · [**Troubleshooting**](#troubleshooting)

<br/>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-API-orange.svg)](https://arxiv.org/help/api)
[![YAML](https://img.shields.io/badge/config-YAML-red.svg)](config.example.yaml)
[![Self-hosted](https://img.shields.io/badge/self--hosted-✓-green.svg)](#key-features)
[![Raycast](https://img.shields.io/badge/Raycast-extension-6366f1.svg)](#raycast-extension)

</div>

---

## Key features

- **Daily Precision (arXiv):** Explainable filtering and ranking with required keywords (`OR` match in title or abstract), exclude keywords, and seed support.
- **Scholar Inbox (email):** Ingest Google Scholar Alert emails from `mbox`, `.eml` directories, or Gmail IMAP into a separate inbox.
- **Weekly review layer:** Generate weekly digests with top topics, top categories, frequent authors, highlighted papers, and an auto-written summary sentence.
- **Related local papers:** Backfill note metadata with explainable local-paper links, then surface them in Raycast detail panes and action panels.
- **Raycast workflow:** Browse today, recent, search, favorites, reading queue, run the pipeline, install/remove daily schedule, inspect schedule status, and open the paper directory.
- **Idempotent and catch-up safe:** Re-running the same window produces 0 duplicates; missed days can be recovered safely.
- **Workflow-friendly outputs:** Generate local notes, daily/weekly digests, and optional BibTeX/RIS exports.

---

## Raycast at a glance

If you mainly use Raycast, these are the implemented commands:

- **Run & automation:** `Run Paper Agent`, `Install Daily Schedule` (04:00 + catch-up), `Remove Daily Schedule`, `Daily Schedule Status`
- **Browse & search:** `Today Papers`, `Recent Papers`, `Search Papers`
- **Workflow:** `Favorite Papers`, `Reading Queue`, `Open Paper Directory`
- **In-list actions:** open paper/note, related-paper actions, mark read/unread, add/remove favorites, add/remove reading queue

Details and setup: [Raycast extension](#raycast-extension).

---

## Quick start

```bash
git clone https://github.com/galleonli/paper-agent.git
cd paper-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python -m paper_agent run --config config.yaml
```

Edit `config.yaml` as needed (e.g. `interests.seeds`, `selection`, `export`, `advanced`). If you use **Run Paper Agent** from Raycast, or install the macOS daily schedule from Raycast, treat extension **Preferences as the primary place** to set runtime fields such as direction, delivery, summarize, sources, and `policy.type`. Use `config.yaml` mainly for the sections Raycast does not override. For CLI/cron runs, add those runtime sections to config or rely on defaults.

Useful next links:

- Need Gmail / Google Scholar email ingestion? Start with [Google Scholar setup](#google-scholar-setup).
- Want the Raycast workflow and scheduled runs? Jump to [Raycast extension](#raycast-extension).
- Curious about legacy `policy.*` or `autotune.*` knobs in `config.yaml`? Read [Advanced tuning (legacy compatibility)](#advanced-tuning-legacy-compatibility) before changing them.

First run writes notes, daily digest, weekly digest, and any configured exports; second run with same state prints no new papers.

OpenAI summarization is optional. For CLI/cron, set `OPENAI_API_KEY` in your environment if needed. For Raycast, prefer filling **OpenAI API Key** directly in extension Preferences. If no key is available, the pipeline still runs and falls back to abstract/snippet-based notes.

### CLI commands

| Command                                                              | Description                                                    |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| `python -m paper_agent run --config config.yaml`                     | Run the full pipeline once.                                    |
| `python -m paper_agent today --json --config config.yaml`            | Print today's local paper entries as JSON.                     |
| `python -m paper_agent list --json [--limit N] --config config.yaml` | Print recent local paper entries as JSON (optional `--limit`). |
| `python -m paper_agent open <paper_id> --config config.yaml`         | Open the local Markdown note for the given paper id.           |
| `python -m paper_agent search --query "<text>" --json --config config.yaml` | Search the local library JSON entries and print matches as JSON. |

### Run daily (automatic)

You can run the agent every day via **cron** (or your system scheduler). Set `CRON_TZ` for your timezone, then add a daily job:

```bash
CRON_TZ=Europe/Berlin
0 8 * * * cd /path/to/paper-agent && .venv/bin/python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
```

Replace `/path/to/paper-agent` with your repo path. The example runs at 08:00 local time; change `0 8` to another hour if needed.

On macOS, the Raycast extension also includes **Install Daily Schedule**, which installs a `launchd` job that:

- runs the same shared runner script every day at **04:00**
- runs once after boot/login if the Mac was off at 04:00 and the day has not succeeded yet
- skips duplicate runs after a successful run on the same day
- sends a macOS notification when the scheduled run succeeds or fails
- writes schedule artifacts under `~/Library/Application Support/PaperAgent/`
- writes launch logs under `~/Library/Logs/PaperAgent/`

The extension also includes:

- **Remove Daily Schedule** to uninstall the `launchd` job in one step while keeping logs and status history
- **Daily Schedule Status** to check whether the schedule is installed and whether today's scheduled run succeeded, failed, or was skipped

Re-run **Install Daily Schedule** after changing Raycast Preferences that affect the pipeline, because the scheduled job refreshes its runtime config and secrets from the current preferences at install time. More options: [Scheduling](#scheduling).

---

## Raycast extension

A [Raycast](https://www.raycast.com/) extension lets you run the pipeline, browse today/recent papers, search the local library, inspect related local papers, manage favorites and a reading queue, schedule daily runs on macOS, and open the paper directory from a Paper Agent workflow.

**The extension lives in a separate repository:** [paper-agent-raycast](https://github.com/galleonli/paper-agent-raycast) (or your fork). Install the **Paper Agent core** (this repo) first, then install the extension from the Raycast Store or from the extension repo.

**Status:** Early MVP. The API and behavior may change between versions.

### Requirements

- Raycast (macOS)
- Paper Agent core installed (this repository), with a valid `config.yaml` and working Python environment
- A local Paper Agent library (JSON outputs under a date-based folder structure) after you run the pipeline

### Getting started

1. **Install Paper Agent core** (this repo): clone, create venv, `pip install -r requirements.txt`, copy `config.example.yaml` to `config.yaml`, and configure it.
2. **Install the Raycast extension** from the [Raycast Store](https://www.raycast.com/) or from the [extension repository](https://github.com/galleonli/paper-agent-raycast): clone that repo, run `npm install` and `npm run dev` to load it in Raycast during development.
3. **Set extension Preferences**: **Config file path** (full path to your `config.yaml`), **Paper directory** (your `delivery.paper_dir`). Optionally set **Python executable** if you use a custom path.

If the extension cannot find the core (missing config, wrong paths, or `paper_agent` not runnable), it shows **Core not found** with a link to this repo and a **Copy bootstrap command** action that copies a one-line install command to the clipboard.

### Configuration

By default, the extension expects your Paper Agent project at:

- Paper directory and config path (set in Raycast Preferences; no hardcoded path)
- Library layout: `<paper_dir>/library/<YYYY-MM-DD>/*.json`

If your Paper Agent project lives elsewhere, set **Config file path** and **Paper directory** in the extension Preferences (Raycast → Extensions → Paper Agent → Preferences).

For **Recent Papers**, the limit is set in extension Preferences (Recent papers limit).

#### Config vs Preferences when using Run Paper Agent

When you trigger **Run Paper Agent** from Raycast, the extension uses a **preference-first** rule for runtime sections:

- **direction** (limits, categories, keywords, queries), **delivery** (paper_dir and derived library path), **summarize** (LLM summary), and **sources** (arXiv + Scholar Inbox) are built **entirely from extension Preferences**. Values in `config.yaml` for these sections are **not** used for the Run Paper Agent command, except that local-only paths like `delivery.state_dir` and `delivery.logs_dir` still come from config.
- **policy.type** is also taken from extension Preferences (currently `off` in the UI).
- The remaining config sections (such as `interests`, `selection`, `feedback`, `export`, `advanced`, `prompts`, and legacy compatibility blocks) are still read from `config.yaml`.

For **CLI or cron** runs (`python -m paper_agent run --config config.yaml`), the app reads the full config from YAML. If `direction`, `delivery`, `summarize`, or `sources` are missing in the file, the Python app uses its built-in defaults.

The same preference-first behavior also applies to the macOS `launchd` job installed by **Install Daily Schedule**, because that command snapshots the current Preferences into its runtime config and environment.

### Commands

| Command             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Run Paper Agent** | Runs the full pipeline once. Builds direction, delivery, summarize, sources, and `policy.type` from extension Preferences; reads the rest from `config.yaml`. Shows a toast when done, skipped, or failed.                                                                                                                                                                                                                                                                                                                                                          |
| **Open Paper Directory** | Opens the configured paper directory in Finder. Useful for jumping directly to `library/`, daily digest files, and exported files.                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **Install Daily Schedule** | Installs or updates a macOS `launchd` job for **04:00** local time. The job uses the same shared runner script as **Run Paper Agent**, catches up after boot/login when 04:00 was missed, and writes logs under `~/Library/Logs/PaperAgent/`. Re-run it after changing scheduling-related preferences.                                                                                                                                                                                                 |
| **Remove Daily Schedule** | Unloads and removes the macOS `launchd` job for the daily run. It keeps the log and state directories so you can still inspect previous runs.                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Daily Schedule Status** | Shows whether the `launchd` job is installed, today's schedule result, the last successful day, and the most recent run metadata with quick actions to open the log or state directory.                                                                                                                                                                                                                                                                                                                                                      |
| **Today Papers**    | Reads today's papers from local library outputs via the Paper Agent `today --json` CLI. Source: `<library_dir>/<YYYY-MM-DD>/*.json`. Detail pane: title, authors, categories, abstract, "Why this paper", optional research summary, and any related local papers. Actions: Open paper, open local note, open related notes or related links, mark read/unread, add/remove favorites, add/remove reading queue, and jump to favorites or queue. Note path: uses `note_path` from JSON if set, otherwise `<date_dir>/<basename>.md`.                                     |
| **Recent Papers**   | Source: `<library_dir>/<YYYY-MM-DD>/*.json` from the last few days. Sorting: newest first, using `published` when present, otherwise `date` from the JSON or folder name. Supports the same related-paper, read/unread, favorites, and reading-queue actions as Today Papers.                                                                                                                                                                                                                                                                                    |
| **Search Papers**   | Scope: all JSON files under `<library_dir>/*/*.json`. Searchable: `title`, `authors`, `abstract`, `categories`, `id`, `date`, `published`. Case-insensitive substring match; query split on whitespace with AND logic. Ranking: title/authors > abstract > categories/metadata; phrase matches get a boost; recency tie-breaker. Date matching: substrings (e.g. `2026`, `2026-03-11`) and arXiv-style `YYMM.DD` normalized to `20YY-MM-DD` (e.g. `2603.11` → `2026-03-11`). Supports the same related-paper, read/unread, favorites, and reading-queue actions as Today Papers. |
| **Favorite Papers** | Shows papers you manually added to favorites from any list view. Favorites are stored locally in Raycast and can be removed directly from this list. Read/unread state and reading-queue state are also shown here.                                                                                                                                                                                                                                                                                                                                              |
| **Reading Queue**   | Shows papers you manually queued from any list view. The queue is stored locally in Raycast, keeps newest queued items first, and supports the same open/read/favorite actions as the other list views.                                                                                                                                                                                                                                                                                                                                                            |

#### Read/unread behavior

- Each paper is shown with a local read/unread marker in Raycast.
- A paper is marked as **read** after it stays selected in the detail view for at least 5 seconds.
- You can also manually switch a paper between **Mark as Read** and **Mark as Unread** from the action panel.
- Read/unread state, favorites, and reading queue are stored locally in Raycast and do not modify your Paper Agent library JSON files.

#### Related local papers

- If a note metadata JSON contains `related_local_papers`, Raycast shows them in the detail pane under **Related local papers**.
- The action panel adds a **Related Papers** section when any related item has a local note or external link.
- Related-paper links are generated from your full local library and are meant as lightweight, explainable navigation help rather than embedding-based semantic search.

### Development (Raycast)

From the [extension repository](https://github.com/galleonli/paper-agent-raycast): **Build:** `npm run build` · **Lint:** `npm run lint`

---

## Google Scholar setup

The Scholar Inbox reads **Google Scholar Alert emails** only. No RSS, no crawling, and no Google Scholar scraping.

Core config supports four provider values:

- **`mbox`:** one local mbox file.
- **`eml_dir`:** a directory containing `.eml` files.
- **`imap`:** generic IMAP mailbox (commonly Gmail IMAP).
- **`gmail`:** Gmail-flavored IMAP alias; same mailbox flow, with Gmail label support.

If you run from **Raycast**, or use **Install Daily Schedule** from Raycast, configure Scholar Inbox in **extension Preferences first**. The current Raycast workflow supports IMAP/Gmail-style mailbox settings, while local-path providers such as `mbox` and `eml_dir` are mainly for CLI/cron/manual config runs.

Next steps by provider:

- **mbox:** set `email.mbox_path`.
- **eml_dir:** set `email.eml_dir`.
- **imap / gmail:** set `email.imap_host`, `email.imap_user`, `email.imap_password_env` (default env var name: `IMAP_PASSWORD`), and optional `email.gmail_label`.

### Gmail IMAP (recommended for automation)

If you use **Raycast Run Paper Agent** or the Raycast-installed daily schedule, put these values in **Preferences** instead of duplicating them in `config.yaml`.

Recommended setup:

1. Use a dedicated Gmail account or label for Scholar Alerts.
2. Enable 2-Step Verification on the Google account.
3. Generate a Google App Password for the workflow.
4. Export the password into your shell environment instead of committing it to YAML.
5. Point `email.imap_password_env` to that variable.

Example:

```bash
export IMAP_PASSWORD='your-16-char-app-password'
python -m paper_agent run --config config.yaml
```

Recommended:

- For automation: prefer **`imap`** or **`gmail`** with a dedicated Gmail inbox/label.
- For local or offline testing: prefer **`mbox`** or **`eml_dir`**.
- Set `email.from_addresses` (for example `["scholaralerts-noreply@google.com"]`) to reduce noise.
- Keep `sources.scholar_alerts.max_items_per_run` at a reasonable cap for each run.

Runtime semantics:

- Scholar Inbox does **not** count toward `direction.max_papers_per_day`.
- Scholar Inbox does **not** use bandit / exploration / diversity policy logic.
- Scholar Inbox is ordered by **arrival time** only.
- Scholar Inbox uses only `sources.scholar_alerts.light_filter.*` for filtering.

Verification checklist:

1. Run `python -m paper_agent run --config config.yaml`.
2. Confirm `<paper_dir>/YYYY-MM-DD.md` has a **Scholar Inbox** section.
3. Check `<logs_dir>/latest.log` for `scholar_provider=...` and `scholar_new=N`.
4. Confirm `<library_dir>/YYYY-MM-DD/` contains Scholar notes when new alert emails exist.

---

## Configuration (user settings first)

Copy `config.example.yaml` to `config.yaml`.

Use `config.yaml` mainly for:

- `interests`
- `delivery.state_dir` and `delivery.logs_dir`
- `selection`
- `export`
- `advanced`
- `prompts`
- legacy compatibility blocks such as `feedback`, `policy`, and `autotune`

For **CLI/cron** runs, you can also define runtime sections such as `direction`, `delivery`, `summarize`, and `sources` in `config.yaml`.

For **Raycast Run Paper Agent** and the Raycast-installed macOS daily schedule, treat **Preferences as the source of truth** for runtime sections such as:

- `direction`
- `delivery.paper_dir` / derived library path
- `summarize`
- `sources`
- `policy.type`

In other words:

- **CLI/cron only:** put runtime knobs in `config.yaml`.
- **Raycast-triggered runs:** set runtime knobs in Raycast Preferences.
- **Using both:** keep shared policy/export/prompt sections in `config.yaml`, but expect Raycast-triggered runs to override runtime sections from Preferences.

All dates (paths, digest filename, run date, lookback) use **system local time** only; no timezone config. For cron, set `CRON_TZ` if you want the job to run at a specific wall-clock time.
If you enable OpenAI-based research summaries, provide an API key either via `OPENAI_API_KEY` (CLI/cron) or, for Raycast-triggered runs, the Raycast **OpenAI API Key** preference.

Example:

```bash
echo 'export OPENAI_API_KEY="your_openai_api_key"' >> ~/.zshrc
source ~/.zshrc
echo $OPENAI_API_KEY
python -m paper_agent run --config config.yaml
```

If you do **not** use AI summarization:

- You do **not** need to set `OPENAI_API_KEY`.
- The pipeline still writes notes, digest, and logs (plus exports when configured).
- Notes use the abstract (or snippet from the source); the optional `Research-focused summary` section is simply omitted.

If you want to customize the research-summary prompt, leave the built-in default as-is or override it with `prompts.research_summary_template` near the end of `config.yaml`.

---

## Advanced tuning (legacy compatibility)

This section replaces the old standalone tuning guide.

Current behavior summary:

- The active/default discovery path is effectively `policy.type: "off"`.
- Candidate ranking is based on required-keyword tiering: title keyword match > abstract keyword match > seed match.
- Final picks still go through `selection.*` (`explore_ratio`, `topic_cap`, `min_topics`).
- Legacy `policy.*`, `feedback.*`, and `autotune.*` fields remain in config for compatibility and experimentation, but the current main pipeline does **not** instantiate the legacy deterministic / LinUCB policies.

For most users:

- Tune `direction.*`, `selection.*`, `interests.seeds`, and optional prompt overrides.
- Leave `policy.type: "off"`.
- Leave `autotune.enabled: false`.

Keep in mind:

- `direction.lookback_days` affects both arXiv discovery and Scholar Inbox ingestion.
- `direction.max_papers_per_day` applies to discovery only; Scholar Inbox is bounded by `sources.scholar_alerts.max_items_per_run`.
- You may still see autotune-related fields in logs and config because they remain part of the compatibility surface, but they are not active in the default pipeline.

---

## Output artifacts

| Artifact                 | Path                                                         | Contents                                                                                                                                                                                                                                           |
| ------------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Notes**                | `<library_dir>/YYYY-MM-DD/{id}.md`                           | Title, ID, published, authors, link, categories, source, abstract, why-this-paper, and key points. Discovery notes may include an optional `Research-focused summary`; Scholar notes stay light and may use placeholders when abstract is missing. |
| **Note metadata (JSON)** | `<library_dir>/YYYY-MM-DD/{id}.json`                         | Machine-readable mirror of each note (id, title, authors, link, abstract, why_this_paper, optional research_summary, `related_local_papers`, etc.) for scripts and `today` / `list --json` / `search --json`.                                       |
| **Digest**               | `<paper_dir>/YYYY-MM-DD.md`                                  | Two sections: **Daily Precision** (capped) and **Scholar Inbox** (capped by `max_items_per_run`). Each entry links to local note files under `<library_dir>/YYYY-MM-DD/`.                                                                            |
| **Weekly digest**        | `<paper_dir>/weekly/YYYY-MM-DD_to_YYYY-MM-DD.md`             | Week-to-date rollup for the current local week. Rebuilds from `<library_dir>/*/*.json`, summarizes total papers, top topics, top categories, frequent authors, highlighted papers, and an auto summary sentence, then groups entries by day with links back to local notes. |
| **Log**                  | `<logs_dir>/latest.log`                                      | One line per run with fetch/filter/selection summary fields such as `fetched_total`, `after_category`, `after_filters`, `selected`, `new_count`, `discovery_selected`, `scholar_new`, `scholar_provider`, plus selection / autotune diagnostics.   |
| **Exports**              | `<library_dir>/YYYY-MM-DD/{id}.bib`, `<library_dir>/YYYY-MM-DD/{id}.ris` | BibTeX and RIS for **discovery** papers only (when in `export.formats`).                                                                                                                                                                           |

Example digest snippet:

```markdown
# Daily digest — 2025-01-02

## Total papers: 5 (Daily Precision: 2, Scholar Inbox: 3)

## Daily Precision

Papers: 2

### First paper

- **Why**: Keyphrase matched.
- **Link**: https://arxiv.org/abs/2501.00001
- **Local note**: [2501.00001.md](../library/2025-01-02/2501.00001.md)

---

## Scholar Inbox

Papers: 3

### Scholar item title

- **Link**: https://...
- **Local note**: [scholar....md](../library/2025-01-02/scholar....md)
```

---

## Sources

### Daily Precision (arXiv)

- Fetched via arXiv API, then filtered in this order: `lookback_days` -> categories -> exclude keywords -> required keywords / seeds.
- **Required keywords** = `direction.include_keywords`: `OR` match. A paper is kept if at least one phrase appears in the **title** or **abstract**. It does not need to match all phrases, and it does not need to match both title and abstract.
- **Exclude keywords** = `direction.exclude_keywords`: `OR` match on **title + abstract + authors** combined. If any exclude phrase matches, the paper is dropped.
- **Seeds**: if a paper ID is listed in `interests.seeds`, it can pass even when it matches no required keyword.
- With the current default flow (`policy.type: "off"`), candidates are tiered by title keyword match > abstract keyword match > seed match, then newer papers first.
- Final picks still go through `selection.*` constraints such as `topic_cap`, `min_topics`, and `explore_ratio`.
- **Capped by `direction.max_papers_per_day`.**

### Scholar Inbox (email alerts)

- Ingest **Google Scholar Alert emails** only (mbox, `.eml` directory, IMAP, or Gmail-flavored IMAP). No RSS and no Google Scholar crawling.
- **Not** capped by `max_papers_per_day`; bounded only by `sources.scholar_alerts.max_items_per_run`.
- **Never** uses bandit or exploration/diversity constraints; **arrival-ordered** (received time, descending); **light filtering** only (`sources.scholar_alerts.light_filter.*`).
- **Abstract enrichment:** If the alert link is arXiv, the agent fetches the full abstract (and authors, categories, PDF link) from the arXiv API. For other links it may try to fetch title and abstract from the page (best-effort); if that fails or is not possible, it keeps the email snippet. Enrichment never blocks: you always get at least the snippet.
- Scholar notes do not include the optional LLM `Research-focused summary` section.
- Setup and provider details: see [Google Scholar setup](#google-scholar-setup).

---

## Scheduling

Daily automation is covered in [Quick start → Run daily (automatic)](#run-daily-automatic). Use cron (or launchd / systemd timer) with `CRON_TZ` set to your timezone.

---

## Troubleshooting

### Logs and state

- **Where are logs?**  
  `delivery.logs_dir/latest.log` (default: `logs/latest.log`). One summary line per run with `fetched_total`, `after_category`, `after_filters`, `selected`, `new_count`, `discovery_selected`, `scholar_new`, `scholar_provider`, and selection diagnostics such as `num_topics` / `exploration_picks`. Inspect this first when something looks wrong.

- **Second run still shows new papers / duplicates?**  
  Ensure `delivery.state_dir` is stable and writable; do not clear `state/seen.json` between runs. Use the same `library_dir` and `paper_dir` across runs. If you changed the repo path or run from a different working directory, state may not be found and papers can be treated as new again.

### Config and startup

- **Config file not found / Invalid YAML / Invalid config**  
  Run with an explicit path: `python -m paper_agent run --config config.yaml`. Ensure the file exists and is valid YAML. Typical validation errors: unknown `export.formats` value, invalid `sources.scholar_alerts.email.provider`, invalid `policy.type`. Fix the reported key and re-run.

- **No discovery papers at all (arXiv)?**  
  Check: (1) `direction.allow_categories` or `direction.queries` — at least one must yield results. (2) `direction.lookback_days` — papers are filtered by update date within this window. (3) `direction.include_keywords` / Required keywords — if non-empty, each paper needs at least one keyword match in the title or abstract, or a seed match, to pass. Relax filters or add keywords and re-run.

### Scholar Inbox

- **No Scholar items?**
  - **Enabled and provider:** `sources.scholar_alerts.enabled: true` and `sources.scholar_alerts.email.provider` set to `mbox`, `eml_dir`, `imap`, or `gmail`.
  - **mbox/eml_dir:** Set `sources.scholar_alerts.email.mbox_path` or `sources.scholar_alerts.email.eml_dir`; ensure messages exist and are within `direction.lookback_days`.
- **IMAP / Gmail setup**
  - Set `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, and `sources.scholar_alerts.email.imap_password_env`; for CLI/cron put the password in the environment (e.g. `IMAP_PASSWORD`), while Raycast-triggered runs should prefer the matching Scholar IMAP Preferences.
  - If `sources.scholar_alerts.email.gmail_label` is configured and supported by the current implementation, the agent attempts to read from that label; otherwise it reads from `INBOX`.
  - Check `<logs_dir>/latest.log` for `scholar_provider` and `scholar_new` to confirm the source and count.

- **IMAP login works but no papers are extracted?**  
  Inspect one raw Scholar Alert email and confirm the parser can extract paper entries from its current HTML/text structure. Check that the message body actually contains paper links. If you use `sources.scholar_alerts.light_filter.include_keywords`, ensure at least one matches; if filters are too strict, you may get zero items.

### Summarization (optional)

- **Research summary missing or "OPENAI_API_KEY is not set"?**
  The research-focused summary is optional. If `summarize.enabled` is true and you want LLM summaries, provide an API key via `OPENAI_API_KEY` (CLI/cron) or, for Raycast-triggered runs, the Raycast **OpenAI API Key** preference. If you do not set it, the pipeline still runs and writes notes with abstract/snippet summary only; the research-summary section is omitted. You can verify the CLI key is visible to the process with `echo $OPENAI_API_KEY`.

### Cron / scheduling

- **Cron job does not run or runs at wrong time?**  
  Set `CRON_TZ` to your timezone (e.g. `CRON_TZ=Europe/Berlin`). Use the full path to the repo and to the venv Python in the cron line. Ensure the user running cron has read access to the repo and write access to `state_dir`, `library_dir`, `paper_dir`, and `logs_dir`.

---

## Safety & ethics

- **arXiv:** Use the official API only; respect terms and rate limits.
- **Google Scholar:** **Inbox (email) only.** We do not crawl or scrape Google Scholar. Only user-provided email (`mbox`, `.eml` directory, IMAP, or Gmail-flavored IMAP) is ingested.
- **Privacy:** Config, state, and outputs stay on your machine; no required external DB or hosted service.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). See [LICENSE](LICENSE) for the full text.
