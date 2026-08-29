"""Generic Harness Adapter Package for Memory System v2."""

from .adapter import (
    REQUIRED_PROJECT_MEMORY_FILES,
    SUPPORTED_OPERATIONS,
    CapabilityReport,
    CapabilityStatus,
    Finding,
    GenericMemoryAdapter,
    OperationResult,
)

__all__ = [
    "CapabilityReport",
    "CapabilityStatus",
    "Finding",
    "GenericMemoryAdapter",
    "OperationResult",
    "REQUIRED_PROJECT_MEMORY_FILES",
    "SUPPORTED_OPERATIONS",
]
