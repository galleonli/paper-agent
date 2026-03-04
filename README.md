# Paper Intelligence Agent

**Your daily paper digest—tuned to your interests, not keyword soup.**

Discover papers from arXiv, filter by **seeds** and **keyphrases**, get a short *why this paper* for each pick, and receive a brief in Slack plus full notes and BibTeX/RIS locally. Config-driven, catch-up safe, idempotent.

*Like a personal research assistant. One YAML config. Self-hosted. No vendor lock-in.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-API-orange.svg)](https://arxiv.org/help/api)
[![YAML](https://img.shields.io/badge/config-YAML-red.svg)](config.example.yaml)
[![Self-hosted](https://img.shields.io/badge/self--hosted-✓-green.svg)](README.md#features)

[![Slack](https://img.shields.io/badge/Slack-optional-4A154B?logo=slack)](https://slack.com/)
[![BibTeX / RIS](https://img.shields.io/badge/export-BibTeX%20%7C%20RIS-00599C.svg)](README.md#example-output)
[![Idempotent](https://img.shields.io/badge/idempotent-re-run%20safe-lightgrey.svg)](README.md#verification)
[![GPU](https://img.shields.io/badge/GPU-not%20required-brightgreen.svg)](README.md#quick-start)

---

## Features

- **Interest-first** — Seeds (example papers) + keyphrases; every recommendation includes a short “why this paper.”
- **Catch-up safe & idempotent** — Lookback window + persisted state; no missed papers, no duplicate Slack or notes on re-run.
- **Config-first** — One `config.yaml`; no code edits for daily use.
- **Two-level output** — Slack: brief only (title, one-liner, why, links). Local: full notes in `library/`, daily digest in `daily/`.
- **Reference export** — BibTeX and RIS (EndNote-compatible) for Zotero, Mendeley, etc.
- **Self-hosted** — Your config and data stay on your machine.

---

## Quick start

**Requirements:** Python 3.10+

```bash
git clone https://github.com/your-org/daily-paper-agent.git
cd daily-paper-agent
cp config.example.yaml config.yaml
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m paper_agent run --config config.yaml
```

1. **Configure** — Edit `config.yaml`: set `interests.seeds`, `interests.keyphrases`, and (optionally) `delivery.slack.webhook_url`. Paths and limits are in the same file.
2. **Run** — `python -m paper_agent run --config config.yaml`. First run: “Processed N new paper(s).”; second run (same state): “Processed 0 new paper(s).”
3. **Check** — Outputs under `library/` (`.md`, `.bib`, `.ris` per paper) and `daily/YYYY-MM-DD.md`; log in `logs/latest.log`.

---

## Configuration

All behavior is driven by `config.yaml` (copy from `config.example.yaml`). Main knobs:

| What | Where in config |
| ---- | ---------------- |
| What you care about | `interests.seeds`, `interests.keyphrases`, `interests.negative_keyphrases` |
| Scope & limits | `direction.allow_categories`, `direction.max_papers_per_day`, `direction.lookback_days` |
| Slack brief | `delivery.slack.enabled`, `delivery.slack.webhook_url`, `delivery.slack.max_message_chars` |
| Output dirs | `delivery.library_dir`, `delivery.daily_dir`, `delivery.state_dir`, `delivery.logs_dir` |
| Export formats | `export.formats` (e.g. `["bibtex", "ris"]`) |

Timezone for *when* the job runs is set by the environment (e.g. `CRON_TZ`), not by config.

---

## Example output

**Slack (brief only):**

```text
📄 *Contrastive Representation Learning for Protein Folding*
One-liner: Extends AlphaFold with contrastive pretraining on MSA; +2% on CAMEO.
Why this paper: Keyphrase(s) matched: contrastive learning; In your seeds.
🔗 arXiv: https://arxiv.org/abs/2401.xxxxx  |  Note: 2401.xxxxx.md
```

**Local note** (`library/<id>.md`): title, arXiv ID, published, authors, link, categories, abstract, summary, “Why this paper,” and a Key points section (for your notes). Same paper also gets `<id>.bib` and `<id>.ris` when export is enabled.

---

## Scheduling

Run daily via cron (or your scheduler). Example: 8:00 AM in your timezone:

```bash
CRON_TZ=Asia/Shanghai
0 8 * * * cd /path/to/daily-paper-agent && . .venv/bin/activate && python -m paper_agent run --config config.yaml >> logs/cron.log 2>&1
```

---

## Verification

- **First run** (empty state): stdout “Processed N new paper(s).”; new files in `library/` and `daily/`.
- **Second run** (same state): “Processed 0 new paper(s).” — idempotent; no duplicate Slack or files.
- **Log:** `logs/latest.log` contains one line per run with `fetched_total`, `after_lookback`, `after_filters`, `selected`, `new_count`, `pushed_count`, `digest_path`.

Full copy-paste steps and a design-level checklist: [AUDIT.md](AUDIT.md).

---

## Docs

| Doc | Purpose |
| --- | ------- |
| [AUDIT.md](AUDIT.md) | Module overview, run/verify script, verification checklist |
| [SPEC.md](SPEC.md) | Product spec, users, v0.1 definition of done |
| [VERIFICATION.md](VERIFICATION.md) | Checklist with code/test evidence |
| [ROADMAP.md](ROADMAP.md) | v0.1 / v0.2 / v0.3 milestones |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local setup, code style, contribution areas |

---

## Safety & license

- **arXiv:** Respect terms of use and rate limits; no aggressive scraping.
- **License:** [MIT](LICENSE).
