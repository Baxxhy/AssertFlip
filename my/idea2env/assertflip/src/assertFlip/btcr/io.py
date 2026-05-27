import json
from pathlib import Path
from typing import Any


def load_related_tests(path: Path | None, instance_id: str) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if isinstance(data, dict):
        tests = data.get(instance_id, [])
    elif isinstance(data, list):
        tests = []
        for item in data:
            if isinstance(item, dict) and item.get("instance_id") == instance_id:
                tests.extend(item.get("related_tests", item.get("tests", [])))
    else:
        tests = []
    return [t for t in tests if isinstance(t, dict)]


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def resolve_repo_file(repo_root: Path, source_dir: Path, filename: str) -> Path | None:
    candidates = [
        repo_root / filename,
        repo_root / source_dir / filename,
        Path("/testbed") / filename,
        Path("/testbed") / source_dir / filename,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
