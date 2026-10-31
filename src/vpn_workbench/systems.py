"""容器用户空间配置 —— 镜像和软件包名称属于系统差异。

宿主仍需先安装 Docker/Distrobox；本模块只构造容器内的安装命令。
当前只声明已使用过的 Ubuntu 26.04 路线，不虚构其他系统支持。
"""
from abc import ABC, abstractmethod


class SystemProfile(ABC):
    """发行版安装策略。"""
    image = ""

    @abstractmethod
    def install_commands(self):
        """生成容器内部包管理命令。

        :return: argv 列表序列。
        """


class Ubuntu26Profile(SystemProfile):
    """Ubuntu 26.04 图形、代理配置与授权工具集合。"""
    image = "docker.io/library/ubuntu:26.04"
    packages = (
        "ca-certificates", "curl", "libgtk-3-0t64", "libayatana-appindicator3-1",
        "libsecret-1-0", "libnss3", "libasound2t64", "libgbm1", "libgl1",
        "libgles2", "libegl1", "libgl1-mesa-dri", "libglx-mesa0", "libegl-mesa0",
        "libcanberra-gtk3-module", "libglib2.0-bin", "gsettings-desktop-schemas",
        "mesa-utils", "pkexec", "libcap2-bin",
    )

    def install_commands(self):
        """构造更新索引和安装依赖两个阶段。

        :return: apt-get argv 列表序列。
        """
        return [["apt-get", "update"], ["apt-get", "install", "-y", *self.packages]]


SYSTEMS = {"ubuntu26": Ubuntu26Profile}
