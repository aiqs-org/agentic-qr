# Caveman Architecture

Caveman is the execution and object pipeline layer. It should be easy to walk
around because each service has a narrow responsibility, explicit inputs, and
explicit outputs.

## Rules

```text
1. Mechanical catalogs stay mechanical.
2. Research interpretation lives in context graph nodes or reasoning packets.
3. Strategy workers consume ContextPacks, not ambient repo memory.
4. Every output should say what produced it and what should consume it.
```

## Layers

```text
pipelines
  Raw market and macro data ingestion.

quant-lib
  Object factory. Builds instruments, bars, and mechanical catalogs.

strategy-core
  Strategy implementation and backtesting. Consumes hypotheses, strategy specs,
  mechanical catalogs, and selected ContextPacks.

results/postmortems
  Backtest output, interpretation, and memory updates.
```

## Context Boundary

The old failure mode was mixing research context directly into mechanical
catalogs. That caused downstream hallucination because workers could not tell
what was instrument definition, research opinion, or strategy instruction.

The preferred flow is:

```text
shared/models/instruments.json
  mechanical definition only

shared/models/macro_catalog.json
  mechanical macro source definition only

shared/context_graph/reasoning_packets/*.json
  optional interpretation and routing hints

shared/projects/<project_id>/context_packs/*.json
  scoped context for a specific worker task
```

## Example

Instead of:

```text
SPY instrument has research_context: "gamma support means buy dips"
```

Use:

```text
SPY instrument:
  symbol, venue, currency, price precision

ContextPack:
  principle: SPY dips may mean-revert outside crisis regimes
  heuristic: do not add macro gates unless explicitly requested
  prior_result: SPY dip hold-5 smoke produced 10 orders and PnL 342
```

That makes it possible for a very small worker to do the right thing without
reading the whole system.
