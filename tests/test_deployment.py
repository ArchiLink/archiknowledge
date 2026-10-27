"""Static checks on the deployment files (REQ-OPS-003 AC-05, AC-06)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SERVICES = {"proxy"}  # the only service allowed to publish a port (SECURITY.md)


def compose_services(text):
    """Map each top-level service in a Compose file to its lines (enough for these checks)."""
    services, current, in_services = {}, None, False
    for line in text.splitlines():
        if re.match(r"^\S", line):
            in_services = line.startswith("services:")
            current = None
            continue
        if not in_services:
            continue
        match = re.match(r"^  ([\w-]+):\s*$", line)
        if match:
            current = match.group(1)
            services[current] = []
        elif current:
            services[current].append(line)
    return services


def test_only_proxy_publishes_ports():
    services = compose_services((ROOT / "docker-compose.yml").read_text())
    assert {"web", "db"} <= services.keys()
    for name, lines in services.items():
        publishes = any(re.match(r"^    ports:", line) for line in lines)
        assert not publishes or name in PUBLIC_SERVICES, f"{name} publishes a port"


def test_images_are_pinned_to_specific_tags():
    text = (ROOT / "Dockerfile").read_text() + (ROOT / "docker-compose.yml").read_text()
    stages = set(re.findall(r"^FROM \S+ AS (\w+)", text, re.MULTILINE))
    images = re.findall(r"(?:^FROM|^COPY --from=|^\s+image:)\s*(\S+)", text, re.MULTILINE)
    assert images
    for image in (i for i in images if i not in stages):
        tag = image.rsplit(":", 1)[-1] if ":" in image else ""
        assert re.match(r"\d+\.\d+", tag), f"{image} is not pinned to a version"


def test_runtime_image_runs_as_non_root():
    dockerfile = (ROOT / "Dockerfile").read_text()
    runtime = dockerfile.split("AS runtime", 1)[1]
    assert re.search(r"^USER app$", runtime, re.MULTILINE)


def test_dependencies_are_locked():
    assert (ROOT / "uv.lock").is_file()


def test_compose_parser_detects_published_port():
    text = "services:\n  web:\n    ports:\n      - '80:80'\nvolumes:\n  x:\n"
    assert compose_services(text) == {"web": ["    ports:", "      - '80:80'"]}
