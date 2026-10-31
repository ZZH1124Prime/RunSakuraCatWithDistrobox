# 怎样扩展另一款 VPN 或另一发行版

先确定变动属于哪一层，不把所有参数继续堆进 cli.py。

## 新 VPN：增加 VpnAdapter 子类

在 adapters.py 增加子类（实现较多时拆到 adapters/ 包），实现：

- candidates(home)：发现本软件安装包。
- environment()：软件自己的运行变量。
- executable：真实主 ELF 的文件名，供 PID 识别。
- uses_polkit：只有实际使用 polkit 的软件才设为 True。
- rank(path)：命名不符合默认数字版本规则时覆盖。

然后登记到 ADAPTERS，增加 configs/软件名.json，并编写来源选择测试。不要给其他软件默认套上 SakuraCat 的软件绘制参数。

当前后端支持 AppImage 或已解包 AppRun。若新软件是 deb、tarball 或原生二进制，先扩展 SourceResolver/后端的安装契约；不能只换 executable 就宣布已经支持。

## 新容器系统：增加 SystemProfile 子类

SystemProfile 的 image 是镜像标签，install_commands 返回容器内部 argv。例如换发行版时不只是更改 ubuntu:26.04，GTK/ALSA 包名与包管理器也需要调整。登记 SYSTEMS 后在配置中选择。

现有软件依赖集合先放在 Ubuntu26Profile，若支持多个软件，应进一步把“软件要求的能力”映射到“发行版具体包名”，避免某软件不需要的依赖进入所有配置。没有第二个实际适配前不引入复杂依赖求解框架。

## 新后端或宿主平台

ContainerBackend 定义部署与启动边界。增加 Podman 时实现新的后端并让 CLI 按配置选择；当前 CLI 明确构造 Docker 后端，不会仅因系统装了 Podman 就自动切换。

当前使用 Linux /proc、systemd、polkit、X11/Wayland 集成。Windows/macOS 不只是新增包名，应有自己的进程查询、权限、显示和容器后端，并重新定义 TUN 服务宿主的路径。

## 验证顺序

来源解析 → 创建用户空间 → 普通用户身份 → GUI → 指定入口 HTTP 请求 → 目标应用 → 实际管理员请求 → 退出 → 再启动 → 冷启动。

至少覆盖版本比较、非法配置、多个同名主进程、认证取消、原生提示变化、旧 GUI 未退出时升级。新增代码保留模块 docstring，参数用 `:param name:`，返回值用 `:return:`。shell 只做薄入口，不放软件业务逻辑。
