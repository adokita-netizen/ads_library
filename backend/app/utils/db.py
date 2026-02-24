"""Database utility functions."""


def escape_like(value: str) -> str:
    """Escape LIKE wildcards to prevent LIKE injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
