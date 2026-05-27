import os
import shlex
from urllib.parse import urlparse


DEFAULT_DOCKER_IMAGE_REGISTRY = "docker.1ms.run"
DEFAULT_PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
DEFAULT_APT_MIRROR = "https://mirrors.tuna.tsinghua.edu.cn"


def docker_image_candidates(base_image_name: str) -> list[str]:
    registries_env = os.getenv("DOCKER_IMAGE_REGISTRIES", "").strip()
    if registries_env:
        registries = [item.strip().strip("/") for item in registries_env.split(",")]
    else:
        registry = os.getenv("DOCKER_IMAGE_REGISTRY", DEFAULT_DOCKER_IMAGE_REGISTRY).strip().strip("/")
        registries = [registry]

    candidates: list[str] = []
    for registry in registries:
        if registry:
            candidates.append(f"{registry}/{base_image_name}")
    candidates.append(base_image_name)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def pip_options() -> str:
    index_url = os.getenv("PIP_INDEX_URL", DEFAULT_PIP_INDEX_URL).strip()
    parsed = urlparse(index_url)
    trusted_host = os.getenv("PIP_TRUSTED_HOST", parsed.hostname or "").strip()
    parts = ["-i", shlex.quote(index_url)]
    if trusted_host:
        parts.extend(["--trusted-host", shlex.quote(trusted_host)])
    return " ".join(parts)


def apt_mirror_setup_command() -> str:
    mirror = os.getenv("APT_MIRROR", DEFAULT_APT_MIRROR).strip().rstrip("/")
    ubuntu = f"{mirror}/ubuntu"
    debian = f"{mirror}/debian"
    debian_security = f"{mirror}/debian-security"
    return (
        "if command -v apt-get >/dev/null 2>&1; then "
        "cp /etc/apt/sources.list /etc/apt/sources.list.bak.assertflip 2>/dev/null || true; "
        "find /etc/apt -type f \\( -name 'sources.list' -o -name '*.list' -o -name '*.sources' \\) -print0 "
        "| xargs -0 -r sed -i "
        f"-e 's|http://archive.ubuntu.com/ubuntu|{ubuntu}|g' "
        f"-e 's|http://security.ubuntu.com/ubuntu|{ubuntu}|g' "
        f"-e 's|http://deb.debian.org/debian|{debian}|g' "
        f"-e 's|http://security.debian.org/debian-security|{debian_security}|g' "
        f"-e 's|http://security.debian.org/|{debian_security}|g' "
        f"-e 's|https://archive.ubuntu.com/ubuntu|{ubuntu}|g' "
        f"-e 's|https://security.ubuntu.com/ubuntu|{ubuntu}|g' "
        f"-e 's|https://deb.debian.org/debian|{debian}|g' "
        f"-e 's|https://security.debian.org/debian-security|{debian_security}|g' "
        f"-e 's|https://security.debian.org/|{debian_security}|g'; "
        "fi"
    )
