import { Detail, getPreferenceValues, popToRoot, showToast, Toast } from "@raycast/api";
import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";
import * as os from "node:os";
import { useEffect } from "react";
import yaml from "js-yaml";
import { applyPaperDirOverride } from "./config-utils";

const prefs = getPreferenceValues<Preferences.RunPipeline>();
const CONFIG_PATH = prefs.configPath?.trim() ?? "";
const PREF_PAPER_DIR = prefs.paperDir?.trim() ?? "";
const AGENT_ROOT = CONFIG_PATH.length > 0 ? path.dirname(CONFIG_PATH) : "";
const PYTHON_BIN =
  prefs.pythonPath && prefs.pythonPath.trim().length > 0
    ? prefs.pythonPath.trim()
    : path.join(AGENT_ROOT, ".venv", "bin", "python3");

function parseList(value: string | undefined): string[] {
  if (!value || !value.trim()) return [];
  return value
    // Support comma/newline/semicolon (including Chinese punctuation) separators.
    .split(/[\n,，;；]+/g)
    .map((s) => s.trim())
    .filter(Boolean);
}

function parseRequiredPositiveInt(value: string | undefined, fieldName: string): { ok: true; value: number } | { ok: false; message: string } {
  const raw = value?.trim() ?? "";
  if (!raw) {
    return { ok: false, message: `${fieldName} is required in extension Preferences.` };
  }
  const n = parseInt(raw, 10);
  if (Number.isNaN(n) || n < 1) {
    return { ok: false, message: `${fieldName} must be a positive integer.` };
  }
  return { ok: true, value: n };
}

/**
 * Merge YAML config with Raycast preferences. Preferences override YAML when the pref has a value
 * (for text fields: when non-empty after trim; for checkbox/dropdown: always).
 * Package.json defaults for maxPapersPerDay, lookbackDays, allowCategories are non-empty, so those always override.
 */
function mergeConfig(base: Record<string, unknown>): Record<string, unknown> {
  const merged = applyPaperDirOverride(base, PREF_PAPER_DIR);

  if (!merged.direction || typeof merged.direction !== "object") {
    merged.direction = {};
  }
  const direction = merged.direction as Record<string, unknown>;
  direction.max_papers_per_day = parseInt(prefs.maxPapersPerDay?.trim() ?? "", 10);
  direction.lookback_days = parseInt(prefs.lookbackDays?.trim() ?? "", 10);
  direction.include_keywords = parseList(prefs.keyphrases);
  direction.allow_categories = parseList(prefs.allowCategories);
  direction.deny_categories = parseList(prefs.denyCategories);
  direction.exclude_keywords = parseList(prefs.excludeKeywords);

  if (!merged.summarize || typeof merged.summarize !== "object") {
    merged.summarize = {};
  }
  const summarize = merged.summarize as Record<string, unknown>;
  summarize.enabled = prefs.summarizeEnabled;
  summarize.provider = prefs.summarizeEnabled ? (prefs.summarizeProvider?.trim() ?? "") : "openai";
  summarize.model = prefs.summarizeEnabled ? (prefs.summarizeModel?.trim() ?? "") : "gpt-4o-mini";
  summarize.language = prefs.summarizeLanguage;

  if (!merged.sources || typeof merged.sources !== "object") {
    merged.sources = {};
  }
  const sources = merged.sources as Record<string, unknown>;

  // arXiv: always on (preference overrides config)
  if (!sources.arxiv || typeof sources.arxiv !== "object") {
    sources.arxiv = {};
  }
  (sources.arxiv as Record<string, unknown>).enabled = true;

  // Scholar Alerts: mode email only; all from preferences
  if (!sources.scholar_alerts || typeof sources.scholar_alerts !== "object") {
    sources.scholar_alerts = {};
  }
  const scholar = sources.scholar_alerts as Record<string, unknown>;
  scholar.enabled = prefs.scholarEnabled;
  scholar.mode = "email";
  if (!scholar.light_filter || typeof scholar.light_filter !== "object") {
    scholar.light_filter = { include_keywords: [], exclude_keywords: [] };
  }
  if (!scholar.email || typeof scholar.email !== "object") {
    scholar.email = {};
  }
  const email = scholar.email as Record<string, unknown>;
  const provider = (prefs.scholarProvider?.trim() ?? "").toLowerCase();
  email.provider = provider || "imap";
  email.imap_host = prefs.scholarImapHost?.trim() ?? "";
  email.imap_user = prefs.scholarImapUser?.trim() ?? "";
  email.imap_password_env = prefs.scholarImapPasswordEnv?.trim() ?? "";
  email.gmail_label = prefs.scholarGmailLabel?.trim() ?? "";
  const fromAddrs = prefs.scholarFromAddresses?.trim();
  email.from_addresses = fromAddrs ? parseList(fromAddrs) : [];
  email.mbox_path = "";
  email.eml_dir = "";

  // Policy: set from preference (off = required-keyword match only)
  if (!merged.policy || typeof merged.policy !== "object") {
    merged.policy = {};
  }
  (merged.policy as Record<string, unknown>).type = prefs.policyType ?? "off";

  return merged;
}

