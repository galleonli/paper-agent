# Paper Agent Changelog

All notable changes to the Paper Agent core (pipeline, CLI, config) are documented here.

## [0.4.0] - 2026-03-16

### Added

- CLI diagnostics: `diagnostics` command for config, paths, and environment checks (see README).

### Changed

- Documentation: repository references (core vs Raycast), clearer README structure and troubleshooting.
- Bootstrap: macOS/Unix only; removed Windows bootstrap script; virtual environment instructions simplified.
- Raycast extension lives in a separate repo: [paper-agent-raycast](https://github.com/galleonli/paper-agent-raycast).

### Fixed

- Local output path handling and test assertions for delivered paths.

---

## [0.3.0]

- Daily Precision (arXiv): explainable filtering, required/exclude keywords, seed support.
- Scholar Inbox: ingest from mbox, .eml, or Gmail IMAP.
- Weekly digests: top topics, categories, authors, highlighted papers, summary sentence.
- Related local papers: backfill and surface in notes/Raycast.
- Idempotent, catch-up safe runs; local notes, daily/weekly digests, optional BibTeX/RIS export.
