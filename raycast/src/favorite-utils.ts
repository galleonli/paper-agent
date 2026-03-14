import { LocalStorage } from "@raycast/api";
import * as fs from "node:fs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type Paper } from "./paper-utils";
import { getPaperStateKey } from "./read-utils";

const FAVORITES_STORAGE_KEY = "favorite-papers";

export type FavoritePaper = Paper & {
  favoritedAt: string;
};

function normalizePaper(paper: Paper): Paper {
  return {
    ...paper,
    hasNote: fs.existsSync(paper.notePath),
  };
}

function sortFavorites(favorites: FavoritePaper[]): FavoritePaper[] {
  return [...favorites].sort((left, right) => right.favoritedAt.localeCompare(left.favoritedAt));
}

async function readFavorites(): Promise<FavoritePaper[]> {
  const raw = await LocalStorage.getItem<string>(FAVORITES_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    const favorites = parsed
      .filter((entry): entry is FavoritePaper => !!entry && typeof entry === "object")
      .map((entry) => ({
        ...normalizePaper(entry),
        favoritedAt: typeof entry.favoritedAt === "string" ? entry.favoritedAt : new Date(0).toISOString(),
      }));

    return sortFavorites(favorites);
  } catch {
    return [];
  }
}

async function writeFavorites(favorites: FavoritePaper[]): Promise<void> {
  await LocalStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(sortFavorites(favorites)));
}

export function useFavoritePapers() {
  const [favorites, setFavorites] = useState<FavoritePaper[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const reloadFavorites = useCallback(async () => {
    setIsLoading(true);
    const next = await readFavorites();
    setFavorites(next);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void reloadFavorites();
  }, [reloadFavorites]);

  const favoriteKeys = useMemo(() => new Set(favorites.map((paper) => getPaperStateKey(paper))), [favorites]);

  const isFavorite = useCallback((paper: Paper) => favoriteKeys.has(getPaperStateKey(paper)), [favoriteKeys]);

  const addFavorite = useCallback(
    async (paper: Paper) => {
      const next = sortFavorites([
        ...favorites.filter((entry) => getPaperStateKey(entry) !== getPaperStateKey(paper)),
        {
          ...normalizePaper(paper),
          favoritedAt: new Date().toISOString(),
        },
      ]);
      await writeFavorites(next);
      setFavorites(next);
    },
    [favorites],
  );

  const removeFavorite = useCallback(
    async (paper: Paper) => {
      const next = favorites.filter((entry) => getPaperStateKey(entry) !== getPaperStateKey(paper));
      await writeFavorites(next);
      setFavorites(next);
    },
    [favorites],
  );

  return {
    favorites,
    isLoading,
    isFavorite,
    addFavorite,
    removeFavorite,
    reloadFavorites,
  };
}
