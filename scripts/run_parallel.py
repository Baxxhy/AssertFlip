import os
import re
import json
import subprocess
import select
import time
import uuid
from constants import MAP_REPO_VERSION_TO_SPECS, CUSTOM_INSTRUCTIONS
import docker
from pathlib import Path
import shlex
from unidiff import PatchSet
from datasets import load_dataset
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from config import (
    DATASET_PATH,
    DATASET,
    ASSERTFLIP_DIR,
    RESULTS_DIR,
    max_attempts,
    model,
    phase_mode,
    max_generation_retries,
)
from mirror_config import apt_mirror_setup_command, docker_image_candidates, pip_options

# Parallel processing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Any

NUM_WORKERS = 1  # Number of parallel workers

load_dotenv()

# List of instances you want to rerun
FORCE_INSTANCES = {

}

# Ensure results directory exists
os.makedirs(RESULTS_DIR, exist_ok=True)


def docker_pull_command(image_name: str) -> list[str]:
    help_result = subprocess.run(
        ["docker", "pull", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    if "--progress" in help_result.stdout:
        return ["docker", "pull", "--progress=plain", image_name]
    return ["docker", "pull", image_name]


def run_streaming_command(command, log_prefix: str, heartbeat_seconds: int = 30, max_quiet_seconds: int | None = None):
    """Run a command while printing streamed output plus periodic progress heartbeats."""
    started = time.monotonic()
    last_output = started
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    while True:
        ready, _, _ = select.select([process.stdout], [], [], heartbeat_seconds)
        if ready:
            line = process.stdout.readline()
            if line:
                last_output = time.monotonic()
                print(f"{log_prefix} {line.rstrip()}", flush=True)
                continue

        rc = process.poll()
        if rc is not None:
            for line in process.stdout:
                if line:
                    print(f"{log_prefix} {line.rstrip()}", flush=True)
            if rc != 0:
                raise subprocess.CalledProcessError(rc, command)
            elapsed = int(time.monotonic() - started)
            print(f"{log_prefix} 命令完成，耗时 {elapsed} 秒", flush=True)
            return

        elapsed = int(time.monotonic() - started)
        quiet = int(time.monotonic() - last_output)
        if max_quiet_seconds is not None and quiet >= max_quiet_seconds:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            raise subprocess.TimeoutExpired(command, elapsed)
        print(f"{log_prefix} 仍在执行，已耗时 {elapsed} 秒，最近 {quiet} 秒没有新输出", flush=True)


def ensure_docker_image(base_image_name: str, instance_id: str, log_step) -> str:
    candidates = docker_image_candidates(base_image_name)
    for candidate in candidates:
        result = subprocess.run(["docker", "images", "-q", candidate], capture_output=True, text=True)
        if result.stdout.strip():
            log_step(f"使用本地缓存镜像: {candidate}")
            return candidate

    errors: list[str] = []
    total = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        log_step(f"本地没有镜像，尝试拉取第 {index}/{total} 个镜像源: {candidate}")
        try:
            quiet_timeout = int(os.getenv("DOCKER_PULL_QUIET_TIMEOUT", "300"))
            run_streaming_command(
                docker_pull_command(candidate),
                f"[{instance_id}] [镜像拉取 {index}/{total}]",
                max_quiet_seconds=quiet_timeout,
            )
            log_step(f"镜像拉取成功，后续使用: {candidate}")
            return candidate
        except subprocess.CalledProcessError as exc:
            message = f"{candidate} 拉取失败，退出码 {exc.returncode}"
            errors.append(message)
            if index < total:
                log_step(f"{message}，继续尝试下一个镜像源")
            else:
                log_step(f"{message}，已经没有更多镜像源")
        except subprocess.TimeoutExpired as exc:
            message = f"{candidate} 拉取超时，{exc.timeout} 秒内没有有效进展"
            errors.append(message)
            if index < total:
                log_step(f"{message}，继续尝试下一个镜像源")
            else:
                log_step(f"{message}，已经没有更多镜像源")

    raise RuntimeError("所有 Docker 镜像源都拉取失败: " + " | ".join(errors))

# Define repo directories mapping
repo_directories = {
    'flask': {'source_dir': 'src/flask', 'tests_dir': 'tests'},
    'django': {'source_dir': 'django', 'tests_dir': 'tests'},
    'matplotlib': {'source_dir': 'lib/matplotlib', 'tests_dir': 'lib/matplotlib/tests'},
    'pylint': {'source_dir': 'pylint', 'tests_dir': 'tests'},
    'pytest': {'source_dir': 'src/_pytest', 'tests_dir': 'testing'},
    'requests': {'source_dir': 'requests', 'tests_dir': 'tests'},
    'scikit-learn': {'source_dir': 'sklearn', 'tests_dir': 'sklearn/tests'},
    'seaborn': {'source_dir': 'seaborn', 'tests_dir': 'tests'},
    'sphinx': {'source_dir': 'sphinx', 'tests_dir': 'tests'},
    'sympy': {'source_dir': 'sympy', 'tests_dir': 'sympy/testing'},
    'astropy': {'source_dir': 'astropy', 'tests_dir': 'astropy/tests'},
    'xarray': {'source_dir': 'xarray', 'tests_dir': 'xarray/tests'}
}

NON_TEST_EXTS = [
    ".json",
    ".png",
    "csv",
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".pkl",
    ".yml",
    ".yaml",
    ".toml",
]

def parse_diff(diff_text: str):
    try:
        patch_set = PatchSet(diff_text)
    except Exception:
        return []
    file_changes = []
    for patched_file in patch_set:
        if patched_file.is_added_file:
            continue
        sorted_lines = []
        file_path = patched_file.path
        if not file_path.startswith('/'):
            file_path = '/' + file_path
        file_changes.append([file_path, sorted_lines])
    return file_changes

def get_test_dir(repo_name: str, instance_id: str, test_patch: str = "") -> str:
    if instance_id in ["psf__requests-1142", "psf__requests-1921", "psf__requests-2931"]:
        return "."
    if repo_name == "sympy":
        patch = parse_diff(test_patch)
        if patch:
            for p in patch:
                if p[0].endswith(".py"):
                    return str(Path(p[0]).parent).strip("/")
    return repo_directories[repo_name]['tests_dir']

def get_test_directives(repo: str, test_patch: str) -> list:
    if repo == "swe-bench/humaneval":
        return ["test.py"]
    diff_pat = r"diff --git a/.* b/(.*)"
    directives = re.findall(diff_pat, test_patch)
    directives = [d for d in directives if not any(d.endswith(ext) for ext in NON_TEST_EXTS)]
    if repo == "django/django":
        directives_transformed = []
        for d in directives:
            d = d[:-len(".py")] if d.endswith(".py") else d
            d = d[len("tests/"):] if d.startswith("tests/") else d
            d = d.replace("/", ".")
            directives_transformed.append(d)
        directives = directives_transformed
    return directives

def file_exists_in_container(container_id: str, file_path: str) -> bool:
    check_cmd = f"test -f {shlex.quote(file_path)}"
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "-c", check_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def process_instance(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single SWE‑bench instance inside its own Docker container.

    Returns a dict describing the outcome so the parent process can log it.
    """
    instance_id = instance["instance_id"]
    def log_step(message: str):
        print(f"[{instance_id}] {message}", flush=True)

    outcome = {
        "instance_id": instance_id,
        "status": "success",
        "error": "",
    }

    attempts_path = Path(RESULTS_DIR) / f"attempts_{instance_id}.json"
    if instance_id not in FORCE_INSTANCES and attempts_path.exists():
        try:
            with open(attempts_path) as f:
                if os.path.getsize(f.name):
                    data = json.load(f)
                    if data:
                        log_step("已存在 attempts 日志，跳过该项目")
                        outcome["status"] = "skipped"
                        return outcome
        except Exception:
            pass  # fall through and re‑process if file is corrupt / empty

    repo_full_name = instance["repo"]  # e.g. "astropy/astropy"
    repo_name = repo_full_name.split("/")[-1]

    if repo_name not in repo_directories:
        outcome["status"] = "skipped"
        outcome["error"] = f"Unknown repo: {repo_name}"
        return outcome

    # Docker image name transformation
    id_docker_compatible = instance_id.replace("__", "_1776_")
    base_image_name = f"swebench/sweb.eval.x86_64.{id_docker_compatible}"
    image_name = ""
    remove_image_after_run = os.getenv("REMOVE_IMAGE_AFTER_RUN", "0") == "1"

    source_dir = repo_directories[repo_name]['source_dir']
    tests_dir = get_test_dir(repo_name, instance_id, instance.get("test_patch", ""))

    temp_json_path = Path(RESULTS_DIR) / f"{instance_id}.json"
    try:
        with open(temp_json_path, "w") as json_file:
            json.dump(instance, json_file, indent=4)

        version = str(instance["version"])
        if version not in MAP_REPO_VERSION_TO_SPECS[repo_full_name]:
            version_alt = version + "0"
            if version_alt not in MAP_REPO_VERSION_TO_SPECS[repo_full_name]:
                outcome["status"] = "skipped"
                outcome["error"] = f"Version {version} not in specs"
                return outcome
            version = version_alt
        _spec = MAP_REPO_VERSION_TO_SPECS[repo_full_name][version]
        test_cmd = _spec["test_cmd"]
        eval_commands = _spec.get("eval_commands", [])
        if isinstance(test_cmd, list):
            test_cmd = test_cmd[-1]

        log_step("步骤 1/7：检查 Docker 镜像")
        image_name = ensure_docker_image(base_image_name, instance_id, log_step)

        env = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "OPENAI_API_BASE": os.getenv("OPENAI_API_BASE", ""),
            "AZURE_API_KEY": os.getenv("AZURE_API_KEY", ""),
            "AZURE_API_BASE": os.getenv("AZURE_API_BASE", ""),
            "AZURE_API_VERSION": os.getenv("AZURE_API_VERSION", ""),
            "CUSTOM_INSTRUCTIONS": CUSTOM_INSTRUCTIONS.get(repo_name, None),
            "PROJECT_NAME": repo_name,
        }
        # Ensure RESULTS_DIR is absolute
        results_dir_abs = str(Path(RESULTS_DIR).resolve())
        log_step("步骤 2/7：创建 Docker 容器")
        container_name = f"assertflip_{instance_id.replace('__', '_').replace('-', '_')}_{uuid.uuid4().hex[:8]}"
        create_cmd = [
            "docker",
            "create",
            "--name",
            container_name,
            "--network",
            "host",
            "-v",
            f"{results_dir_abs}:/results:rw",
        ]
        for key, value in env.items():
            if value is not None:
                create_cmd.extend(["-e", f"{key}={value}"])
        create_cmd.extend([image_name, "sleep", "infinity"])
        create_result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        container_id = create_result.stdout.strip()
        log_step(f"Docker 容器已创建: {container_id[:12]}")

        log_step("步骤 2/7：启动 Docker 容器")
        run_streaming_command(
            ["docker", "start", container_id],
            f"[{instance_id}] [容器启动]",
            heartbeat_seconds=15,
        )
        container_assertflip_path = f"/assertflip"
        log_step(f"Docker 容器已启动: {container_id[:12]}")

        log_step("步骤 3/7：复制 AssertFlip 代码到容器")
        # Copy into container (safe for parallel builds)
        subprocess.run(
          ["docker", "cp", ASSERTFLIP_DIR, f"{container_id}:{container_assertflip_path}"],
          check=True,
        )
        env_export = "export PYTHONWARNINGS=ignore::UserWarning,ignore::SyntaxWarning && " if repo_name == 'sympy' else ""
        if repo_name == 'sympy':
            test_cmd = "/testbed/bin/test -C --verbose"
        quoted_test_cmd = shlex.quote(test_cmd)

        log_step("步骤 4/7：配置 apt 国内源并安装 coverage")
        # Prepare container: basic deps + coverage
        prep_cmd = (
            f"{apt_mirror_setup_command()} && "
            "source /opt/miniconda3/etc/profile.d/conda.sh && "
            "conda activate testbed && "
            f"python -m pip install {pip_options()} coverage"
        )
        subprocess.run(f'docker exec {container_id} bash -c "{prep_cmd}"', shell=True, check=True)

        eval_cmd_str = " && ".join(eval_commands) + " && " if eval_commands else ""

        log_step("步骤 5/7：容器内安装 assertflip 和 hypothesis")
        log_step("步骤 6/7：开始运行 assertflip，内部会执行 planning、passing test、修复、反转、LLM validation")
        bash_cmd = (
            f"{env_export}{eval_cmd_str}"
            f"pip install {pip_options()} /assertflip && "
            f"pip install {pip_options()} hypothesis && "
            f"assertflip --test-cmd {quoted_test_cmd} "
            f"--source-dir {source_dir} "
            f"--tests-dir {tests_dir} "
            f"--max-attempts {max_attempts} "
            f"--dataset /results/{instance_id}.json "
            f"--model {model} "
            f"--phase {phase_mode} "  # Options: pass_then_invert (default mode), direct_fail_variant 
            f"--max-generation-retries {max_generation_retries} " 
            f"--max-attempts {max_attempts} "
            # f"--no-llm-validation "  # Uncomment to disable LLM validation
        )
        subprocess.run(f'docker exec {container_id} bash -c "{bash_cmd}"', shell=True, check=True, timeout=3600)

        log_step("步骤 7/7：复制生成的测试文件到结果目录")
        # Copy generated test file back to host (optional)
        generated_test_path = f"/testbed/{tests_dir}/test_assertflip_{instance_id}.py"
        local_test_path = Path(RESULTS_DIR) / f"test_assertflip_{instance_id}.py"
        if file_exists_in_container(container_id, generated_test_path):
            subprocess.run(
                ["docker", "cp", f"{container_id}:{generated_test_path}", str(local_test_path)],
                check=True,
            )
        log_step("项目处理成功")
    except Exception as e:
        log_step(f"项目处理失败: {e}")
        outcome["status"] = "error"
        outcome["error"] = str(e)
    finally:
        # Teardown container & image
        try:
            if 'container_id' in locals():
                subprocess.run(["docker", "stop", container_id], capture_output=True, text=True, check=False)
                subprocess.run(["docker", "rm", container_id], capture_output=True, text=True, check=False)
                log_step("Docker 容器已删除")
        except docker.errors.APIError:
            pass
        try:
            temp_json_path.unlink(missing_ok=True)
        except Exception:
            pass
        if remove_image_after_run and image_name:
            log_step(f"开始删除本次镜像缓存: {image_name}")
            remove_result = subprocess.run(
                ["docker", "rmi", image_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if remove_result.returncode == 0:
                log_step(f"镜像已删除: {image_name}")
            else:
                msg = (remove_result.stderr or remove_result.stdout or "").strip()
                log_step(f"镜像删除未成功，通常是仍被容器使用或层被复用: {msg[:300]}")

    return outcome

def main():
    # Load dataset
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)
    print(f"Loaded {len(dataset)} instances from {DATASET_PATH}")

    error_counter = 0
    skipped_counter = 0

    # Submit all jobs to the process pool
    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(process_instance, inst): inst["instance_id"] for inst in dataset}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            result = future.result()
            if result["status"] == "error":
                error_counter += 1
                print(f"[ERROR] {result['instance_id']}: {result['error']}")
            elif result["status"] == "skipped":
                skipped_counter += 1

    print(f"Finished. Errors: {error_counter}, Skipped: {skipped_counter}")


if __name__ == "__main__":
    main()
