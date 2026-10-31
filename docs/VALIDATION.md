# 验证记录与原实现对应

整理日期：2026-10-31。运行环境 Python 3.8.10。

## 已完成

- 6 项自动化测试：数字版本排序、查询无缓存副作用、显式来源失效、软链接路径越界、配置与依赖命令计划、真实 CLI 预览。
- 全部 Python 文件语法检查、CLI --help。
- 原启动器中的 GTK + PTY 认证提取为 auth.py，并加上模块与参数说明。
- 用户身份由当前账户推导；取消写死 UID 1000 与 /home/zzh。
- 新入口命名与现有入口隔开，本次没有安装菜单、启动 VPN 或改容器。

## 尚未重新执行

此次重构没有在真实桌面执行管理员密码流程、重建容器或做整机重启。
原代码的历史成功不等于重构版已经完成集成测试。部署后按 README 和经验文档逐项验收。

## 原代码到新模块

- 原 source_path/launch_location → adapters.py + sources.py。
- 原 app_subject → processes.py。
- 原 prepare → backend.py。
- 原 GraphicalAgent → auth.py。
- 原 main/start-sakuracat.sh → cli.py + run.py。

“选择安装包”暂以配置中的 source 代替原文件选择对话框；自动发现仍保留。
没有把原机图标、设置、订阅或缓存复制进项目，也没有创建开机自启。

## 与经验文档的关系

经验文档保留历史排障与原机验证记录；本项目 README 是新代码的实际操作入口。
历史文档中的 sakuracat-launcher 文件名不等于新项目生成的文件名。
