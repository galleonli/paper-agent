# Paper Agent Changelog

All notable changes to the Paper Agent core (pipeline, CLI, config) are documented here.

## [0.4.2] - 2026-10-17

- Install and update the packaged core and CLI during bootstrap, reusing an existing supported Python environment and preserving local configuration.
- Refresh dependencies within supported major versions during installation and updates.
- Update bundled pip and setuptools before installation to avoid retaining known installer vulnerabilities.
- Require certifi 2026.10.19 or later to remove the affected emSign trust root, and audit runtime dependencies before publishing packages.
- Verify bootstrap installation and configuration preservation in CI.
- Publish wheel and source archives with SHA-256 checksums from tested release tags on the main branch.

## [0.4.1] - 2026-10-06

- Package the core as a wheel and source distribution with a `paper-agent` CLI entry point.
- Add Python 3.11 and 3.14 checks and package validation in CI.
- Fix the missing `date` import that prevented pipeline imports on Python 3.11.
- Shorten the README and preserve detailed instructions in the user guide.
- Preserve earlier daily digest entries on repeated runs and resolve local note links against configured directories.
- Record Scholar papers as seen after successful local output; deduplicate alerts before applying the run limit.
- Report email login failures, bound IMAP connection time, and atomically replace seen-state files.
- Check the Python version during bootstrap and cover runner success, failure, and active-lock handling in offline tests.
- Read full process command lines when validating runner locks, including long installation paths.

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
