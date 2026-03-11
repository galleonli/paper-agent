/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Config file path - Path to Paper Agent config.yaml (same file used by Config.py). */
  "configPath": string,
  /** Paper directory - Root directory for papers (daily digest and notes). Library is stored under paper_dir/library. Maps to delivery.paper_dir. */
  "paperDir": string,
  /** Python executable - Optional override for Python binary (defaults to .venv/bin/python3 in the Paper Agent repo). */
  "pythonPath": string,
  /** Recent papers limit - Maximum number of papers shown in Recent Papers (used as --limit for the list CLI). */
  "recentLimit": string,
  /** Max papers per day - Maps to direction.max_papers_per_day in config.yaml. */
  "maxPapersPerDay": string,
  /** Lookback days - Maps to direction.lookback_days (catch-up window). */
  "lookbackDays": string,
  /** Interest keyphrases - Comma-separated interest keyphrases (maps to direction.include_keywords). */
  "keyphrases": string,
  /** Allow categories - Comma-separated arXiv categories to include (maps to direction.allow_categories). */
  "allowCategories": string,
  /** Deny categories - Comma-separated categories to exclude (maps to direction.deny_categories). */
  "denyCategories": string,
  /** Exclude keywords - Comma-separated keywords; papers matching these are excluded (maps to direction.exclude_keywords). */
  "excludeKeywords": string,
  /** Enable LLM research summary - When on, the three options below are used to generate research summaries. When off, they are ignored. */
  "summarizeEnabled": boolean,
  /** Summary provider - Only used when "Enable LLM research summary" is on. LLM provider (e.g. openai). */
  "summarizeProvider": string,
  /** Summary model - Only used when "Enable LLM research summary" is on. Model name (e.g. gpt-4o-mini). */
  "summarizeModel": string,
  /** Summary language - Only used when "Enable LLM research summary" is on. Maps to summarize.language. */
  "summarizeLanguage": "en" | "zh" | "ja" | "de",
  /** Enable Scholar Inbox - Toggles sources.scholar_alerts.enabled in config.yaml. */
  "scholarEnabled": boolean
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `today-papers` command */
  export type TodayPapers = ExtensionPreferences & {}
  /** Preferences accessible in the `recent-papers` command */
  export type RecentPapers = ExtensionPreferences & {}
  /** Preferences accessible in the `search-papers` command */
  export type SearchPapers = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `today-papers` command */
  export type TodayPapers = {}
  /** Arguments passed to the `recent-papers` command */
  export type RecentPapers = {}
  /** Arguments passed to the `search-papers` command */
  export type SearchPapers = {}
}

