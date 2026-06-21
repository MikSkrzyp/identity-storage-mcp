"""identity-storage: portable long-term memory for AI agents.

Layered: ``model/`` (pure data + validation), ``repository/`` (SQLite
queries), ``service/`` (logic, calls repository), ``db/`` (connection
management), ``adapters/`` (MCP server, CLI future), ``schemas/schema.sql``
(DDL).
"""

from identity_storage.model.memory_model import MemoryRecord, MemoryType
from identity_storage.model.store_request import StoreRequest
from identity_storage.repository.memory_repository import MemoryRepository
from identity_storage.service.memory_service import MemoryService
from identity_storage.service.validation import ValidationError

__all__ = [
    "MemoryRecord",
    "MemoryType",
    "MemoryRepository",
    "MemoryService",
    "StoreRequest",
    "ValidationError",
]

__version__ = "0.1.0"
