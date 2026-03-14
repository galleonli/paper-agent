import { LocalStorage } from "@raycast/api";
import * as fs from "node:fs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type Paper } from "./paper-utils";
import { getPaperStateKey } from "./read-utils";

const READING_QUEUE_STORAGE_KEY = "reading-queue-papers";

export type QueuedPaper = Paper & {
  queuedAt: string;
};

function normalizePaper(paper: Paper): Paper {
  return {
    ...paper,
    hasNote: fs.existsSync(paper.notePath),
  };
}

function sortQueue(queue: QueuedPaper[]): QueuedPaper[] {
  return [...queue].sort((left, right) => right.queuedAt.localeCompare(left.queuedAt));
}

async function readQueue(): Promise<QueuedPaper[]> {
  const raw = await LocalStorage.getItem<string>(READING_QUEUE_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    const queue = parsed
      .filter((entry): entry is QueuedPaper => !!entry && typeof entry === "object")
      .map((entry) => ({
        ...normalizePaper(entry),
        queuedAt: typeof entry.queuedAt === "string" ? entry.queuedAt : new Date(0).toISOString(),
      }));

    return sortQueue(queue);
  } catch {
    return [];
  }
}

async function writeQueue(queue: QueuedPaper[]): Promise<void> {
  await LocalStorage.setItem(READING_QUEUE_STORAGE_KEY, JSON.stringify(sortQueue(queue)));
}

export function useReadingQueue() {
  const [queue, setQueue] = useState<QueuedPaper[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const reloadQueue = useCallback(async () => {
    setIsLoading(true);
    const next = await readQueue();
    setQueue(next);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void reloadQueue();
  }, [reloadQueue]);

  const queueKeys = useMemo(() => new Set(queue.map((paper) => getPaperStateKey(paper))), [queue]);

  const isQueued = useCallback((paper: Paper) => queueKeys.has(getPaperStateKey(paper)), [queueKeys]);

  const addToQueue = useCallback(
    async (paper: Paper) => {
      const next = sortQueue([
        ...queue.filter((entry) => getPaperStateKey(entry) !== getPaperStateKey(paper)),
        {
          ...normalizePaper(paper),
          queuedAt: new Date().toISOString(),
        },
      ]);
      await writeQueue(next);
      setQueue(next);
    },
    [queue],
  );

  const removeFromQueue = useCallback(
    async (paper: Paper) => {
      const next = queue.filter((entry) => getPaperStateKey(entry) !== getPaperStateKey(paper));
      await writeQueue(next);
      setQueue(next);
    },
    [queue],
  );

  return {
    queue,
    isLoading,
    isQueued,
    addToQueue,
    removeFromQueue,
    reloadQueue,
  };
}
