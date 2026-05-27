import argparse
import json
import tempfile
import subprocess
from pathlib import Path
from tqdm import tqdm

MODEL_NAME = "AssertFlip"
INTERESTING_INSTANCES = []

# Mapping from repo name → target path prefix
REPO_TO_PREFIX = {
    "astropy": "astropy/tests/test_assertflip_",
    "django": "tests/test_assertflip_",
    "matplotlib": "lib/matplotlib/tests/test_assertflip_",
    "pallets": "tests/test_assertflip_",
    "mwaskom_seaborn": "tests/test_assertflip_",
    "psf": "test_assertflip_",
    "pydata": "xarray/tests/test_assertflip_",
    "pylint-dev": "tests/test_assertflip_",
    "pytest-dev": "testing/test_assertflip_",
    "scikit-learn": "sklearn/tests/test_assertflip_",
    "sphinx-doc": "tests/test_assertflip_",
    "sympy": "sympy/polys/tests/test_assertflip_",
}

def rewrite_patch_as_new_file(raw_patch: str, target_path: str) -> str:
    lines = raw_patch.splitlines()
    new_lines = []

    for line in lines:
        if line.startswith("diff --git"):
            new_lines.append(f"diff --git a/dev/null b/{target_path}")
            new_lines.append("new file mode 100644")
        elif line.startswith("---"):
            new_lines.append("--- /dev/null")
        elif line.startswith("+++"):
            new_lines.append(f"+++ b/{target_path}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

def make_patch(test_code: str, instance_id: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        old_file = tmp / f"{instance_id}_empty.py"
        new_file = tmp / f"{instance_id}_test.py"

        old_file.write_text("")  # baseline
        new_file.write_text(test_code)

        result = subprocess.run(
            ["git", "diff", "--no-index", "--minimal", str(old_file), str(new_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()

def get_final_successful_test(attempts: list) -> dict:
    for item in reversed(attempts):
        if (
            item.get("phase") == "terminating"
            and item.get("outcome") == "success"
            and "final_test" in item
        ):
            return item
    return None

def get_target_path(instance_id: str) -> str:
    repo_name = instance_id.split("__")[0]
    prefix = REPO_TO_PREFIX.get(repo_name, "tests/test_assertflip_")  # fallback default
    return f"{prefix}{instance_id}.py"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--model-name", default=MODEL_NAME)
    parser.add_argument(
        "--instance-ids",
        default="",
        help="Optional comma-separated instance IDs to include.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    model_name = args.model_name
    interesting_instances = set(filter(None, args.instance_ids.split(",")))
    processed_instances = set()
    if out_file.exists():
        with open(out_file) as existing:
            for line in existing:
                if line.strip():
                    processed_instances.add(json.loads(line)["instance_id"])

    preds = []

    for fpath in tqdm(sorted(results_dir.glob("attempts_*.json"))):
        with open(fpath) as f:
            attempts = json.load(f)

        instance_id = attempts[0]["instance_id"]

        if interesting_instances and instance_id not in interesting_instances:
            continue
        if instance_id in processed_instances:
            continue

        last_successful = get_final_successful_test(attempts)
        if not last_successful:
            print(f"{instance_id}: No successful final_test found. Skipping.")
            continue

        final_test = last_successful["final_test"]
        target_path = get_target_path(instance_id)
        raw_patch = make_patch(final_test, instance_id)
        patch = rewrite_patch_as_new_file(raw_patch, target_path)

        preds.append({
            "instance_id": instance_id,
            "model_name_or_path": model_name,
            "model_patch": patch
        })

        with open(out_file, "a") as out:
            out.write(json.dumps(preds[-1]) + "\n")
        processed_instances.add(instance_id)

    print(f"\nWrote {len(preds)} new entries to {out_file}")

if __name__ == "__main__":
    main()
