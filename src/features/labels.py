"""Single label helper (S-4): next-session open-to-close.

Label contract (AI-02/AI-03): label(date t) = 1 iff
  (Open[t+1] ... Close[t+1]) intraday return >= threshold,
known only AFTER t+1 close. Serving horizon must match:
"buy at next open, TP +3% intraday".

Both ``src/features/build_features.py`` and ``notebooks/02_Preprocessing.ipynb``
(sel 4) MUST call :func:`add_open_to_close_label` so the two paths cannot drift
(temp ``next_open``/``next_close`` + ``iloc[:-1]`` vs ``Next_Day_*`` + drop).
"""

import pandas as pd

from src.config import PROFIT_THRESHOLD


def compute_open_to_close_label(
    df: pd.DataFrame,
    threshold: float = PROFIT_THRESHOLD,
) -> pd.Series:
    """Return int (0/1) Series; last row NaN (no next bar yet).

    Uses ``Open.shift(-1)`` / ``Close.shift(-1)``; caller drops the
    trailing NaN via :func:`add_open_to_close_label` (never cast NaN to 0).
    """
    next_open = df["Open"].shift(-1)
    next_close = df["Close"].shift(-1)
    ret = (next_close - next_open) / next_open
    label = (ret >= threshold).astype("float")
    label.iloc[-1] = float("nan")  # no future bar -> unlabeled, not 0
    return label.astype("float")


def add_open_to_close_label(
    df: pd.DataFrame,
    threshold: float = PROFIT_THRESHOLD,
) -> pd.DataFrame:
    """Copy ``df`` + ``Target`` col; drop trailing row without future bar."""
    df = df.copy()
    label = compute_open_to_close_label(df, threshold=threshold)
    df["Target"] = (label >= 1.0).astype(int)
    # Last row has no next session: unlabeled, drop (not false-negative 0).
    df = df.iloc[:-1].copy()
    return df
