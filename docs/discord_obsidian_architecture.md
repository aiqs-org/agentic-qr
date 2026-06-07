# Discord and Obsidian Architecture

This document defines the first version of the user-facing workflow for the
belief graph, project system, and Caveman/Verbose bridge.

## Roles

```text
Discord
  Operational cockpit: commands, project channels, review prompts, status feeds.

Obsidian
  Knowledge map: source notes, distilled beliefs, principles, heuristics,
  project memory, postmortems, backlinks, and graph traversal.

Verbose
  Context intelligence layer: ingestion, distillation, reasoning packets,
  belief updates, and postmortems.

Caveman
  Execution layer: data pipelines, code objects, strategy implementation,
  backtests, and result events.
```

The core loop is:

```text
Raw Source or User Idea
  -> KnowledgeNode
  -> ContextPack
  -> StrategySpec or Task
  -> Caveman Execution
  -> Result
  -> Postmortem
  -> MemoryUpdate
```

## Channel Types

Only channels created through a project command or named with the `proj-`
prefix are treated as projects.

```text
command-center
  Global commands, routing, summaries, and admin actions.

proj-*
  Active project workspace. Messages are project-scoped by default.

inbox-*
  Raw ingestion. Messages become raw sources, candidate beliefs, or source
  notes, not projects.

review-*
  Human validation. The bot asks whether to promote, revise, reject, or attach
  beliefs and memory updates.

feed-*
  Status streams for backtests, system events, and artifact creation.
```

Recommended starter channels:

```text
#command-center
#proj-agentic-qr
#proj-spy-dip-engine
#inbox-raw
#inbox-market-beliefs
#inbox-sources
#review-beliefs
#review-results
#feed-backtests
#feed-system
```

## Discord Behaviors

### Project Channels

When a project is created, the system creates or links:

```text
shared/projects/<project_id>/project.json
shared/projects/<project_id>/tasks/
shared/projects/<project_id>/context_packs/
shared/projects/<project_id>/artifacts/
Obsidian/Projects/<Project Name>.md
```

Project-channel messages are interpreted as project-relevant by default.

Examples:

```text
Test whether 5-day holds work better than 3-day holds after >1% SPY drops.
```

Expected routing:

```text
project message
  -> task or strategy thesis
  -> context resolver
  -> strategy spec
  -> Caveman execution
  -> result and postmortem
```

### Ingestion Channels

Inbox messages are raw material. They should not automatically become projects.

Examples:

```text
I think forced rebalancing flow is one of the best intraday opportunity sources.
```

Expected routing:

```text
raw message
  -> source or candidate belief
  -> distillation queue
  -> review-beliefs prompt
  -> promoted principle, heuristic, project idea, or archived note
```

### Review Channels

Review channels are where the system asks for human judgment.

Common actions:

```text
promote
revise
reject
attach_to_project
mark_contradicted
request_more_evidence
```

## Obsidian Behaviors

Obsidian exposes the durable knowledge structure. Generated notes should use
stable frontmatter so the graph can be round-tripped into machine-readable
objects.

Example note:

```markdown
---
node_id: kn_20260606_spy_dip_mean_reversion
node_type: principle
status: candidate
confidence: 0.64
parents:
  - kn_equity_index_liquidity
children:
  - kn_avoid_vix_over_30
evidence_supports:
  - result_20260530_spy_dip_hold_5
evidence_contradicts: []
---

# SPY Dip Mean Reversion

SPY close-to-close drops greater than 1% may mean-revert over short holding
windows when volatility is elevated but not crisis-level.
```

## Validation Gates

Knowledge nodes should carry their validation requirement. The gate depends on
where the node sits in the hierarchy.

```text
source
  Needs provenance and summary.

belief
  Needs distillation review.

principle
  Needs reasoning review plus supporting examples or evidence.

heuristic
  Needs operational formulation and at least one test path.

strategy_thesis
  Needs exact rules, assumptions, and relevant context pack.

result
  Needs reproducible artifact and metrics.

postmortem
  Needs memory update proposal and affected-node links.
```

## First Implementation Target

The first version should not require a dashboard.

Build order:

1. Define shared graph and project schemas.
2. Add a Discord adapter that can classify channel type and write intake events.
3. Add Obsidian note writer for projects and knowledge nodes.
4. Route `proj-*` messages to project tasks.
5. Route `inbox-*` messages to raw knowledge nodes.
6. Route backtest results to `feed-backtests` and postmortem review.

## Current Adapter Contract

The first Discord adapter lives at `intake/src/discord_agent.py`.

It requires:

```text
DISCORD_BOT_TOKEN
DISCORD_GUILD_ID
```

It writes:

```text
shared/projects/<project_id>/project.json
shared/projects/<project_id>/tasks/<task_id>.json
shared/context_graph/nodes/<node_id>.json
shared/context_graph/raw/<node_id>.md
vault/bus/review-events/*.json
```

For the first version, project messages are captured as tasks but are not
automatically executed. Inbox messages are captured as raw knowledge nodes and
queued for distillation review.

## Distillation Worker

`verbose/context_distiller.py` watches raw source nodes and writes candidate
belief, principle, or heuristic nodes.

It reads:

```text
shared/context_graph/nodes/*.json
shared/context_graph/raw/*.md
```

It writes:

```text
shared/context_graph/nodes/<candidate_node_id>.json
shared/context_graph/distilled/<candidate_node_id>.md
vault/bus/review-events/*_distillation_completed.json
```

The worker only promotes raw source material to `candidate` status. Human review
is still required before a node becomes `validated`.
