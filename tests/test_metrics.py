import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics import metrics as m
from analytics.taxonomy import ACTIONS, HAPPY_PATH, UNINSTRUMENTED
from insights.claude_insights import gap_for_prompt, generate_insights, rule_based_insights


def make_df(sessions):
    rows = []
    for sid, actions in sessions.items():
        for i, a in enumerate(actions):
            rows.append({"session_id": sid, "ts": 1000.0 + i * 10, "action": a})
    return pd.DataFrame(rows)


FULL = list(HAPPY_PATH)


def test_taxonomy_consistency():
    assert all(a in ACTIONS for a in HAPPY_PATH)
    assert UNINSTRUMENTED <= set(ACTIONS)
    assert all(v["description"] and v["feature"] for v in ACTIONS.values())


def test_completion_rate_and_time_on_task():
    df = make_df({"a": FULL, "b": FULL[:3], "c": FULL, "d": FULL[:1]})
    assert m.completion_rate(df) == pytest.approx(0.5)
    tot = m.time_on_task(df)
    assert tot["completed_sessions"] == 2
    assert tot["median_s"] == pytest.approx(70.0)  # 8 events, 7 gaps of 10s


def test_funnel_is_monotonic_for_clean_paths():
    df = make_df({"a": FULL, "b": FULL[:4], "c": FULL[:2]})
    f = m.funnel(df)["sessions"].tolist()
    assert f == sorted(f, reverse=True) and f[0] == 3 and f[-1] == 1


def test_deviation_detection():
    df = make_df({
        "clean": FULL,
        "detour": FULL[:5] + ["remove_from_cart"] + FULL[5:],
        "repeat": FULL[:2] + ["view_product"] + FULL[2:],
        "missing": [s for s in FULL if s != "enter_payment"],
    })
    c = m.deviations(df)["counts"]
    assert c == {"detour": 1, "repeated": 1, "missing_step": 1}


def test_feature_usage_shares():
    df = make_df({"a": FULL, "b": ["view_product_list", "search_products"]})
    fu = m.feature_usage(df).set_index("feature")["share"]
    assert fu["catalogue"] == 1.0 and fu["search"] == 0.5 and fu["promo_code"] == 0.0


def test_gap_analysis_flags_uninstrumented_and_invisible():
    true_df = make_df({"a": FULL + ["apply_promo_code"], "b": FULL, "c": FULL})
    obs_df = make_df({"a": FULL, "b": FULL[:-1]})  # c invisible, b lost submit_order
    gap = m.gap_analysis(true_df, obs_df)
    assert gap["invisible_sessions"] == 1
    assert gap["completion_true"] == pytest.approx(1.0)
    assert gap["completion_observed_all_sessions"] == pytest.approx(1 / 3)
    assert "apply_promo_code" in gap["never_observed"]


def test_empty_input_does_not_crash():
    empty = pd.DataFrame(columns=["session_id", "ts", "action"])
    assert math.isnan(m.completion_rate(empty))
    assert m.summary(empty)["sessions"] == 0


def test_insights_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    df = make_df({"a": FULL, "b": FULL[:4]})
    text, source = generate_insights(m.summary(df))
    assert "Completion rate" in text and "fallback" in source


def test_gap_payload_is_json_serialisable():
    true_df = make_df({"a": FULL, "b": FULL})
    obs_df = make_df({"a": FULL})
    json.dumps(gap_for_prompt(m.gap_analysis(true_df, obs_df)), default=str)
    assert "Data quality" in rule_based_insights(
        m.summary(obs_df), gap_for_prompt(m.gap_analysis(true_df, obs_df)))
