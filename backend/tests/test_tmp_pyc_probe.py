from pathlib import Path
import marshal


def _load_code(path: Path):
    data = path.read_bytes()
    return marshal.loads(data[16:])


def _walk(code):
    yield code
    for const in code.co_consts:
        if hasattr(const, "co_name"):
            yield from _walk(const)


def test_probe_rankings_pyc():
    path = Path(__file__).resolve().parents[1] / "app" / "api" / "endpoints" / "__pycache__" / "rankings.cpython-313.pyc"
    code = _load_code(path)
    names = sorted({c.co_name for c in _walk(code)})
    interesting = [name for name in names if "ad360" in name or "bedrock" in name or "cache" in name or "sanitize" in name or "policy" in name]
    raise AssertionError("\n".join(interesting))
