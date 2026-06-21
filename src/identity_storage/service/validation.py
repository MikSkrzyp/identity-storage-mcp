"""Validation for memory records.

Type-specific payload validation lives here, not in the model. The model
guarantees structure (non-empty content, confidence range); this module
guarantees semantic correctness per ``MemoryType`` (which keys are allowed in
``payload`` for episodic, semantic, etc.).

New memory types register their validators in ``_PAYLOAD_VALIDATORS``.
"""

from __future__ import annotations

from typing import Any

from identity_storage.model.memory_model import MemoryType


class ValidationError(ValueError):
    """Raised when a memory record fails semantic validation."""


_EPISODIC_PAYLOAD_KEYS = frozenset(
    {"session_id", "agent", "task", "outcome", "parent_id", "metadata"}
)


def _validate_episodic_payload(payload: dict[str, Any]) -> None:
    extra = set(payload) - _EPISODIC_PAYLOAD_KEYS
    if extra:
        raise ValidationError(
            f"episodic payload has unexpected keys: {sorted(extra)}. "
            f"Allowed: {sorted(_EPISODIC_PAYLOAD_KEYS)}"
        )


_PAYLOAD_VALIDATORS = {
    MemoryType.EPISODIC: _validate_episodic_payload,
}


def validate_payload(memory_type: MemoryType, payload: dict[str, Any]) -> None:
    validator = _PAYLOAD_VALIDATORS.get(memory_type)
    if validator is not None:
        validator(payload)
