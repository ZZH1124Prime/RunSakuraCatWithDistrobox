"""命令行编排 —— 配置检查、部署计划、启动与菜单安装。

默认 check/provision/desktop 不修改系统；provision 和 desktop 需 --apply。
launch 是用户主动启动入口；root 内部准备不允许作为普通业务入口使用。
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from .adapters import ADAPTERS
from .backend import DockerDistroboxBackend
from .config import Config, User
from .processes import find_subject
from .sources import SourceResolver
from .systems import SYSTEMS


def launch(config_path, config, user, adapter, resolver, entry, agent_check=False):
    """启动或复用 GUI，为真实进程提供认证。

    :param config_path: 绝对配置路径。
    :param config: 部署配置。
    :param user: 用户上下文。
    :param adapter: 软件适配器。
    :param resolver: 来源解析器。
    :param entry: 项目 run.py 绝对路径。
    :param agent_check: 只检查代理注册，不请求密码。
    """
    from .auth import GraphicalAgent
    state = user.home / ".local/state/vpn-workbench" / config.container
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / "launcher.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("启动器已在运行，不重复注册认证代理。")
            return
        subject = find_subject(adapter.executable, user.uid)
        if not subject:
            if agent_check:
                raise RuntimeError("自检需要已有客户端窗口。")
            source = resolver.choose()
            app_dir, extract = resolver.location(source)
            if extract:
                extract.mkdir(parents=True, exist_ok=True, mode=0o700)
                source.chmod(source.stat().st_mode | 0o100)
            log = state / (time.strftime("%Y%m%d-%H%M%S") + ".log")
            log.touch(mode=0o600)
            session = {key: os.environ.get(key, "") for key in
                       ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS",
                        "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY")}
            env = os.environ.copy()
            env["SHELL"] = "/bin/bash"
            env.pop("DBUS_SYSTEM_BUS_ADDRESS", None)
            command = ["/usr/bin/pkexec", "/usr/bin/python3", str(entry),
                       "--config", str(config_path), "_prepare",
                       "--source", str(source), "--session", json.dumps(session), "--log", str(log)]
            with (state / "prepare.log").open("w") as stream:
                subprocess.run(command, env=env, check=True, stdout=stream, stderr=stream)
            for _ in range(120):
                subject = find_subject(adapter.executable, user.uid)
                if subject:
                    break
                time.sleep(0.5)
            if not subject:
                raise RuntimeError("GUI 未出现，请查看 " + str(log))
        if adapter.uses_polkit:
            if not GraphicalAgent(subject, ready_check=agent_check, title=adapter.title).run():
                raise RuntimeError("认证代理注册或运行失败；客户端不会因此被停止。")
        else:
            print("客户端已启动，无需 polkit 认证代理。")


def install_desktop(entry, config_path, config, user, adapter, apply):
    """生成独立菜单入口，不覆盖现有 SakuraCat 启动器。

    :param entry: 项目入口。
    :param config_path: 配置绝对路径。
    :param config: 部署配置。
    :param user: 宿主用户。
    :param adapter: 软件适配器。
    :param apply: 是否写入菜单。
    """
    target = user.home / ".local/share/applications" / ("vpn-workbench-" + config.adapter + ".desktop")
    wrapper = user.home / ".local/bin" / ("vpn-workbench-" + config.adapter)
    print("菜单：", target, "\n包装入口：", wrapper)
    if not apply:
        return
    for tool in ("desktop-file-validate", "update-desktop-database"):
        if not shutil.which(tool):
            raise RuntimeError("缺少 " + tool + "，请先安装 desktop-file-utils。")
    if target.exists() or wrapper.exists() or target.is_symlink() or wrapper.is_symlink():
        raise RuntimeError("目标入口已存在，请先备份并检查，不自动覆盖。")
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text("#!/bin/sh\n# VPN 工作台菜单薄入口；业务逻辑位于项目 src。\nexec " +
                       " ".join(shlex.quote(str(p)) for p in
                                ("/usr/bin/python3", entry, "--config", config_path, "launch")) + '\n')
    wrapper.chmod(0o755)
    # desktop 的 Exec 不使用 shell；home 路径不允许换行等控制字符。
    quoted = str(wrapper).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    target.write_text("[Desktop Entry]\nType=Application\nName=" + adapter.title +
                      "（VPN 工作台）\nExec=\"" + quoted + "\"\nIcon=network-workgroup\n"
                      "Terminal=false\nCategories=Network;\n")
    subprocess.run(["desktop-file-validate", str(target)], check=True)
    subprocess.run(["update-desktop-database", str(target.parent)], check=True)


def main():
    """解析 CLI，异常以非零状态呈现；桌面启动还显示错误对话框。

    :return: Unix 退出码。
    """
    entry = Path(__file__).resolve().parents[2] / "run.py"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=entry.parent / "configs/sakuracat.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    for name in ("provision", "desktop"):
        commands.add_parser(name).add_argument("--apply", action="store_true")
    commands.add_parser("launch")
    commands.add_parser("agent-check")
    prepare = commands.add_parser("_prepare", help=argparse.SUPPRESS)
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--session", required=True)
    prepare.add_argument("--log", required=True)
    args = parser.parse_args()
    try:
        os.umask(0o077)
        user = User.current()
        config_path = args.config.resolve()
        config = Config.load(config_path)
        adapter = ADAPTERS[config.adapter]()
        system = SYSTEMS[config.system]()
        resolver = SourceResolver(config, user, adapter)
        backend = DockerDistroboxBackend(config, user, adapter, system, resolver)
        if args.command == "_prepare":
            # 仍通过 resolver 检查来源，拒绝传入主目录之外的路径。
            from dataclasses import replace
            source = SourceResolver(replace(config, source=args.source), user, adapter).choose()
            backend.prepare_launch(source, json.loads(args.session), Path(args.log))
        else:
            if os.geteuid() == 0 or Path("/.dockerenv").exists() or os.environ.get("CONTAINER_ID"):
                raise RuntimeError("请在宿主以普通用户运行。")
            if args.command == "check":
                print(json.dumps({"adapter": config.adapter, "container": config.container,
                                  "source": str(resolver.choose()), "uid": user.uid,
                                  "subject": find_subject(adapter.executable, user.uid)}, ensure_ascii=False, indent=2))
            elif args.command == "provision":
                for command in backend.provision_plan():
                    print(shlex.join(command), flush=True)
                    if args.apply:
                        subprocess.run(command, check=True)
            elif args.command == "desktop":
                install_desktop(entry, config_path, config, user, adapter, args.apply)
            else:
                launch(config_path, config, user, adapter, resolver, entry, args.command == "agent-check")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        if args.command == "launch":
            try:
                from .auth import message
                message(str(exc))
            except Exception:
                pass
        return 1
