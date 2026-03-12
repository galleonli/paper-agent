import { ActionPanel, List, Action, getPreferenceValues } from "@raycast/api";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { useMemo, useState } from "react";
import { resolveDeliveryDirs, withEffectiveConfigPath } from "./config-utils";
import { type Paper, parseCliPapers, renderPaperDetailMarkdown } from "./paper-utils";

const prefs = getPreferenceValues<Preferences.SearchPapers>();
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
        { cwd: AGENT_ROOT, encoding: "utf-8" }
      )
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

  const papers = useMemo(() => loadSearchResults(searchText), [searchText]);

  return (
    <List
      isShowingDetail
      searchBarPlaceholder="Search by title, authors, abstract, date..."
      onSearchTextChange={setSearchText}
    >
      {(!HAS_CONFIG || !HAS_PAPER_DIR) && (
        <List.EmptyView
          title="Set preferences first"
          description="Set 'Config file path' in preferences. 'Paper directory' can be set in preferences or config.yaml (delivery.paper_dir)."
        />
      )}
      {HAS_CONFIG && HAS_PAPER_DIR && papers.length === 0 && (
        <List.EmptyView
          title="No papers or CLI failed"
          description="Check: Config path = full path to config.yaml; Paper directory = paper repo root; .venv/bin/python3 has paper_agent; run the pipeline at least once."
        />
      )}
      {HAS_CONFIG && HAS_PAPER_DIR &&
        papers.map((paper) => (
        <List.Item
          key={`${paper.date}-${paper.id}`}
          title={paper.title}
          subtitle={[paper.date, paper.authors?.length ? paper.authors.join(", ") : undefined]
            .filter(Boolean)
            .join(" · ")}
          detail={
            <List.Item.Detail
              markdown={renderPaperDetailMarkdown(paper, paper.date)}
            />
          }
          actions={
            <ActionPanel>
              {paper.link && <Action.OpenInBrowser url={paper.link} title="Open Paper Link" />}
              {paper.hasNote && (
                <Action.Open title="Open Local Note" target={paper.notePath} />
              )}
            </ActionPanel>
          }
        />))}
    </List>
  );
}
