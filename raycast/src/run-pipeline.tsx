import { Detail, getPreferenceValues, popToRoot, showToast, Toast } from "@raycast/api";
import { useEffect } from "react";
import { buildRunEnv, parseProcessedCount, prepareRun, runViaRunner } from "./run-utils";

const prefs = getPreferenceValues<Preferences.RunPipeline>();

function parseSkipMessage(output: string): string | undefined {
  if (output.includes("Skipping run because another Paper Agent process is active.")) {
    return "Another Paper Agent run is already active.";
  }
  if (output.includes("Skipping daily run before")) {
    return "Skipped because the daily schedule has not reached its run hour yet.";
  }
  if (output.includes("Skipping daily run because today's run already succeeded.")) {
    return "Skipped because today's scheduled run already succeeded.";
  }
  return undefined;
}

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
            const skipMessage = parseSkipMessage([stdout ?? "", stderr ?? ""].join("\n"));
            if (skipMessage) {
              await showToast({
                style: Toast.Style.Failure,
                title: "Paper Agent skipped",
                message: skipMessage,
              });
              return;
            }
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
