import { getPreferenceValues, showToast, Toast } from "@raycast/api";
import * as fs from "node:fs";
import * as path from "node:path";
import { spawn } from "node:child_process";
import * as os from "node:os";
import yaml from "js-yaml";
import { applyPaperDirOverride, getPaperDirFromConfigObject } from "./config-utils";

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
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
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
  const maxPapers = prefs.maxPapersPerDay?.trim();
  if (maxPapers) {
    const n = parseInt(maxPapers, 10);
    if (!Number.isNaN(n)) direction.max_papers_per_day = n;
  }
  const lookback = prefs.lookbackDays?.trim();
  if (lookback) {
    const n = parseInt(lookback, 10);
    if (!Number.isNaN(n)) direction.lookback_days = n;
  }
  if (prefs.keyphrases?.trim()) {
    direction.include_keywords = parseList(prefs.keyphrases);
  }
  if (prefs.allowCategories?.trim()) {
    direction.allow_categories = parseList(prefs.allowCategories);
  }
  if (prefs.denyCategories?.trim()) {
    direction.deny_categories = parseList(prefs.denyCategories);
  }
  if (prefs.excludeKeywords?.trim()) {
    direction.exclude_keywords = parseList(prefs.excludeKeywords);
  }

  if (!merged.summarize || typeof merged.summarize !== "object") {
    merged.summarize = {};
  }
  const summarize = merged.summarize as Record<string, unknown>;
  summarize.enabled = prefs.summarizeEnabled;
  summarize.provider = prefs.summarizeProvider?.trim() || "openai";
  summarize.model = prefs.summarizeModel?.trim() || "gpt-4o-mini";
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
  const provider = prefs.scholarProvider?.trim();
  email.provider = provider || "imap";
  email.imap_host = prefs.scholarImapHost?.trim() ?? "";
  email.imap_user = prefs.scholarImapUser?.trim() ?? "";
  email.imap_password_env = prefs.scholarImapPasswordEnv?.trim() || "IMAP_PASSWORD";
  email.gmail_label = prefs.scholarGmailLabel?.trim() || "scholar-alerts";
  const fromAddrs = prefs.scholarFromAddresses?.trim();
  email.from_addresses = fromAddrs ? parseList(fromAddrs) : [];
  email.mbox_path = "";
  email.eml_dir = "";

  // Policy: set from preference (LinUCB or Deterministic)
  if (prefs.policyType === "linucb" || prefs.policyType === "deterministic") {
    if (!merged.policy || typeof merged.policy !== "object") {
      merged.policy = {};
    }
    (merged.policy as Record<string, unknown>).type = prefs.policyType;
  }

  return merged;
}

function runPipeline(configPath: string): Promise<{ success: boolean; stderr?: string }> {
  return new Promise((resolve) => {
    let stderr = "";
    const proc = spawn(PYTHON_BIN, ["-m", "paper_agent", "run", "--config", configPath], {
      cwd: AGENT_ROOT,
      env: process.env,
    });
    proc.stderr?.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    proc.on("close", (code) => {
      resolve({ success: code === 0, stderr: stderr.trim() || undefined });
    });
    proc.on("error", () => {
      resolve({ success: false, stderr: "Failed to start process" });
    });
  });
}

export default async function Command() {
  if (!CONFIG_PATH) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Config path required",
      message: "Set Config file path in extension Preferences.",
    });
    return;
  }

  if (!fs.existsSync(CONFIG_PATH)) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Config not found",
      message: CONFIG_PATH,
    });
    return;
  }

  let base: Record<string, unknown>;
  try {
    const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
    const loaded = yaml.load(raw);
    if (loaded == null || typeof loaded !== "object" || Array.isArray(loaded)) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Invalid config",
        message: "Config must be a YAML object, not a string or array.",
      });
      return;
    }
    base = loaded as Record<string, unknown>;
  } catch (e) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Invalid config YAML",
      message: e instanceof Error ? e.message : String(e),
    });
    return;
  }

  const effectivePaperDir = PREF_PAPER_DIR || getPaperDirFromConfigObject(base);
  if (!effectivePaperDir) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Paper directory not set",
      message: "Set 'Paper directory' in Preferences or config.yaml delivery.paper_dir.",
    });
    return;
  }

  const merged = mergeConfig(base);
  const tempConfigPath = path.join(
    os.tmpdir(),
    `paper-agent-run-${Date.now()}-${Math.random().toString(36).slice(2, 10)}.yaml`
  );
  try {
    fs.writeFileSync(tempConfigPath, yaml.dump(merged), "utf-8");
  } catch (e) {
    await showToast({
      style: Toast.Style.Failure,
      title: "Failed to write temp config",
      message: e instanceof Error ? e.message : String(e),
    });
    return;
  }

  try {
    await showToast({
      style: Toast.Style.Animated,
      title: "Running Paper Agent…",
    });

    const { success, stderr } = await runPipeline(tempConfigPath);

    if (success) {
      await showToast({
        style: Toast.Style.Success,
        title: "Paper Agent finished",
      });
    } else {
      await showToast({
        style: Toast.Style.Failure,
        title: "Paper Agent failed",
        message: stderr ? stderr.slice(0, 200) : undefined,
      });
    }
  } finally {
    try {
      if (fs.existsSync(tempConfigPath)) {
        fs.unlinkSync(tempConfigPath);
      }
    } catch {
      // ignore cleanup errors
    }
  }

}
