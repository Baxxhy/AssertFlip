#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from constants import CUSTOM_INSTRUCTIONS, MAP_REPO_VERSION_TO_SPECS  # type: ignore
from mirror_config import apt_mirror_setup_command, docker_image_candidates, pip_options  # type: ignore


REPO_DIRECTORIES = {
    "flask": {"source_dir": "src/flask", "tests_dir": "tests"},
    "django": {"source_dir": "django", "tests_dir": "tests"},
    "matplotlib": {"source_dir": "lib/matplotlib", "tests_dir": "lib/matplotlib/tests"},
    "pylint": {"source_dir": "pylint", "tests_dir": "tests"},
    "pytest": {"source_dir": "src/_pytest", "tests_dir": "testing"},
    "requests": {"source_dir": "requests", "tests_dir": "tests"},
    "scikit-learn": {"source_dir": "sklearn", "tests_dir": "sklearn/tests"},
    "seaborn": {"source_dir": "seaborn", "tests_dir": "tests"},
    "sphinx": {"source_dir": "sphinx", "tests_dir": "tests"},
    "sympy": {"source_dir": "sympy", "tests_dir": "sympy/testing"},
    "astropy": {"source_dir": "astropy", "tests_dir": "astropy/tests"},
    "xarray": {"source_dir": "xarray", "tests_dir": "xarray/tests"},
}

NON_TEST_EXTS = [".json", ".png", "csv", ".txt", ".md", ".jpg", ".jpeg", ".pkl", ".yml", ".yaml", ".toml"]


def run(command: list[str], *, check: bool = True, timeout: int | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, timeout=timeout, text=True, capture_output=capture)


def load_project_env(root_dir: str) -> None:
    env_path = Path(root_dir) / "scripts" / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def docker_pull_command(image_name: str) -> list[str]:
    help_result = subprocess.run(["docker", "pull", "--help"], capture_output=True, text=True, check=False)
    if "--progress" in help_result.stdout:
        return ["docker", "pull", "--progress=plain", image_name]
    return ["docker", "pull", image_name]


def stream(command: list[str], prefix: str, quiet_timeout: int = 600) -> None:
    started = time.monotonic()
    last_output = started
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if line:
            last_output = time.monotonic()
            print(f"{prefix} {line.rstrip()}", flush=True)
            continue
        rc = proc.poll()
        if rc is not None:
            for rest in proc.stdout:
                if rest:
                    print(f"{prefix} {rest.rstrip()}", flush=True)
            if rc:
                raise subprocess.CalledProcessError(rc, command)
            return
        if time.monotonic() - last_output > quiet_timeout:
            proc.terminate()
            raise subprocess.TimeoutExpired(command, int(time.monotonic() - started))
        time.sleep(1)


def docker_exists(name: str) -> bool:
    return subprocess.run(["docker", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def docker_running(name: str) -> bool:
    result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == "true"


def ensure_image(base_image_name: str, instance_id: str) -> str:
    candidates = docker_image_candidates(base_image_name)
    for candidate in candidates:
        result = subprocess.run(["docker", "images", "-q", candidate], capture_output=True, text=True)
        if result.stdout.strip():
            print(f"[{instance_id}] 使用本地缓存镜像: {candidate}", flush=True)
            return candidate
    timeout = int(os.getenv("DOCKER_PULL_QUIET_TIMEOUT", "600"))
    for index, candidate in enumerate(candidates, start=1):
        try:
            print(f"[{instance_id}] 拉取镜像 {index}/{len(candidates)}: {candidate}", flush=True)
            stream(docker_pull_command(candidate), f"[{instance_id}] [docker pull]", quiet_timeout=timeout)
            return candidate
        except Exception as exc:
            print(f"[{instance_id}] 镜像源失败: {candidate}: {exc}", flush=True)
    raise RuntimeError(f"all image candidates failed for {base_image_name}")


def parse_test_patch_dir(repo_name: str, instance_id: str, test_patch: str) -> str:
    if instance_id in {"psf__requests-1142", "psf__requests-1921", "psf__requests-2931"}:
        return "."
    if repo_name == "sympy":
        match = re.search(r"diff --git a/(.*?\.py) b/", test_patch or "")
        if match:
            return str(Path(match.group(1)).parent)
    return REPO_DIRECTORIES[repo_name]["tests_dir"]


def container_name(instance_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", instance_id)
    return f"btcr_assertflip_{safe}"


def clean_generated_test(container: str, tests_dir: str, instance_id: str) -> None:
    test_path = f"/testbed/{tests_dir}/test_assertflip_{instance_id}.py"
    disabled_path = f"/testbed/{tests_dir}/disabled_test_assertflip_{instance_id}.py"
    subprocess.run(["docker", "exec", container, "bash", "-lc", f"rm -f {shlex.quote(test_path)} {shlex.quote(disabled_path)}"], check=False)


def copy_if_exists(container: str, src: str, dst: Path) -> None:
    check = subprocess.run(["docker", "exec", container, "bash", "-lc", f"test -e {shlex.quote(src)}"], check=False)
    if check.returncode == 0:
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["docker", "cp", f"{container}:{src}", str(dst)], check=False)


def put_file_in_container(container: str, src: Path, dst: str) -> None:
    data = src.read_bytes()
    put_bytes_in_container(container, data, dst)


def put_bytes_in_container(container: str, data: bytes, dst: str) -> None:
    command = f"mkdir -p {shlex.quote(str(Path(dst).parent))} && cat > {shlex.quote(dst)}"
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "bash", "-lc", command],
        input=data,
        check=False,
    )
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, ["docker", "exec", "-i", container, "bash", "-lc", command])


