"""Tests for the Claude Code ingestor.

Uses synthetic JSONL transcripts to verify pairing of user prompts with
assistant responses, handling of tool results, and edge cases.
"""

from __future__ import annotations

import json
from pathlib import Path

from identity_storage.adapters.ingest.claude_code import ClaudeCodeIngestor

EXPECTED_PAIR_COUNT = 2
LONG_TEXT_LENGTH = 5000


def _write_transcript(path: Path, lines: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n",
        encoding="utf-8",
    )


def _user_msg(content: str | list[dict[str, str]]) -> dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": content}}


def _assistant_msg(content: str | list[dict[str, str]]) -> dict[str, object]:
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def _tool_result_msg() -> dict[str, object]:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_1"}],
        },
    }


def test_basic_prompt_response_pair(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("fix the login bug"),
            _assistant_msg("Fixed auth check in login.py"),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript), "session_id": "s1"}))

    assert len(memories) == 1
    assert "fix the login bug" in memories[0].content
    assert "Fixed auth check" in memories[0].content
    assert "session:s1" in memories[0].tags
    assert memories[0].source == "stop-hook"


def test_multiple_pairs(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("what is 2+2"),
            _assistant_msg("4"),
            _user_msg("and 3+3"),
            _assistant_msg("6"),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript)}))

    assert len(memories) == EXPECTED_PAIR_COUNT
    assert "what is 2+2" in memories[0].content
    assert "and 3+3" in memories[1].content


def test_tool_result_messages_are_not_prompts(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("run the tests"),
            _assistant_msg([{"type": "text", "text": "Running tests..."}]),
            _tool_result_msg(),
            _assistant_msg([{"type": "text", "text": "All tests passed."}]),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript)}))

    assert len(memories) == 1
    assert "run the tests" in memories[0].content


def test_missing_transcript_path_returns_empty() -> None:
    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({}))
    assert memories == []


def test_nonexistent_file_returns_empty(tmp_path: Path) -> None:
    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(tmp_path / "nope.jsonl")}))
    assert memories == []


def test_prompt_without_response_is_still_saved(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("hello"),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript)}))

    assert len(memories) == 1
    assert "hello" in memories[0].content


def test_assistant_text_blocks_are_concatenated(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("explain the bug"),
            _assistant_msg(
                [
                    {"type": "text", "text": "The bug was in auth.py."},
                    {"type": "text", "text": "I fixed it by adding a null check."},
                ]
            ),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript)}))

    assert len(memories) == 1
    content = memories[0].content
    assert "The bug was in auth.py." in content
    assert "I fixed it by adding a null check." in content


def test_long_assistant_response_is_truncated(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    long_text = "x" * LONG_TEXT_LENGTH
    _write_transcript(
        transcript,
        [
            _user_msg("generate text"),
            _assistant_msg(long_text),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript)}))

    assert len(memories) == 1
    assert "..." in memories[0].content
    assert len(memories[0].content) < LONG_TEXT_LENGTH


def test_payload_includes_session_id_and_full_prompt(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    _write_transcript(
        transcript,
        [
            _user_msg("remember this"),
            _assistant_msg("OK, remembered."),
        ],
    )

    ingestor = ClaudeCodeIngestor()
    memories = list(ingestor.ingest({"transcript_path": str(transcript), "session_id": "abc-123"}))

    assert len(memories) == 1
    payload = memories[0].payload
    assert payload is not None
    assert payload["session_id"] == "abc-123"
    assert payload["agent"] == "claude-code"
    assert payload["metadata"]["user_prompt"] == "remember this"
