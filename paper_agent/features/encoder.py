"""
Paper -> feature vector for LinUCB. Explainable: keyphrase matches + category one-hot + bias.
"""

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.utils import normalize_text


def get_feature_names(config: Config) -> list[str]:
    """Canonical order: bias, keyphrases (from direction.include_keywords), allow_categories. Determines dimension d."""
    names = ["bias"]
    names.extend(normalize_text(k) for k in config.direction.include_keywords if k)
    names.extend(normalize_text(c) for c in config.direction.allow_categories if c)
    if len(names) == 1:
        names.append("default")
    return names


def encode_paper(paper: Paper, config: Config) -> tuple[list[float], list[str], list[str]]:
    """
    Encode paper into feature vector x and return (x, feature_names, matched_phrases).
    x = [bias=1, ...keyphrase binaries..., ...category binaries...].
    matched_phrases = keyphrase strings (original) that appeared in title+summary (for why_this_paper).
    """
    keyphrases_norm = [normalize_text(k) for k in config.direction.include_keywords if k]
    categories_norm = [normalize_text(c) for c in config.direction.allow_categories if c]
    names = get_feature_names(config)

    combined = normalize_text(paper.title) + " " + normalize_text(paper.summary)
    paper_cats = set(normalize_text(c) for c in paper.categories)

    x = [1.0]
    for p in keyphrases_norm:
        x.append(1.0 if p in combined else 0.0)
    for c in categories_norm:
        x.append(1.0 if c in paper_cats else 0.0)
    if not keyphrases_norm and not categories_norm:
        x.append(1.0)  # default slot

    matched_phrases = [
        orig for orig in config.direction.include_keywords
        if orig and normalize_text(orig) in combined
    ]
    return x, names, matched_phrases
