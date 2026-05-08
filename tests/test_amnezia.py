"""Тесты плана установки Amnezia WG (dry-run)."""

from proxy_installer.installers.amnezia import AmneziaInstaller


def test_build_install_plan_contains_docker() -> None:
    inst = AmneziaInstaller(port=51820)
    plan = inst.build_install_plan()
    joined = "\n".join(cmd for _, cmd in plan)
    assert "apt-get update" in joined
    assert "docker run -d --name amnezia-wg" in joined
    assert "51820:51820/udp" in joined


def test_core_steps_match_plan_without_meta() -> None:
    inst = AmneziaInstaller()
    core = inst._core_ssh_steps()
    plan = inst.build_install_plan()
    assert len(plan) == len(core) + 1
