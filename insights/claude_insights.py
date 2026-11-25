"""Turn aggregated usage metrics into business-relevant insights with Claude.

Only AGGREGATED numbers are sent to the model (never raw events or user ids).
Without an API key the module falls back to a deterministic rule-based summary,
so the pipeline always runs offline.

Set ANTHROPIC_API_KEY to use Claude. Override the model with CLAUDE_MODEL.
"""
import json
import os

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = (
    "You are a product analytics assistant for an operations team. "
    "You receive aggregated usage metrics of a web application (checkout task) and, "
    "optionally, a gap analysis comparing monitoring data with ground truth. "
    "Write concise, business-relevant insights for a product manager. "
    "Rules: use ONLY the numbers provided, never invent figures; state clearly when the "
    "monitoring data may be biased or incomplete and how that changes the conclusion; "
    "end with 3 concrete, prioritised recommendations."
)

USER_TEMPLATE = (
    "Metrics (JSON):\n{metrics}\n\n"
    "Gap analysis (JSON, may be empty):\n{gap}\n\n"
    "Please cover: (1) task completion rate, (2) time on task, (3) task deviations, "
    "(4) most used features, (5) how far the monitoring data can be trusted, "
    "then give 3 recommendations. Use short paragraphs or bullets, max 250 words."
)


def _pct(x):
    return f"{x * 100:.1f}%"


def rule_based_insights(metrics: dict, gap: dict | None = None) -> str:
    """Deterministic fallback used when no API key is configured."""
    lines = [f"Completion rate: {_pct(metrics['completion_rate'])} of {metrics['sessions']} sessions "
             f"reached order submission."]

    funnel = [f for f in metrics["funnel"] if f["step_conversion"] == f["step_conversion"]]
    if funnel:
        worst = min(funnel, key=lambda f: f["step_conversion"])
        lines.append(f"Biggest drop-off: the step '{worst['step']}' converts only "
                     f"{_pct(worst['step_conversion'])} of the sessions that reached the step before it.")

    tot = metrics["time_on_task"]
    if tot["completed_sessions"]:
        lines.append(f"Time on task: median {tot['median_s']:.0f}s, 90th percentile {tot['p90_s']:.0f}s "
                     f"across {tot['completed_sessions']} completed sessions.")
    if metrics["step_median_seconds"]:
        slow = max(metrics["step_median_seconds"], key=lambda r: r["median_seconds"])
        lines.append(f"Slowest step: '{slow['step']}' (median {slow['median_seconds']:.0f}s).")

    dev = metrics["deviations"]["shares"]
    lines.append(f"Deviations: {_pct(dev['detour'])} of sessions took a detour, "
                 f"{_pct(dev['repeated'])} repeated a step, "
                 f"{_pct(dev['missing_step'])} show a missing step (possible lost events).")

    top = metrics["feature_usage"][:3]
    lines.append("Most used features: " + ", ".join(f"{f['feature']} ({_pct(f['share'])})" for f in top) + ".")

    if gap:
        lines.append(f"Data quality: {_pct(gap['invisible_share'])} of true sessions are invisible to monitoring; "
                     f"completion appears as {_pct(gap['completion_observed_all_sessions'])} instead of "
                     f"{_pct(gap['completion_true'])}. Never observed: {', '.join(gap['never_observed']) or 'none'}.")
    return "\n".join(f"- {l}" for l in lines)


def generate_insights(metrics: dict, gap: dict | None = None, model: str | None = None) -> tuple[str, str]:
    """Return (text, source) where source is 'claude' or 'rule-based fallback'."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return rule_based_insights(metrics, gap), "rule-based fallback (no ANTHROPIC_API_KEY set)"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL),
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_TEMPLATE.format(
                metrics=json.dumps(metrics, default=str),
                gap=json.dumps(gap or {}, default=str))}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), "claude"
    except Exception as exc:  # network, auth, model name...
        return rule_based_insights(metrics, gap), f"rule-based fallback (Claude call failed: {type(exc).__name__})"


def gap_for_prompt(gap: dict) -> dict:
    """Drop the DataFrame so the gap analysis is JSON-serialisable."""
    return {k: v for k, v in gap.items() if k != "capture_by_action"} | {
        "capture_rate_by_action": {r["action"]: round(r["capture_rate"], 3)
                                   for r in gap["capture_by_action"].to_dict(orient="records")}
    }
