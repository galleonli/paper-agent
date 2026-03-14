import { Detail, getPreferenceValues, popToRoot, showToast, Toast } from "@raycast/api";
import { useEffect } from "react";
import { buildRunEnv, parseProcessedCount, prepareRun, runViaRunner } from "./run-utils";

const prefs = getPreferenceValues<Preferences.RunPipeline>();

function RunPipelineView() {
  useEffect(() => {
    let cancelled = false;
    let cleanup: (() => void) | null = null;
    const run = async () => {
      try {
        const prepared = prepareRun(prefs);
        cleanup = prepared.cleanup;
        const { success, stderr, stdout } = await runViaRunner({
          agentRoot: prepared.agentRoot,
          pythonBin: prepared.pythonBin,
          configPath: prepared.configPath,
          env: buildRunEnv(prefs),
          mode: "manual",
        });
        if (cancelled) return;
        if (!cancelled) {
          if (success) {
            const count = parseProcessedCount(stdout ?? "");
            const message = count !== undefined ? `${count} new paper(s)` : undefined;
            await showToast({ style: Toast.Style.Success, title: "Paper Agent finished", message });
          } else {
            await showToast({
              style: Toast.Style.Failure,
              title: "Paper Agent failed",
              message: stderr ? stderr.slice(0, 200) : undefined,
            });
          }
        }
      } catch (err) {
        if (!cancelled) {
          await showToast({
            style: Toast.Style.Failure,
            title: "Paper Agent failed",
            message: err instanceof Error ? err.message : String(err),
          });
        }
      } finally {
        if (cleanup) {
          cleanup();
        }
        if (!cancelled) {
          await popToRoot({ clearSearchBar: true });
        }
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, []);

  return <Detail isLoading={true} markdown="Running Paper Agent…" navigationTitle="Run Paper Agent" />;
}

export default function Command() {
  return <RunPipelineView />;
}
