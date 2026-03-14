import { List, getPreferenceValues } from "@raycast/api";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { withEffectiveConfigPath } from "./config-utils";
import { type Paper, parseCliPapers } from "./paper-utils";
import { PaperListView } from "./paper-list";

const prefs = getPreferenceValues<Preferences.RecentPapers>();
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
const DEFAULT_LIMIT = 30;
const rawLimit = prefs.recentLimit;
const parsedLimit = typeof rawLimit === "number" ? rawLimit : parseInt(String(rawLimit ?? "").trim(), 10);
const RECENT_LIMIT = Number.isNaN(parsedLimit) || parsedLimit < 1 ? DEFAULT_LIMIT : Math.min(parsedLimit, 500);

function loadRecentPapers(limit: number = RECENT_LIMIT): Paper[] {
  if (!HAS_CONFIG || !HAS_PAPER_DIR) {
    return [];
  }
  let rawJson = "";
  try {
    rawJson = withEffectiveConfigPath(CONFIG_PATH, PREF_PAPER_DIR, (effectiveConfigPath) =>
      execFileSync(
        PYTHON_BIN,
        ["-m", "paper_agent", "list", "--json", "--limit", String(limit), "--config", effectiveConfigPath],
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

  const papers = loadRecentPapers();

  return (
    <PaperListView
      papers={papers}
      emptyTitle="No papers shown"
      emptyDescription="Config and Paper directory are set but no data came back. Check: Config path is the full path to config.yaml; Paper directory is your paper repo root; Python at .venv/bin/python3 (or Preferences) has paper_agent installed; you have run the pipeline at least once."
      subtitleMode="date-and-authors"
    />
  );
}
