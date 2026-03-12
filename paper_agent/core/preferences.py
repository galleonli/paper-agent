"""
LinUCB preference state: theta, A, b stored in state_dir/preferences.json.
Cold start: A = ridge * I, b = 0, theta = 0. Update from feedback: A += x x^T, b += r * x.
"""

import json
from pathlib import Path

import numpy as np

PREFERENCES_FILENAME = "preferences.json"


def _preferences_path(state_dir: str | Path) -> Path:
    return Path(state_dir) / PREFERENCES_FILENAME


def load_preferences(
    state_dir: str | Path,
    d: int,
    ridge: float = 1.0,
    feature_names: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list]:
    """
    Load theta, A_inv, and feature_names from state_dir/preferences.json.
    If file missing or invalid, return cold-start: theta = zeros(d), A_inv = I/ridge, feature_names as given.
    """
    path = _preferences_path(state_dir)
    if not path.exists():
        theta = np.zeros(d)
        A = np.eye(d) * ridge
        A_inv = np.eye(d) / ridge
        return theta, A_inv, feature_names or []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        theta = np.zeros(d)
        A_inv = np.eye(d) / ridge
        return theta, A_inv, feature_names or []

    stored_d = data.get("d")
    if stored_d is None or stored_d != d:
        theta = np.zeros(d)
        A_inv = np.eye(d) / ridge
        return theta, A_inv, feature_names or []

    A = np.array(data["A"], dtype=np.float64)
    b = np.array(data["b"], dtype=np.float64)
    names = data.get("feature_names", feature_names or [])

    try:
        A_inv = np.linalg.inv(A)
        theta = A_inv @ b
    except np.linalg.LinAlgError:
        theta = np.zeros(d)
        A_inv = np.eye(d) / ridge

    return theta, A_inv, names


def save_preferences(
    state_dir: str | Path,
    A: np.ndarray,
    b: np.ndarray,
    feature_names: list[str],
) -> None:
    """Persist A, b, feature_names to state_dir/preferences.json."""
    path = _preferences_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "d": A.shape[0],
        "A": A.tolist(),
        "b": b.tolist(),
        "feature_names": feature_names,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def update_preferences(
    state_dir: str | Path,
    feature_names: list[str],
    x: np.ndarray,
    reward: float,
    ridge: float = 1.0,
) -> None:
    """
    Update LinUCB state with one (context, reward): A += x x^T, b += reward * x; save.
    If preferences.json does not exist, initialize A = ridge*I, b = 0 then update.
    """
    d = len(x)
    path = _preferences_path(state_dir)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            A = np.array(data["A"], dtype=np.float64)
            b = np.array(data["b"], dtype=np.float64)
            if A.shape[0] != d or b.shape[0] != d:
                A = np.eye(d) * ridge
                b = np.zeros(d)
        except (json.JSONDecodeError, OSError, KeyError):
            A = np.eye(d) * ridge
            b = np.zeros(d)
    else:
        A = np.eye(d) * ridge
        b = np.zeros(d)

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    A = A + np.outer(x, x)
    b = b + reward * x
    save_preferences(state_dir, A, b, feature_names or [])
