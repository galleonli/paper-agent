<div align="center">

# 🔥 Paper Intelligence Agent

**Your daily paper digest—tuned to your interests, not keyword soup.**

*Discover papers from arXiv, filter by seeds & keyphrases, rank with an explainable policy (deterministic or LinUCB + diversity), and get a short “why this paper” plus an optional research-focused summary for each pick. Slack brief + full local notes + BibTeX/RIS. One YAML config. Self-hosted. No vendor lock-in.*

[**Quick start**](#quick-start) · [**Features**](#features) · [**Outputs**](#outputs)

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

## Who is this for?

- **Individual users / researchers**: want a reproducible, local arXiv digest with minimal setup and a simple YAML config.
- **Small teams**: share daily digests in Slack while keeping full notes and reference files under versioned directories (`library/`, `daily/`).
- **Self-hosted deployments**: run as a cron job or in existing automation without external services, GPU, or database dependencies.

---

## How it works

<div align="center">

| 1. Configure | 2. Run daily | 3. Get output |
|:------------:|:------------:|:-------------:|
| Set `seeds`, `keyphrases`, and (optional) Slack webhook in `config.yaml` | `python -m paper_agent run --config config.yaml` or cron | **Slack:** brief only · **Local:** full notes in `library/`, digest in `daily/`, BibTeX & RIS |

</div>

---

## Features

| | Description |
|:---|:---|
| **Interest-first** | Seeds (example papers) + keyphrases; every recommendation includes a short “why this paper.” |
| **Catch-up safe & idempotent** | Lookback window + persisted state; no missed papers, no duplicate Slack or notes on re-run. Seen state is saved **after** local notes, digest, and exports are written; if Slack push fails, the run logs a warning and does not re-push the same papers on the next run. |
| **Config-first** | One `config.yaml`; no code edits for daily use. |
| **Two-level output** | Slack: brief only (title, one-liner, why, links). Local: full notes in `library/`, daily digest in `daily/`. |
| **Reference export** | BibTeX and RIS (EndNote-compatible) for Zotero, Mendeley, etc. |
| **Explainable ranking** | Deterministic phrase-based policy or **LinUCB contextual bandit** with uncertainty + novelty + diversity constraints (`selection.*`, `policy.*`). |
| **Research-focused notes (optional)** | LLM-generated structured summary per paper (subfield, problem, motivation, contributions, method overview), language-controlled via `summarize.language`. |
| **Self-hosted** | Your config and data stay on your machine. |

---

## Quick start

### Environment setup

- **Requirements:** Python 3.10+

First-time setup:

```bash
git clone https://github.com/your-org/daily-paper-agent.git
cd daily-paper-agent

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml`: set `interests.seeds`, `interests.keyphrases`, and (optionally) `delivery.slack.webhook_url`. Paths (`delivery.*`) and limits (`direction.*`) are in the same file.

### Run the agent

Single run:

```bash
python -m paper_agent run --config config.yaml
```

- First run: prints `Processed N new paper(s).` and writes notes/digest/exports.
- Second run with the same state: prints `Processed 0 new paper(s).` (no duplicates).

Then check outputs (Slack + local files) in [Outputs](#outputs).

**Idempotency (no duplicates):** Papers are marked as “seen” in `state_dir/seen.json` **after** local notes, daily digest, and BibTeX/RIS exports are written. Even if Slack delivery fails, the run only logs a warning; the next run will **not** re-send or re-write the same papers.

---

## Configuration

All behavior is driven by `config.yaml` (copy from `config.example.yaml`). Main knobs:

| What | Where in config |
| ---- | ---------------- |
| What you care about | `interests.seeds`, `interests.keyphrases`, `interests.negative_keyphrases` |
| Scope & limits | `direction.allow_categories`, `direction.max_papers_per_day`, `direction.lookback_days` |
| Feedback (policy) | `feedback.blocked_phrases`, `feedback.blocked_authors`, `feedback.boosted_phrases` |
| Selection | `selection.explore_ratio`, `selection.topic_cap`, `selection.min_topics` |
| Policy (bandit) | `policy.type` (`deterministic` \| `linucb`), `policy.alpha`, `policy.lambda_ucb`, `policy.mu_novelty` |
| Sources | `sources.arxiv.enabled`; `sources.scholar_alerts` (v0.2 placeholder: **Inbox Mode** — we do **not** crawl Google Scholar; only user-provided RSS or email exports) |
| Slack brief | `delivery.slack.enabled`, `delivery.slack.webhook_url`, `delivery.slack.max_message_chars` |
| Output dirs | `delivery.library_dir`, `delivery.daily_dir`, `delivery.state_dir`, `delivery.logs_dir` |
| Export formats | `export.formats` (e.g. `["bibtex", "ris"]`) |
| Summaries & language | `summarize.enabled`, `summarize.language` (e.g. `"en"`, `"zh"`), `summarize.research_summary_enabled`, `summarize.brief_one_liner_enabled` |

Timezone for *when* the job runs is set by the environment (e.g. `CRON_TZ`), not by config.

**Google Scholar Alerts (v0.2 placeholder):** Config includes `sources.scholar_alerts` with `enabled: false`, `input: "rss"` (or `"email"`), and `rss_urls: []`. We do **not** crawl or scrape Google Scholar. Any future integration will only ingest **user-provided** RSS links or email exports (Inbox Mode).

**Code layout:** `paper_agent/sources/` (arXiv), `core/` (config, state, preferences, topic_stats, models, dates, logging), `features/` (paper→vector for LinUCB), `policy/` (deterministic + LinUCB, `why_this_paper`), `selection/` (constrained top-k, exploration_pick), `output/`, `deliver/`, `export/`, `pipeline.py`. Entrypoint: `python -m paper_agent run` → `run.py` → `pipeline.run()`. State: `state/seen.json`, `state/preferences.json` (LinUCB), `state/topic_stats.json` (novelty).

---

## Outputs

| Target | Where | Contents | For users? |
|--------|-------|----------|-----------|
| **Slack** (optional) | Slack channel | Brief digest message: title, one-liner, “why this paper”, links. | **Yes** — main daily view if Slack enabled. |
| **Per-paper notes** | `library/` | One file per paper: full note `{id}.md` plus optional `{id}.bib`, `{id}.ris`. | **Yes** — your long-term paper archive. |
| **Daily digests** | `daily/` | One file per day: `YYYY-MM-DD.md` listing that day’s picks with links to `library/` notes. | **Yes** — browse by day. |
| **Logs** | `logs/` | `latest.log` with pipeline counters per run; includes `num_topics`, `exploration_picks` (diversity). | Mostly for debugging. |
| **State** | `state/` | `seen.json` (idempotency), `preferences.json` (LinUCB), `topic_stats.json` (novelty). | No need to edit manually. |

### Slack example

```text
📄 Contrastive Representation Learning for Protein Folding
One-liner: Extends AlphaFold with contrastive pretraining on MSA; +2% on CAMEO.
Why this paper: Keyphrase(s) matched: contrastive learning; In your seeds.
🔗 arXiv: https://arxiv.org/abs/2401.xxxxx  |  Note: 2401.xxxxx.md
```

### Local note example

`library/<id>.md`: title, arXiv ID, published, authors, link, categories, abstract, summary, “Why this paper,” an optional **research-focused summary** section (if `summarize.research_summary_enabled` and an LLM provider are configured), and a Key points section (for your notes). Same paper also gets `<id>.bib` and `<id>.ris` when export is enabled.

---

## How to run and verify (v0.1)

**Run once:**

```bash
cp config.example.yaml config.yaml
# Edit config.yaml: set interests, (optional) delivery.slack.webhook_url, paths
python -m paper_agent run --config config.yaml
```

**Expected:** Console prints `Processed N new paper(s).` (N ≥ 0). Check `delivery.library_dir` for `{arxiv_id}.md`, `{arxiv_id}.bib`, `{arxiv_id}.ris`; `delivery.daily_dir` for `YYYY-MM-DD.md`; `delivery.logs_dir/latest.log` for counts.

**Verify idempotency (no duplicate pushes):**

```bash
python -m paper_agent run --config config.yaml
python -m paper_agent run --config config.yaml  # must print `Processed 0 new paper(s).`
```

Second run must print `Processed 0 new paper(s).` and `logs/latest.log` must show `new_count=0 pushed_count=0`.

**Run tests:**

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

**Verification checklist:**

| Check | Expected |
|-------|----------|
| Second run same day | `Processed 0 new paper(s).`, `new_count=0` in `latest.log` |
| Local outputs | `library/{id}.md`, `library/{id}.bib`, `library/{id}.ris`, `daily/YYYY-MM-DD.md` |
| Each note has | Title, arXiv ID, Published, Authors, Link, Categories, Abstract, Summary, Why this paper, optional research-focused summary (if enabled) |
| Slack (if enabled) | Brief message: title, one-liner (if `summarize.brief_one_liner_enabled`), why_this_paper, arXiv + note links; length ≤ `max_message_chars` |
| Filters | Papers outside `allow_categories` or matching `deny_categories` / `exclude_keywords` / `exclude_authors` are excluded |

---

## Scheduling

Run daily via cron (or your scheduler). Example: 8:00 AM in your timezone:

```bash
CRON_TZ=Asia/Shanghai
0 8 * * * cd /path/to/daily-paper-agent && . .venv/bin/activate && python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
```

---

## Safety & license

- **arXiv:** Respect terms of use and rate limits; avoid aggressive scraping.
- **License:** [MIT](LICENSE).
