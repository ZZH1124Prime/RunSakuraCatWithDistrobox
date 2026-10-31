# ZaH 项目结构与开发入口

当前阶段：目录骨架，尚未实现 Electron / React / Go 应用，也未安装依赖或验证构建。
产品行为以 [技术规格](TECHNICAL_ROADMAP.md) 为准；本文解释现在磁盘上有哪些目录，以及后续代码应放在哪里。

## 1. 项目根目录与现有内容

当前工程根目录是 `/home/zzh/zah`，已将原工程目录整体重命名以统一 ZaH 命名。
用户可在此目录自行建立 Git 仓库；工程内部文件结构保持不变，历史 Python 包 `src/vpn_workbench` 及其 imports 暂时保留，它不是产品名。

现有 `run.py`、`configs/`、`src/vpn_workbench/`、`tests/test_core.py` 和原有文档保留。
它们是 SakuraCat Python 原型及其历史经验，不是已完成的新版管理核心。
原部署程序、菜单、容器及用户数据不在本次改动范围内。

## 2. 当前目录树

下列新增叶目录各有一个空的 `.gitkeep`，使目录在用户提交文件后可以保留。
`.gitkeep` 只是普通占位文件，不是代码、依赖或 Git 初始化标记；添加实际文件后可删除。
下图省略这些占位文件，已有 Python 包内文件仍保留原状。

```text
zah/
├── README.md
├── .gitignore
├── desktop/
│   ├── main/
│   ├── preload/
│   └── protocol/
├── frontend/src/
│   ├── app/
│   ├── features/
│   ├── components/ui/
│   └── lib/
├── cmd/zah/
├── internal/
│   ├── bootstrap/
│   ├── domain/
│   ├── service/
│   ├── catalog/
│   ├── migration/
│   ├── transport/
│   ├── backend/
│   ├── recipe/
│   ├── host/
│   ├── jobs/
│   ├── process/
│   ├── infra/
│   └── storage/
├── recipes/
├── schemas/
├── scripts/
├── release/
├── run.py                         # 已有 Python 原型入口
├── configs/                       # 已有原型配置
├── src/vpn_workbench/              # 已有 Python 原型代码
├── tests/
│   └── test_core.py                # 已有原型测试
└── docs/
    ├── PROJECT_STRUCTURE.md
    ├── TECHNICAL_ROADMAP.md
    ├── EXTENDING.md                # 已有 Python 原型扩展说明
    ├── VALIDATION.md               # 已有 Python 原型验证记录
    └── Skills_Ubuntu_SakuraCatContainer.md
```

## 3. 桌面与界面

| 目录 | 后续职责 |
| --- | --- |
| `desktop/main` | Electron 窗口、系统文件选择、Go 连接和进程协调 |
| `desktop/preload` | 用 contextBridge 向界面提供有限、类型明确的操作 |
| `desktop/protocol` | 提供随包的 `zah://app/` 静态资源，检查资源路径 |
| `frontend/src/app` | React 入口、布局、路由和查询状态组装 |
| `frontend/src/features` | 应用库、添加应用、环境、任务和迁移界面；按实际功能逐步细分 |
| `frontend/src/components/ui` | 按需加入基础界面组件，不预先复制整个组件库 |
| `frontend/src/lib` | 界面使用的类型化客户端和少量通用辅助函数 |

