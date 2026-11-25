"""Streamlit dashboard: usage metrics, gap analysis and AI-generated insights.

Run from the project root:  streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from analytics import metrics as m
from insights.claude_insights import gap_for_prompt, generate_insights

DATA = ROOT / "data"

st.set_page_config(page_title="Usage Insights Demo", layout="wide")
st.title("Usage Insights Demo")
st.caption("Semantic usage events of a sample checkout app, analysed with Claude. "
           "Simulated data unless you select live events.")

source = st.sidebar.radio("Data source", ["Simulated (observed by monitoring)", "Live events from sample app"])
path = DATA / ("observed_events.jsonl" if source.startswith("Simulated") else "live_events.jsonl")
df = m.load_events(path)

if df.empty:
    st.warning(f"No events found in {path.name}. Run `python -m data.simulate` or use the sample app first.")
    st.stop()

true_path = DATA / "true_events.jsonl"
true_df = m.load_events(true_path) if source.startswith("Simulated") else pd.DataFrame()
summary = m.summary(df)

# ---- KPIs
tot = summary["time_on_task"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sessions", f"{summary['sessions']:,}")
c2.metric("Task completion rate", f"{summary['completion_rate'] * 100:.1f}%")
c3.metric("Median time on task", f"{tot['median_s']:.0f} s" if tot["completed_sessions"] else "n/a")
c4.metric("Sessions with a detour", f"{summary['deviations']['shares']['detour'] * 100:.1f}%")

# ---- Funnel and step durations
left, right = st.columns(2)
with left:
    st.subheader("Checkout funnel")
    fn = m.funnel(df).set_index("step")
    st.bar_chart(fn["sessions"])
    st.dataframe(fn.assign(share_of_all=(fn["share_of_all"] * 100).round(1),
                           step_conversion=(fn["step_conversion"] * 100).round(1)),
                 width="stretch")
with right:
    st.subheader("Median seconds before each step")
    sd = m.step_durations(df).set_index("step")
    st.bar_chart(sd["median_seconds"])

# ---- Deviations and feature usage
left, right = st.columns(2)
with left:
    st.subheader("Task deviations")
    dev = m.deviations(df)
    st.bar_chart(pd.Series(dev["counts"], name="sessions"))
    st.caption("A 'missing step' can mean a shortcut OR a lost event; see the gap analysis.")
with right:
    st.subheader("Most used features")
    fu = m.feature_usage(df).set_index("feature")
    st.bar_chart(fu["share"])

# ---- Gap analysis (needs ground truth)
gap = None
if not true_df.empty:
    st.header("Gap analysis: monitoring vs. actual usage")
    gap = m.gap_analysis(true_df, df)
    g1, g2, g3 = st.columns(3)
    g1.metric("Sessions invisible to monitoring", f"{gap['invisible_share'] * 100:.1f}%")
    g2.metric("Completion rate (true)", f"{gap['completion_true'] * 100:.1f}%")
    g3.metric("Completion rate (as monitored, all sessions)",
              f"{gap['completion_observed_all_sessions'] * 100:.1f}%")
    st.write("Capture rate per action (observed events / actual events):")
    st.bar_chart(gap["capture_by_action"].set_index("action")["capture_rate"])
    if gap["never_observed"]:
        st.error("Never observed (uninstrumented): " + ", ".join(gap["never_observed"]))

# ---- AI insights
st.header("AI-generated insights")
if st.button("Generate insights with Claude"):
    with st.spinner("Analysing..."):
        text, src = generate_insights(summary, gap_for_prompt(gap) if gap else None)
    st.markdown(text)
    st.caption(f"Source: {src}")
else:
    st.caption("Needs ANTHROPIC_API_KEY. Without a key a rule-based summary is shown instead.")
