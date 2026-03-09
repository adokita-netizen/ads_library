"""A28 (CI-025): Hardcoded secret detection for CI.

Scans Python/Terraform files for hardcoded secrets, API keys, tokens, passwords.
Returns exit code 1 if any secrets found (fails CI).

Usage:
    python -m scripts.check_secrets
    python -m scripts.check_secrets --ci  # strict mode: exit 1 on findings
"""

import argparse
import os
import re
import sys

# Patterns that indicate hardcoded secrets
SECRET_PATTERNS = [
    # API keys and tokens (long hex/base64 strings assigned to key-like variables)
    (r"""(?:api_key|access_token|secret_key|password|api_secret|bearer)\s*[=:]\s*["'][A-Za-z0-9+/=_-]{20,}["']""",
     "Possible hardcoded API key/token"),
    # AWS keys
    (r"""AKIA[0-9A-Z]{16}""", "AWS Access Key ID"),
    (r"""(?:aws_secret_access_key|AWS_SECRET)\s*[=:]\s*["'][A-Za-z0-9+/=]{30,}["']""",
     "AWS Secret Access Key"),
    # Database URLs with embedded passwords (not localhost/dev)
    (r"""(?:postgresql|mysql|mongodb)(?:\+\w+)?://\w+:[^@\s]{8,}@(?!localhost)(?!127\.0\.0\.1)[^/\s]+""",
     "Database URL with embedded password"),
    # Private keys
    (r"""-----BEGIN (?:RSA |EC )?PRIVATE KEY-----""", "Private key"),
    # JWT secrets
    (r"""(?:jwt_secret|JWT_SECRET)\s*[=:]\s*["'][^"']{16,}["']""",
     "JWT secret"),
]

# Files/dirs to skip
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "media_cache", "exports",
    "models",  # ML model files
}
SKIP_FILES = {
    "check_secrets.py",  # this file
    "conftest.py",  # test fixtures with fake credentials
}

# Known safe patterns (false positives)
SAFE_PATTERNS = [
    r"change-this-to-a-secure-random-string",  # default placeholder
    r"minioadmin",  # local MinIO default
    r"vaap_password",  # local dev default
    r"localhost",
    r"127\.0\.0\.1",
    r"example\.com",
    r"your[-_]?token",
    r"your[-_]?key",
    r"PLACEHOLDER",
    r"xxx+",
    r"test[-_]",
]

SCAN_EXTENSIONS = {".py", ".tf", ".yaml", ".yml", ".json", ".env.example", ".toml", ".cfg"}


def is_safe(line: str) -> bool:
    """Check if a line contains only known-safe/placeholder values."""
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def scan_file(filepath: str) -> list[dict]:
    """Scan a single file for secret patterns."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                for pattern, description in SECRET_PATTERNS:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        if not is_safe(stripped):
                            findings.append({
                                "file": filepath,
                                "line": lineno,
                                "description": description,
                                "content": stripped[:120] + ("..." if len(stripped) > 120 else ""),
                            })
    except (OSError, UnicodeDecodeError):
        pass
    return findings


def scan_directory(root: str) -> list[dict]:
    """Recursively scan directory for secrets."""
    all_findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip excluded dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if filename in SKIP_FILES:
                continue
            ext = os.path.splitext(filename)[1]
            if ext not in SCAN_EXTENSIONS:
                continue
            filepath = os.path.join(dirpath, filename)
            findings = scan_file(filepath)
            all_findings.extend(findings)

    return all_findings


def main():
    parser = argparse.ArgumentParser(description="Scan for hardcoded secrets")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 if secrets found")
    parser.add_argument("--path", type=str, default=".", help="Directory to scan")
    args = parser.parse_args()

    scan_root = os.path.abspath(args.path)
    print(f"Scanning for hardcoded secrets: {scan_root}")

    findings = scan_directory(scan_root)

    if findings:
        print(f"\n{'!'*60}")
        print(f"  FOUND {len(findings)} potential secret(s)")
        print(f"{'!'*60}\n")
        for f in findings:
            rel = os.path.relpath(f["file"], scan_root)
            print(f"  [{f['description']}]")
            print(f"    {rel}:{f['line']}")
            print(f"    {f['content']}")
            print()

        if args.ci:
            print("CI FAILED: Hardcoded secrets detected. Remove or use environment variables.")
            sys.exit(1)
    else:
        print(f"\nNo hardcoded secrets found. All clear!")
        sys.exit(0)


if __name__ == "__main__":
    main()
