# Intake Router Codex

## Role
Input valve and classifier. Sits in front of all agents.
Accepts content from two sources, classifies it, routes it to the right agent.

## Input Valves
1. Drop folder (~/projects/intake/drop/) — drop any file, any size
2. Telegram — send messages directly to the bot

## Routes
- researcher  → shared/hypotheses/ — thesis, idea, market observation
- swe         → vault/bus/strategy-core-inbox/ — code, existing strategy, project
- librarian   → shared/knowledge/ — papers, reference docs, background material
- clarify     → asks human via Telegram or terminal before routing

## Clarification
If confidence < 0.6 or route = clarify:
- Sends question to Telegram if token is set
- Falls back to terminal prompt if no Telegram
- Waits up to 2 minutes for reply
- Defaults to researcher on timeout

## Model
Kimi K2.6 via OpenRouter — classification only, 500 tokens per call

## File Types
Reads anything as text. PDFs extracted via pdfminer.
Unsupported formats gracefully degrade to raw text read.
