"""Claude Code ingestor: reads session JSONL transcripts into raw memories.

Claude Code stores sessions as ``.jsonl`` files under
``~/.claude/projects/<project>/<session-id>.jsonl``. Each line is a JSON
object; the ones we care about have ``type`` of ``user`` or ``assistant``
with a ``message.content`` field (string or list of content blocks).

The Stop hook receives a JSON payload on stdin with a ``transcript_path``
key pointing at this file. We read it, pair each user prompt with the
following assistant response, and emit one ``RawMemory`` per pair. The
agent later consolidates these into typed memories.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from uuid_utils import uuid7

from identity_storage.model.raw_memory import RawMemory

ASSISTANT_RESPONSE_MAX_CHARS = 2000


class ClaudeCodeIngestor:
    """Parse a Claude Code JSONL transcript into raw memories."""

    def ingest(self, payload: dict[str, str]) -> Sequence[RawMemory]:
        transcript_path = payload.get("transcript_path")
        if not transcript_path:
            return []

        path = Path(transcript_path).expanduser()
        if not path.is_file():
            return []

        session_id = payload.get("session_id", "unknown")
        messages = _read_messages(path)
        pairs = _pair_prompts_with_responses(messages)
        return [
            RawMemory(
                id=uuid7(),  # type: ignore[arg-type]
                content=_build_content(user_prompt, assistant_response),
                tags=[f"session:{session_id}"],
                payload={
                    "session_id": session_id,
                    "agent": "claude-code",
                    "metadata": {
                        "user_prompt": user_prompt,
                        "assistant_response": assistant_response,
                    },
                },
                source="stop-hook",
            )
            for user_prompt, assistant_response in pairs
        ]


def _read_messages(path: Path) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("type") in ("user", "assistant"):
            messages.append(obj)
    return messages


def _extract_text(obj: dict[str, object]) -> str:
    message = obj.get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _pair_prompts_with_responses(
    messages: list[dict[str, object]],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    current_prompt = ""

    for msg in messages:
        msg_type = msg.get("type")
        if msg_type == "user":
            text = _extract_text(msg)
            if text and not _is_tool_result(msg):
                if current_prompt:
                    pairs.append((current_prompt, ""))
                current_prompt = text
        elif msg_type == "assistant":
            text = _extract_text(msg)
            if text and current_prompt:
                pairs.append((current_prompt, text))
                current_prompt = ""

    if current_prompt:
        pairs.append((current_prompt, ""))

    return pairs


def _is_tool_result(msg: dict[str, object]) -> bool:
    message = msg.get("message", {})
    if not isinstance(message, dict):
        return False
    content = message.get("content", "")
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    return False


def _build_content(user_prompt: str, assistant_response: str) -> str:
    truncated = assistant_response[:ASSISTANT_RESPONSE_MAX_CHARS]
    if len(assistant_response) > ASSISTANT_RESPONSE_MAX_CHARS:
        truncated += "..."
    return f"User: {user_prompt}\nAssistant: {truncated}"
