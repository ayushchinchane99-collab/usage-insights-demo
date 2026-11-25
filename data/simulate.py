"""Generate SYNTHETIC sessions: ground truth vs. what the monitoring would observe.

All data produced here is simulated. It exists to demonstrate the analysis
pipeline and the gap analysis, not to make claims about real users.

Two files are written:
  data/true_events.jsonl      what users actually did (ground truth)
  data/observed_events.jsonl  what the instrumentation recorded (with realistic losses)

Observation losses (the "gaps"):
  - uninstrumented actions (apply_promo_code) are never recorded
  - 8% of sessions run a tracker blocker and record nothing
  - each remaining event is lost with 3% probability (network/beacon failure)
  - the final submit_order beacon is lost with 7% probability (page unload)

Run:  python -m data.simulate --sessions 2000 --seed 42
"""
import argparse
import json
import math
import random
from pathlib import Path

from analytics.taxonomy import ACTIONS, HAPPY_PATH, UNINSTRUMENTED, describe, feature_of

DATA_DIR = Path(__file__).resolve().parent

# Probability that a user who reached a step continues to the next one.
CONTINUE_PROB = {
    "view_product_list": 0.93,
    "view_product": 0.78,
    "add_to_cart": 0.82,
    "view_cart": 0.80,
    "start_checkout": 0.88,
    "enter_shipping": 0.72,  # payment form is the biggest drop-off
    "enter_payment": 0.97,
}

# Median seconds spent before the action (log-normal).
MEDIAN_SECONDS = {
    "view_product_list": 4, "view_product": 18, "add_to_cart": 6, "view_cart": 9,
    "start_checkout": 5, "enter_shipping": 45, "enter_payment": 55, "submit_order": 4,
    "search_products": 10, "apply_filter": 7, "add_to_wishlist": 5,
    "remove_from_cart": 6, "apply_promo_code": 14, "back_to_cart": 5,
}

BLOCKED_SESSION_RATE = 0.08
EVENT_LOSS_RATE = 0.03
SUBMIT_LOSS_RATE = 0.07


def _seconds(rng, action):
    median = MEDIAN_SECONDS[action]
    return max(1.0, rng.lognormvariate(math.log(median), 0.45))


def simulate_session(rng, sid, start_ts):
    """Return the list of TRUE events of one session."""
    actions = []

    def add(a):
        actions.append(a)

    add("view_product_list")
    if rng.random() < 0.35:
        add("search_products")
    if rng.random() < 0.25:
        add("apply_filter")

    for step in HAPPY_PATH[1:]:
        prev = actions_last_step(actions)
        if rng.random() > CONTINUE_PROB[prev]:
            break  # user abandoned the task
        if step == "view_product" and rng.random() < 0.20:
            add("view_product")  # looked at a second product
        if step == "add_to_cart" and rng.random() < 0.18:
            add("add_to_wishlist")
        add(step)
        if step == "view_cart":
            if rng.random() < 0.12:
                add("remove_from_cart")
                add("view_cart") if rng.random() < 0.5 else None
            if rng.random() < 0.22:
                add("apply_promo_code")
        if step == "enter_shipping" and rng.random() < 0.07:
            add("back_to_cart")
            add("start_checkout")
            add("enter_shipping")

    ts = start_ts
    events = []
    for a in actions:
        ts += _seconds(rng, a)
        events.append({
            "session_id": sid, "ts": round(ts, 3), "action": a,
            "description": describe(a), "feature": feature_of(a), "task": "checkout",
        })
    return events


def actions_last_step(actions):
    """Last happy-path action reached so far (drives the drop-off probability)."""
    for a in reversed(actions):
        if a in CONTINUE_PROB:
            return a
    return "view_product_list"


def observe(rng, events):
    """Apply realistic observation losses to the true events of one session."""
    if rng.random() < BLOCKED_SESSION_RATE:
        return []
    seen = []
    for e in events:
        if e["action"] in UNINSTRUMENTED:
            continue
        loss = SUBMIT_LOSS_RATE if e["action"] == "submit_order" else EVENT_LOSS_RATE
        if rng.random() < loss:
            continue
        seen.append(e)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    true_events, observed_events = [], []
    base_ts = 1_764_000_000  # fixed base so output is reproducible
    for i in range(args.sessions):
        sid = f"sim_{i:05d}"
        start = base_ts + i * 97 + rng.random() * 60
        ev = simulate_session(rng, sid, start)
        true_events.extend(ev)
        observed_events.extend(observe(rng, ev))

    for name, rows in (("true_events.jsonl", true_events),
                       ("observed_events.jsonl", observed_events)):
        with (DATA_DIR / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    print(f"sessions={args.sessions} true_events={len(true_events)} "
          f"observed_events={len(observed_events)}")


if __name__ == "__main__":
    main()