def write_runtime_env(container: str, instance_id: str, repo_name: str) -> str:
    runtime_env = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OPENAI_API_BASE": os.getenv("OPENAI_API_BASE", ""),
        "AZURE_API_KEY": os.getenv("AZURE_API_KEY", ""),
        "AZURE_API_BASE": os.getenv("AZURE_API_BASE", ""),
        "AZURE_API_VERSION": os.getenv("AZURE_API_VERSION", ""),
        "CUSTOM_INSTRUCTIONS": CUSTOM_INSTRUCTIONS.get(repo_name, ""),
        "PROJECT_NAME": repo_name,
    }
    lines = [f"export {key}={shlex.quote(value or '')}" for key, value in runtime_env.items()]
    path = f"/results/assertflip_env_{instance_id}.sh"
    put_bytes_in_container(container, ("\n".join(lines) + "\n").encode(), path)
    subprocess.run(["docker", "exec", container, "bash", "-lc", f"chmod 600 {shlex.quote(path)}"], check=False)
    return path


def process_instance(instance: dict[str, Any], args: argparse.Namespace, index: int, total: int) -> dict[str, Any]:
    instance_id = instance["instance_id"]
    print(f"[当前项目 {index}/{total}] {instance_id} 开始处理", flush=True)
    outcome = {"instance_id": instance_id, "status": "success", "error": ""}

    results_dir = Path(args.results_dir).resolve()
    attempts_path = results_dir / f"attempts_{instance_id}.json"
    if not args.force and attempts_path.exists() and attempts_path.stat().st_size > 0:
        print(f"[{instance_id}] 已存在 attempts 日志，跳过", flush=True)
        return {"instance_id": instance_id, "status": "skipped", "error": ""}

    repo_full_name = instance["repo"]
    repo_name = repo_full_name.split("/")[-1]
    if repo_name not in REPO_DIRECTORIES:
        return {"instance_id": instance_id, "status": "skipped", "error": f"Unknown repo: {repo_name}"}

    source_dir = REPO_DIRECTORIES[repo_name]["source_dir"]
    tests_dir = parse_test_patch_dir(repo_name, instance_id, instance.get("test_patch", ""))
    id_docker_compatible = instance_id.replace("__", "_1776_")
    base_image_name = f"swebench/sweb.eval.x86_64.{id_docker_compatible}"
    container = container_name(instance_id)
    temp_json = results_dir / f"{instance_id}.json"
    related_tests_src = Path(args.root_dir) / "datasets" / "related_tests.json"
    related_tests_dst = results_dir / "related_tests.json"

    try:
        temp_json.write_text(json.dumps(instance, indent=2))
        if related_tests_src.exists() and not related_tests_dst.exists():
            related_tests_dst.write_text(related_tests_src.read_text())

        version = str(instance["version"])
        if version not in MAP_REPO_VERSION_TO_SPECS[repo_full_name]:
            alt = version + "0"
            if alt not in MAP_REPO_VERSION_TO_SPECS[repo_full_name]:
                return {"instance_id": instance_id, "status": "skipped", "error": f"Version {version} not in specs"}
            version = alt
        spec = MAP_REPO_VERSION_TO_SPECS[repo_full_name][version]
        test_cmd = spec["test_cmd"]
        if isinstance(test_cmd, list):
            test_cmd = test_cmd[-1]
        eval_cmd_str = " && ".join(spec.get("eval_commands", []))
        if eval_cmd_str:
            eval_cmd_str += " && "
        if repo_name == "sympy":
            test_cmd = "/testbed/bin/test -C --verbose"

        image = ensure_image(base_image_name, instance_id)
        if docker_exists(container):
            if not docker_running(container):
                run(["docker", "start", container])
            print(f"[{instance_id}] 复用容器: {container}", flush=True)
        else:
            create_cmd = [
                "docker", "create", "--name", container, "--network", "host",
                "-v", f"{results_dir}:/results:rw",
            ]
            create_cmd.extend([image, "sleep", "infinity"])
            run(create_cmd)
            run(["docker", "start", container])
            print(f"[{instance_id}] 创建并启动容器: {container}", flush=True)

        run(["docker", "exec", container, "bash", "-lc", "mkdir -p /results"])
        put_file_in_container(container, temp_json, f"/results/{instance_id}.json")
        if related_tests_dst.exists():
            put_file_in_container(container, related_tests_dst, "/results/related_tests.json")
        env_file = write_runtime_env(container, instance_id, repo_name)

        clean_generated_test(container, tests_dir, instance_id)

        run(["docker", "exec", container, "bash", "-lc", "rm -rf /assertflip"])
        run(["docker", "cp", str((Path(args.root_dir) / "assertflip").resolve()), f"{container}:/assertflip"])

        prep_cmd = (
            f"{apt_mirror_setup_command()} && "
            "source /opt/miniconda3/etc/profile.d/conda.sh && "
            "conda activate testbed && "
            f"python -m pip install {pip_options()} coverage"
        )
        run(["docker", "exec", container, "bash", "-lc", prep_cmd], timeout=1800)

        env_export = "export PYTHONWARNINGS=ignore::UserWarning,ignore::SyntaxWarning && " if repo_name == "sympy" else ""
        bash_cmd = (
            f"source {shlex.quote(env_file)} && "
            f"{env_export}{eval_cmd_str}"
            f"/opt/miniconda3/bin/python -m pip install {pip_options()} /assertflip && "
            f"/opt/miniconda3/bin/python -m pip install {pip_options()} hypothesis && "
            f"/opt/miniconda3/bin/python -m assertFlip --test-cmd {shlex.quote(test_cmd)} "
            f"--source-dir {shlex.quote(source_dir)} "
            f"--tests-dir {shlex.quote(tests_dir)} "
            f"--dataset /results/{shlex.quote(instance_id)}.json "
            f"--model {shlex.quote(args.model)} "
            f"--phase {shlex.quote(args.phase)} "
            f"--max-generation-retries {args.max_generation_retries} "
            f"--max-attempts {args.max_attempts} "
            "--related-tests /results/related_tests.json "
            f"--btcr-output-dir /results/btcr_results"
        )
        run(["docker", "exec", container, "bash", "-lc", bash_cmd], timeout=args.instance_timeout)

        generated_test = f"/testbed/{tests_dir}/test_assertflip_{instance_id}.py"
        copy_if_exists(container, generated_test, results_dir / f"test_assertflip_{instance_id}.py")
        copy_if_exists(container, f"/results/attempts_{instance_id}.json", results_dir / f"attempts_{instance_id}.json")
        copy_if_exists(container, f"/results/btcr_results/{instance_id}", results_dir / "btcr_results" / instance_id)
        clean_generated_test(container, tests_dir, instance_id)
    except Exception as exc:
        outcome = {"instance_id": instance_id, "status": "error", "error": repr(exc)}
        try:
            clean_generated_test(container, tests_dir, instance_id)
        except Exception:
            pass
    finally:
        try:
            temp_json.unlink(missing_ok=True)
        except Exception:
            pass

    print(f"[当前项目 {index}/{total}] {instance_id} 处理完成: {outcome}", flush=True)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--phase", default="pass_then_invert")
    parser.add_argument("--limit", type=int, default=1000000000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-generation-retries", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--instance-timeout", type=int, default=3600)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    load_project_env(args.root_dir)

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(args.dataset) as f:
        dataset = json.load(f)
    selected = dataset[: args.limit]
    summary_path = results_dir / "run_summary.jsonl"

    print(f"准备运行 AssertFlip+BTCR，共 {len(selected)} 条数据")
    print(f"并行 workers: {args.workers}")
    print(f"结果目录: {results_dir.resolve()}")

    if args.workers <= 1:
        for index, instance in enumerate(selected, start=1):
            result = process_instance(instance, args, index, len(selected))
            result["index"] = index
            with summary_path.open("a") as out:
                out.write(json.dumps(result) + "\n")
    else:
        indexed = [(i, inst) for i, inst in enumerate(selected, start=1)]
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_instance, inst, args, i, len(selected)): (i, inst["instance_id"]) for i, inst in indexed}
            for future in as_completed(futures):
                index, instance_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"instance_id": instance_id, "status": "error", "error": repr(exc)}
                result["index"] = index
                with summary_path.open("a") as out:
                    out.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
