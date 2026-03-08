<div align="center">

# 🔥 Paper Agent

**A self-hosted paper inbox for arXiv discovery and Google Scholar alerts.**

*Discover relevant arXiv papers with explainable, interest-aware selection instead of raw keyword matching.
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

- **Daily Precision (arXiv):** Explainable interest signals, policy-based ranking, and optional exploration/diversity controls instead of simple keyword-only matching.
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
      provider: imap # mbox | eml_dir | imap (or gmail alias)
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
| **Summarization** | `summarize.enabled`, `summarize.provider`, `summarize.model`, `summarize.language`, `summarize.brief_one_liner_enabled`, `summarize.research_summary_enabled`; for OpenAI, set `OPENAI_API_KEY` in the environment rather than storing it in `config.yaml` |
| **Output paths** | `delivery.library_dir`, `delivery.daily_dir`, `delivery.state_dir`, `delivery.logs_dir` |
| **Scholar Inbox** | `sources.scholar_alerts.enabled`, `sources.scholar_alerts.email.provider` (`mbox` \| `eml_dir` \| `imap` \| `gmail`), `sources.scholar_alerts.max_items_per_run`, `sources.scholar_alerts.light_filter.*` |
| **Scholar email source** | `sources.scholar_alerts.email.mbox_path`, `sources.scholar_alerts.email.eml_dir`, or IMAP keys `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, `sources.scholar_alerts.email.imap_password_env`, `sources.scholar_alerts.email.gmail_label` |
| **Policy (discovery only)** | `policy.type` (`deterministic` \| `linucb`), `selection.explore_ratio`, `selection.topic_cap`, `selection.min_topics`; advanced tuning in [TUNING.md](TUNING.md) (`policy.*`, `autotune.*`) |
| **Export** | `export.formats` (e.g. `["bibtex", "ris"]`) |

Timezone for *when* the job runs: set `CRON_TZ` in the environment; `timezone` in config is metadata only.
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

---

## Output artifacts

| Artifact | Path | Contents |
|----------|------|----------|
| **Notes** | `library/YYYY-MM-DD/{id}.md` | Title, ID, published, authors, link, categories, source, abstract/summary, why-this-paper, key points. Discovery notes may include optional LLM-based `Research-focused summary`; Scholar notes stay light and may contain placeholders. |
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

Run daily via cron (or your scheduler). Set timezone with `CRON_TZ`:

```bash
CRON_TZ=Europe/Berlin
0 8 * * * cd /path/to/paper-agent && .venv/bin/python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
```

---

## Troubleshooting

- **Where are logs?**  
  `delivery.logs_dir/latest.log` (default: `logs/latest.log`). One summary line per run with `discovery_selected`, `scholar_new`, `scholar_pushed`, `scholar_provider`.

- **Second run still shows new papers?**  
  Ensure `delivery.state_dir` is stable and writable; do not clear `state/seen.json` between runs. Same `library_dir` and `daily_dir` across runs.

- **Slack not sending?**  
  Check `delivery.slack.webhook_url`; if Slack fails, the run still writes local outputs and marks papers seen (no re-send next run).

- **No Scholar items?**  
  Confirm `sources.scholar_alerts.enabled: true` and `sources.scholar_alerts.email.provider` set. For mbox/eml: set `sources.scholar_alerts.email.mbox_path` or `sources.scholar_alerts.email.eml_dir` and ensure messages are within `direction.lookback_days`. For IMAP: set `sources.scholar_alerts.email.imap_host`, `sources.scholar_alerts.email.imap_user`, and `sources.scholar_alerts.email.imap_password_env` (default env var name `IMAP_PASSWORD`). If configured, `sources.scholar_alerts.email.gmail_label` is used and falls back to `INBOX` when label select fails. Check `scholar_provider` in `latest.log`.

- **IMAP login works but no papers are extracted?**  
  Inspect one raw Scholar Alert email and confirm the parser can extract paper entries from its current HTML/text structure. Check whether the message actually contains paper links and whether your `sources.scholar_alerts.light_filter.*` conditions are too strict.

---

## Safety & ethics

- **arXiv:** Use the official API only; respect terms and rate limits.
- **Google Scholar:** **Inbox (email) only.** We do not crawl or scrape Google Scholar. Only user-provided email (mbox, .eml directory, or Gmail IMAP) is ingested.
- **Privacy:** Config, state, and outputs stay on your machine; no required external DB or hosted service.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). See [LICENSE](LICENSE) for the full text.
