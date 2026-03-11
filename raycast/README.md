# Paper Agent Raycast

Raycast extension for [Paper Agent](https://github.com/galleonli/paper-agent).

This extension provides a minimal interface for browsing today's local papers and opening local Markdown notes from a Paper Agent workflow.

## Status

Early MVP. The API and behavior may change between versions.

## Requirements

- Raycast
- A local Paper Agent library (JSON outputs under a date-based folder structure)

## Getting Started

- Clone this repository.
- Install dependencies with `npm install`.
- In Raycast, enable the Developer Tools (if not already enabled).
- Run `npm run dev` to load the extension in Raycast during development.

## Configuration

By default, the extension expects your Paper Agent project at:

- Paper directory and config path (set in Raycast Preferences; no hardcoded path)
- Library layout: `<paper_dir>/library/<YYYY-MM-DD>/*.json`

If your Paper Agent project lives elsewhere, set **Config file path** and **Paper directory** in the extension Preferences (Raycast → Extensions → Paper Agent → Preferences).

For **Recent Papers**, the limit is set in extension Preferences (Recent papers limit).

## Commands

### Today Papers

Reads today's papers from the local library **without** invoking the Paper Agent CLI.

- **Source:** `<library_dir>/<YYYY-MM-DD>/*.json` (library path is hardcoded in code).
- **Detail pane:** Title; authors and categories only when present; full abstract; "Why this paper"; research summary (heading + body) when present.
- **Actions:** Open paper (browser), Open local note (when a matching `.md` exists next to the JSON).
- **Note path:** Uses `note_path` from JSON if set, otherwise derives `<date_dir>/<basename>.md`.

### Recent Papers

- **Source:** `<library_dir>/<YYYY-MM-DD>/*.json` from the last few days (window is hardcoded in code).
- **Sorting:** Newest first, using `published` when present, otherwise `date` from the JSON or folder name.

### Search Papers

- **Scope:** All JSON files under `<library_dir>/*/*.json`.
- **Searchable fields:** `title`, `authors`, `summary`, `abstract`, `categories`, `id`, `date`, `published`.
- **Matching:** Case-insensitive substring match; the query is split on whitespace and **all tokens must match** (AND logic) for a paper to be included.
- **Ranking priority:** Among matching papers, results are ranked so that:
  - Matches in `title` or `authors` are considered most important.
  - Matches in `abstract` are next.
  - Matches in `summary` / `categories` and metadata fields (`id`, `date`, `published`) are lower priority.
- **Phrase preference:** If the whole query phrase appears contiguously in `title` or `authors`, that paper gets a strong boost; contiguous matches in `abstract` or `summary` / `categories` also improve the score over scattered matches.
- **Recency tie-breaker:** When scores are equal, papers are sorted by recency (`published` when present, otherwise `date`) from newest to oldest.
- **Date matching:** Direct substrings work (e.g. `2026`, `2026-03`, `2026-03-11`). In addition, short arXiv-style date tokens of the form `YYMM.DD` are normalized to `20YY-MM-DD`. For example, typing `2603.11` is treated as `2026-03-11` and will match papers whose `date` or `published` contains `2026-03-11`.

## Development

- **Build:** `npm run build`
- **Lint:** `npm run lint`

## License

This extension is released under the MIT License. See `LICENSE` for details.
