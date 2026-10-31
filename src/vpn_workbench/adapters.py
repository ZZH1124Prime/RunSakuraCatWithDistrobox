"""VPN 适配层 —— 基类定义差异，子类不承担 Docker 或密码交互。

增加软件时实现发现规则、主进程名和运行环境，再登记 ADAPTERS。
网络账号与订阅由客户端管理，不进入本项目配置。
"""
from abc import ABC, abstractmethod
import re


class VpnAdapter(ABC):
    """VPN 软件扩展接口。"""
    key = ""
    title = ""
    executable = ""
    uses_polkit = False

    @abstractmethod
    def candidates(self, home):
        """返回可用安装来源。

        :param home: 宿主用户目录。
        :return: 来源路径列表。
        """

    @abstractmethod
    def environment(self):
        """返回应用需要的环境变量。

        :return: 字符串键值字典。
        """

    def rank(self, path):
        """按数字版本排序，不把 1.10 排在 1.9 前面。

        :param path: 候选来源。
        :return: 数字版本及修改时间排序键。
        """
        match = re.search(r"(\d+(?:\.\d+)+)", str(path))
        return (tuple(map(int, match.group(1).split("."))) if match else (0,),
                path.stat().st_mtime)


class SakuraCatAdapter(VpnAdapter):
    """SakuraCat AppImage —— 复用已验证的软件绘制与 polkit 路径。"""
    key = "sakuracat"
    title = "SakuraCat"
    executable = "com.sakuracat.app"
    uses_polkit = True

    def candidates(self, home):
        """寻找官方命名 AppImage 与已有解包目录。

        :param home: 宿主用户目录。
        :return: 现有普通文件列表。
        """
        paths = list((home / "Downloads").glob("com.sakuracat.app*.AppImage"))
        paths += list((home / ".local/opt").glob("sakuracat*/squashfs-root/AppRun"))
        return [path for path in paths if path.is_file()]

    def environment(self):
        """返回本案例图形兼容变量。

        :return: 软件渲染和合法 shell 配置。
        """
        return {"SHELL": "/bin/bash", "LIBGL_ALWAYS_SOFTWARE": "true",
                "GALLIUM_DRIVER": "llvmpipe", "__GLX_VENDOR_LIBRARY_NAME": "mesa",
                "GDK_GL": "software-draw", "DBUS_SYSTEM_BUS_ADDRESS": ""}


ADAPTERS = {"sakuracat": SakuraCatAdapter}
