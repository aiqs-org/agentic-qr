# Triage Plan

This is the working order for stabilizing the current server runtime before
larger architecture work.

## 1. Runtime Health

Goal: make it obvious what is alive, stale, or misconfigured before changing
code.

- Run `python3 scripts/smoke_check.py` for tracked Python syntax.
- Run `python3 scripts/server_health.py` on the server for container, log,
  config-file, and zeroclaw checks.
- Treat stopped runtime containers and model-provider errors as first-class
  blockers.

## 2. Quant-Lib And Backtesting

Goal: make the data-object layer and strategy runtime deterministic.

- Treat top-level `quant-lib/` as the current canonical object factory because
  it matches the running `quant-lib_quant-lib` image and JSON pipeline data.
- Treat `caveman/quant-lib/` as an experimental or stale compact variant until
  its paths and data format are reconciled.
- Fix backtest failures by using real result files and generated strategy
  artifacts as test cases, not just synthetic unit tests.
- Add regression checks for non-zero trade generation and known NautilusTrader
  failure modes.

## 3. Routing And Telegram

Goal: make user input land in the right runtime without guessing.

- Audit Telegram intake and classifier routing.
- Add route events that are easy to trace from Telegram message to hypothesis,
  strategy-core inbox, result event, and human response.
- Keep voice/clipboard input as a local desktop surface, but let Telegram remain
  the remote surface for server-side strategy work.

## 4. Model Configuration

Goal: stop confusing provider labels with model identity.

- Rename Kimi-facing config in docs to Moonshot/Kimi where appropriate.
- Record actual provider, base URL, and model ID without exposing API keys.
- Diagnose hallucination by checking whether objects and packet context reach
  the model prompt before blaming the model itself.
- Replace stale Qwen/OpenRouter model IDs when provider checks show upstream
  404s.

## 5. Context Axes For Zeroclaw

Goal: use context packets as productive runtime boundaries, not generic chat
memory.

- Add packet stacks by project, branch, domain, class, task, and runtime.
- Start with `verbose`, `caveman`, `backtesting`, and `telegram-routing`
  packets.
- Give primary agents only the resolved packet stack needed for the current
  task.
- Use sub-agents sparingly: one scout for broad context, one worker for the
  active implementation loop.

## 6. Dashboards And Health UI

Goal: make the top-level hedge-fund-style view readable.

- Promote health data from scripts into a lightweight dashboard.
- Show strategy states, recent events, running containers, current hypotheses,
  and latest backtest outcomes.
- Keep Obsidian-style notes as human-facing context, not runtime truth.
