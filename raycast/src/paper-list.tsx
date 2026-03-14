import { Action, ActionPanel, Color, Icon, List, Toast, showToast } from "@raycast/api";
import { type ReactElement, useEffect, useMemo, useState } from "react";
import { type Paper, renderPaperDetailMarkdown } from "./paper-utils";
import { useFavoritePapers } from "./favorite-utils";
import { getPaperStateKey, useReadPapers } from "./read-utils";

const READ_AFTER_MS = 5000;

type SubtitleMode = "authors" | "date-and-authors";

type PaperListViewProps = {
  papers: Paper[];
  emptyTitle: string;
  emptyDescription: string;
  subtitleMode: SubtitleMode;
  showOpenFavoritesAction?: boolean;
  searchBarPlaceholder?: string;
  onSearchTextChange?: (text: string) => void;
};

function buildSubtitle(paper: Paper, subtitleMode: SubtitleMode): string | undefined {
  if (subtitleMode === "authors") {
    return paper.authors?.length ? paper.authors.join(", ") : undefined;
  }

  const subtitle = [paper.date, paper.authors?.length ? paper.authors.join(", ") : undefined]
    .filter(Boolean)
    .join(" · ");
  return subtitle || undefined;
}

async function toggleFavoritePaper(
  paper: Paper,
  isFavorite: boolean,
  addFavorite: (paper: Paper) => Promise<void>,
  removeFavorite: (paper: Paper) => Promise<void>,
): Promise<void> {
  try {
    if (isFavorite) {
      await removeFavorite(paper);
      await showToast({
        style: Toast.Style.Success,
        title: "Removed from favorites",
        message: paper.title,
      });
      return;
    }

    await addFavorite(paper);
    await showToast({
      style: Toast.Style.Success,
      title: "Added to favorites",
      message: paper.title,
    });
  } catch (error) {
    await showToast({
      style: Toast.Style.Failure,
      title: isFavorite ? "Failed to remove favorite" : "Failed to add favorite",
      message: error instanceof Error ? error.message : paper.title,
    });
  }
}

async function toggleReadPaper(
  paper: Paper,
  isRead: boolean,
  markAsRead: (paper: Paper) => Promise<void>,
  markAsUnread: (paper: Paper) => Promise<void>,
): Promise<void> {
  try {
    if (isRead) {
      await markAsUnread(paper);
      await showToast({
        style: Toast.Style.Success,
        title: "Marked as unread",
        message: paper.title,
      });
      return;
    }

    await markAsRead(paper);
    await showToast({
      style: Toast.Style.Success,
      title: "Marked as read",
      message: paper.title,
    });
  } catch (error) {
    await showToast({
      style: Toast.Style.Failure,
      title: isRead ? "Failed to mark as unread" : "Failed to mark as read",
      message: error instanceof Error ? error.message : paper.title,
    });
  }
}

function PaperActions(props: {
  paper: Paper;
  isFavorite: boolean;
  isRead: boolean;
  favoriteCount: number;
  addFavorite: (paper: Paper) => Promise<void>;
  removeFavorite: (paper: Paper) => Promise<void>;
  markAsRead: (paper: Paper) => Promise<void>;
  markAsUnread: (paper: Paper) => Promise<void>;
  showOpenFavoritesAction: boolean;
}): ReactElement {
  const {
    paper,
    isFavorite,
    isRead,
    favoriteCount,
    addFavorite,
    removeFavorite,
    markAsRead,
    markAsUnread,
    showOpenFavoritesAction,
  } = props;

  return (
    <ActionPanel>
      {paper.link && <Action.OpenInBrowser url={paper.link} title="Open Paper" />}
      {paper.hasNote && <Action.Open title="Open Local Note" target={paper.notePath} />}
      <Action
        title={isRead ? "Mark as Unread" : "Mark as Read"}
        icon={isRead ? Icon.Circle : Icon.CheckCircle}
        onAction={() => toggleReadPaper(paper, isRead, markAsRead, markAsUnread)}
      />
      <Action
        title={isFavorite ? "Remove from Favorites" : "Add to Favorites"}
        icon={isFavorite ? Icon.XMarkCircle : Icon.Star}
        onAction={() => toggleFavoritePaper(paper, isFavorite, addFavorite, removeFavorite)}
      />
      {showOpenFavoritesAction && (
        <Action.Push
          title={favoriteCount > 0 ? `Open Favorites (${favoriteCount})` : "Open Favorites"}
          icon={Icon.Star}
          target={<FavoritePapersView />}
        />
      )}
    </ActionPanel>
  );
}

