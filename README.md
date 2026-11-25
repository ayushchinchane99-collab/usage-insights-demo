# Usage Insights Demo

A small end-to-end experiment: **instrument a sample web app with semantic user actions, analyse the usage data, compare it with what users really did, and use Claude to turn the numbers into business insights.**

It is inspired by the idea behind Real User Monitoring (RUM). It does not use any vendor's monitoring product.

## What it does

| Step | Where | What happens |
|---|---|---|
| 1. Instrument | `sample_app/`, `analytics/taxonomy.py` | A small shop (catalogue, cart, checkout) calls `track("add_to_cart")` instead of sending raw clicks. Each action has a business-readable description and a feature. |
| 2. Collect | `server/collector.py` | Flask endpoint that validates events and appends them to a JSONL file. |
| 3. Analyse | `analytics/metrics.py` | Task completion rate, time on task, funnel, task deviations, most used features. |
| 4. Compare | `analytics/metrics.py: gap_analysis` | Compares monitored data with ground truth: invisible sessions, capture rate per action, bias in completion rate. |
| 5. Explain | `insights/claude_insights.py` | Sends only **aggregated** metrics to the Claude API and asks for insights and recommendations. Falls back to a rule-based summary without an API key. |
| 6. Present | `dashboard/app.py` | Streamlit dashboard with all of the above. |

## Run it

```bash
pip install -r requirements.txt

python -m data.simulate --sessions 2000 --seed 42   # synthetic data (ground truth + observed)
streamlit run dashboard/app.py                      # dashboard

# optional: AI insights from Claude
export ANTHROPIC_API_KEY=...                        # model: claude-sonnet-5-5 (override with CLAUDE_MODEL)

# optional: collect real events from the sample app
python -m server.collector                          # open http://localhost:5000, click through the shop
# then choose "Live events from sample app" in the dashboard

python -m pytest -q                                 # tests
```

## Important: the data is simulated

The numbers in the dashboard come from `data/simulate.py`, which generates synthetic sessions with documented drop-off rates and then applies realistic **observation losses**:

- an action that exists in the app but is not instrumented (`apply_promo_code`),
- 8% of sessions where a tracker blocker hides everything,
- 3% of events lost to network or beacon failures,
- 7% of the final `submit_order` events lost on page unload.

Because I chose these loss rates, the gap analysis shows that the pipeline *detects* such gaps. It does not show how large they are in any real system. With real data you would replace the simulated ground truth with something independent, such as server-side order records.

## Example findings (simulated, 2000 sessions, seed 42)

- True task completion is 28.1%, but monitoring reports 23.9% when counted over all sessions, because invisible sessions and lost `submit_order` events both push it down.
- The largest drop-off is between shipping and payment (71% conversion), and the payment step is also the slowest (median 57 s).
- 7% of monitored sessions show a "missing step", which is a data-quality signal and not necessarily user behaviour.
- `apply_promo_code` is never observed, so any conclusion about promo codes would be silently wrong.

## Limitations and next steps

- The sample app is intentionally small and the browser flow was not tested in a browser here. The collector and the analytics are covered by tests.
- Session = browser tab session; there is no user identity and no consent banner. A real deployment needs privacy review.
- Deviation detection is rule-based. A natural extension is to ask Claude to classify unusual paths.
- Next ideas: compare Claude's insights against hand-computed numbers to measure how often it misstates a figure; try the same approach on logs or incident data.

## Layout

```
analytics/    taxonomy.py, metrics.py
data/         simulate.py (+ generated *.jsonl)
insights/     claude_insights.py
server/       collector.py
sample_app/   index.html, tracker.js
dashboard/    app.py
tests/        test_metrics.py
```
