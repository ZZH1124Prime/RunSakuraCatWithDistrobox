"""VPN 核心回归测试 —— 临时文件验证版本选择与配置边界，不启动 Docker。"""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from vpn_workbench.adapters import SakuraCatAdapter
from vpn_workbench.backend import DockerDistroboxBackend
from vpn_workbench.config import Config, User
from vpn_workbench.sources import SourceResolver
from vpn_workbench.systems import Ubuntu26Profile


class CoreTests(unittest.TestCase):
    """覆盖来源选择、纯检查与命令计划。"""
    def setUp(self):
        """建立临时用户目录。"""
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.user = User(self.home, 2345, 2346)
        (self.home / "Downloads").mkdir()
        self.adapter = SakuraCatAdapter()

    def tearDown(self):
        """删除临时文件。"""
        self.temp.cleanup()

    def test_cli_preview(self):
        """实际入口的预览命令应成功，不执行部署或迁移。"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / "run.py"), "provision"],
                                cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())

    def test_numeric_versions_and_no_side_effect(self):
        """1.10 高于 1.9，查询与定位不创建缓存、不改执行位。"""
        for version in ("1.9.0", "1.10.0"):
            (self.home / "Downloads" / ("com.sakuracat.app-" + version + ".AppImage")).write_bytes(version.encode())
        resolver = SourceResolver(Config(), self.user, self.adapter)
        chosen = resolver.choose()
        self.assertIn("1.10.0", chosen.name)
        original_mode = chosen.stat().st_mode
        resolver.location(chosen)
        self.assertEqual(chosen.stat().st_mode, original_mode)
        self.assertFalse((self.home / ".local").exists())

    def test_explicit_missing_does_not_fallback(self):
        """用户指定文件失效时不能偷偷改用另一个版本。"""
        resolver = SourceResolver(Config(source=str(self.home / "missing.AppImage")), self.user, self.adapter)
        with self.assertRaises(FileNotFoundError):
            resolver.choose()

    def test_symlink_escape_is_rejected(self):
        """安装来源软链接不能绕过用户目录边界。"""
        with tempfile.TemporaryDirectory() as outside:
            source = Path(outside) / "x.AppImage"
            source.write_bytes(b"example")
            link = self.home / "x.AppImage"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                SourceResolver(Config(source=str(link)), self.user, self.adapter).choose()

    def test_config_validation(self):
        """容器名不能包含 shell 或 Docker 选项分隔符。"""
        path = self.home / "config.json"
        path.write_text(json.dumps({"container": "a; rm"}))
        with self.assertRaises(ValueError):
            Config.load(path)

    def test_plan_uses_configured_identity_and_system(self):
        """部署计划使用配置路径，并包含增强模式需要的能力工具。"""
        config = Config(container="example")
        resolver = SourceResolver(config, self.user, self.adapter)
        backend = DockerDistroboxBackend(config, self.user, self.adapter, Ubuntu26Profile(), resolver)
        plan = backend.provision_plan()
        self.assertIn("example", plan[1])
        self.assertIn(str(self.home / ".local/bin/distrobox"), plan[1])
        self.assertIn("libcap2-bin", plan[-1])
        self.assertIn("pkexec", plan[-1])
        self.assertFalse(any("rm" in command for command in plan))


if __name__ == "__main__":
    unittest.main()
