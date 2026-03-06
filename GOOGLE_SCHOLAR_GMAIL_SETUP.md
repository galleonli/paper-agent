# Google Scholar Alerts + Gmail IMAP Setup

**Purpose:** Google Scholar Alerts are delivered by **email only** (no RSS). This tutorial explains how to configure the **Scholar Inbox** to ingest those alerts directly from Gmail via IMAP—no manual export of mbox or .eml files required.

---

## 1. Recommended setup

1. **Use a dedicated personal Gmail account** (or your main account) for Scholar Alerts.
2. **Create Google Scholar alerts** at [scholar.google.com](https://scholar.google.com) and set delivery to that Gmail address.
3. **Enable 2-Step Verification** on the Gmail account (required for App Passwords).
4. **Generate an App Password** in your Google Account: Security → 2-Step Verification → App passwords. Create one for "Mail" (or "Other").
5. **Export the App Password** as an environment variable:

   ```bash
   export IMAP_PASSWORD='your-16-char-app-password'
   ```

   Do not put the password in `config.yaml`; use `imap_password_env` to point to the env var name.

---

## 2. Config fields to edit

Add or update the following under `sources.scholar_alerts` in `config.yaml`:

```yaml
sources:
  scholar_alerts:
    enabled: true
    mode: "email"
    email:
      provider: "imap"
      imap_host: "imap.gmail.com"
      imap_user: "your_scholar_inbox@gmail.com"
      imap_password_env: "IMAP_PASSWORD"
      gmail_label: "scholar-alerts"
      mbox_path: ""
      eml_dir: ""
      from_addresses: []
    max_items_per_run: 200
    push_to_slack: true
    ordering: "arrival"
    light_filter:
      include_keywords: []
      exclude_keywords:
        - "point cloud"
        - "survey"
      exclude_authors: []
```

| Field | Description |
|-------|-------------|
| `enabled` | Set to `true` to enable Scholar Inbox. |
| `mode` | Must be `"email"` (only email is supported). |
| `email.provider` | Use `"imap"` for Gmail IMAP. |
| `email.imap_host` | `imap.gmail.com` for Gmail. |
| `email.imap_user` | Your Gmail address. |
| `email.imap_password_env` | Name of the environment variable holding the App Password (e.g. `IMAP_PASSWORD`). |
| `email.gmail_label` | Gmail label to read from (e.g. `scholar-alerts`). If the label does not exist or select fails, the agent falls back to `INBOX`. Create the label in Gmail and apply it to Scholar Alert emails for best results. |
| `max_items_per_run` | Cap on Scholar items processed per run (default 200). |
| `ordering` | Only `"arrival"` (email received time, descending). |
| `light_filter` | `include_keywords`, `exclude_keywords`, `exclude_authors`—applied only to Scholar Inbox items. |

---

## 3. Runtime semantics

- **Scholar Inbox does NOT count toward `max_papers_per_day`.** The discovery feed (arXiv) is capped separately; Scholar items are bounded only by `max_items_per_run`.
- **Scholar Inbox does NOT participate in exploration/diversity constraints.** No bandit scoring, topic caps, or min-topics; it is a separate feed.
- **Scholar Inbox is ordered by arrival time** (email received time, descending).
- **Scholar Inbox uses only light filtering** (`include_keywords`, `exclude_keywords`, `exclude_authors`).

---

## 4. Local verification checklist

1. `export IMAP_PASSWORD='your-app-password'`
2. Run the pipeline: `python -m paper_agent run --config config.yaml`
3. Check:
   - `daily/YYYY-MM-DD.md` contains a **Scholar Inbox** section with items
   - `logs/latest.log` shows `scholar_provider=imap` and `scholar_new=N` (N > 0 if you have new alerts)
   - `library/` contains notes for Scholar items (IDs prefixed with `scholar:`)
   - If Slack is enabled: Scholar items appear in the Slack brief when `push_to_slack: true`

---

## 5. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **Wrong IMAP password / missing app password** | Use an App Password, not your main Gmail password. Ensure `IMAP_PASSWORD` is set in the environment before running. |
| **2-Step Verification not enabled** | App Passwords require 2-Step Verification. Enable it in Google Account → Security. |
| **Org/school Gmail blocks app passwords** | Some Google Workspace accounts disable App Passwords. Use a personal Gmail or `mbox`/`eml_dir` export instead. |
| **No Scholar alert emails in the mailbox yet** | Create alerts at scholar.google.com and wait for at least one delivery. Check that emails arrive in the configured label or INBOX. |
| **Label exists but is not used** | The implementation uses `gmail_label` when configured. If the label select fails (e.g. label name differs), Gmail IMAP falls back to `INBOX`. Ensure the label name matches exactly (e.g. `scholar-alerts`). |

---

## 6. Safety note

- **No Google Scholar crawling.** We do not scrape or crawl Google Scholar.
- **Email ingestion only.** The agent reads emails you provide (via mbox, eml_dir, or IMAP) and parses Scholar Alert message content. No other access to Google Scholar.
