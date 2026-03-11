/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {}

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

