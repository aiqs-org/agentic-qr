# Projects

A multi-agent system for quantitative research and strategy development, organized into two AI branches, a shared layer, persistent storage, an orchestration manager, and a construction agent.

---

## Structure

```
projects/
├── verbose/          # Verbose branch — research-oriented agents
├── caveman/          # Caveman branch — execution-oriented agents
├── shared/           # Shared layer — common libraries and data
├── vault/            # Persistent storage — state, logs, artifacts
├── manager/          # Orchestration — human and strategy loops
├── construction/     # Construction agent — scaffolds new projects/skills
└── infisical/        # Secrets management (empty / external)
```

---

## Branches

### `verbose/` — Research Branch
Agents focused on knowledge acquisition and synthesis.

- **librarian** — indexes and retrieves from a knowledge base (`index/`, `retrieval/`)
- **researcher** — produces research output and applies skills (`output/`, `skills/`)

### `caveman/` — Execution Branch
Agents focused on data pipelines and strategy logic.

- **pipelines** — data connectors, scrapers, and ingestion codex
- **quant-lib** — quantitative objects and reusable financial primitives
- **strategy-core** — core strategy logic and documentation

---

## Shared Layer (`shared/`)
Common code and data shared across both branches.

| Folder | Purpose |
|---|---|
| `backtesting/` | Backtesting framework |
| `data/` | Raw and processed datasets |
| `hypotheses/` | Hypothesis tracking |
| `knowledge/` | Shared knowledge store |
| `models/` | Shared model definitions |
| `utils/` | Common utilities |

---

## Vault (`vault/`)
Persistent runtime storage — the system's memory between runs.

| Folder | Purpose |
|---|---|
| `artifacts/` | Produced outputs and deliverables |
| `bus/` | Inter-agent message bus |
| `clarifications/` | Queued clarification requests |
| `feedback/` | Feedback records |
| `logs/` | Run logs |
| `state/` | Agent and project state snapshots |

---

## Manager (`manager/`)
Orchestrates agent loops and human interaction.

- **human-loop** — handles human-in-the-loop checkpoints and approvals
- **strat-loop** — drives the autonomous strategy execution loop
- **src/** — manager core logic

---

## Construction Agent (`construction/`)
Scaffolds new projects, skills, and templates. The agent that builds the other agents.

- **codex/** — agent codex / instructions
- **projects/** — project scaffolds
- **skills/** — skill templates
- **templates/** — reusable file templates
- **src/** — construction agent logic