Electron 的 main、renderer 和 preload 有不同职责。[官方进程模型](https://www.electronjs.org/docs/latest/tutorial/process-model)
preload 只暴露具体方法，不透传任意 IPC、shell 或文件访问；main 仍需校验来源和参数。[上下文隔离](https://www.electronjs.org/docs/latest/tutorial/context-isolation)、[IPC](https://www.electronjs.org/docs/latest/tutorial/ipc)

React 官方提供基于 Vite 等工具从零构建应用的路径；ZaH 已选择 React + TypeScript + Vite，后续固定版本再配置，不在此阶段执行脚手架安装器。[React 官方说明](https://react.dev/learn/build-a-react-app-from-scratch)

## 4. Go 核心

`cmd/zah` 预留 CLI / manager / worker 的薄入口，尚未创建 `main.go`。
`internal` 放项目内部实现。Go 官方说明了 `cmd` 约定与 `internal` 导入边界；下面的细分是 ZaH 的设计，并非 Go 强制的模板。[Go 模块布局](https://go.dev/doc/modules/layout)

| 目录 | 后续职责 |
| --- | --- |
| `internal/bootstrap` | 组装组件、manager 单实例和启动准备 |
| `internal/domain` | 应用、版本、实例、状态和错误等领域定义 |
| `internal/service` | 组织业务步骤，不承担窗口绘制 |
| `internal/catalog` | 安装材料归档、摘要、追溯和资源引用 |
| `internal/migration` | 导出清单、归档、导入和目标重绑定 |
| `internal/transport` | Unix socket、RPC 分帧、握手和事件续读 |
| `internal/backend` | 运行环境接口及 Distrobox / Bottles 实现 |
| `internal/recipe` | 声明式配方解析和必要的软件专用适配 |
| `internal/host` | 宿主能力探测、目录及桌面集成 |
| `internal/jobs` | 任务状态、执行、取消与故障恢复 |
| `internal/process` | 子进程参数、环境、超时与进程身份 |
| `internal/infra` | 路径、锁与授权等基础设施 |
| `internal/storage` | SQLite 连接、仓储与数据库迁移 |

领域定义不依赖 Electron 或具体后端，业务逻辑集中在 Go。未来 Go 单元测试放在对应包旁；跨模块验收放根目录 `tests/`。
只有开始某项功能时才添加对应源码和测试，不用返回假成功的空实现填满目录。

## 5. 规范、配方和交付

| 目录 | 后续职责 |
| --- | --- |
| `recipes` | 可分享的应用运行配方，不存账号、订阅或私有安装包 |
| `schemas` | RPC、配方和迁移格式的版本化规范；后续生成 Go / TS 类型 |
| `scripts` | 实际需要的构建、安装和验证脚本；当前没有可执行脚本 |
| `release` | Forge 打包、SBOM 和签名配置；私钥不进仓库 |
| `tests` | 保留现有原型测试，后续按需增加契约、集成与 Electron 验收 |
| `docs` | 技术规格、结构解释与后续真实兼容性结果 |

预定调用链为：React → preload → Electron IPC → main → Go Unix socket。
CLI 与桌面共用 Go 业务能力，SQLite 由 Go 访问；不为产品另外启动 TCP 服务。
这些通信与存储机制尚未实现，目录存在不表示能力可用。

## 6. 为什么现在没有依赖清单和启动命令

- `go.mod`：待仓库地址和 Go 版本确定后创建，module 路径不猜测账号。
- `package.json`：待 Electron / Forge / React / Vite 的版本和构建入口确定后创建。
- `go.sum`、`package-lock.json`：由实际依赖解析生成，不手写虚构锁文件；产生后应纳入版本管理。
- `LICENSE`：许可证由项目所有者选择；第三方声明和 SBOM 随真实依赖补齐。
- `main.go`、TS/TSX 入口、HTML、Forge/Vite 配置：随第一轮教学实现添加，本阶段不提供空应用。

因此现在没有新版 `npm start` 或 `go run` 操作。README 后半部分的 Python 命令仍只对应旧原型。
原型的启动或部署可能准备容器、申请权限并影响客户端状态，不能当作新版的无副作用演示。

## 7. 下一步

由用户在当前项目根目录自行创建 Git 仓库并上传；本次没有执行任何 Git 初始化、提交、远端设置或推送。
`.gitignore` 保留旧规则，并加入依赖、构建产物、本地开发数据与迁移归档的排除规则；它不能替代提交前查看文件清单。

用户提供仓库地址后，按小步教学确定工具链并建立最小 Go 入口和 Electron 本地窗口。
先验证只读信息展示和通信，再实现材料归档，最后接入真实运行后端。
不使用正在承担联网的 SakuraCat 作为开发测试对象；需要影响宿主代理、网络或 Docker 服务的操作，必须另行说明影响并获得具体授权。