/** Matches "Processed N new paper(s)." from paper_agent CLI stdout. */
function parseProcessedCount(stdout: string): number | undefined {
  const m = stdout.match(/Processed\s+(\d+)\s+new\s+paper/i);
  return m ? parseInt(m[1], 10) : undefined;
}

/** Build env for the pipeline child: process.env plus optional secrets from Preferences. */
function buildRunEnv(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  const openaiKey = prefs.openaiApiKey?.trim();
  if (openaiKey) {
    env.OPENAI_API_KEY = openaiKey;
  }
  const imapEnvName = prefs.scholarImapPasswordEnv?.trim() || "IMAP_PASSWORD";
  const imapPassword = prefs.scholarImapPassword?.trim();
  if (imapPassword) {
    env[imapEnvName] = imapPassword;
  }
  return env;
}

function runPipeline(configPath: string): Promise<{ success: boolean; stderr?: string; stdout?: string }> {
  return new Promise((resolve) => {
    let stderr = "";
    let stdout = "";
    const proc = spawn(PYTHON_BIN, ["-m", "paper_agent", "run", "--config", configPath], {
      cwd: AGENT_ROOT,
      env: buildRunEnv(),
    });
    proc.stdout?.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    proc.stderr?.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({
        success: code === 0,
        stderr: stderr.trim() || undefined,
        stdout: stdout.trim() || undefined,
      });
    });
    proc.on("error", () => {
      resolve({ success: false, stderr: "Failed to start process" });
    });
  });
}

type PrepareResult =
  | { ok: true; tempConfigPath: string }
  | { ok: false; title: string; message?: string };

