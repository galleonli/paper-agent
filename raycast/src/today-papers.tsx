import { ActionPanel, List, Action } from "@raycast/api";
import * as fs from "node:fs";
import * as path from "node:path";

const PROJECT_ROOT = "/Users/dominik/Desktop/paper";
const LIBRARY_DIR = path.join(PROJECT_ROOT, "library");

type ResearchSummary = {
  heading?: string;
  body?: string;
};

type Paper = {
  id: string;
  title: string;
  date: string;
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

function getTodayDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function loadTodayPapers(): Paper[] {
  const dateDir = path.join(LIBRARY_DIR, getTodayDateString());
  if (!fs.existsSync(dateDir)) return [];

  const files = fs.readdirSync(dateDir).filter((f) => f.endsWith(".json"));
  const papers: Paper[] = [];

  for (const file of files) {
    try {
      const jsonPath = path.join(dateDir, file);
      const raw = fs.readFileSync(jsonPath, "utf-8");
      const data = JSON.parse(raw) as Record<string, unknown>;

      const id = (data.id as string) ?? path.basename(file, ".json");
      const rawNotePath = data.note_path as string | undefined;
      const notePath = rawNotePath
        ? path.join(PROJECT_ROOT, rawNotePath)
        : path.join(dateDir, `${path.basename(file, ".json")}.md`);

      const rs = data.research_summary as Record<string, unknown> | undefined;
      const dateStr = getTodayDateString();
      const date = (data.date as string) ?? dateStr;
      const published = data.published as string | undefined;
      papers.push({
        id,
        title: (data.title as string) ?? "Untitled",
        date,
        published,
        authors: data.authors as string[] | undefined,
        abstract: data.abstract as string | undefined,
        whyThisPaper: data.why_this_paper as string | undefined,
        categories: data.categories as string[] | undefined,
        researchSummary: rs
          ? { heading: rs.heading as string, body: rs.body as string }
          : undefined,
        link: data.link as string | undefined,
        notePath,
        hasNote: fs.existsSync(notePath),
      });
    } catch {
      continue;
    }
  }

  const sortKey = (p: Paper) => p.published ?? p.date;
  return papers.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
}

export default function Command() {
  const papers = loadTodayPapers();

  return (
    <List isShowingDetail>
      {papers.map((paper) => (
        <List.Item
          key={paper.id}
          title={paper.title}
          subtitle={paper.authors?.length ? paper.authors.join(", ") : undefined}
          detail={
            <List.Item.Detail
              markdown={`# ${paper.title}

${paper.authors?.length ? `**Authors:** ${paper.authors.join(", ")}\n\n` : ""}${paper.categories?.length ? `**Categories:** ${paper.categories.join(", ")}\n\n` : ""}**Date:** ${paper.published ?? paper.date}

---

${paper.abstract ?? "No abstract available."}

---

**Why this paper**

${paper.whyThisPaper ?? "N/A"}
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
