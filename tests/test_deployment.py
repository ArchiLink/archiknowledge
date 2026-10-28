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


def test_proxy_publishes_only_portal_port_on_http():
    # REQ-OPS-004 AC-05
    services = compose_services((ROOT / "docker-compose.yml").read_text())
    mappings = [line.strip() for line in services["proxy"] if line.strip().startswith('- "$')]
    assert mappings == ['- "${PORTAL_PORT:-80}:8080"']
    caddyfile = (ROOT / "proxy" / "Caddyfile").read_text()
    assert "auto_https off" in caddyfile
    assert ":443" not in caddyfile


def test_every_service_rotates_logs():
    # REQ-OPS-005 AC-05
    text = (ROOT / "docker-compose.yml").read_text()
    assert re.search(r'max-size: "\d+m"', text)
    assert re.search(r'max-file: "\d+"', text)
    for name, lines in compose_services(text).items():
        assert "    logging: *logging" in lines, f"{name} has no log rotation"


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


def compose_project_name(path):
    match = re.search(r"^name:\s*(\S+)\s*$", path.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def test_test_stack_has_its_own_project_name():
    # REQ-OPS-008 AC-01: the default project name comes from the folder, so set one for tests.
    test_name = compose_project_name(ROOT / "docker-compose.test.yml")
    assert test_name
    assert test_name != compose_project_name(ROOT / "docker-compose.yml")
