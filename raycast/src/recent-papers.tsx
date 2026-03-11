import { ActionPanel, List, Action } from "@raycast/api";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";

const PROJECT_ROOT = "/Users/dominik/Desktop/paper";
const LIBRARY_DIR = path.join(PROJECT_ROOT, "library");
const AGENT_ROOT = "/Users/dominik/Desktop/agents/daily-paper-agent";
const CONFIG_PATH = path.join(AGENT_ROOT, "config.yaml");
const PYTHON_BIN = path.join(AGENT_ROOT, ".venv", "bin", "python3");
const DEFAULT_LIMIT = 30;

type ResearchSummary = {
  heading?: string;
  body?: string;
};

type Paper = {
  id: string;
  date: string;
  title: string;
  published?: string;
  authors?: string[];
  abstract?: string;
  whyThisPaper?: string;
  categories?: string[];
  researchSummary?: ResearchSummary;
  link?: string;
  notePath: string;
  hasNote: boolean;
};

function loadRecentPapers(limit: number = DEFAULT_LIMIT): Paper[] {
  let rawJson = "";
  try {
    rawJson = execFileSync(
      PYTHON_BIN,
      ["-m", "paper_agent", "list", "--json", "--limit", String(limit), "--config", CONFIG_PATH],
      { cwd: AGENT_ROOT, encoding: "utf-8" }
    );
  } catch {
    return [];
  }

  let data: unknown;
  try {
    data = JSON.parse(rawJson);
  } catch {
    return [];
  }

  if (!Array.isArray(data)) {
    return [];
  }

  return data
    .filter((e): e is Record<string, unknown> => !!e && typeof e === "object")
    .map((e) => {
      const id = (e.id as string) ?? "";
      const date = (e.date as string) ?? "";
      const published = e.published as string | undefined;
      const rawNotePath = e.note_path as string | undefined;
      const notePath = rawNotePath
        ? path.join(PROJECT_ROOT, rawNotePath)
        : path.join(LIBRARY_DIR, date || "unknown", `${id || "note"}.md`);
      const rs = e.research_summary as Record<string, unknown> | undefined;

      return {
        id: id || path.basename(notePath, ".md"),
        date,
        title: (e.title as string) ?? "Untitled",
        published,
        authors: e.authors as string[] | undefined,
        abstract: e.abstract as string | undefined,
        whyThisPaper: e.why_this_paper as string | undefined,
        categories: e.categories as string[] | undefined,
        researchSummary: rs
          ? { heading: rs.heading as string, body: rs.body as string }
          : undefined,
        link: e.link as string | undefined,
        notePath,
        hasNote: fs.existsSync(notePath),
      } satisfies Paper;
    });
}

export default function Command() {
  const papers = loadRecentPapers();

  return (
    <List isShowingDetail>
      {papers.map((paper) => (
        <List.Item
          key={`${paper.date}-${paper.id}`}
          title={paper.title}
          subtitle={[paper.date, paper.authors?.length ? paper.authors.join(", ") : undefined]
            .filter(Boolean)
            .join(" · ")}
          detail={
            <List.Item.Detail
              markdown={`# ${paper.title}

${paper.authors?.length ? `**Authors:** ${paper.authors.join(", ")}\n\n` : ""}${paper.categories?.length ? `**Categories:** ${paper.categories.join(", ")}\n\n` : ""}**Date:** ${paper.date}

---

**Why this paper**

${paper.whyThisPaper ?? "N/A"}

---

${paper.abstract ?? "No abstract available."}
${paper.researchSummary?.body ? `

---

## ${paper.researchSummary.heading ?? "Research summary"}

${paper.researchSummary.body}` : ""}
${paper.link ? `\n---\n[Open Paper](${paper.link})` : ""}
`}
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
