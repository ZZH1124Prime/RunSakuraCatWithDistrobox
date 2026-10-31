"""配置层 —— 只保存部署选择，不保存账号、订阅或密码。

JSON 配置选择适配器、系统镜像和来源；用户身份从登录账户推导，
避免原脚本中 /home/zzh、UID 1000 等机器绑定。
"""
import json
import os
import pwd
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class User:
    """宿主用户上下文。

    :param home: 用户主目录。
    :param uid: 普通用户 UID。
    :param gid: 普通用户主组 GID。
    """
    home: Path
    uid: int
    gid: int

    @classmethod
    def current(cls):
        """解析普通用户或 pkexec 原始调用者。

        :return: 用户上下文；拒绝直接以 root 启动。
        """
        uid = int(os.environ.get("PKEXEC_UID", os.getuid()))
        if uid == 0:
            raise RuntimeError("请由普通用户运行入口；管理员准备由 pkexec 调用。")
        account = pwd.getpwuid(uid)
        return cls(Path(account.pw_dir), uid, account.pw_gid)


@dataclass(frozen=True)
class Config:
    """部署配置；新软件和新系统通过注册表扩展。

    :param adapter: 软件适配器键。
    :param container: Docker 容器名称。
    :param system: 用户空间配置键，不等于宿主系统。
    :param source: AppImage 或已解包 AppRun；为空时自动发现。
    :param distrobox: Distrobox 可执行文件路径。
    """
    adapter: str = "sakuracat"
    container: str = "sakuracat26"
    system: str = "ubuntu26"
    source: str = ""
    distrobox: str = "~/.local/bin/distrobox"

    @classmethod
    def load(cls, path):
        """从 JSON 读取配置并拒绝未知字段、非法容器名。

        :param path: 配置文件路径。
        :return: 已校验配置。
        """
        config = cls(**json.loads(Path(path).read_text()))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", config.container):
            raise ValueError("容器名称含非法字符。")
        return config

    def path(self, value, user):
        """按调用者主目录展开路径，root 准备时也不使用 /root。

        :param value: 绝对路径或以 ~/ 开头的路径。
        :param user: 宿主用户上下文。
        :return: 展开后的绝对路径。
        """
        path = user.home / value[2:] if value.startswith("~/") else Path(value)
        if not path.is_absolute():
            raise ValueError("配置路径必须为绝对路径或 ~/ 路径。")
        return path
