## Hyperparameter Tuning Guide (Advanced / Legacy)

This guide is for **advanced users** who want to inspect or tune the remaining
selection / legacy hyperparameter knobs beyond the defaults.
Most users can ignore this file and only edit `interests.*`, `direction.*`,
`selection.*`, and `delivery.*` in `config.yaml`.

Scope note: this guide is for **Daily Precision (arXiv discovery)** only.
Scholar Inbox (`sources.scholar_alerts.*`) does not use `policy.*`,
`selection.*`, or `autotune.*`.

Current behavior summary:

- The active/default discovery path is effectively `policy.type: "off"`.
- Candidate ranking is based on required-keyword tiering:
  title keyword match > abstract keyword match > seed match.
- Final picks still go through `selection.*`
  (`max_papers_per_day`, `explore_ratio`, `topic_cap`, `min_topics`).
- Legacy `policy.*` / `autotune.*` fields remain in config mainly for backward
  compatibility and experimentation, but they are not the recommended path.

---

### 1. When NOT to tune

Do **not** touch `policy.*` or `autotune.*` if:

- You are still shaping your **queries / required keywords / filters**.
- You mainly care about “are these papers on-topic?” rather than micro-optimizing exploration.
- You are running the agent for the first few weeks.

For most users:

- Set up `direction.*` (categories, lookback_days, max_papers_per_day,
  include_keywords, exclude_keywords).
- Add `interests.seeds` only if you have useful seed papers.
- Tune `selection.*` (`explore_ratio`, `topic_cap`, `min_topics`) only after
  your keyword filter is working well.
- Leave `policy.type: "off"` and ignore `policy.*` / `autotune.*`.

This already gives a solid Daily Precision feed.

Clarification:

- `direction.lookback_days` is a global catch-up window and also affects Scholar Inbox ingestion.
- `direction.max_papers_per_day` applies to discovery only (Scholar Inbox is bounded by `sources.scholar_alerts.max_items_per_run`).

---

### 2. Legacy policy hyperparameters (`policy.*`)

```yaml
policy:
  type: "off"             # recommended / current path
  # Legacy compatibility only:
  # type: "deterministic"  # accepted by config loader
  # type: "linucb"         # accepted by config loader
  # alpha: 0.5
  # lambda_ucb: 1.0
  # mu_novelty: 0.3
  # ridge: 1.0
```

- **`type`**
  - `"off"`: current/default discovery path. Uses required-keyword tiering plus
    `selection.*` constraints.
  - `"deterministic"` / `"linucb"`: accepted by config validation for backward
    compatibility, but not the recommended/current pipeline path.

- **`alpha`** (uncertainty scale)
  - Effect: how strongly to boost **uncertain** papers.
  - Too low → pure exploitation; too high → noisy exploration.
  - Safe range: `0.3–1.5`. Default around `0.5` is a balanced choice.

- **`lambda_ucb`** (weight for uncertainty)
  - Effect: how much the **uncertainty term** contributes to the final score.
  - If you do adjust, treat `alpha * lambda_ucb` as one knob (overall exploration strength).

- **`mu_novelty`** (weight for novelty)
  - Effect: how much to boost **novel topics / phrases**.
  - Too low → converge to familiar topics; too high → feed becomes noisy with fringe topics.
  - Safe range: `0.1–0.7`. Default around `0.3` is conservative.

- **`ridge`** (L2 regularization)
  - Effect: numerical stability and how fast LinUCB adapts.
  - Too small → overfit / unstable; too large → slow learning.
  - Safe range: `0.5–5.0`. Default `1.0` is a standard, stable choice.

**Recommendation:** in the current codebase, leave `type` at `"off"` and avoid
changing the other `policy.*` fields unless you are intentionally auditing or
reviving legacy behavior.

---

### 3. AutoTune (`autotune.*`) — legacy / experimental

AutoTune is an **optional meta-controller** intended to tune legacy `policy.*`
hyperparameters based on **feedback + diversity/novelty reward**.
It is not part of the recommended/default `policy.type: "off"` workflow.

In `config.example.yaml` it is commented out and looks like:

```yaml
# autotune:
#   enabled: false
#   method: "thompson"
#   schedule:
#     daily_hour_utc: 23
#     weekly_day_of_week: "sun"
#   candidates:
#     - id: "baseline"
#       alpha: 0.5
#       lambda_ucb: 1.0
#       mu_novelty: 0.3
#       ridge: 1.0
#   reward:
#     signals:
#       click: 0.2
#       open_note: 0.5
#       star: 1.0
#       export: 1.5
#       skip: -0.05
#       mute: -2.0
#     diversity:
#       num_topics: 0.1
#       exploration_picks: 0.05
#       avg_novelty: 0.2
```

#### 3.1 When to consider AutoTune

- You are explicitly experimenting with the legacy tuning path, and:
  - you log feedback events (click/open/star/export/skip/mute) into
    `state/feedback_log.jsonl` or `state/feedback.yaml`,
  - you want the system to automatically search for a better balance of
    exploration / novelty.

If you are not logging feedback yet, **leave `autotune.enabled=false`**.

#### 3.2 Minimal AutoTune setup

1. Audit the current code path before relying on AutoTune in production.
2. If you still want the legacy experiment, set `policy.type: "linucb"` and
   verify that the runtime path you want is still present in the current code.
3. Uncomment the `autotune` block in your `config.yaml`.
4. Keep:
   - `enabled: true`
   - `method: "thompson"`
   - A small set of candidates (e.g. 2–3) that differ in `alpha`, `lambda_ucb`, `mu_novelty`.
5. Ensure feedback events are written daily.

In the current codebase, AutoTune is only relevant for the legacy experiment and
is active only when **both** are true:

- `autotune.enabled: true`
- `policy.type: "linucb"`

AutoTune will:

- pick a candidate each run,
- compute a scalar reward from feedback + diversity/novelty,
- update `state/autotune.json`,
- log chosen candidate and reward in `logs/latest.log`.

---

### 4. Safe tuning workflow

1. **Lock config for 1–2 weeks**
   - Only adjust `interests.*`, `direction.*`, and `selection.*`.
   - Keep `policy.type: "off"`.
2. **Tune selection only if needed**
   - Adjust `topic_cap`, `min_topics`, or `explore_ratio` after your keyword
     filter is stable.
   - Inspect `logs/latest.log` to see `after_filters`, `selected`, `num_topics`,
     and `exploration_picks`.
3. **Consider legacy experiments only if necessary**
   - Only if you are comfortable with the current behavior and have feedback logs.
   - Start with very few changes and verify the actual runtime path in code.
4. **Change one thing at a time**
   - Do not change `direction.*`, `selection.*`, `policy.*`, and `autotune.*`
     all at once.
   - After each change, run for several days before drawing conclusions.

If in doubt, prefer **simpler config** and let the defaults work for you.

