"""Тесты плана установки MTProto (dry-run)."""

from proxy_installer.installers.mtproto import MTProtoInstaller, SERVICE_NAME


def test_build_install_plan_contains_apt_and_systemctl() -> None:
    inst = MTProtoInstaller()
    plan = inst.build_install_plan()
    joined = "\n".join(cmd for _, cmd in plan)
    assert "apt-get update" in joined
    assert "systemctl daemon-reload" in joined
    assert f"systemctl is-active {SERVICE_NAME}" in joined
    assert "telegrammessenger/proxy" in joined


def test_core_steps_match_plan_without_meta() -> None:
    inst = MTProtoInstaller()
    core = inst._core_ssh_steps()
    plan = inst.build_install_plan()
    assert len(plan) == len(core) + 2
