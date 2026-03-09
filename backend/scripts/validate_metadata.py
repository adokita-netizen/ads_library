"""Compatibility wrapper for ad_metadata validation.

Delegates to validate_metadata_schema.py so older task docs and scripts can
invoke the expected module path without duplicating logic.
"""

from scripts.validate_metadata_schema import main


if __name__ == "__main__":
    main()
