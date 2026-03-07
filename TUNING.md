## Hyperparameter Tuning Guide (Advanced)

This guide is for **advanced users** who want to tune bandit / agent hyperparameters beyond the defaults.
Most users can ignore this file and only edit `interests.*`, `direction.*`, `selection.*`, and `delivery.*`
in `config.yaml`.

Scope note: this guide is for **Daily Precision (arXiv discovery)** only.
Scholar Inbox (`sources.scholar_alerts.*`) does not use `policy.*`, `selection.*`, or `autotune.*`.

For the full agent logic and AutoTune design, see:

- `docs/agent-logic.md`
- `docs/autotune-design.md`

---

### 1. When NOT to tune

Do **not** touch `policy.*` or `autotune.*` if:

- You are still shaping your **queries / keyphrases / filters**.
- You mainly care about “are these papers on-topic?” rather than micro-optimizing exploration.
- You are running the agent for the first few weeks.

For most users:

- Set up:
  - `direction.*` (categories, lookback_days, max_papers_per_day)
  - `interests.*` (seeds, keyphrases)
  - `feedback.*` (blocked/boosted phrases/authors)
  - `selection.*` (explore_ratio, topic_cap, min_topics)
- Use:
  - `policy.type: "deterministic"` **or**
  - `policy.type: "linucb"` with **default** hyperparameters.

This already gives a solid Daily Precision feed.

---

### 2. Policy hyperparameters (`policy.*`)

```yaml
policy:
  type: "deterministic"   # or "linucb"
  # alpha: 0.5
  # lambda_ucb: 1.0
  # mu_novelty: 0.3
  # ridge: 1.0
```

- **`type`**
  - `"deterministic"`: phrase-based, fully explainable, no learning. Good baseline.
  - `"linucb"`: contextual bandit; uses feedback + features to learn over time.

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

**Recommendation:** if you are not debugging LinUCB itself, **only change `type`** and leave other
fields at their documented defaults.

---

### 3. AutoTune (`autotune.*`) — optional and advanced

AutoTune is an **optional meta-controller** that uses a separate bandit to tune `policy.*`
hyperparameters based on **feedback + diversity/novelty reward**.

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

- You have run the agent for **a while** and:
  - you log feedback events (click/open/star/export/skip/mute) into `state/feedback_log.jsonl` or `state/feedback.yaml`,
  - you want the system to automatically search for a better balance of exploration / novelty.

If you are not logging feedback yet, **leave `autotune.enabled=false`**.

#### 3.2 Minimal AutoTune setup

1. Make sure `policy.type: "linucb"`.
2. Uncomment the `autotune` block in your `config.yaml`.
3. Keep:
   - `enabled: true`
   - `method: "thompson"`
   - A small set of candidates (e.g. 2–3) that differ in `alpha`, `lambda_ucb`, `mu_novelty`.
4. Ensure feedback events are written daily; see `docs/autotune-design.md` for the event schema.

AutoTune is active only when **both** are true:

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
   - Only adjust `interests.*`, `direction.*`, `selection.*`.
   - Keep `policy.type` fixed (start with `"deterministic"`).
2. **Switch to LinUCB**
   - Set `policy.type: "linucb"`, but leave other `policy.*` at default.
   - Run for a while and inspect `logs/latest.log` and `state/preferences.json`.
3. **Consider AutoTune (optional)**
   - Only if you are comfortable with the current behavior and have feedback logs.
   - Start with very few candidates and modest differences.
4. **Change one thing at a time**
   - Do not change `direction.*`, `selection.*`, `policy.*`, and `autotune.*` all at once.
   - After each change, run for several days before drawing conclusions.

If in doubt, prefer **simpler config** and let the defaults work for you.

