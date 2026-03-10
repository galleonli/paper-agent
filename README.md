<div align="center">

# 🔥 Paper Agent

**A self-hosted paper inbox for arXiv discovery and Google Scholar alerts.**

*Discover relevant arXiv papers with explainable, interest-aware selection (instead of raw keyword matching).
Keep Google Scholar Alert emails in a separate inbox, then write local notes, Slack digests, and BibTeX/RIS exports.*

[**Quick start**](#quick-start) · [**Key features**](#key-features) · [**Google Scholar setup**](#google-scholar-setup) · [**Configuration**](#configuration-user-settings-first) · [**Output artifacts**](#output-artifacts)

<br/>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-API-orange.svg)](https://arxiv.org/help/api)
[![YAML](https://img.shields.io/badge/config-YAML-red.svg)](config.example.yaml)
[![Self-hosted](https://img.shields.io/badge/self--hosted-✓-green.svg)](#key-features)
[![Slack](https://img.shields.io/badge/Slack-optional-4A154B?logo=slack)](https://slack.com/)
[![BibTeX / RIS](https://img.shields.io/badge/export-BibTeX%20%7C%20RIS-00599C.svg)](#output-artifacts)

</div>

---

## Key features

- **Daily Precision (arXiv):** Interest-aware ranking with explainable signals, plus optional exploration/diversity controls.
- **Scholar Inbox (email):** Ingest Google Scholar Alert emails from `mbox`, `.eml` directories, or Gmail IMAP into a separate inbox.
- **Idempotent and catch-up safe:** Re-running the same window produces 0 duplicates; missed days can be recovered safely.
- **Workflow-friendly outputs:** Generate local notes, daily digests, optional Slack summaries, and BibTeX/RIS exports.

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

Edit `config.yaml` at minimum:

- `interests.keyphrases`
- `direction.queries`
- optional `delivery.slack.webhook_url`
- optional `sources.scholar_alerts.*`

First run writes notes, digest, and exports; second run with same state prints no new papers.

OpenAI summarization is optional. If you do not set `OPENAI_API_KEY`, the pipeline still runs and falls back to abstract/snippet-based notes.

### CLI commands

| Command | Description |
|---------|-------------|
| `python -m paper_agent run --config config.yaml` | Run the full pipeline once. |
| `python -m paper_agent today --json --config config.yaml` | Print today's local paper entries as JSON. |
| `python -m paper_agent list --json [--limit N] --config config.yaml` | Print recent local paper entries as JSON (optional `--limit`). |
| `python -m paper_agent open <paper_id> --config config.yaml` | Open the local Markdown note for the given paper id. |

### Run daily (automatic)

Run the agent every day via **cron** (or your system scheduler). Set `CRON_TZ` for your timezone, then add a daily job:

```bash
CRON_TZ=Europe/Berlin
0 8 * * * cd /path/to/paper-agent && .venv/bin/python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
```

Replace `/path/to/paper-agent` with your repo path. The example runs at 08:00 local time; change `0 8` to another hour if needed. More options: [Scheduling](#scheduling).

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

Copy `config.example.yaml` to `config.yaml`. Main knobs:

| What | Where |
|------|--------|
| **Interests** | `interests.seeds`, `interests.keyphrases`, `interests.negative_keyphrases` |
| **Direction (scope)** | `direction.lookback_days` applies to both discovery and Scholar Inbox (arrival window for Scholar); `direction.max_papers_per_day` and `direction.allow_categories` / `direction.deny_categories` / `direction.queries` / `direction.include_keywords` / `direction.exclude_keywords` / `direction.exclude_authors` apply to discovery only |
| **Slack** | `delivery.slack.enabled`, `delivery.slack.webhook_url`, `delivery.slack.max_message_chars` |
| **Summarization** | `summarize.enabled`, `summarize.provider`, `summarize.model`, `summarize.language`, `summarize.brief_one_liner_enabled`, `summarize.research_summary_enabled`; optional advanced prompt override at `prompts.research_summary_template`; for OpenAI, set `OPENAI_API_KEY` in the environment rather than storing it in `config.yaml` |
| **Output paths** | `delivery.library_dir`, `delivery.daily_dir`, `delivery.state_dir`, `delivery.logs_dir` |
| **Scholar Inbox** | `sources.scholar_alerts.enabled`, `sources.scholar_alerts.email.provider` (`mbox` \| `eml_dir` \| `imap`), `sources.scholar_alerts.max_items_per_run`, `sources.scholar_alerts.light_filter.*` |
| **Scholar email source** | `sources.scholar_alerts.email.mbox_path`, `sources.scholar_alerts.email.eml_dir`, or IMAP keys `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, `sources.scholar_alerts.email.imap_password_env`, `sources.scholar_alerts.email.gmail_label` |
| **Policy (discovery only)** | `policy.type` (`deterministic` \| `linucb`), `selection.explore_ratio`, `selection.topic_cap`, `selection.min_topics`; advanced tuning in [TUNING.md](TUNING.md) (`policy.*`, `autotune.*`) |
| **Export** | `export.formats` (e.g. `["bibtex", "ris"]`) |

All dates (paths, digest filename, run date, lookback) use **system local time** only; no timezone config. For cron, set `CRON_TZ` if you want the job to run at a specific wall-clock time.
If you enable OpenAI-based research summaries, set `OPENAI_API_KEY` in your shell environment before running the pipeline.

Example:

```bash
echo 'export OPENAI_API_KEY="your_openai_api_key"' >> ~/.zshrc
source ~/.zshrc
echo $OPENAI_API_KEY
python -m paper_agent run --config config.yaml
```

If you do **not** use AI summarization:

- You do **not** need to set `OPENAI_API_KEY`.
- The pipeline still writes notes, digest, exports, logs, and optional Slack output.
- The note `Summary` section falls back to a short abstract/snippet summary.
- The extra structured `Research-focused summary` section is simply omitted.

If you want to customize the research-summary prompt, leave the built-in default as-is or override it with `prompts.research_summary_template` near the end of `config.yaml`.

---

## Output artifacts

| Artifact | Path | Contents |
|----------|------|----------|
| **Notes** | `library/YYYY-MM-DD/{id}.md` | Title, ID, published, authors, link, categories, source, abstract/snippet summary, why-this-paper, and key points. Discovery notes may also include an optional LLM-based `Research-focused summary`; Scholar notes stay light and may contain placeholders. |
| **Note metadata (JSON)** | `library/YYYY-MM-DD/{id}.json` | Machine-readable mirror of each note (id, title, authors, link, summary, why_this_paper, etc.) for programmatic use. |
| **Digest** | `daily/YYYY-MM-DD.md` | Two sections: **Daily Precision** (capped) and **Scholar Inbox** (capped by `max_items_per_run`). Each entry links to `library/YYYY-MM-DD/{id}.md`. |
| **Log** | `logs/latest.log` | One line per run: `fetched_total`, `selected`, `new_count`, `pushed_count`, `discovery_selected`, `scholar_new`, `scholar_pushed`, `scholar_provider`, etc. |
| **Exports** | `library/YYYY-MM-DD/{id}.bib`, `library/YYYY-MM-DD/{id}.ris` | BibTeX and RIS for **discovery** papers only (when in `export.formats`). |

Example digest snippet:

```markdown
# Daily digest — 2025-01-02
Total papers: 5 (Daily Precision: 2, Scholar Inbox: 3)
---
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

- Fetched via arXiv API; filtered by categories/keywords/authors; scored by policy (deterministic or LinUCB); constrained selection (exploration, topic cap, min topics).
- **Capped by `direction.max_papers_per_day`.**

### Scholar Inbox (email alerts)

- Ingest **Google Scholar Alert emails** only (mbox, `.eml` directory, or Gmail IMAP). No RSS and no Google Scholar crawling.
- **Not** capped by `max_papers_per_day`; bounded only by `sources.scholar_alerts.max_items_per_run`.
- **Never** uses bandit or exploration/diversity constraints; **arrival-ordered** (received time, descending); **light filtering** only (`sources.scholar_alerts.light_filter.include_keywords`, `sources.scholar_alerts.light_filter.exclude_keywords`, `sources.scholar_alerts.light_filter.exclude_authors`).
- Scholar notes do not include the optional LLM `Research-focused summary` section.
- Setup and provider details: see [Google Scholar setup](#google-scholar-setup) and [GOOGLE_SCHOLAR_GMAIL_SETUP.md](GOOGLE_SCHOLAR_GMAIL_SETUP.md).

---

## Scheduling

Daily automation is covered in [Quick start → Run daily (automatic)](#run-daily-automatic). Use cron (or launchd / systemd timer) with `CRON_TZ` set to your timezone.

---

## Troubleshooting

### Logs and state

- **Where are logs?**  
  `delivery.logs_dir/latest.log` (default: `logs/latest.log`). One summary line per run with `fetched_total`, `selected`, `new_count`, `discovery_selected`, `scholar_new`, `scholar_pushed`, `scholar_provider`. Inspect this first when something looks wrong.

- **Second run still shows new papers / duplicates?**  
  Ensure `delivery.state_dir` is stable and writable; do not clear `state/seen.json` between runs. Use the same `library_dir` and `daily_dir` across runs. If you changed the repo path or run from a different working directory, state may not be found and papers can be treated as new again.

### Config and startup

- **Config file not found / Invalid YAML / Invalid config**  
  Run with an explicit path: `python -m paper_agent run --config config.yaml`. Ensure the file exists and is valid YAML. Typical validation errors: unknown `export.formats` value, invalid `sources.scholar_alerts.email.provider`, invalid `policy.type`. Fix the reported key and re-run.

- **No discovery papers at all (arXiv)?**  
  Check: (1) `direction.allow_categories` or `direction.queries` — at least one must yield results. (2) `direction.lookback_days` — papers are filtered by update date within this window. (3) `interests.keyphrases` — if non-empty, each paper needs at least one keyphrase match or seed match to pass. Relax filters or add keyphrases and re-run.

### Slack

- **Slack not sending?**  
  Check `delivery.slack.enabled` and `delivery.slack.webhook_url`. Use a valid Slack Incoming Webhook URL. If the webhook fails, the run still writes local notes, digest, and exports and marks papers seen; Slack is best-effort and is not retried on the next run.

### Scholar Inbox

- **No Scholar items?**  
  - **Enabled and provider:** `sources.scholar_alerts.enabled: true` and `sources.scholar_alerts.email.provider` set to `mbox`, `eml_dir`, or `imap`.  
  - **mbox/eml_dir:** Set `sources.scholar_alerts.email.mbox_path` or `sources.scholar_alerts.email.eml_dir`; ensure messages exist and are within `direction.lookback_days`.  
  - **IMAP:** Set `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, and `sources.scholar_alerts.email.imap_password_env`; put the password in the environment (e.g. `IMAP_PASSWORD`). If `sources.scholar_alerts.email.gmail_label` is configured and supported by the current implementation, the agent attempts to read from that label; otherwise it reads from `INBOX`.  
  - Check `logs/latest.log` for `scholar_provider` and `scholar_new` to confirm the source and count.

- **IMAP login works but no papers are extracted?**  
  Inspect one raw Scholar Alert email and confirm the parser can extract paper entries from its current HTML/text structure. Check that the message body actually contains paper links. If you use `sources.scholar_alerts.light_filter.include_keywords`, ensure at least one matches; if filters are too strict, you may get zero items.

### Summarization (optional)

- **Research summary missing or "OPENAI_API_KEY is not set"?**
  The research-focused summary is optional. If `summarize.enabled` is true and you want LLM summaries, set `OPENAI_API_KEY` in your environment before running. If you do not set it, the pipeline still runs and writes notes with abstract/snippet summary only; the research-summary section is omitted. You can verify the key is visible to the process with `echo $OPENAI_API_KEY`.

### Cron / scheduling

- **Cron job does not run or runs at wrong time?**  
  Set `CRON_TZ` to your timezone (e.g. `CRON_TZ=Europe/Berlin`). Use the full path to the repo and to the venv Python in the cron line. Ensure the user running cron has read access to the repo and write access to `state_dir`, `library_dir`, `daily_dir`, and `logs_dir`.

---

## Safety & ethics

- **arXiv:** Use the official API only; respect terms and rate limits.
- **Google Scholar:** **Inbox (email) only.** We do not crawl or scrape Google Scholar. Only user-provided email (mbox, .eml directory, or Gmail IMAP) is ingested.
- **Privacy:** Config, state, and outputs stay on your machine; no required external DB or hosted service.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). See [LICENSE](LICENSE) for the full text.
