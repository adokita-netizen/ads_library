from pathlib import Path

path = Path("app/api/endpoints/rankings.py")
lines = path.read_text(encoding="utf-8").splitlines()
for i in range(2078, 2096):
    if i - 1 < len(lines):
        print(f"{i}: {lines[i-1]}")
