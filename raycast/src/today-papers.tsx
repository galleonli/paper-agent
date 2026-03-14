import { List, getPreferenceValues } from "@raycast/api";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { withEffectiveConfigPath } from "./config-utils";
import { type Paper, parseCliPapers } from "./paper-utils";
import { PaperListView } from "./paper-list";

const prefs = getPreferenceValues<Preferences.TodayPapers>();
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

function getTodayDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function loadTodayPapers(): Paper[] {
  if (!HAS_CONFIG || !HAS_PAPER_DIR) {
    return [];
  }

  let rawJson = "";
  try {
    rawJson = withEffectiveConfigPath(CONFIG_PATH, PREF_PAPER_DIR, (effectiveConfigPath) =>
      execFileSync(PYTHON_BIN, ["-m", "paper_agent", "today", "--json", "--config", effectiveConfigPath], {
        cwd: AGENT_ROOT,
        encoding: "utf-8",
      }),
    );
  } catch {
    // If CLI is not available or fails, fall back to empty list.
    return [];
  }

  return parseCliPapers(rawJson, {
    paperDir: PAPER_DIR,
    libraryDir: LIBRARY_DIR,
    fallbackDate: getTodayDateString(),
  });
}

export default function Command() {
  if (!HAS_CONFIG || !HAS_PAPER_DIR) {
    return (
      <List>
        <List.EmptyView
          title="Set preferences first"
          description="Set both 'Config file path' and 'Paper directory' in extension preferences."
        />
      </List>
    );
  }

  const papers = loadTodayPapers();

  return (
    <PaperListView
      papers={papers}
      emptyTitle="No papers shown"
      emptyDescription="Config and Paper directory are set but no data came back. Check: Config path is the full path to config.yaml; Paper directory is your paper repo root; Python at .venv/bin/python3 (or Preferences) has paper_agent installed; you have run the pipeline at least once."
      subtitleMode="authors"
    />
  );
}
