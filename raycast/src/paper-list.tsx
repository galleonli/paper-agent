import { Action, ActionPanel, Color, Icon, List, Toast, showToast } from "@raycast/api";
import { type ReactElement } from "react";
import { type Paper, renderPaperDetailMarkdown } from "./paper-utils";
import { useFavoritePapers } from "./favorite-utils";

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

function PaperActions(props: {
  paper: Paper;
  isFavorite: boolean;
  favoriteCount: number;
  addFavorite: (paper: Paper) => Promise<void>;
  removeFavorite: (paper: Paper) => Promise<void>;
  showOpenFavoritesAction: boolean;
}): ReactElement {
  const { paper, isFavorite, favoriteCount, addFavorite, removeFavorite, showOpenFavoritesAction } = props;

  return (
    <ActionPanel>
      {paper.link && <Action.OpenInBrowser url={paper.link} title="Open Paper" />}
      {paper.hasNote && <Action.Open title="Open Local Note" target={paper.notePath} />}
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

  return (
    <List
      isShowingDetail
      isLoading={isLoading}
      searchBarPlaceholder={searchBarPlaceholder}
      onSearchTextChange={onSearchTextChange}
    >
      {papers.length === 0 && <List.EmptyView title={emptyTitle} description={emptyDescription} />}
      {papers.map((paper) => {
        const favorite = isFavorite(paper);
        const subtitle = buildSubtitle(paper, subtitleMode);

        return (
          <List.Item
            key={`${paper.date}-${paper.id}`}
            title={paper.title}
            subtitle={subtitle}
            accessories={
              favorite
                ? [
                    {
                      icon: { source: Icon.Star, tintColor: Color.Yellow },
                      tooltip: "In favorites",
                    },
                  ]
                : undefined
            }
            detail={<List.Item.Detail markdown={renderPaperDetailMarkdown(paper, paper.published ?? paper.date)} />}
            actions={
              <PaperActions
                paper={paper}
                isFavorite={favorite}
                favoriteCount={favorites.length}
                addFavorite={addFavorite}
                removeFavorite={removeFavorite}
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

  return (
    <List isShowingDetail isLoading={isLoading}>
      {favorites.length === 0 && (
        <List.EmptyView
          title="No favorites yet"
          description="Add papers to favorites from Today Papers, Recent Papers, or Search Papers."
        />
      )}
      {favorites.map((paper) => (
        <List.Item
          key={`${paper.date}-${paper.id}`}
          title={paper.title}
          subtitle={buildSubtitle(paper, "date-and-authors")}
          accessories={[
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
              favoriteCount={favorites.length}
              addFavorite={addFavorite}
              removeFavorite={removeFavorite}
              showOpenFavoritesAction={false}
            />
          }
        />
      ))}
    </List>
  );
}