export function PaperListView({
  papers,
  emptyTitle,
  emptyDescription,
  subtitleMode,
  showOpenFavoritesAction = true,
  searchBarPlaceholder,
  onSearchTextChange,
}: PaperListViewProps): ReactElement {
  const { favorites, isLoading, isFavorite, addFavorite, removeFavorite } = useFavoritePapers();
  const { isLoading: isReadLoading, isRead, markAsRead, markAsUnread } = useReadPapers();
  const [selectedItemId, setSelectedItemId] = useState<string | undefined>();
  const papersById = useMemo(() => new Map(papers.map((paper) => [getPaperStateKey(paper), paper])), [papers]);

  useEffect(() => {
    if (!selectedItemId) {
      return;
    }

    const selectedPaper = papersById.get(selectedItemId);
    if (!selectedPaper || isRead(selectedPaper)) {
      return;
    }

    const timer = setTimeout(() => {
      void markAsRead(selectedPaper);
    }, READ_AFTER_MS);

    return () => clearTimeout(timer);
  }, [selectedItemId, papersById, isRead, markAsRead]);

  return (
    <List
      isShowingDetail
      isLoading={isLoading || isReadLoading}
      searchBarPlaceholder={searchBarPlaceholder}
      onSearchTextChange={onSearchTextChange}
      onSelectionChange={setSelectedItemId}
    >
      {papers.length === 0 && <List.EmptyView title={emptyTitle} description={emptyDescription} />}
      {papers.map((paper) => {
        const favorite = isFavorite(paper);
        const read = isRead(paper);
        const subtitle = buildSubtitle(paper, subtitleMode);
        const accessories = [];

        accessories.push({
          icon: { source: read ? Icon.CheckCircle : Icon.Circle, tintColor: read ? Color.Green : Color.SecondaryText },
          tooltip: read ? "Read" : "Unread",
        });

        if (favorite) {
          accessories.push({
            icon: { source: Icon.Star, tintColor: Color.Yellow },
            tooltip: "In favorites",
          });
        }

        return (
          <List.Item
            id={getPaperStateKey(paper)}
            key={getPaperStateKey(paper)}
            title={paper.title}
            subtitle={subtitle}
            accessories={accessories}
            detail={<List.Item.Detail markdown={renderPaperDetailMarkdown(paper, paper.published ?? paper.date)} />}
            actions={
              <PaperActions
                paper={paper}
                isFavorite={favorite}
                isRead={read}
                favoriteCount={favorites.length}
                addFavorite={addFavorite}
                removeFavorite={removeFavorite}
                markAsRead={markAsRead}
                markAsUnread={markAsUnread}
                showOpenFavoritesAction={showOpenFavoritesAction}
              />
            }
          />
        );
      })}
    </List>
  );
}

export function FavoritePapersView(): ReactElement {
  const { favorites, isLoading, addFavorite, removeFavorite } = useFavoritePapers();
  const { isLoading: isReadLoading, isRead, markAsRead, markAsUnread } = useReadPapers();
  const [selectedItemId, setSelectedItemId] = useState<string | undefined>();
  const favoritesById = useMemo(() => new Map(favorites.map((paper) => [getPaperStateKey(paper), paper])), [favorites]);

  useEffect(() => {
    if (!selectedItemId) {
      return;
    }

    const selectedPaper = favoritesById.get(selectedItemId);
    if (!selectedPaper || isRead(selectedPaper)) {
      return;
    }

    const timer = setTimeout(() => {
      void markAsRead(selectedPaper);
    }, READ_AFTER_MS);

    return () => clearTimeout(timer);
  }, [selectedItemId, favoritesById, isRead, markAsRead]);

  return (
    <List isShowingDetail isLoading={isLoading || isReadLoading} onSelectionChange={setSelectedItemId}>
      {favorites.length === 0 && (
        <List.EmptyView
          title="No favorites yet"
          description="Add papers to favorites from Today Papers, Recent Papers, or Search Papers."
        />
      )}
      {favorites.map((paper) => (
        <List.Item
          id={getPaperStateKey(paper)}
          key={getPaperStateKey(paper)}
          title={paper.title}
          subtitle={buildSubtitle(paper, "date-and-authors")}
          accessories={[
            {
              icon: {
                source: isRead(paper) ? Icon.CheckCircle : Icon.Circle,
                tintColor: isRead(paper) ? Color.Green : Color.SecondaryText,
              },
              tooltip: isRead(paper) ? "Read" : "Unread",
            },
            {
              icon: { source: Icon.Star, tintColor: Color.Yellow },
              tooltip: "In favorites",
            },
          ]}
          detail={<List.Item.Detail markdown={renderPaperDetailMarkdown(paper, paper.published ?? paper.date)} />}
          actions={
            <PaperActions
              paper={paper}
              isFavorite
              isRead={isRead(paper)}
              favoriteCount={favorites.length}
              addFavorite={addFavorite}
              removeFavorite={removeFavorite}
              markAsRead={markAsRead}
              markAsUnread={markAsUnread}
              showOpenFavoritesAction={false}
            />
          }
        />
      ))}
    </List>
  );
}
