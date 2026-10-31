"""安装来源解析 —— 自动发现与内容摘要缓存分离。

check 只读取文件；chmod、解包只发生于用户明确启动后。
SHA-256 用于缓存一致性，不代替厂商签名。
"""
import hashlib
from pathlib import Path


def digest(path):
    """计算大文件摘要。

    :param path: 文件路径。
    :return: SHA-256 十六进制摘要。
    """
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


class SourceResolver:
    """管理一个软件的安装来源。

    :param config: 部署配置。
    :param user: 宿主用户。
    :param adapter: VPN 软件适配器。
    """
    def __init__(self, config, user, adapter):
        """保存本实例所需的上下文。

        :param config: 部署配置。
        :param user: 宿主用户上下文。
        :param adapter: 软件适配器。
        """
        self.config, self.user, self.adapter = config, user, adapter

    def choose(self):
        """解析显式来源或选出最高版本候选。

        :return: 已存在的 AppImage 或 AppRun 路径。
        """
        if self.config.source:
            source = self.config.path(self.config.source, self.user)
        else:
            candidates = self.adapter.candidates(self.user.home)
            if not candidates:
                raise RuntimeError("未找到安装包，请设置配置中的 source。")
            source = max(candidates, key=self.adapter.rank)
        if source.is_dir():
            source = source / "AppRun"
        source = source.resolve(strict=True)
        if self.user.home.resolve() not in source.parents:
            raise ValueError("安装来源必须位于当前用户主目录内。")
        if source.name != "AppRun" and source.suffix != ".AppImage":
            raise ValueError("来源应为 AppImage 或 AppRun。")
        return source

    def location(self, source):
        """计算启动目录和可选解包目录，不创建文件。

        :param source: 已解析来源。
        :return: (启动目录, 解包目录或 None)。
        """
        if source.name == "AppRun":
            return source.parent, None
        cache = self.user.home / ".local/share/vpn-workbench" / self.adapter.key / digest(source)
        return cache / "squashfs-root", cache
