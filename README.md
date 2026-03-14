<div align="center">

# 🔥 Paper Agent

**A self-hosted paper inbox for arXiv discovery and Google Scholar alerts.**

_Discover relevant arXiv papers with explainable, interest-aware selection (instead of raw keyword matching).
Keep Google Scholar Alert emails in a separate inbox, then write local notes, daily digests, and BibTeX/RIS exports._

[**Quick start**](#quick-start) · [**Key features**](#key-features) · [**Configuration**](#configuration-user-settings-first) · [**Google Scholar setup**](#google-scholar-setup) · [**Raycast extension**](#raycast-extension) · [**Troubleshooting**](#troubleshooting)

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
- **Idempotent and catch-up safe:** Re-running the same window produces 0 duplicates; missed days can be recovered safely.
- **Workflow-friendly outputs:** Generate local notes, daily digests, and BibTeX/RIS exports.

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

Edit `config.yaml` as needed (e.g. `interests.seeds`, `selection`, `export`, `advanced`). If you use **Run Paper Agent** from Raycast, set direction/delivery/summarize/sources in extension Preferences; for CLI/cron, add those sections to config or use defaults.

First run writes notes, digest, and exports; second run with same state prints no new papers.

OpenAI summarization is optional. For CLI/cron, set `OPENAI_API_KEY` in your environment if needed. For Raycast, you can instead fill **OpenAI API Key** directly in extension Preferences. If no key is available, the pipeline still runs and falls back to abstract/snippet-based notes.

### CLI commands

| Command                                                              | Description                                                    |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| `python -m paper_agent run --config config.yaml`                     | Run the full pipeline once.                                    |
| `python -m paper_agent today --json --config config.yaml`            | Print today's local paper entries as JSON.                     |
| `python -m paper_agent list --json [--limit N] --config config.yaml` | Print recent local paper entries as JSON (optional `--limit`). |
| `python -m paper_agent open <paper_id> --config config.yaml`         | Open the local Markdown note for the given paper id.           |

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

## Google Scholar setup

The Scholar Inbox reads **Google Scholar Alert emails** from one of three providers:

- **`mbox`:** one local mbox file.
- **`eml_dir`:** a directory containing `.eml` files.
- **`imap`:** Gmail IMAP inbox (or label/folder).

Minimal config:

```yaml
sources:
  scholar_alerts:
    enabled: true
    email:
      provider: imap # mbox | eml_dir | imap
```

Next steps by provider:

- **mbox:** set `email.mbox_path`.
- **eml_dir:** set `email.eml_dir`.
- **imap (Gmail):** set `email.imap_host`, `email.imap_user`, `email.imap_password_env` (default env var name: `IMAP_PASSWORD`), and optional `email.gmail_label`.

Recommended:

- For automation: prefer **`imap`** with a dedicated Gmail inbox/label.
- For local or offline testing: prefer **`mbox`** or **`eml_dir`**.
- Set `email.from_addresses` (for example `["scholaralerts-noreply@google.com"]`) to reduce noise.
- Keep `sources.scholar_alerts.max_items_per_run` at a reasonable cap for each run.
- Follow the full Gmail IMAP guide in [GOOGLE_SCHOLAR_GMAIL_SETUP.md](GOOGLE_SCHOLAR_GMAIL_SETUP.md).

---

## Configuration (user settings first)

Copy `config.example.yaml` to `config.yaml`. The example config keeps the always-useful local sections (`interests`, `delivery.state_dir`, `delivery.logs_dir`, `selection`, `export`, `advanced`, `prompts`) and omits the Raycast-managed sections for running from the extension (`direction`, most of `delivery`, `summarize`, and `sources`). When you use **Run Paper Agent** from Raycast, those runtime sections are taken from extension Preferences only (see [Raycast → Config vs Preferences](#config-vs-preferences-when-using-run-paper-agent)). For CLI or cron runs, add those sections to `config.yaml` if you need non-default behavior; otherwise the app uses built-in defaults.

Main knobs in config and/or Raycast:

| What                                        | Where (config and/or Raycast)                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Direction, delivery, summarize, sources** | **Raycast:** set in extension Preferences when using Run Paper Agent. **CLI/cron:** add `direction`, `delivery`, `summarize`, `sources` to `config.yaml` or rely on app defaults.                                                                                                                                                                           |
| **Interests**                               | `interests.seeds` in config                                                                                                                                                                                                                                                                                                                                 |
| **Discovery ranking / selection**           | Current discovery flow uses required-keyword tiers: title keyword match > abstract keyword match > seed match. Final picks still go through `selection.*` (`max_papers_per_day`, `explore_ratio`, `topic_cap`, `min_topics`). `policy.type: "off"` is the intended/default setting; legacy policy knobs remain in config mainly for backward compatibility. |
| **Export**                                  | `export.formats` (e.g. `["bibtex", "ris"]`) in config                                                                                                                                                                                                                                                                                                       |
| **Advanced fetch limit**                    | `advanced.max_results_per_query` in config. Default: `9999`. This is a per-run fetch cap for arXiv discovery, not an infinite mode. In code it is validated as `Field(default=9999, ge=1, le=9999)`, meaning: use `9999` if omitted, and only allow values from `1` to `9999`.                                                                              |

All dates (paths, digest filename, run date, lookback) use **system local time** only; no timezone config. For cron, set `CRON_TZ` if you want the job to run at a specific wall-clock time.
If you enable OpenAI-based research summaries, provide an API key either via `OPENAI_API_KEY` (CLI/cron) or the Raycast **OpenAI API Key** preference (extension run).

Example:

```bash
echo 'export OPENAI_API_KEY="your_openai_api_key"' >> ~/.zshrc
source ~/.zshrc
echo $OPENAI_API_KEY
python -m paper_agent run --config config.yaml
```

If you do **not** use AI summarization:

- You do **not** need to set `OPENAI_API_KEY`.
- The pipeline still writes notes, digest, exports, and logs.
- Notes use the abstract (or snippet from the source); the optional `Research-focused summary` section is simply omitted.

If you want to customize the research-summary prompt, leave the built-in default as-is or override it with `prompts.research_summary_template` near the end of `config.yaml`.

---

## Output artifacts

| Artifact                 | Path                                                         | Contents                                                                                                                                                                                                                                           |
| ------------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Notes**                | `library/YYYY-MM-DD/{id}.md`                                 | Title, ID, published, authors, link, categories, source, abstract, why-this-paper, and key points. Discovery notes may include an optional `Research-focused summary`; Scholar notes stay light and may use placeholders when abstract is missing. |
| **Note metadata (JSON)** | `library/YYYY-MM-DD/{id}.json`                               | Machine-readable mirror of each note (id, title, authors, link, abstract, why_this_paper, optional research_summary, etc.) for scripts and `today` / `list --json`.                                                                                |
| **Digest**               | `daily/YYYY-MM-DD.md`                                        | Two sections: **Daily Precision** (capped) and **Scholar Inbox** (capped by `max_items_per_run`). Each entry links to `library/YYYY-MM-DD/{id}.md`.                                                                                                |
| **Log**                  | `logs/latest.log`                                            | One line per run with fetch/filter/selection summary fields such as `fetched_total`, `after_category`, `after_filters`, `selected`, `new_count`, `discovery_selected`, `scholar_new`, `scholar_provider`, plus selection / autotune diagnostics.   |
| **Exports**              | `library/YYYY-MM-DD/{id}.bib`, `library/YYYY-MM-DD/{id}.ris` | BibTeX and RIS for **discovery** papers only (when in `export.formats`).                                                                                                                                                                           |

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
- Final picks still go through `selection.*` constraints such as `max_papers_per_day`, `topic_cap`, `min_topics`, and `explore_ratio`.
- **Capped by `direction.max_papers_per_day`.**

### Scholar Inbox (email alerts)

- Ingest **Google Scholar Alert emails** only (mbox, `.eml` directory, or Gmail IMAP). No RSS and no Google Scholar crawling.
- **Not** capped by `max_papers_per_day`; bounded only by `sources.scholar_alerts.max_items_per_run`.
- **Never** uses bandit or exploration/diversity constraints; **arrival-ordered** (received time, descending); **light filtering** only (`sources.scholar_alerts.light_filter.*`).
- **Abstract enrichment:** If the alert link is arXiv, the agent fetches the full abstract (and authors, categories, PDF link) from the arXiv API. For other links it may try to fetch title and abstract from the page (best-effort); if that fails or is not possible, it keeps the email snippet. Enrichment never blocks: you always get at least the snippet.
- Scholar notes do not include the optional LLM `Research-focused summary` section.
- Setup and provider details: see [Google Scholar setup](#google-scholar-setup) and [GOOGLE_SCHOLAR_GMAIL_SETUP.md](GOOGLE_SCHOLAR_GMAIL_SETUP.md).

---

## Scheduling

Daily automation is covered in [Quick start → Run daily (automatic)](#run-daily-automatic). Use cron (or launchd / systemd timer) with `CRON_TZ` set to your timezone.

---

## Raycast extension

A [Raycast](https://www.raycast.com/) extension lets you run the pipeline, browse today/recent papers, search the local library, and open the paper repo from a Paper Agent workflow.

**Status:** Early MVP. The API and behavior may change between versions.

### Requirements

- Raycast
- A local Paper Agent library (JSON outputs under a date-based folder structure)

### Getting started

- Clone this repository.
- In the `raycast/` directory, run `npm install`.
- In Raycast, enable the Developer Tools (if not already enabled).
- Run `npm run dev` from `raycast/` to load the extension in Raycast during development.

### Configuration

By default, the extension expects your Paper Agent project at:

- Paper directory and config path (set in Raycast Preferences; no hardcoded path)
- Library layout: `<paper_dir>/library/<YYYY-MM-DD>/*.json`

If your Paper Agent project lives elsewhere, set **Config file path** and **Paper directory** in the extension Preferences (Raycast → Extensions → Paper Agent → Preferences).

For **Recent Papers**, the limit is set in extension Preferences (Recent papers limit).

#### Config vs Preferences when using Run Paper Agent

When you trigger **Run Paper Agent** from Raycast, the extension uses a **preference-first** rule for four config sections:

- **direction** (limits, categories, keywords, queries), **delivery** (paper_dir and derived library path), **summarize** (LLM summary), and **sources** (arXiv + Scholar Inbox) are built **entirely from extension Preferences**. Values in `config.yaml` for these sections are **not** used for the Run Paper Agent command, except that local-only paths like `delivery.state_dir` and `delivery.logs_dir` still come from config.
- The rest of the config (interests, policy, selection, feedback, export, advanced, prompts) is still read from `config.yaml`. So you keep one config file for policy, export, and other knobs; Run Paper Agent gets direction/delivery/summarize/sources only from Raycast Preferences.

For **CLI or cron** runs (`python -m paper_agent run --config config.yaml`), the app reads the full config from YAML. If `direction`, `delivery`, `summarize`, or `sources` are missing in the file, the Python app uses its built-in defaults.

### Commands

| Command             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Run Paper Agent** | Runs the full pipeline once. Builds direction, delivery, summarize, and sources from extension Preferences; reads the rest from `config.yaml`. Shows a toast when done or on failure.                                                                                                                                                                                                                                                                                                                                                                                |
| **Install Daily Schedule** | Installs or updates a macOS `launchd` job for **04:00** local time. The job uses the same shared runner script as **Run Paper Agent**, catches up after boot/login when 04:00 was missed, and writes logs under `~/Library/Logs/PaperAgent/`. Re-run it after changing scheduling-related preferences.                                                                                                                                                                                                 |
| **Remove Daily Schedule** | Unloads and removes the macOS `launchd` job for the daily run. It keeps the log and state directories so you can still inspect previous runs.                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Daily Schedule Status** | Shows whether the `launchd` job is installed, today's schedule result, the last successful day, and the most recent run metadata with quick actions to open the log or state directory.                                                                                                                                                                                                                                                                                                                                                      |
| **Today Papers**    | Reads today's papers from the local library without invoking the Paper Agent CLI. Source: `<library_dir>/<YYYY-MM-DD>/*.json`. Detail pane: title; authors and categories when present; full abstract; "Why this paper"; research summary when present. Actions: Open paper (browser), open local note (when a matching `.md` exists), mark read/unread, add/remove favorites, and open the favorites list. Note path: uses `note_path` from JSON if set, otherwise `<date_dir>/<basename>.md`.                                                                      |
| **Recent Papers**   | Source: `<library_dir>/<YYYY-MM-DD>/*.json` from the last few days. Sorting: newest first, using `published` when present, otherwise `date` from the JSON or folder name. Supports the same read/unread and favorites actions as Today Papers.                                                                                                                                                                                                                                                                                                                       |
| **Search Papers**   | Scope: all JSON files under `<library_dir>/*/*.json`. Searchable: `title`, `authors`, `summary`, `abstract`, `categories`, `id`, `date`, `published`. Case-insensitive substring match; query split on whitespace with AND logic. Ranking: title/authors > abstract > summary/categories/metadata; phrase matches get a boost; recency tie-breaker. Date matching: substrings (e.g. `2026`, `2026-03-11`) and arXiv-style `YYMM.DD` normalized to `20YY-MM-DD` (e.g. `2603.11` → `2026-03-11`). Supports the same read/unread and favorites actions as Today Papers. |
| **Favorite Papers** | Shows papers you manually added to favorites from any list view. Favorites are stored locally in Raycast and can be removed directly from this list. Read/unread state is also shown here.                                                                                                                                                                                                                                                                                                                                                                           |

#### Read/unread behavior

- Each paper is shown with a local read/unread marker in Raycast.
- A paper is marked as **read** after it stays selected in the detail view for at least 5 seconds.
- You can also manually switch a paper between **Mark as Read** and **Mark as Unread** from the action panel.
- Read/unread state and favorites are stored locally in Raycast and do not modify your Paper Agent library JSON files.

### Development (Raycast)

- **Build:** `npm run build` (from `raycast/`)
- **Lint:** `npm run lint`

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
  - **Enabled and provider:** `sources.scholar_alerts.enabled: true` and `sources.scholar_alerts.email.provider` set to `mbox`, `eml_dir`, or `imap`.
  - **mbox/eml_dir:** Set `sources.scholar_alerts.email.mbox_path` or `sources.scholar_alerts.email.eml_dir`; ensure messages exist and are within `direction.lookback_days`.
- **IMAP:** Set `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, and `sources.scholar_alerts.email.imap_password_env`; for CLI/cron put the password in the environment (e.g. `IMAP_PASSWORD`), while Raycast can also pass it from the **Scholar IMAP password** preference. If `sources.scholar_alerts.email.gmail_label` is configured and supported by the current implementation, the agent attempts to read from that label; otherwise it reads from `INBOX`.
  - Check `logs/latest.log` for `scholar_provider` and `scholar_new` to confirm the source and count.

- **IMAP login works but no papers are extracted?**  
  Inspect one raw Scholar Alert email and confirm the parser can extract paper entries from its current HTML/text structure. Check that the message body actually contains paper links. If you use `sources.scholar_alerts.light_filter.include_keywords`, ensure at least one matches; if filters are too strict, you may get zero items.

### Summarization (optional)

- **Research summary missing or "OPENAI_API_KEY is not set"?**
  The research-focused summary is optional. If `summarize.enabled` is true and you want LLM summaries, provide an API key via `OPENAI_API_KEY` (CLI/cron) or the Raycast **OpenAI API Key** preference. If you do not set it, the pipeline still runs and writes notes with abstract/snippet summary only; the research-summary section is omitted. You can verify the CLI key is visible to the process with `echo $OPENAI_API_KEY`.

### Cron / scheduling

- **Cron job does not run or runs at wrong time?**  
  Set `CRON_TZ` to your timezone (e.g. `CRON_TZ=Europe/Berlin`). Use the full path to the repo and to the venv Python in the cron line. Ensure the user running cron has read access to the repo and write access to `state_dir`, `library_dir`, `paper_dir`, and `logs_dir`.

---

## Safety & ethics

- **arXiv:** Use the official API only; respect terms and rate limits.
- **Google Scholar:** **Inbox (email) only.** We do not crawl or scrape Google Scholar. Only user-provided email (mbox, .eml directory, or Gmail IMAP) is ingested.
- **Privacy:** Config, state, and outputs stay on your machine; no required external DB or hosted service.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). See [LICENSE](LICENSE) for the full text.
