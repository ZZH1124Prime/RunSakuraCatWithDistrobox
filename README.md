# ZaH：Linux 应用运行与迁移工作台

ZaH 面向 Linux 桌面，计划统一管理 Linux 与 Windows 应用的安装材料、运行环境、多版本实例、宿主文件访问及备份迁移。产品显示名为 **ZaH**，程序和文件系统标识使用小写 `zah`。

> **当前状态：目录骨架与技术设计。** Electron / React / Go 新架构尚未实现，当前没有可运行的新版应用。仓库同时保留 SakuraCat 的历史 Python 原型；其代码、命令和验证记录不代表新版功能已完成。

## 目标技术栈

| 层次 | 规划方案 |
| --- | --- |
| 桌面 | Electron，负责窗口、系统对话框及 Go 连接 |
| 界面 | React + TypeScript + Vite，配合 Tailwind、shadcn/ui、React Router 与 TanStack Query |
| 核心 | Go，集中处理 CLI、任务、材料、运行后端和数据管理 |
| 存储 | SQLite，由 Go 访问，规划使用 `database/sql` + `modernc.org/sqlite` |
| Linux 应用后端 | Distrobox + Docker |
| Windows 应用后端 | Flatpak 版 Bottles + 经验证的 Wine runner，在 Linux 宿主运行 Windows 应用 |
| 分发 | Electron Forge 组装版本化安装目录，前端资源与 Go 程序随包提供 |

以上均为目标方案，兼容性与支持范围需后续实测。管理界面计划可在未准备应用后端时打开；具体应用运行时再按需准备后端。

## 目录与实现状态

```text
zah/
├── desktop/                  # Electron main、preload、本地资源协议（预留）
├── frontend/src/             # React 页面、组件与客户端（预留）
├── cmd/zah/                  # Go CLI / manager / worker 入口（预留）
├── internal/                 # Go 领域、业务、后端、任务和存储等模块（预留）
├── recipes/                  # 应用运行配方（预留）
├── schemas/                  # RPC、配方和迁移格式规范（预留）
├── scripts/                  # 构建、安装、验证脚本（预留）
├── release/                  # 打包、SBOM 与签名配置源码（预留）
├── run.py                    # 已有 Python 原型入口
├── configs/                  # 已有原型配置
├── src/vpn_workbench/         # 保留原名的历史 Python 原型
├── tests/                    # 已有原型测试，后续扩展新版验收
└── docs/                     # 技术规格、结构说明与原型资料
```

预留目录目前通过 `.gitkeep` 保留；占位文件不代表实现。新版尚无 `main.go`、TS/TSX 入口、`package.json`、`go.mod` 或 Forge/Vite 构建配置，因此暂不提供新版安装、启动和构建命令。依赖版本及入口确定后再补充清单，由实际依赖解析生成锁文件。

项目不要求固定的个人绝对路径。`src/vpn_workbench` 暂时保留历史包名以维持原型 imports，不代表产品名称。

## 文档导航

- [技术规格与实施路线](docs/TECHNICAL_ROADMAP.md)：目标行为、架构、数据、迁移及验收条件。
- [项目结构与开发入口](docs/PROJECT_STRUCTURE.md)：现有目录、模块职责与后续实施顺序。
- [历史 Python 原型扩展说明](docs/EXTENDING.md)。
- [历史原型验证记录](docs/VALIDATION.md)。
- [历史 SakuraCat 容器部署教程](docs/Skills_Ubuntu_SakuraCatContainer.md)：仅作原型部署参考。

后续先确定工具链并实现最小 Go 入口与 Electron 本地窗口，验证只读信息展示和通信，再逐步实现材料归档与运行后端。原型经验需转换为新版实现与验证，不能直接视为新版能力。

## 版本管理与本地文件

`.gitignore` 采用通用、保守规则，排除依赖目录、明确的构建输出、缓存、覆盖率报告、日志、临时文件、本地环境配置、安装材料与迁移包。项目内临时开发数据（包括 SQLite 数据库）约定放在 `.dev-data/`；正式运行数据按技术规格使用用户的 XDG 目录。

源码、`release/` 打包配置、`recipes/`、`schemas/`、公开配置样例与 `.gitkeep` 应保留。实际产生的 `package-lock.json` 等依赖锁文件和 `go.sum` 应纳入版本管理；不全局忽略 JSON 或数据库文件，以免隐藏配方和测试夹具。环境配置示例可命名为 `.env.example`、`.env.sample` 或 `.env.template`，内容只能包含占位值。

后续工具产生新的中间文件时，再按实际路径补充规则。忽略规则不会自动移除已跟踪的文件，提交前仍需检查内容。Git 仓库创建与上传由项目所有者自行管理；仓库地址和许可证尚待所有者确定。

## 历史 Python 原型参考

以下保留旧原型说明和命令，**不是新版 ZaH 的启动步骤**。部署、启动或创建菜单的操作可能准备容器、请求权限或影响客户端状态；阅读 README 不需要执行这些操作，也不应把现用代理作为开发测试对象。

## 当前原型说明

`src/vpn_workbench` 保留历史 Python 包名以维持原型 imports；它不是产品名，产品与工程名称均为 ZaH / zah。

把“软件差异”“容器用户空间”“宿主授权”拆开维护。当前提供 **SakuraCat + Docker/Distrobox + Ubuntu 26.04 容器**，宿主案例是 Ubuntu 20.04。其他软件、发行版和容器后端是扩展点，尚未实现或验证。

本项目从原机已经使用的启动器重构而来，保留 AppImage 自动发现、摘要缓存、软件绘制、普通用户 GUI、宿主 GTK + PTY 密码认证。没有复制账号、订阅、密码或原机运行状态。源项目不需要放在固定路径。

