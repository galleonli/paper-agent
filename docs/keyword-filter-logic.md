# Keyword filter logic (include / exclude)

Where it lives: `paper_agent/filter_papers.py` (main) and `paper_agent/core/utils.py` (matching).

Config: `direction.include_keywords` (required keywords) and `direction.exclude_keywords` (exclude keywords).  
Raycast: "Required keywords" and "Exclude keywords" in Preferences map to these.

---

## 1. Filter order

For each paper we apply, in order:

1. **Category**  
   - `allow_categories`: paper must have at least one of these (if non-empty).  
   - `deny_categories`: paper must have none of these (if non-empty).

2. **Exclude keywords**  
   - If the paper’s **title + summary + authors** (combined, normalized) matches **any** exclude phrase → drop the paper.

3. **Required keywords (include)**  
   - If `include_keywords` is non-empty: keep the paper only if  
     - it matches **at least one** include phrase in **title or abstract**, or  
     - it is in **seeds**.  
   - If `include_keywords` is empty → no keyword gate; all papers that passed step 1–2 are kept.

---

## 2. Include (required) keywords — “must contain”

- **Config**: `direction.include_keywords` (list of strings).
- **Semantics**: OR. The paper must contain **at least one** of the phrases.  
  - Not “all of them”.  
  - Not “must be in both title and abstract”; **either title or abstract** is enough.
- **Where we look**:
  - `title_match = text_matches_any(normalize_text(paper.title), keyphrases)`
  - `abstract_match = text_matches_any(normalize_text(paper.summary), keyphrases)`
  - Keep if `title_match or abstract_match or seed_match`.
- **Seeds**: If the paper ID is in `config.interests.seeds`, it is kept even when it matches no include keyword.

Code (filter_papers.py):

```python
keyphrases = [k for k in direction.include_keywords if k]
# ...
title_match = bool(keyphrases) and text_matches_any(normalize_text(paper.title), keyphrases)
abstract_match = bool(keyphrases) and text_matches_any(normalize_text(paper.summary), keyphrases)
# ...
if enforce_gate and not (title_match or abstract_match) and not seed_match:
    continue  # drop
```

---

## 3. Exclude keywords — “must not contain”

- **Config**: `direction.exclude_keywords` (list of strings).
- **Semantics**: If the paper matches **any** exclude phrase → drop.  
  - Text = **title + summary + authors** (concatenated, normalized).
- **Where we look**: One combined string:  
  `normalize_text(paper.title) + " " + normalize_text(paper.summary) + " " + " ".join(normalize_text(a) for a in paper.authors)`.

Code (filter_papers.py):

```python
neg_phrases = [n for n in direction.exclude_keywords if n]
exclude_kw = neg_phrases
# ...
combined_with_authors = (
    normalize_text(paper.title) + " " + normalize_text(paper.summary)
    + " " + " ".join(normalize_text(a) for a in paper.authors)
)
if text_matches_any(combined_with_authors, exclude_kw):
    continue  # drop
```

So: **exclude is applied on title + abstract + authors**; **include is applied only on title and abstract** (each checked separately, then OR’d).

---

## 4. Matching function: `text_matches_any(text, phrases)`

Location: `paper_agent/core/utils.py`.

- **Normalization**: `normalize_text(s) = s.lower().strip()` (case-insensitive).
- **Return**: `True` if **any** non-empty phrase matches the text.

Per phrase:

| Phrase type        | Rule |
|--------------------|------|
| Contains space     | Substring: `phrase in norm_text`. |
| Single-word, alnum | Word boundary: `(?<![a-z0-9]){phrase}(?![a-z0-9])` so e.g. "pose" does not match inside "propose". |
| Other              | Substring: `phrase in norm_text`. |

So:

- **Include**: OR across phrases; for each phrase, substring (or word-boundary for single alnum word) in title or in abstract.
- **Exclude**: OR across phrases; for each phrase, same rule on the combined string (title + summary + authors).

---

## 5. Summary

| Concept        | Config / Pref      | Logic |
|----------------|--------------------|--------|
| Must contain   | `include_keywords` / Required keywords | OR: at least one phrase in **title** or **abstract** (or in seeds). |
| Must not contain | `exclude_keywords` / Exclude keywords | If any phrase appears in **title + abstract + authors** → drop. |
| Matching       | —                  | Case-insensitive; single alnum word = word boundary; multi-word = substring. |

Filter order: category → exclude keywords → include gate (with seeds).  
Ranking (after filter): title match > abstract match > seed > rest; within same tier, newer first.