function prepareRun(): PrepareResult {
  if (!CONFIG_PATH) {
    return { ok: false, title: "Config path required", message: "Set Config file path in extension Preferences." };
  }
  if (!fs.existsSync(CONFIG_PATH)) {
    return { ok: false, title: "Config not found", message: CONFIG_PATH };
  }
  let base: Record<string, unknown>;
  try {
    const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
    const loaded = yaml.load(raw);
    if (loaded == null || typeof loaded !== "object" || Array.isArray(loaded)) {
      return { ok: false, title: "Invalid config", message: "Config must be a YAML object, not a string or array." };
    }
    base = loaded as Record<string, unknown>;
  } catch (e) {
    return { ok: false, title: "Invalid config YAML", message: e instanceof Error ? e.message : String(e) };
  }
  if (!PREF_PAPER_DIR) {
    return {
      ok: false,
      title: "Paper directory required",
      message: "Set 'Paper directory' in extension Preferences for Run Paper Agent.",
    };
  }
  const maxPapersParsed = parseRequiredPositiveInt(prefs.maxPapersPerDay, "Max papers per day");
  if (!maxPapersParsed.ok) {
    return { ok: false, title: "Invalid preference", message: maxPapersParsed.message };
  }
  const lookbackParsed = parseRequiredPositiveInt(prefs.lookbackDays, "Lookback days");
  if (!lookbackParsed.ok) {
    return { ok: false, title: "Invalid preference", message: lookbackParsed.message };
  }
  if (prefs.summarizeEnabled) {
    if (!(prefs.summarizeProvider?.trim() ?? "")) {
      return { ok: false, title: "Invalid preference", message: "Summary provider is required when LLM summary is enabled." };
    }
    if (!(prefs.summarizeModel?.trim() ?? "")) {
      return { ok: false, title: "Invalid preference", message: "Summary model is required when LLM summary is enabled." };
    }
  }
  if (prefs.scholarEnabled) {
    const provider = (prefs.scholarProvider?.trim() ?? "").toLowerCase();
    if (!provider) {
      return { ok: false, title: "Invalid preference", message: "Scholar email provider is required when Scholar Inbox is enabled." };
    }
    if (!["imap", "gmail", "mbox", "eml_dir"].includes(provider)) {
      return { ok: false, title: "Invalid preference", message: "Scholar email provider must be one of: imap, gmail, mbox, eml_dir." };
    }
    if (provider === "mbox" || provider === "eml_dir") {
      return {
        ok: false,
        title: "Unsupported in Preferences",
        message: `Scholar provider '${provider}' requires local paths not exposed in Raycast Preferences. Use imap/gmail or CLI config.`,
      };
    }
    if (!(prefs.scholarImapHost?.trim() ?? "")) {
      return { ok: false, title: "Invalid preference", message: "Scholar IMAP host is required when Scholar Inbox is enabled." };
    }
    if (!(prefs.scholarImapUser?.trim() ?? "")) {
      return { ok: false, title: "Invalid preference", message: "Scholar IMAP user is required when Scholar Inbox is enabled." };
    }
    if (!(prefs.scholarImapPasswordEnv?.trim() ?? "")) {
      return { ok: false, title: "Invalid preference", message: "Scholar IMAP password env var is required when Scholar Inbox is enabled." };
    }
    const imapEnvName = prefs.scholarImapPasswordEnv?.trim() || "IMAP_PASSWORD";
    const hasImapPassword = !!(prefs.scholarImapPassword?.trim() || process.env[imapEnvName]);
    if (!hasImapPassword) {
      return {
        ok: false,
        title: "Scholar IMAP password required",
        message: "Set 'Scholar IMAP password' in Preferences or set the env var (e.g. IMAP_PASSWORD) so Raycast can pass it to the pipeline.",
      };
    }
  }
  const merged = mergeConfig(base);
  const tempConfigPath = path.join(
    os.tmpdir(),
    `paper-agent-run-${Date.now()}-${Math.random().toString(36).slice(2, 10)}.yaml`
  );
  try {
    fs.writeFileSync(tempConfigPath, yaml.dump(merged), "utf-8");
  } catch (e) {
    return {
      ok: false,
      title: "Failed to write temp config",
      message: e instanceof Error ? e.message : String(e),
    };
  }
  return { ok: true, tempConfigPath };
}

function RunPipelineView() {
  useEffect(() => {
    let cancelled = false;
    let tempConfigPath: string | null = null;
    const run = async () => {
      try {
        const prepared = prepareRun();
        if (!prepared.ok) {
          if (!cancelled) {
            await showToast({ style: Toast.Style.Failure, title: prepared.title, message: prepared.message });
          }
          return;
        }
        tempConfigPath = prepared.tempConfigPath;
        const { success, stderr, stdout } = await runPipeline(tempConfigPath);
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
            title: "Paper Agent error",
            message: err instanceof Error ? err.message : String(err),
          });
        }
      } finally {
        if (tempConfigPath) {
          try {
            if (fs.existsSync(tempConfigPath)) {
              fs.unlinkSync(tempConfigPath);
            }
          } catch {
            // ignore cleanup errors
          }
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

  return (
    <Detail
      isLoading={true}
      markdown="Running Paper Agent…"
      navigationTitle="Run Paper Agent"
    />
  );
}

export default function Command() {
  return <RunPipelineView />;
}
