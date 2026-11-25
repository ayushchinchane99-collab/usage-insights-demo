"""Usage metrics computed from semantic events, plus gap analysis.

Input is a DataFrame with columns: session_id, ts (epoch seconds), action.
All functions are pure and return plain pandas / dict objects.
"""
from pathlib import Path

import pandas as pd

from .taxonomy import ACTIONS, DETOUR_ACTIONS, HAPPY_PATH, feature_of

COMPLETION_ACTION = HAPPY_PATH[-1]


def load_events(path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["session_id", "ts", "action"])
    df = pd.read_json(path, lines=True)
    return df.sort_values(["session_id", "ts"]).reset_index(drop=True)


def session_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session: start/end, duration, completion flag, action list."""
    if df.empty:
        return pd.DataFrame(columns=["session_id", "start", "end", "duration", "completed", "actions"])
    g = df.sort_values(["session_id", "ts"]).groupby("session_id")
    out = pd.DataFrame({
        "start": g["ts"].min(),
        "end": g["ts"].max(),
        "actions": g["action"].apply(list),
    })
    out["duration"] = out["end"] - out["start"]
    out["completed"] = out["actions"].apply(lambda a: COMPLETION_ACTION in a)
    return out.reset_index()


def completion_rate(df: pd.DataFrame) -> float:
    s = session_table(df)
    return float(s["completed"].mean()) if len(s) else float("nan")


def funnel(df: pd.DataFrame) -> pd.DataFrame:
    """Sessions that reached each happy-path step (an action seen at least once)."""
    s = session_table(df)
    total = len(s)
    rows, prev = [], None
    for step in HAPPY_PATH:
        reached = int(s["actions"].apply(lambda a: step in a).sum()) if total else 0
        rows.append({
            "step": step,
            "sessions": reached,
            "share_of_all": reached / total if total else float("nan"),
            "step_conversion": (reached / prev) if prev else float("nan"),
        })
        prev = reached if reached else None
    return pd.DataFrame(rows)


def time_on_task(df: pd.DataFrame) -> dict:
    """Seconds from first event to order submission, for completed sessions."""
    s = session_table(df)
    done = s.loc[s["completed"].astype(bool), "duration"]
    if done.empty:
        return {"completed_sessions": 0, "median_s": float("nan"), "p90_s": float("nan")}
    return {
        "completed_sessions": int(len(done)),
        "median_s": float(done.median()),
        "p90_s": float(done.quantile(0.9)),
    }


def step_durations(df: pd.DataFrame) -> pd.DataFrame:
    """Median seconds spent before each happy-path step (gap since previous event)."""
    d = df.sort_values(["session_id", "ts"]).copy()
    d["gap"] = d.groupby("session_id")["ts"].diff()
    d = d[d["action"].isin(HAPPY_PATH) & d["gap"].notna()]
    res = d.groupby("action")["gap"].median().reindex(HAPPY_PATH).dropna()
    return res.rename("median_seconds").reset_index().rename(columns={"action": "step"})


def deviations(df: pd.DataFrame) -> dict:
    """Sessions that deviate from the expected happy path, by deviation type.

    detour:       used a detour action (e.g. removed an item, went back to the cart)
    repeated:     repeated a happy-path step
    missing_step: reached a later step without an event for an earlier one
                  (a sign of lost events OR of a shortcut)
    """
    s = session_table(df)
    counts = {"detour": 0, "repeated": 0, "missing_step": 0}
    for actions in s["actions"]:
        hp = [a for a in actions if a in HAPPY_PATH]
        if any(a in DETOUR_ACTIONS for a in actions):
            counts["detour"] += 1
        if len(hp) != len(set(hp)):
            counts["repeated"] += 1
        if hp:
            furthest = max(HAPPY_PATH.index(a) for a in hp)
            expected = set(HAPPY_PATH[1: furthest + 1])  # first step may be skipped on deep links
            if not expected.issubset(set(hp)):
                counts["missing_step"] += 1
    total = len(s)
    return {
        "sessions": total,
        "counts": counts,
        "shares": {k: (v / total if total else float("nan")) for k, v in counts.items()},
    }


def feature_usage(df: pd.DataFrame) -> pd.DataFrame:
    """Share of sessions that used each feature at least once."""
    s = session_table(df)
    total = len(s)
    rows = []
    for feat in sorted({a["feature"] for a in ACTIONS.values()}):
        used = int(s["actions"].apply(lambda acts: any(feature_of(a) == feat for a in acts)).sum()) if total else 0
        rows.append({"feature": feat, "sessions": used, "share": used / total if total else float("nan")})
    return pd.DataFrame(rows).sort_values("sessions", ascending=False).reset_index(drop=True)


def gap_analysis(true_df: pd.DataFrame, observed_df: pd.DataFrame) -> dict:
    """Compare what monitoring observed with what users actually did."""
    true_s, obs_s = session_table(true_df), session_table(observed_df)
    t_counts = true_df["action"].value_counts()
    o_counts = observed_df["action"].value_counts()
    capture = pd.DataFrame({"true": t_counts, "observed": o_counts}).fillna(0).astype(int)
    capture["capture_rate"] = capture["observed"] / capture["true"]
    capture.index.name = "action"
    capture = capture.sort_values("capture_rate").reset_index()

    true_ids, obs_ids = set(true_s["session_id"]), set(obs_s["session_id"])
    t_tot, o_tot = time_on_task(true_df), time_on_task(observed_df)
    return {
        "sessions_true": len(true_ids),
        "sessions_observed": len(obs_ids),
        "invisible_sessions": len(true_ids - obs_ids),
        "invisible_share": len(true_ids - obs_ids) / len(true_ids) if true_ids else float("nan"),
        "completion_true": completion_rate(true_df),
        "completion_observed_all_sessions": int(obs_s["completed"].astype(bool).sum()) / len(true_ids) if true_ids else float("nan"),
        "completion_observed_visible_sessions": completion_rate(observed_df),
        "median_time_on_task_true_s": t_tot["median_s"],
        "median_time_on_task_observed_s": o_tot["median_s"],
        "capture_by_action": capture,
        "never_observed": sorted(capture.loc[capture["observed"] == 0, "action"].tolist()),
    }


def summary(df: pd.DataFrame) -> dict:
    """Compact, JSON-serialisable summary of all metrics (input for the AI insights)."""
    return {
        "sessions": int(df["session_id"].nunique()) if len(df) else 0,
        "completion_rate": round(completion_rate(df), 4),
        "time_on_task": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in time_on_task(df).items()},
        "funnel": funnel(df).round(4).to_dict(orient="records"),
        "step_median_seconds": step_durations(df).round(1).to_dict(orient="records"),
        "deviations": {
            "counts": deviations(df)["counts"],
            "shares": {k: round(v, 4) for k, v in deviations(df)["shares"].items()},
        },
        "feature_usage": feature_usage(df).round(4).to_dict(orient="records"),
    }
