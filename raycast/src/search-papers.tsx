import { List, getPreferenceValues } from "@raycast/api";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { useMemo, useState } from "react";
import { withEffectiveConfigPath } from "./config-utils";
import { type Paper, parseCliPapers } from "./paper-utils";
import { PaperListView } from "./paper-list";

const prefs = getPreferenceValues<Preferences.SearchPapers>();
const CONFIG_PATH = prefs.configPath?.trim() ?? "";
const HAS_CONFIG = CONFIG_PATH.length > 0;
const PREF_PAPER_DIR = prefs.paperDir?.trim() ?? "";
const PAPER_DIR = PREF_PAPER_DIR;
const LIBRARY_DIR = PREF_PAPER_DIR ? path.join(PREF_PAPER_DIR, "library") : "";
const HAS_PAPER_DIR = PREF_PAPER_DIR.length > 0;
const AGENT_ROOT = HAS_CONFIG ? path.dirname(CONFIG_PATH) : "";
const PYTHON_BIN =
  prefs.pythonPath && prefs.pythonPath.trim().length > 0
    ? prefs.pythonPath
    : path.join(AGENT_ROOT, ".venv", "bin", "python3");

function loadSearchResults(query: string): Paper[] {
  if (!HAS_CONFIG || !HAS_PAPER_DIR) {
    return [];
  }
  let rawJson = "";
  try {
    rawJson = withEffectiveConfigPath(CONFIG_PATH, PREF_PAPER_DIR, (effectiveConfigPath) =>
      execFileSync(
        PYTHON_BIN,
        ["-m", "paper_agent", "search", "--query", query, "--json", "--config", effectiveConfigPath],
        { cwd: AGENT_ROOT, encoding: "utf-8" },
      ),
    );
  } catch {
    return [];
  }

  return parseCliPapers(rawJson, {
    paperDir: PAPER_DIR,
    libraryDir: LIBRARY_DIR,
    fallbackDate: "unknown",
  });
}

export default function Command() {
  const [searchText, setSearchText] = useState("");
  const papers = useMemo(() => (HAS_CONFIG && HAS_PAPER_DIR ? loadSearchResults(searchText) : []), [searchText]);

  if (!HAS_CONFIG || !HAS_PAPER_DIR) {
    return (
      <List
        isShowingDetail
        searchBarPlaceholder="Search by title, authors, abstract, date..."
        onSearchTextChange={setSearchText}
      >
        <List.EmptyView
          title="Set preferences first"
          description="Set both 'Config file path' and 'Paper directory' in extension preferences."
        />
      </List>
    );
  }

  return (
    <PaperListView
      papers={papers}
      emptyTitle="No papers or CLI failed"
      emptyDescription="Check: Config path = full path to config.yaml; Paper directory = paper repo root; .venv/bin/python3 has paper_agent; run the pipeline at least once."
      subtitleMode="date-and-authors"
      searchBarPlaceholder="Search by title, authors, abstract, date..."
      onSearchTextChange={setSearchText}
    />
  );
}
