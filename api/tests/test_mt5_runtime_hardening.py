from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MT5 = REPO_ROOT / "mt5"
IMAGE = "trading-platform/mt5-rpyc:6.0.2"
NETWORK = "trading-mt5-api"
EGRESS_NETWORK = "trading-mt5-egress"
AUTOTRADING_OPTIONS = r"/config:C:\mt5-autotrading.ini"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_start_linux_rejects_an_existing_unmanaged_mt5_container(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "docker.calls"
    _write_executable(
        fake_bin / "docker",
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {calls}
if [ "$1" = ps ]; then printf '%s\\n' mt5; fi
""",
    )
    for command in ("uv", "npm"):
        _write_executable(fake_bin / command, "#!/bin/sh\nexit 0\n")

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "start-linux.sh")],
        cwd=REPO_ROOT,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "refusing" in (result.stdout + result.stderr).lower()
    assert "remove" in (result.stdout + result.stderr).lower()
    assert calls.read_text(encoding="utf-8").splitlines() == ["ps -a --format {{.Names}}"]


def _compose_config(file: Path) -> dict:
    result = subprocess.run(
        ["docker", "compose", "-f", str(file), "config", "--format", "json"],
        cwd=REPO_ROOT,
        env={**os.environ, "MT5_VNC_PASSWORD": "test-only"},
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_effective_local_bindings_are_loopback_only_and_exact_image() -> None:
    config = _compose_config(MT5 / "compose.local.yaml")
    service = config["services"]["mt5"]

    assert service["image"] == IMAGE
    assert service["environment"]["MT5_CMD_OPTIONS"] == AUTOTRADING_OPTIONS
    assert service.get("network_mode") != "host"
    assert {
        (port["target"], port["published"], port["host_ip"])
        for port in service["ports"]
    } == {(3000, "3000", "127.0.0.1"), (8001, "8001", "127.0.0.1")}


def test_effective_production_network_is_dedicated_and_rpyc_is_not_published() -> None:
    config = _compose_config(MT5 / "compose.yaml")
    for service_name in ("mt5", "mt5-2", "mt5-3"):
        service = config["services"][service_name]
        assert service["image"] == IMAGE
        assert service["environment"]["MT5_CMD_OPTIONS"] == AUTOTRADING_OPTIONS
        assert "build" not in service
        assert set(service["networks"]) == {NETWORK, EGRESS_NETWORK}
        assert all(port["target"] != 8001 for port in service.get("ports", []))

    assert config["networks"][NETWORK]["name"] == NETWORK
    assert config["networks"][NETWORK]["external"] is True
    assert config["networks"][EGRESS_NETWORK]["name"] == EGRESS_NETWORK
    assert config["networks"][EGRESS_NETWORK]["external"] is True
    assert config["volumes"]["mt5-config"]["external"] is True
    assert "dokploy-network" not in json.dumps(config)


def test_network_provisioner_requires_internal_attachable_network() -> None:
    provisioner = MT5 / "ensure-production-network.sh"
    assert provisioner.is_file()
    source = provisioner.read_text(encoding="utf-8")
    assert "--driver overlay" in source
    assert "--internal" in source
    assert "--attachable" in source
    assert NETWORK in source
    assert EGRESS_NETWORK in source
    assert "--driver bridge" in source
    assert "docker volume create" in source
    assert "docker network inspect" in source


def test_production_rollback_is_compose_aware_and_executable() -> None:
    readme = (MT5 / "README.md").read_text(encoding="utf-8")
    assert "docker inspect mt5" not in readme
    assert "docker compose -p trading-platform-mt5docker-1uotpe" in readme
    assert "docker-compose.previous.yml" in readme
    assert "MT5_VNC_PASSWORD" in readme


def test_exact_patch_mismatch_is_executable_and_fail_closed(tmp_path: Path) -> None:
    script = (MT5 / "patch-start.py").read_text(encoding="utf-8")
    script = script.replace('START = Path("/Metatrader/start.sh")', 'START = Path("start.sh")')
    (tmp_path / "patch-start.py").write_text(script, encoding="utf-8")
    (tmp_path / "start.sh").write_text("unexpected upstream patch level\n", encoding="utf-8")

    result = subprocess.run(
        ["python3", "patch-start.py"], cwd=tmp_path, text=True, capture_output=True
    )

    assert result.returncode != 0
    assert "did not match pinned upstream exactly" in result.stderr
    patched_source = (tmp_path / "start.sh").read_text(encoding="utf-8")
    assert patched_source == "unexpected upstream patch level\n"


def test_compose_volume_identity_persists_across_recreate() -> None:
    for compose_file, expected in (
        (MT5 / "compose.local.yaml", "trading-mt5-config-local"),
        (MT5 / "compose.yaml", "trading-mt5-config"),
    ):
        config = _compose_config(compose_file)
        mount = config["services"]["mt5"]["volumes"][0]
        assert mount["type"] == "volume"
        assert mount["target"] == "/config"
        assert mount["source"] in config["volumes"]
        assert config["volumes"][mount["source"]]["name"] == expected


def test_production_runtime_slots_have_unique_persistent_volumes() -> None:
    config = _compose_config(MT5 / "compose.yaml")
    mounts = {
        service_name: config["services"][service_name]["volumes"][0]["source"]
        for service_name in ("mt5", "mt5-2", "mt5-3")
    }

    assert len(set(mounts.values())) == len(mounts)
    assert {
        config["volumes"][volume_name]["name"]
        for volume_name in mounts.values()
    } == {
        "trading-mt5-config",
        "trading-mt5-config-2",
        "trading-mt5-config-3",
    }
    for service_name in ("mt5-2", "mt5-3"):
        healthcheck = config["services"][service_name]["healthcheck"]
        health_command = " ".join(healthcheck["test"])
        assert "rpyc.classic.connect('127.0.0.1', 8001)" in health_command
        assert "connection.eval('6 * 7') == 42" in health_command


def test_production_runtime_init_seeds_autotrading_for_new_slots() -> None:
    config = _compose_config(MT5 / "compose.yaml")
    init = config["services"]["mt5-runtime-init"]
    command = " ".join(init["command"])

    assert init["network_mode"] == "none"
    assert "AllowLiveTrading=1" in command
    assert "Account=0" in command
    assert "Profile=0" in command
    assert 'chown -R 911:911 "$$runtime"' in command
    assert {
        (mount["source"], mount["target"])
        for mount in init["volumes"]
    } == {
        ("mt5-config-2", "/runtime-2"),
        ("mt5-config-3", "/runtime-3"),
    }


def test_autotrading_startup_config_survives_account_and_profile_changes() -> None:
    config = (MT5 / "autotrading.ini").read_text(encoding="utf-8")

    assert "[Experts]" in config
    assert "AllowLiveTrading=1" in config
    assert "Enabled=1" in config
    assert "Account=0" in config
    assert "Profile=0" in config
    assert "Api=0" in config
