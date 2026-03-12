import { ActionPanel, List, Action, getPreferenceValues } from "@raycast/api";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { resolveDeliveryDirs, withEffectiveConfigPath } from "./config-utils";
import { type Paper, parseCliPapers, renderPaperDetailMarkdown } from "./paper-utils";

const prefs = getPreferenceValues<Preferences.TodayPapers>();
const CONFIG_PATH = prefs.configPath?.trim() ?? "";
const HAS_CONFIG = CONFIG_PATH.length > 0;
const PREF_PAPER_DIR = prefs.paperDir?.trim() ?? "";
const { paperDir: PAPER_DIR, libraryDir: LIBRARY_DIR } = resolveDeliveryDirs(CONFIG_PATH, PREF_PAPER_DIR);
const HAS_PAPER_DIR = PAPER_DIR.length > 0;
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
      execFileSync(
        PYTHON_BIN,
        ["-m", "paper_agent", "today", "--json", "--config", effectiveConfigPath],
        { cwd: AGENT_ROOT, encoding: "utf-8" }
      )
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
          description="Set 'Config file path' in preferences. 'Paper directory' can be set in preferences or config.yaml (delivery.paper_dir)."
        />
      </List>
    );
  }

  const papers = loadTodayPapers();

  return (
    <List isShowingDetail>
      {papers.length === 0 && (
        <List.EmptyView
          title="No papers shown"
          description="Config and Paper directory are set but no data came back. Check: Config path is the full path to config.yaml; Paper directory is your paper repo root; Python at .venv/bin/python3 (or Preferences) has paper_agent installed; you have run the pipeline at least once."
        />
      )}
      {papers.map((paper) => (
        <List.Item
          key={paper.id}
          title={paper.title}
          subtitle={paper.authors?.length ? paper.authors.join(", ") : undefined}
          detail={
            <List.Item.Detail
              markdown={renderPaperDetailMarkdown(paper, paper.published ?? paper.date)}
            />
          }
          actions={
            <ActionPanel>
              {paper.link && <Action.OpenInBrowser url={paper.link} title="Open Paper" />}
              {paper.hasNote && <Action.Open title="Search Paper" target={paper.notePath} />}
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
