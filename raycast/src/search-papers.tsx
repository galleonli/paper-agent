import { ActionPanel, List, Action } from "@raycast/api";
import * as fs from "node:fs";
import * as path from "node:path";
import { useMemo, useState } from "react";

const PROJECT_ROOT = "/Users/dominik/Desktop/paper";
const LIBRARY_DIR = path.join(PROJECT_ROOT, "library");

type ResearchSummary = {
  heading?: string;
  body?: string;
};

type Paper = {
  id: string;
  date: string;
  title: string;
  authors?: string[];
  abstract?: string;
  summary?: string;
  whyThisPaper?: string;
  categories?: string[];
  researchSummary?: ResearchSummary;
  link?: string;
  notePath: string;
  hasNote: boolean;
  published?: string;
};

function safeString(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(safeString).join(" ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function loadAllPapers(): Paper[] {
  if (!fs.existsSync(LIBRARY_DIR)) return [];

  const dateDirs = fs.readdirSync(LIBRARY_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  const papers: Paper[] = [];

  for (const dateStr of dateDirs) {
    const dateDir = path.join(LIBRARY_DIR, dateStr);
    const files = fs.readdirSync(dateDir).filter((f) => f.endsWith(".json"));

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
        const date = safeString(data.date || dateStr);
        const published = data.published != null ? safeString(data.published) : undefined;

        papers.push({
          id,
          date,
          title: (data.title as string) ?? "Untitled",
          authors: data.authors as string[] | undefined,
          abstract: data.abstract as string | undefined,
          summary: data.summary as string | undefined,
          whyThisPaper: data.why_this_paper as string | undefined,
          categories: data.categories as string[] | undefined,
          researchSummary: rs
            ? { heading: rs.heading as string, body: rs.body as string }
            : undefined,
          link: data.link as string | undefined,
          notePath,
          hasNote: fs.existsSync(notePath),
          published,
        });
      } catch {
        continue;
      }
    }
  }

  return papers;
}

function buildSearchBlob(paper: Paper): string {
  const parts = [
    paper.title,
    paper.authors?.join(" ") ?? "",
    paper.summary ?? "",
    paper.abstract ?? "",
    paper.categories?.join(" ") ?? "",
    paper.id,
    paper.date,
    paper.published ?? "",
  ];
  return parts.join(" ").toLowerCase();
}

function hasAllTokens(blob: string, queryTokens: string[]): boolean {
  if (queryTokens.length === 0) return true;
  return queryTokens.every((t) => t.length === 0 || blob.includes(t.toLowerCase()));
}

function normalizeQueryTokens(text: string): string[] {
  return text
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => {
      const lower = token.toLowerCase();

      // Support arXiv-style short date input like "2603.11" -> "2026-03-11"
      const m = /^(\d{2})(\d{2})\.(\d{1,2})$/.exec(lower);
      if (m) {
        const year = `20${m[1]}`;
        const month = m[2];
        const day = m[3].padStart(2, "0");
        return `${year}-${month}-${day}`;
      }

      return lower;
    });
}

function scorePaper(paper: Paper, queryTokens: string[], fullQuery: string): number {
  if (queryTokens.length === 0) return 0;

  const title = (paper.title ?? "").toLowerCase();
  const authors = (paper.authors?.join(" ") ?? "").toLowerCase();
  const abstract = (paper.abstract ?? "").toLowerCase();
  const summary = (paper.summary ?? "").toLowerCase();
  const categories = (paper.categories?.join(" ") ?? "").toLowerCase();
  const id = paper.id.toLowerCase();
  const date = (paper.date ?? "").toLowerCase();
  const published = (paper.published ?? "").toLowerCase();

  let score = 0;

  for (const token of queryTokens) {
    if (!token) continue;
    if (title.includes(token) || authors.includes(token)) {
      // Highest weight: title and author names
      score += 4;
    } else if (abstract.includes(token)) {
      // Next: abstract
      score += 2;
    } else if (summary.includes(token) || categories.includes(token)) {
      // Then: summary and categories
      score += 1;
    } else if (id.includes(token) || date.includes(token) || published.includes(token)) {
      // Lowest priority: id and date fields
      score += 1;
    }
  }

  const phrase = fullQuery.toLowerCase();
  if (phrase.length > 0) {
    // Contiguous phrase matches are better than scattered matches
    if (title.includes(phrase) || authors.includes(phrase)) {
      score += 10;
    } else if (abstract.includes(phrase)) {
      score += 5;
    } else if (summary.includes(phrase) || categories.includes(phrase)) {
      score += 2;
    }
  }

  return score;
}

export default function Command() {
  const [searchText, setSearchText] = useState("");

  const allPapers = useMemo(() => loadAllPapers(), []);
  const searchBlobs = useMemo(
    () => new Map(allPapers.map((p) => [p.id + p.date, buildSearchBlob(p)])),
    [allPapers]
  );

  const queryTokens = useMemo(
    () => normalizeQueryTokens(searchText),
    [searchText]
  );

  const sortedPapers = useMemo(() => {
    const dateKey = (p: Paper) => p.published ?? p.date ?? "";
    const fullQuery = queryTokens.join(" ");

    if (queryTokens.length === 0) {
      return [...allPapers].sort((a, b) => dateKey(b).localeCompare(dateKey(a)));
    }
    return [...allPapers]
      .filter((paper) => {
        const blob = searchBlobs.get(paper.id + paper.date) ?? buildSearchBlob(paper);
        return hasAllTokens(blob, queryTokens);
      })
      .map((paper) => ({
        paper,
        score: scorePaper(paper, queryTokens, fullQuery),
      }))
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return dateKey(b.paper).localeCompare(dateKey(a.paper));
      })
      .map(({ paper }) => paper);
  }, [allPapers, searchBlobs, queryTokens]);

  return (
    <List
      isShowingDetail
      searchBarPlaceholder="Search by title, authors, summary, date..."
      onSearchTextChange={setSearchText}
    >
      {sortedPapers.map((paper) => (
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

${paper.summary ?? paper.abstract ?? "No abstract or summary available."}

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
              {paper.link && <Action.OpenInBrowser url={paper.link} title="Open Paper Link" />}
              {paper.hasNote && (
                <Action.Open title="Open Local Note" target={paper.notePath} />
              )}
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
