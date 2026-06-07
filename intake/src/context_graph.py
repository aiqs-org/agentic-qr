"""Helpers for writing project and knowledge graph records from intake."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


SHARED_CONTEXT_GRAPH = Path("/shared/context_graph")
SHARED_PROJECTS = Path("/shared/projects")
VAULT_BUS = Path("/vault/bus")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def project_id_from_channel(channel_name: str) -> str:
    if channel_name.startswith("proj-"):
        return slugify(channel_name.removeprefix("proj-"))
    return slugify(channel_name)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def ensure_project(
    *,
    channel_name: str,
    channel_id: int,
    guild_id: int | None,
) -> tuple[str, Path]:
    project_id = project_id_from_channel(channel_name)
    project_dir = SHARED_PROJECTS / project_id
    project_path = project_dir / "project.json"
    now = utc_now()

    if project_path.exists():
        payload = json.loads(project_path.read_text())
        payload["updated_at"] = now
        payload.setdefault("discord", {})
        payload["discord"].update(
            {
                "guild_id": str(guild_id) if guild_id else "",
                "channel_id": str(channel_id),
                "channel_name": channel_name,
            }
        )
    else:
        title = channel_name.removeprefix("proj-").replace("-", " ").title()
        payload = {
            "project_id": project_id,
            "title": title,
            "summary": "",
            "status": "active",
            "discord": {
                "guild_id": str(guild_id) if guild_id else "",
                "channel_id": str(channel_id),
                "channel_name": channel_name,
            },
            "obsidian_path": f"Projects/{title}.md",
            "root_context_nodes": [],
            "active_task_ids": [],
            "artifact_paths": [],
            "created_at": now,
            "updated_at": now,
        }

    write_json(project_path, payload)
    ensure_project_note(project_dir, payload)
    return project_id, project_path


def ensure_project_note(project_dir: Path, project: dict) -> Path:
    note_dir = project_dir / "obsidian"
    note_path = note_dir / "project.md"
    if note_path.exists():
        return note_path

    note_dir.mkdir(parents=True, exist_ok=True)
    note = (
        "---\n"
        f"project_id: {project['project_id']}\n"
        "node_type: project\n"
        f"status: {project['status']}\n"
        "---\n\n"
        f"# {project['title']}\n\n"
        "## Summary\n\n"
        f"{project.get('summary', '')}\n\n"
        "## Active Questions\n\n"
        "## Tasks\n\n"
        "## Linked Beliefs\n"
    )
    note_path.write_text(note)
    return note_path


def create_project_task(
    *,
    project_id: str,
    content: str,
    author: str,
    message_id: int,
    channel_id: int,
) -> Path:
    task_id = f"task_{compact_ts()}"
    task_path = SHARED_PROJECTS / project_id / "tasks" / f"{task_id}.json"
    payload = {
        "task_id": task_id,
        "project_id": project_id,
        "title": content.strip().splitlines()[0][:120] if content.strip() else "Discord task",
        "description": content,
        "status": "new",
        "source": {
            "type": "discord",
            "author": author,
            "message_id": str(message_id),
            "channel_id": str(channel_id),
        },
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    write_json(task_path, payload)
    append_project_task(project_id, task_id)
    return task_path


def append_project_task(project_id: str, task_id: str) -> None:
    project_path = SHARED_PROJECTS / project_id / "project.json"
    if not project_path.exists():
        return
    payload = json.loads(project_path.read_text())
    active = payload.setdefault("active_task_ids", [])
    if task_id not in active:
        active.append(task_id)
    payload["updated_at"] = utc_now()
    write_json(project_path, payload)


def create_raw_knowledge_node(
    *,
    channel_name: str,
    content: str,
    author: str,
    message_id: int,
    channel_id: int,
) -> Path:
    node_id = f"kn_{compact_ts()}"
    node_path = SHARED_CONTEXT_GRAPH / "nodes" / f"{node_id}.json"
    raw_path = SHARED_CONTEXT_GRAPH / "raw" / f"{node_id}.md"
    title = content.strip().splitlines()[0][:120] if content.strip() else "Raw Discord note"
    now = utc_now()

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        "---\n"
        f"node_id: {node_id}\n"
        "node_type: source\n"
        "status: raw\n"
        f"channel: {channel_name}\n"
        f"author: {author}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{content}\n"
    )

    payload = {
        "node_id": node_id,
        "node_type": "source",
        "title": title,
        "summary": "",
        "status": "raw",
        "confidence": 0.0,
        "source_type": "user_belief",
        "validation_required": ["provenance", "distillation_review"],
        "parents": [],
        "children": [],
        "evidence_supports": [],
        "evidence_contradicts": [],
        "project_ids": [],
        "raw_content_ref": str(raw_path),
        "obsidian_path": str(raw_path),
        "source": {
            "type": "discord",
            "author": author,
            "message_id": str(message_id),
            "channel_id": str(channel_id),
            "channel_name": channel_name,
        },
        "created_at": now,
        "updated_at": now,
    }
    return write_json(node_path, payload)


def publish_review_event(kind: str, payload: dict) -> Path:
    outbox = VAULT_BUS / "review-events"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"{compact_ts()}_{kind}.json"
    write_json(path, {"event": kind, "payload": payload, "created_at": utc_now()})
    return path
