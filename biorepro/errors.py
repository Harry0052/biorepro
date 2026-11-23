"""Typed failures. The category string is the contract; exit codes are stable."""

from __future__ import annotations


EXIT_CODE = {
    "valid": 0,
    "match": 0,
    "numeric_disagreement": 1,
    "malformed_input": 2,
    "oversized_input": 3,
    "schema_mismatch": 4,
    "duplicate_key": 5,
    "missing_endpoint": 6,
    "hash_mismatch": 7,
    "review_rejected": 8,
    "missing_output": 9,
    "timeout": 10,
    "resource_limit": 11,
    "isolation_blocked": 12,
    "worker_failed": 13,
    "missing_value": 14,
    "internal_error": 70,
}


class BioreproError(Exception):
    def __init__(self, category: str, message: str, *, reason: str | None = None, path: str | None = None):
        if category not in EXIT_CODE:
            raise ValueError(f"unknown category {category}")
        super().__init__(message)
        self.category = category
        self.message = message
        self.reason = reason
        self.path = path

    @property
    def exit_code(self) -> int:
        return EXIT_CODE[self.category]
