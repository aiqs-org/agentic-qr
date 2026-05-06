"""
classifier.py
-------------
Uses Kimi K2.6 to classify input and decide where to route it.

Routes:
  researcher  — thesis, idea, market observation, macro argument
  swe         — code, existing strategy, backtest script, project dump
  librarian   — research paper, reference material, documentation, data
  clarify     — genuinely ambiguous, needs human input before routing
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
)
MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2")

SYSTEM_PROMPT = """You are the intake router for an autonomous quantitative research system.

Your job is to classify incoming content and decide where to route it.

Routes available:
- researcher  : trading thesis, investment idea, market observation, macro argument, hypothesis to test
- swe         : existing code, strategy implementation, backtest script, QuantConnect/NautilusTrader project
- librarian   : research paper, reference document, data dictionary, background reading, archived material
- clarify     : genuinely ambiguous — you cannot determine the intent without more information

Respond ONLY with a JSON object in this exact format:
{
  "route": "researcher" | "swe" | "librarian" | "clarify",
  "confidence": 0.0-1.0,
  "reason": "one sentence explaining the classification",
  "summary": "2-3 sentence summary of the content",
  "clarify_question": "question to ask the human if route is clarify, otherwise null"
}
"""


def classify(text: str, filename: str = "") -> dict:
    prompt = f"""Classify this content and decide where to route it.

Filename: {filename}

Content (first 3000 chars):
{text[:3000]}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        logger.info(f"[CLASSIFIER] route={result['route']} confidence={result['confidence']} reason={result['reason']}")
        return result
    except Exception as e:
        logger.error(f"[CLASSIFIER] failed: {e}")
        return {
            "route": "clarify",
            "confidence": 0.0,
            "reason": "classifier error",
            "summary": text[:200],
            "clarify_question": "Classification failed. Where should this be routed? (researcher/swe/librarian)",
        }
