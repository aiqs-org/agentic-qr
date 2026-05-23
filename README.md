# Agentic QR

Agentic QR is a multi-agent quantitative research and strategy-development
workspace. The system separates broad reasoning from direct execution so each
agent can carry a smaller, more useful context.

## Mental Model

The repo is organized around two cognitive branches and a shared runtime layer:

- `verbose/`: research-heavy branch for broad reasoning, strategy ideation,
  librarian work, and hypothesis generation.
- `caveman/`: token-frugal branch inspired by compact execution loops. Agents
  here should be direct, file-aware, and implementation-focused.
- `strategy-core/`: active SWE/backtest runtime. It turns hypotheses or strategy
  requests into NautilusTrader strategy code and backtest results.
- `quant-lib/`: object/catalog factory for market, macro, instrument, and bar
  data used by strategy runtimes.
- `intake/`: input router for dropped files and Telegram messages.
- `shared/`: tracked shared fixtures, models, knowledge, and backtesting config.
- `infisical/`: local secrets service configuration.

The server also contains runtime-only directories ignored by Git:

- `vault/`: bus messages, logs, artifacts, runtime state.
- `manager/`: orchestration and human/strategy loops.
- `construction/`: scaffolding agent experiments.
- service `.env` files and Infisical local config.

GitHub should remain the source of truth for tracked source code. The server is
the runtime/test/deploy environment.

## Branch Responsibilities

### Verbose Branch

Use `verbose/` when the work needs ambiguity, explanation, and synthesis.

- `librarian`: gathers and packages context.
- `researcher`: produces research notes and hypotheses.
- Expected output: markdown research, hypotheses, open questions, strategy
  rationale.

### Caveman Branch

Use `caveman/` when the work should be short, concrete, and operational.

- `pipelines`: market and macro data ingestion.
- `quant-lib`: compact object/catalog factory variant.
- Expected output: files, bus events, catalogs, data artifacts, tested behavior.

### SWE / Strategy Execution

Use `strategy-core/` for strategy implementation and backtesting.

- Reads hypotheses and catalogs.
- Writes generated strategy artifacts.
- Runs backtests.
- Publishes result events.

## Runtime Flow

```text
intake
  -> verbose/librarian or verbose/researcher
  -> shared/knowledge or shared/hypotheses
  -> strategy-core
  -> vault/artifacts and shared/backtesting/results

caveman/pipelines
  -> shared/data
  -> quant-lib or caveman/quant-lib
  -> shared/models and shared/backtesting/bars
  -> strategy-core
```

## Current Server Runtime

Observed on the server:

- `caveman-intake`: running.
- `caveman-strategy-core`: running.
- `infisical-backend`, `infisical-db`, `infisical-dev-redis`: running.
- `caveman-quant-lib`: stopped with exit 137.
- `zeroclaw daemon`: running as `gram`.
- Docker is available with legacy `docker-compose` v1. Compose v2 is not
  installed.

## Health Checks

Run tracked-source syntax checks without writing bytecode:

```bash
python scripts/smoke_check.py
```

Server runtime checks currently require Docker/sudo access:

```bash
docker ps
docker-compose ps
docker logs --tail 100 caveman-intake
docker logs --tail 100 caveman-strategy-core
docker logs --tail 100 caveman-quant-lib
```

## Known Cleanup Areas

- Clarify whether top-level `quant-lib/` and `caveman/quant-lib/` should remain
  separate or be consolidated.
- Decide whether `strategy-core/` should live under the caveman execution branch
  conceptually, while staying at the current path for compatibility.
- Promote useful server-only `manager/` and `construction/` concepts into
  tracked docs or source if they are still part of the intended architecture.
- Add safe `.env.example` files for each service.
- Add a server health script that reports container status, recent logs,
  zeroclaw status, and tracked-source health without exposing secrets.
