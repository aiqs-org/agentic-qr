"""Discord intake adapter.

Channel prefixes define routing:
- proj-*   -> project task records
- inbox-*  -> raw knowledge nodes
- review-* -> review comments/events
- feed-*   -> ignored by intake; used for status output
"""

from __future__ import annotations

import os
from pathlib import Path

import discord
from dotenv import load_dotenv
from loguru import logger

from context_graph import (
    create_project_task,
    create_raw_knowledge_node,
    ensure_project,
    publish_review_event,
)


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")
COMMAND_PREFIX = os.getenv("DISCORD_COMMAND_PREFIX", "!")
VAULT_LOGS = Path(os.getenv("VAULT_LOGS", "/vault/logs"))

VAULT_LOGS.mkdir(parents=True, exist_ok=True)
logger.add(VAULT_LOGS / "discord-intake.log", rotation="10 MB", retention=5)


def channel_kind(channel_name: str) -> str:
    if channel_name.startswith("proj-"):
        return "project"
    if channel_name.startswith("inbox-"):
        return "inbox"
    if channel_name.startswith("review-"):
        return "review"
    if channel_name.startswith("feed-"):
        return "feed"
    return "unrouted"


def message_text(message: discord.Message) -> str:
    parts = []
    if message.content:
        parts.append(message.content)
    for attachment in message.attachments:
        parts.append(f"[attachment] {attachment.filename}: {attachment.url}")
    return "\n".join(parts).strip()


intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    guilds = ", ".join(f"{guild.name}({guild.id})" for guild in client.guilds)
    logger.success(f"[DISCORD] logged in as {client.user} guilds={guilds}")

    if GUILD_ID:
        guild = client.get_guild(int(GUILD_ID))
        if guild:
            logger.info(f"[DISCORD] target guild ready: {guild.name}({guild.id})")
        else:
            logger.warning(f"[DISCORD] target guild id not visible: {GUILD_ID}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.TextChannel):
        return

    channel_name = message.channel.name
    kind = channel_kind(channel_name)
    content = message_text(message)
    if not content:
        return

    if kind == "feed":
        return

    if kind == "project":
        project_id, project_path = ensure_project(
            channel_name=channel_name,
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
        )
        task_path = create_project_task(
            project_id=project_id,
            content=content,
            author=str(message.author),
            message_id=message.id,
            channel_id=message.channel.id,
        )
        logger.success(f"[DISCORD] project task {task_path}")
        await message.add_reaction("✅")
        await message.channel.send(
            "Captured project task\n"
            f"project: `{project_id}`\n"
            f"task: `{task_path.name}`"
        )
        return

    if kind == "inbox":
        node_path = create_raw_knowledge_node(
            channel_name=channel_name,
            content=content,
            author=str(message.author),
            message_id=message.id,
            channel_id=message.channel.id,
        )
        publish_review_event("raw_knowledge_captured", {"node_path": str(node_path)})
        logger.success(f"[DISCORD] raw node {node_path}")
        await message.add_reaction("✅")
        await message.channel.send(
            "Captured raw knowledge node\n"
            f"node: `{node_path.stem}`\n"
            "status: `raw`, needs `distillation_review`"
        )
        return

    if kind == "review":
        event_path = publish_review_event(
            "review_comment",
            {
                "channel": channel_name,
                "author": str(message.author),
                "message_id": str(message.id),
                "content": content,
            },
        )
        logger.success(f"[DISCORD] review event {event_path}")
        await message.add_reaction("✅")
        return

    if content.startswith(COMMAND_PREFIX):
        await message.channel.send(
            "I am online. Use `proj-*` channels for projects and `inbox-*` channels for raw ingestion."
        )


def main():
    if not TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN is not set")
    logger.info("[DISCORD] starting intake adapter")
    client.run(TOKEN)


if __name__ == "__main__":
    main()
