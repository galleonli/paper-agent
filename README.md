<div align="center">

# 🔥 Paper Intelligence Agent

**Your Daily Precision feed for arXiv papers—interest-first, explainable, and self-hosted.**

*Discover papers from arXiv (seeds & keyphrases, explainable bandit + diversity) and ingest Google Scholar Alert emails in a separate inbox. Get a short “why this paper,” optional research notes, Slack brief, local notes, and BibTeX/RIS—all from one YAML config. Optional AutoTune. No vendor lock-in.*

[**Quick start**](#quick-start) · [**Features**](#features) · [**Configuration**](#configuration) · [**Outputs**](#outputs) · [**Tuning (advanced)**](#tuning-advanced)

<br/>

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-API-orange.svg)](https://arxiv.org/help/api)
[![YAML](https://img.shields.io/badge/config-YAML-red.svg)](config.example.yaml)
[![Self-hosted](https://img.shields.io/badge/self--hosted-✓-green.svg)](#features)
[![Slack](https://img.shields.io/badge/Slack-optional-4A154B?logo=slack)](https://slack.com/)
[![BibTeX / RIS](https://img.shields.io/badge/export-BibTeX%20%7C%20RIS-00599C.svg)](#outputs)
[![GPU](https://img.shields.io/badge/GPU-not%20required-brightgreen.svg)](#quick-start)

</div>

---

## Key features

- **Daily Precision (arXiv):** Seeds + keyphrases, explainable bandit (deterministic or LinUCB), exploration/diversity constraints, capped by `max_papers_per_day`.
- **Scholar Inbox (email):** Ingest Scholar Alert emails (mbox / .eml dir); **not** capped by `max_papers_per_day`; **no** bandit constraints; ordering by arrival (received time) only; light filtering.
- **Idempotent:** Shared `state/seen.json`; second run over same window → 0 new.
- **Outputs:** Local notes per paper, daily digest (two sections), optional Slack (two sections), BibTeX/RIS for discovery.

---

## Quick start

```bash
git clone https://github.com/your-org/daily-paper-agent.git
cd daily-paper-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml: interests, direction, (optional) Slack and Scholar Inbox
python -m paper_agent run --config config.yaml
```

First run writes notes, digest, and exports; second run with same state prints no new papers.

---

## Configuration (user settings first)

Copy `config.example.yaml` to `config.yaml`. Main knobs:

| What | Where |
|------|--------|
| **Interests** | `interests.seeds`, `interests.keyphrases`, `interests.negative_keyphrases` |
| **Discovery scope** | `direction.allow_categories`, `direction.max_papers_per_day`, `direction.lookback_days` |
| **Slack** | `delivery.slack.enabled`, `delivery.slack.webhook_url`, `delivery.slack.max_message_chars` |
| **Output paths** | `delivery.library_dir`, `delivery.daily_dir`, `delivery.state_dir`, `delivery.logs_dir` |
| **Scholar Inbox** | `sources.scholar_alerts.enabled`, `sources.scholar_alerts.email.provider` (`mbox` \| `eml_dir`), `email.mbox_path` / `email.eml_dir`, `max_items_per_run`, `light_filter` |
| **Policy (discovery only)** | `policy.type` (`deterministic` \| `linucb`), `selection.explore_ratio`, `selection.topic_cap`, `selection.min_topics` |
| **Export** | `export.formats` (e.g. `["bibtex", "ris"]`) |

Timezone for *when* the job runs: set `CRON_TZ` in the environment; `timezone` in config is metadata only.

---

## Output artifacts

| Artifact | Path | Contents |
|----------|------|----------|
| **Notes** | `library/{id}.md` | Title, ID, published, authors, link, categories, source, abstract/summary, why-this-paper, key points. Scholar items: placeholder if no abstract. |
| **Digest** | `daily/YYYY-MM-DD.md` | Two sections: **Daily Precision** (capped), **Scholar Inbox** (capped by `max_items_per_run`). Each entry links to `library/{id}.md`. |
| **Log** | `logs/latest.log` | One line per run: `fetched_total`, `selected`, `new_count`, `pushed_count`, `discovery_selected`, `scholar_new`, `scholar_pushed`, `scholar_provider`, etc. |
| **Exports** | `library/{id}.bib`, `library/{id}.ris` | BibTeX and RIS for **discovery** papers only (when in `export.formats`). |

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
- **Local note**: [2501.00001.md](../library/2501.00001.md)
---
## Scholar Inbox
Papers: 3
### Scholar item title
- **Link**: https://...
- **Local note**: [scholar....md](../library/...)
```

---

## Sources

### Daily Precision (arXiv)

- Fetched via arXiv API; filtered by categories/keywords/authors; scored by policy (deterministic or LinUCB); constrained selection (exploration, topic cap, min topics).
- **Capped by `direction.max_papers_per_day`.**

### Scholar Inbox (email alerts)

- Ingest from **Google Scholar Alert emails** only (mbox file or directory of .eml files). No RSS; no crawling of Google Scholar.
- **Not** capped by `max_papers_per_day`; bounded only by `sources.scholar_alerts.max_items_per_run`.
- **Never** uses bandit or exploration/diversity constraints; **arrival-ordered** (received time, descending); **light filtering** only (`include_keywords`, `exclude_keywords`, `exclude_authors`).
- Setup: create alerts at Google Scholar (email delivery), save messages to mbox or .eml dir, set `email.provider` and `email.mbox_path` or `email.eml_dir`. Optional: `email.from_addresses` (e.g. `["scholaralerts-noreply@google.com"]`).

---

## Scheduling

Run daily via cron (or your scheduler). Set timezone with `CRON_TZ`:

```bash
CRON_TZ=Europe/Berlin
0 8 * * * cd /path/to/daily-paper-agent && .venv/bin/python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
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
  Confirm `sources.scholar_alerts.enabled: true`, `email.provider` and path (`mbox_path` or `eml_dir`) set, and messages are within `lookback_days`. Check `scholar_provider` in `latest.log`.

---

## Safety & ethics

- **arXiv:** Use the official API only; respect terms and rate limits.
- **Google Scholar:** **Inbox (email) only.** We do not crawl or scrape Google Scholar. Only user-provided email (mbox / .eml directory, or IMAP when implemented) is ingested.
- **Privacy:** Config, state, and outputs stay on your machine; no required external DB or hosted service.

**License:** MIT (`LICENSE`).

---

## Advanced

- **Tuning (bandit / AutoTune):** See `TUNING.md`, `docs/agent-logic.md`, `docs/autotune-design.md`. Defaults are stable for most users.
- **Verification (invariants):** See `docs/VERIFICATION.md` for documented invariants and code references.
