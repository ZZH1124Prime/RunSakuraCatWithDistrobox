"""Docker/Distrobox 后端 —— 管理环境，保持 GUI 为普通用户。

provision 是显式的终端部署；prepare_launch 仅由宿主 pkexec 调用。
容器不被自动删除，也不修改宿主系统代理与开机自启配置。
"""
import json
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class ContainerBackend(ABC):
    """容器管理接口。"""
    @abstractmethod
    def provision_plan(self):
        """返回部署命令计划。

        :return: argv 列表序列。
        """

    @abstractmethod
    def prepare_launch(self, source, session, log):
        """准备并以普通用户启动客户端。

        :param source: 安装来源。
        :param session: 显示与会话环境。
        :param log: 普通用户已创建的应用日志路径。
        """


class DockerDistroboxBackend(ContainerBackend):
    """Docker rootful + Distrobox 集成实现。

    :param config: 部署配置。
    :param user: 宿主普通用户。
    :param adapter: VPN 软件差异。
    :param system: 容器发行版差异。
    :param resolver: 安装来源解析器。
    """
    def __init__(self, config, user, adapter, system, resolver):
        """保存本实例所需的上下文。

        :param config: 部署配置。
        :param user: 宿主用户上下文。
        :param adapter: 软件适配器。
        :param system: 容器系统配置。
        :param resolver: 安装来源解析器。
        """
        self.config, self.user, self.adapter = config, user, adapter
        self.system, self.resolver = system, resolver

    def provision_plan(self):
        """构造创建、首次初始化和装库命令；不执行。

        :return: 可按顺序执行的 argv 列表。
        """
        dbx = str(self.config.path(self.config.distrobox, self.user))
        common = ["env", "DBX_CONTAINER_MANAGER=docker", dbx]
        return [
            ["sudo", "systemctl", "start", "docker"],
            [*common, "create", "--root", "--name", self.config.container,
             "--image", self.system.image],
            [*common, "enter", "--root", "--name", self.config.container,
             "--", "/bin/bash", "--noprofile", "--norc", "-c", "cat /etc/os-release; id"],
            *[["sudo", "docker", "exec", "-u", "0", self.config.container, *cmd]
              for cmd in self.system.install_commands()],
        ]

    def docker(self, *parts):
        """在管理员准备阶段调用 Docker，并返回文本。

        :param parts: Docker 子命令参数，不经过 shell 插值。
        :return: 标准输出。
        """
        return subprocess.run(["/usr/bin/docker", *map(str, parts)], check=True,
                              stdout=subprocess.PIPE, text=True).stdout

    def prepare_launch(self, source, session, log):
        """复查网络、修复总线入口、解包并启动普通用户 GUI。

        :param source: AppImage 或 AppRun。
        :param session: 用户桌面环境白名单。
        :param log: 用户日志文件。
        """
        if os.geteuid() != 0:
            raise RuntimeError("准备阶段必须通过 pkexec 执行。")
        subprocess.run(["/usr/bin/systemctl", "start", "docker"], check=True)
        details = json.loads(self.docker("inspect", self.config.container))[0]
        if details["HostConfig"]["NetworkMode"] != "host":
            raise RuntimeError("容器不是本案例要求的 host 网络，停止启动。")
        if not details["State"]["Running"]:
            self.docker("start", self.config.container)
        if self.adapter.uses_polkit:
            self.docker("exec", "-u", "0", self.config.container, "/bin/sh", "-ec", """
command -v pkexec >/dev/null
command -v setcap >/dev/null
if ! test -S /run/dbus/system_bus_socket; then
  test ! -e /run/dbus/system_bus_socket
  test ! -L /run/dbus/system_bus_socket
  test -S /run/host/run/dbus/system_bus_socket
  mkdir -p /run/dbus
  ln -s /run/host/run/dbus/system_bus_socket /run/dbus/system_bus_socket
fi
""")
        app_dir, extract = self.resolver.location(source)
        identity = str(self.user.uid) + ":" + str(self.user.gid)
        if extract:
            # 缓存应已由普通用户创建；root 不向任意用户路径写文件。
            if not extract.is_dir() or extract.stat().st_uid != self.user.uid:
                raise RuntimeError("缓存目录未由普通用户准备。")
            marker = extract / ".complete"
            if not marker.exists() or not (app_dir / "AppRun").is_file():
                self.docker("exec", "-u", identity, "-w", extract,
                            self.config.container, source, "--appimage-extract")
                if not (app_dir / "AppRun").is_file():
                    raise RuntimeError("解包后未找到 AppRun。")
                self.docker("exec", "-u", identity, self.config.container,
                            "/usr/bin/touch", marker)
        if not (app_dir / "AppRun").is_file():
            raise RuntimeError("AppRun 不存在。")
        if self.user.home.resolve() not in Path(log).resolve().parents:
            raise ValueError("日志必须位于用户目录。")
        command = ["exec", "-d", "-u", identity, "-w", str(app_dir)]
        env = dict(self.adapter.environment())
        env.update({key: session[key] for key in
                    ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY")
                    if session.get(key)})
        for key, value in env.items():
            command += ["-e", key + "=" + value]
        command += [self.config.container, "/bin/bash", "--noprofile", "--norc",
                    "-c", 'umask 077; exec ./AppRun >> "$1" 2>&1',
                    "vpn-workbench", str(log)]
        self.docker(*command)
