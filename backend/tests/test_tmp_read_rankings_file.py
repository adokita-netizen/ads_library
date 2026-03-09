from pathlib import Path


def test_dump_rankings_lines():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "endpoints" / "rankings.py"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = 2078
    end = 2096
    snippet = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start - 1, min(end, len(lines))))
    raise AssertionError(snippet)
