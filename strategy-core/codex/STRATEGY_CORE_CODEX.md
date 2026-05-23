# strategy-core Codex

## Role
SWE Agent — middle loop executor.
Takes hypotheses from researcher/human, writes NT strategy code, runs backtests, returns results.

## Does
- Reads hypotheses from shared/hypotheses/*.json
- Reads instrument catalog from shared/models/instruments.json
- Reads macro catalog from shared/models/macro_catalog.json
- Reads research notes from shared/knowledge/*.md
- Writes NautilusTrader strategy code to vault/artifacts/strategy_{ts}.py
- Runs BacktestEngine against real bar data in shared/backtesting/bars/
- Writes results to shared/backtesting/results/result_{ts}.json
- Publishes backtest_complete events to vault/bus/strategy-core-outbox/

## Does NOT
- Generate research hypotheses (that's researcher/verbose)
- Build NT objects (that's quant-lib)
- Manage secrets or infrastructure
- Talk to pipelines directly

## Model
MiniMax via OpenRouter (default: minimax/minimax-m2.7) — 2000 tokens per strategy write

## Bus Events
Inbox:  new_hypothesis          → write strategy + run backtest
        run_pending_hypotheses  → process all pending in shared/hypotheses/
        query_results           → return last 5 results

Outbox: backtest_complete       → result with stats or error
        results_response        → reply to query_results

## Hypothesis Format (shared/hypotheses/*.json)
{
  "id": "hyp_001",
  "title": "SPY momentum crossover",
  "description": "Buy SPY when 5-day MA crosses above 20-day MA, sell on reverse",
  "instruments": ["SPY"],
  "timeframe": "daily",
  "source": "researcher"
}