## 先看哪些文件

```text
zah/
├── run.py                       # 薄命令行入口
├── configs/
│   └── sakuracat.json            # 可公开的默认部署选择
├── src/vpn_workbench/
│   ├── adapters.py              # VpnAdapter → SakuraCatAdapter
│   ├── systems.py               # SystemProfile → Ubuntu26Profile
│   ├── backend.py               # ContainerBackend → DockerDistroboxBackend
│   ├── sources.py               # 来源发现、版本排序、摘要缓存
│   ├── processes.py             # PID + 启动时间，避免关联错误进程
│   ├── auth.py                  # 通用 GTK/pkttyagent 桌面认证
│   ├── config.py                # JSON 与当前用户身份
│   └── cli.py                   # 命令编排、文件锁和菜单安装
├── tests/test_core.py
└── docs/
    ├── EXTENDING.md
    ├── VALIDATION.md
    └── Skills_Ubuntu_SakuraCatContainer.md
```

模块开头解释职责与原理，函数使用 `:param:` / `:return:` docstring。结构参考 gnss_ai 的“薄入口 + 基类/子类 + 独立配置”方式，但保留 CLI 参数，便于比较不同部署环境。

## 1. 准备宿主

Python 3.8+，无需 pip 第三方依赖。桌面认证使用**宿主系统 Python** 的 GTK：

```bash
sudo apt-get install python3-gi gir1.2-gtk-3.0 policykit-1 desktop-file-utils
```

先按 [从零部署教程](docs/Skills_Ubuntu_SakuraCatContainer.md) 第四章安装 Docker 和 Distrobox，确认 Docker 守护进程可用、镜像可下载。不要在 APT 已损坏时直接继续安装；先恢复依赖状态。此项目不替你改软件源、Docker 组权限或宿主开机自启。

本机已有 sakuracat26 容器时，不重复执行下面的 provision。先阅读配置、检查来源，再按需使用 launch；它会启动现有容器。它不替换原来的 ~/.local/opt/sakuracat-launcher。

## 2. 建立自己的配置

在项目根目录：

```bash
cp configs/sakuracat.json configs/sakuracat.local.json
nano configs/sakuracat.local.json
python3 run.py --config configs/sakuracat.local.json check
```

- adapter：注册的软件实现，当前为 sakuracat。
- container：容器名；新实验使用新名字，不覆盖原容器。
- system：容器用户空间配置，当前为 ubuntu26。
- source：留空自动比较 Downloads 内官方命名 AppImage 和已有解包目录；也可填绝对路径或 ~/ 路径。
- distrobox：工具安装位置。

用户主目录、UID、GID 不写死。显式来源失效会报错，不悄悄改用其他版本。check 只检查来源与当前进程，不保证容器和网络都健康；它不解包、不修改执行权限。

## 3. 从新容器开始部署

```bash
python3 run.py --config configs/sakuracat.local.json provision
python3 run.py --config configs/sakuracat.local.json provision --apply
```

第一条只输出命令；第二条依次启动 Docker、创建容器、首次进入初始化、安装依赖。终端会出现正常 sudo 与 Distrobox 初始化提示，按提示完成。需要保持旧代理/下载网络可用。

这是**新建流程**，同名容器已存在时应停止检查，不自动删掉重建。网络、GUI、普通代理和增强模式的验证仍按配套教程完成；“依赖装完”不是完整验收。

## 4. 启动与认证

```bash
python3 run.py --config configs/sakuracat.local.json launch
```

启动分为两个权限阶段：

1. 宿主 pkexec 显示系统认证，准备已有容器、D-Bus 入口并以登录用户 UID 启动 GUI。
2. GUI 请求增强模式时，本项目为真实 PID 注册宿主 pkttyagent，以 GTK 密码框完成交互。

不会把整个 GUI 以 root 运行，不增加免密规则，不记录密码。已运行 GUI 会复用；原启动器或手工认证代理仍占用同一主体时，先退出多余认证代理，避免重复注册。这个锁仅防止本项目自己的重复启动，不能代替其他启动器的协调。

可单独验证注册：

```bash
python3 run.py --config configs/sakuracat.local.json agent-check
```

需要已有 GUI；只测试注册，不请求密码，也不证明增强模式真正可用。

## 5. 创建自己的菜单入口

```bash
python3 run.py --config configs/sakuracat.local.json desktop
python3 run.py --config configs/sakuracat.local.json desktop --apply
```

创建 ~/.local/bin/vpn-workbench-sakuracat 与对应 desktop。不会覆盖原机入口；已有同名文件时拒绝覆盖。菜单启动使用绝对项目路径，**移动项目后需检查并重新生成入口**。主配置可以编辑，菜单会在每次启动时重新读取。

安装本项目本身没有执行 desktop --apply，所有运行入口变更由你之后决定。

## 6. 数据、更新和退出

- 日志：~/.local/state/vpn-workbench/容器名/，prepare.log 与带时间的应用日志。
- 解包缓存：~/.local/share/vpn-workbench/适配器名/文件摘要/。
- 原客户端配置：仍由客户端保存在共享 HOME；本项目不迁移订阅与账户。
- 自动选择来源不等于自动更新正在运行的进程。退出旧 GUI 后再启动新版本。
- 停止网络必须在客户端先关增强模式、断开、退出；关闭认证代理不保证关闭核心。
- 新文件摘要用于区分缓存，不是厂商真实性验证。

## 开发与测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 run.py --help
```

扩展软件请看 [扩展说明](docs/EXTENDING.md)，测试范围看 [验证记录](docs/VALIDATION.md)。原经验文档按原样复制，内部指向其他经验库文章的相对链接需回原经验库阅读。

