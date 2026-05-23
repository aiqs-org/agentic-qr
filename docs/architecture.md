# Architecture Notes

This document describes the intended boundaries. It should guide refactors more
than the current folder names do.

## Core Idea

Agentic QR uses multiple agents because different work modes need different
context density.

```text
verbose branch = abstract reasoning and strategy development
caveman branch = direct execution and token-frugal implementation
SWE runtime     = code generation, backtesting, and result publication
shared layer    = data, models, knowledge, fixtures
vault runtime   = bus, logs, artifacts, state
```

Docker defines process boundaries. These architecture notes define cognitive
and context boundaries.

## Context Axes

Future zeroclaw runtimes should be constrained by layered context packets:

```text
project packet
  -> branch packet
      -> domain packet
          -> class packet
              -> task packet
                  -> runtime packet
```

Example for verbose strategy research:

```text
project: agentic-qr
branch: verbose
domain: strategy-research
class: data-mining-tensors
runtime: zeroclaw-researcher
```

Example for implementation:

```text
project: agentic-qr
branch: caveman
domain: backtesting
class: data-mining-tensors
runtime: strategy-core-swe
```

The primary agent should receive only the resolved packet stack, not all raw
logs or the entire repo.

## Branch Contracts

### Verbose

Purpose:

- Generate and refine research ideas.
- Preserve uncertainty.
- Explain assumptions and evidence.
- Produce hypotheses and research notes.

Avoid:

- Directly editing strategy artifacts.
- Running backtests.
- Building quant object catalogs.

### Caveman

Purpose:

- Execute concrete work with minimal context.
- Build data pipelines and quant objects.
- Keep output machine-readable and testable.

Avoid:

- Long exploratory reasoning.
- Duplicating verbose research.

### Strategy Core

Purpose:

- Convert hypotheses into strategy code.
- Run backtests.
- Publish result events.

Avoid:

- Generating broad research hypotheses.
- Managing market data ingestion.
- Managing secrets or infrastructure.

## Runtime Storage

`vault/` is intentionally runtime storage and is ignored by Git.

Expected roles:

- `vault/bus/`: inter-agent messages.
- `vault/artifacts/`: generated strategy files and outputs.
- `vault/logs/`: runtime logs.
- `vault/state/`: state snapshots.
- `vault/clarifications/`: pending human questions.
- `vault/feedback/`: human feedback.

Do not treat `vault/` as durable source code. Promote durable lessons into
tracked docs, tests, or source files.

## Current Naming Debt

- `strategy-core/` is conceptually part of the caveman/SWE execution axis but is
  currently top-level.
- `quant-lib/` and `caveman/quant-lib/` overlap but are not identical.
- `manager/` and `construction/` exist on the server as ignored runtime/local
  folders but are described in the original README.

These should not be renamed blindly. First add smoke checks, understand current
runtime dependencies, then consolidate one boundary at a time.
