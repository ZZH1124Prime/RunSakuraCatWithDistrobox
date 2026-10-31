# Skills - Ubuntu - SakuraCatContainer

## Ubuntu 20.04 运行新版 SakuraCat：glibc、容器、图形界面、代理与管理员认证

适用于：

- 原系统有 ROS、驱动等既有环境，不方便整体升级，但新版 GUI 软件需要更新的运行库。
- AppImage 报 GLIBC 版本错误，或者进入容器后仍缺图形库、窗口崩溃。
- 代理能更新订阅，宿主应用却不能联网；增强模式始终授权失败。
- 希望做成按需点击、没有常驻终端、仍保留密码认证的启动入口。

本文整理自「解释共享对话中的进展与原理」，记录的是 2026-10-30 的排障与部署。整理日期：2026-10-31。SakuraCat 1.4.5、容器名 `sakuracat26` 和端口 `12450` 是本例实际值，其他场景需要替换。

**最终方案：用 Docker + Distrobox 提供新版用户空间，补齐图形库并使用软件渲染；然后分别接通宿主代理与管理员认证。普通代理、增强模式已有成功验证；静默启动器已部署并做过注册等检查，没有实际重启电脑做完整冷启动测试。**

配套阅读：[.deb 依赖不满足但程序能运行：独立版迁移与 APT 恢复](./Skills_APT_DebDependencyStandalone.md)、[代理影响排查](./Skills_APT_Proxy.md)。

---

## 阅读前：命令里最常见的符号

- `~` 和 `$HOME` 通常表示当前用户主目录；本例是 `/home/zzh`。`./AppRun` 表示运行当前目录里的文件，不能随便换一个目录执行。
- `sudo` 申请管理员身份；root 是管理员用户，UID 0 是它的数字身份。普通用户的 UID 在本例为 1000，其他机器未必相同。
- PID 是运行中进程的编号，像临时工号，退出后可能被另一进程复用；因此认证脚本还核对启动时间。
- `.so` 是 Linux 共享库文件，类似供多个程序调用的公共工具箱。`.sh` 是 shell 脚本，`.py` 是 Python 脚本。
- Shell 是解释命令的程序，本例使用 Bash。命令提示符不是命令本身，复制时不用输入 `zzh@Z1:~$` 或 `bash-5.3$`。
- 返回码 0 通常代表命令成功，非 0 表示失败或特殊状态；具体含义要结合程序，不能把所有 127 都解释成同一故障。

建议第一次按顺序阅读：第一章定位启动障碍，第二章比较路线并解释容器，第三章连接容器与宿主的分工，第四至七章依次验证环境、窗口、网络和授权，第八至十章解释运行、日常入口和恢复。已有环境时可从第四章检查，日常操作看第九章，遇到网络问题看第六、七章。首次部署按下面的操作路线执行；诊断分支用于解释原因和处理失败。

---

### 从零照做的路线与终点

先阅读第一至三章理解选择，再按下面顺序执行，不需要重演每一次失败尝试：

1. 第四章第 0 步安装 Docker、Distrobox 并拉取镜像；第 1～5 步创建容器、确认用户空间、安装依赖、解包应用。
2. 第五章使用已成功的参数打开窗口。第四章已集中补库时，不必故意卸载库来复现缺库错误。
3. 第六章登录服务商账号或导入自己的订阅，选择节点，切换旧代理，再验证宿主请求。
4. 需要增强模式时，按第七章检查授权链并为真实 GUI 注册宿主认证代理；已经满足的条件只检查，不重复修改。
5. 第九章第 0 节创建基础菜单，完成退出、再次打开和重启后的验收。后面的静默启动器属于额外定制记录。

基础路线的完成标准是：从用户菜单打开客户端、普通代理请求成功、需要时能通过密码授权启用增强模式、目标应用实际联网，并能正常退出。无终端图形认证是另一项封装工作，不能把缺少的自定义文件当作读者已经拥有。

每个命令块都标明执行环境；发生错误时停在当前步骤，先读对应解释，不继续执行后续修改。本次补写验证了示例语法与部分文件操作逻辑，没有在空白电脑上重新部署整套环境。

---

## 一、为什么下载完整的软件仍然不能运行

### 从报错开始：为什么首先怀疑运行环境

刚开始只知道“软件打不开”，这个现象本身无法区分下载损坏、没有执行权限、缺库或图形故障。真正把范围缩小的是报错里的具体内容：系统已经执行到了 AppImage 内部，并指出某些组件需要 GLIBC_2.32～GLIBC_2.35。

为什么这比“打不开”更有用？如果文件根本不能执行，通常还到不了检查这些库接口的阶段；现在错误已经说出需要哪个版本，就说明首先应该比较“程序要求什么”和“当前系统提供什么”。因此下一步运行 ldd --version，而不是先重装软件。看到系统只有 2.31，才形成“已暴露出的阻碍是基础库接口不足”这个判断。

这里没有证明下载内容绝对完好，也没有证明后面没有其他问题。只是已经找到了一个足以阻止启动、且有直接证据的原因。先解决它，才能观察下一层。

### 1. 主程序、运行库、内核分别是什么

把软件运行想成开一家餐厅：

- **主程序**是厨师，决定做什么。
- **运行库**是厨师使用的工具，例如内存分配、字符串处理、线程和窗口绘制。
- **内核**负责底层资源管理，例如 CPU、内存、文件、网卡和设备。

```text
SakuraCat 主程序和插件
          ↓ 调用函数
glibc、GTK、Mesa 等运行库
          ↓ 系统调用与驱动接口
宿主 Linux 内核、显卡、网卡
```

`glibc` 是 GNU C Library，很多 Linux 程序直接或间接依赖它。GTK 负责一部分桌面窗口机制；Mesa 提供图形接口实现和驱动。它们各管一层，补好 glibc 不代表图形和网络也正常。

### 2. GLIBC_2.35 not found 究竟在说什么

宿主是 Ubuntu 20.04.6，glibc 为 2.31。SakuraCat 包中的不同组件提出了更新的接口要求：

- 主程序需要 `GLIBC_2.34`。
- 托盘插件涉及 `GLIBC_2.32`、`GLIBC_2.34`。
- 附带的 C/C++ 运行库也需要新版接口，其中暴露出 `GLIBC_2.35` 要求。

像厨师需要工具箱第 35 代新增的工具，而你只有第 31 代工具箱。文件下载完整，也不会凭空补出新工具。

`GLIBC_2.35` 是**符号版本标记**，不是需要单独下载的同名文件。动态加载器检查所需接口，发现当前库提供不了，就拒绝继续。从已出现的错误看，整个软件包至少需要 glibc 2.35 相关接口；不能据此保证达到这个门槛后所有功能都兼容。

### 3. 为什么 AppImage 也会这样

AppImage 像装着程序和许多工具的旅行箱，仍然可能借用目的地的基础设施。它并没有自动携带一套完整 Linux 系统。官方建议也要求在足够旧的系统上构建，并测试目标环境兼容性。[AppImage 官方说明](https://docs.appimage.org/reference/best-practices.html)

```bash
chmod +x application.AppImage
./application.AppImage --appimage-extract
./squashfs-root/AppRun
```

这三步依次是：允许执行、展开包内文件、启动展开的程序。解包可以绕过常见的 FUSE 挂载环节；**不会升级 glibc，也不会补齐所有图形库**。

本例错误已经来自 `/tmp/.mount_.../` 里的程序，说明已进入包内执行阶段，反复安装 FUSE 不会修好 GLIBC 版本。

本章确认了一个具体缺口：原来的库无法提供所需接口。但“缺新接口”并不指定唯一解决办法。下一章先比较可选路线，明确为什么本例愿意承担容器的配置工作。

---

## 二、确定需要新库后：比较路线，再理解为什么选容器

第一章只回答了“当前为什么启动不了”：程序需要的 glibc 接口比宿主提供的更新。它还没有回答“应该怎么修”。要选择路线，先明确成功标准：希望继续用官方客户端，保留原来的 ROS 等工作环境，并让代理服务这台电脑上的应用，而不只是打开一个测试窗口。

下面比较的是这些约束下的工程取舍。除后来实际走通的容器路径外，其他路线没有在本次对话中全部部署验证，不应把比较理解成性能测试排名。

### 1. 升级整个系统：统一解决环境老化，代价是迁移整套工作环境

升级后，应用可以直接使用较新的系统库，GUI、权限和桌面服务处于同一套发行版环境，通常比跨容器连接更直接。以后维护新版软件，也更容易沿用发行版正常更新路径。如果本来就计划迁移工作站、旧环境可以重建，这是一条值得优先评估的长期路线。

本例没有直接采用它，是因为电脑还承担 ROS 等已有工作。系统迁移需要核对已有软件、驱动、配置和项目能否继续使用，准备备份与恢复时间。这并不是断言“升级必然破坏 ROS”，而是当前没有完成这些迁移验证，不能为了一个客户端就把整台机器的变化当作小操作。

例如只有浏览器的新电脑和承载多年实验环境的工作站，即使遇到同一条 GLIBC 错误，也可能作出不同选择。前者更容易接受系统迁移，后者更重视把改动范围限制在一个应用。

### 2. 换兼容的版本或客户端：搭建成本低，但必须满足真正的使用需求

如果厂商提供仍受维护、兼容旧系统的构建，直接使用它可以省去容器和桌面集成。若应用可以从源码构建，也可能在旧环境重新编译；但前提是源码、依赖和构建条件都允许，不能只凭有一个安装包就假定能重编译。

代价可能是旧版本缺功能、修复或服务端兼容性；替代客户端也可能不支持订阅中的全部配置。本例用户反馈其他客户端的使用效果不符合预期，并希望继续使用官方客户端。因此没有把“换一个能启动的软件”当成任务完成。这是本人的需求和反馈，不是替代客户端普遍更差的结论。

### 3. 为单个应用手动准备新运行库：改动范围小，但需要管理整条依赖链

可以研究独立目录中的动态加载器和配套运行库，让特定程序使用它们。这种方式可能保留原系统，又不用完整容器用户空间。

难点是 glibc 并不是随便加一个 .so 就能替换的插件：加载器、C/C++ 库、插件和系统服务调用都可能有关联。需要核对哪些文件实际被加载，避免两套库混用。把宿主系统 libc 文件直接覆盖，更会影响其他依赖它的程序。

本例目标是稳定使用桌面代理，并没有现成、经过验证的独立运行库方案。因此没有优先承担这套手工维护成本。对了解动态加载、依赖很少的程序，这条路仍可能值得研究。

### 4. 虚拟机：完整的新系统，宿主代理集成需要额外设计

虚拟机通常启动自己的内核和用户空间，适合需要完整新系统或独立内核的情况；宿主原环境可以保留。代价是维护另一套系统及其磁盘、内存和桌面资源。

本例还要求代理服务宿主。即使虚拟机里的浏览器能联网，也不等于宿主流量已经交给它：还需配置网络可达性、代理入口或转发；虚拟机里的 TUN 默认作用于客体网络。它能解决运行环境问题，却会引入另一套网络设计，所以本例没有优先走这条路线。

### 5. 容器：提供新用户空间，同时承担桌面和授权集成工作

已有错误指向用户空间库，并没有证明必须换内核。容器因而可以尝试只替换应用看到的用户空间，保留宿主的旧环境。与虚拟机相比，它无需为此再启动一套独立内核。

代价也必须提前说明：新库只解决其中一层；GUI 怎样显示、代理端口怎样服务宿主、管理员认证怎样完成，都仍需验证。本例后来遇到的图形与授权问题，正是这一选择的集成成本，而不是“选了容器就不应该再有问题”。

因此本例选择容器，是接受这些局部集成工作，换取暂时不迁移整台工作站。若这部分维护成本超过收益，或者以后需要宿主内核没有的能力，就应该重新评估升级系统或虚拟机，而不是无限给容器打补丁。

### 6. 容器为什么能让同一电脑使用两套运行库

Ubuntu 不只包含内核，还包含 bash、apt、glibc、GTK 等**用户空间**。Linux 容器可以使用自己的用户空间，同时共享宿主内核。

```text
ROS → 宿主 glibc 2.31 ─────┐
                           ├→ 同一个宿主 Linux 内核
SakuraCat → 容器新版 glibc ─┘
```

像在同一栋楼里开两间配有不同工具的工作室：楼的基础设施相同，每间房的工具不同。容器内外都可能读取 `/lib/.../libc.so.6`，挂载命名空间让相同路径可以指向不同文件。

因此不需要替换宿主 glibc。ROS 继续使用旧环境，SakuraCat 使用容器里的新库。但如果缺的是宿主内核功能，更换容器用户空间仍可能无效。

### 7. 具体用什么工具管理：Docker 与 Distrobox

- **镜像 Image**：环境模板，如 `ubuntu:26.04`。
- **容器 Container**：模板创建的具体实例，可以安装软件并保留自己的可写层。
- **Docker**：管理镜像、容器、进程、网络和挂载的工具。
- **Distrobox**：在 Docker 等工具上补充用户、主目录、显示和桌面集成，方便人在另一发行版环境里使用软件。

例如 `ubuntu:26.04` 是模板，`sakuracat26` 是本例房间名；同一模板还能创建另一个实例。`docker start` 是打开已有房间，创建命令则是在建立实例。

Linux namespaces 控制进程能看到的文件、进程、网络等范围，cgroups 用来统计或限制资源；创建容器不等于自动设置了内存、CPU 上限。Distrobox 主动共享较多资源，重点是兼容和集成。[Distrobox 创建说明](https://distrobox.it/usage/distrobox-create/)

到这里已经选定候选路线，并知道镜像、容器和管理工具各是什么。下一章要把“一个新用户空间”具体放进这台电脑：哪些文件属于容器，哪些资源必须和宿主连接，最终要依次验证哪些能力。

---

## 三、把容器方案落到这台电脑：环境分工与验证顺序

第二章解释了容器能提供新库，但用户最终要的是“当前桌面上能操作、能替宿主联网的客户端”。从库兼容到这个目标，中间需要连接显示、文件、网络和授权。本章先画清这些关系，再进入第四章的实际创建过程；此处不预先把后来的错误当作已经完成的操作。

### 1. 容器拥有自己的库，但窗口仍显示在宿主桌面

容器里有自己的 /usr、/lib、包数据库和相关系统配置；应用进程主要从这套文件视图取运行库。宿主仍提供内核和实际设备。Distrobox 将图形显示等接口接入，让容器进程能把窗口显示到当前桌面，而不必启动另一套完整桌面。[Distrobox 官方介绍](https://distrobox.it/)

例如程序文件可以放在共享的用户目录，而加载到的 glibc 来自容器：文件存放位置、进程所在环境和窗口显示位置是三个不同问题。看见一个桌面窗口，不能据此判断进程用的是哪套库；这就是后面还要检查系统版本和实际命令环境的原因。

### 2. 代理还必须与宿主共享一条能到达的网络路径

如果程序只是图片编辑器，能读文件、显示窗口可能就接近完成；代理还要让宿主应用访问它的入口。本例采用 host 网络，相关进程共享宿主网络空间，宿主可访问其回环监听端口。具体如何确认和测试，放在第六章。

这不代表现在已经证明节点可用，也不代表所有应用都采用该代理。这里确定的只是要建立的连接关系。以后启用增强模式还涉及设备、路由和认证，因此也不能由“端口能连上”直接跳到“增强模式应该能用”。

### 3. 为什么这些共享也决定了容器会影响什么

到这里已经知道，我们主动需要共享主目录、显示接口和网络。于是自然产生另一个问题：在容器里做的操作，哪些会影响宿主？这不是插入一条无关的安全提醒，而是决定后续命令能在哪里执行、能否同时运行两个实例的依据。

例如在容器自己的系统目录安装 GTK，通常是在更新容器的包；修改共享的 ~/.config，却可能直接修改宿主用户配置。两份客户端访问同一配置会互相干扰；共享宿主网络时，修改路由也会影响宿主应用。

本例后续实际检查到 host 网络、Privileged=true，以及 apparmor=unconfined。host 是共享网络；privileged 是较宽的设备与能力配置；后者表示未使用常规的该容器 AppArmor 配置限制。它们是已经观察到的环境条件，不是要求所有读者为任何应用都照着开启的最小配置。

所以这里的容器主要隔开运行库环境，并不提供“所有操作都绝不会影响宿主”的保证。后面安装依赖时明确目标容器，运行 GUI 使用普通用户，切换代理前关闭旧实例，都是从这些共享关系推出来的操作安排。

### 4. 容器镜像版本为什么经历 22.04、24.04、26.04

最初选择 22.04，是它提供的 glibc 2.35 能满足已经暴露的版本要求。它适合验证“较新用户空间是否能越过启动门槛”，不是对所有图形和桌面集成问题的保证。

随后尝试 24.04，是为了对照更新的图形库等环境；初始化缓慢时，需要查包下载和安装日志，不能直接判为镜像坏了。后来按用户要求试用 26.04，实际读到 glibc 2.43，并在该环境继续完成后续排障。

这段历史不构成“26.04 比 22.04 一定稳定”的实验结论。下面复现采用最终工作的 26.04，是为了给出一条明确路径；其他版本只作为方案演进记录，不要求读者重复建三个容器。固定版本标签也比含义会变化的 latest 更便于日后解释环境。

### 5. 从创建环境到完成目标，要通过哪些检查

1. 第四章确认命令确实进入目标用户空间，并准备应用文件。
2. 第五章验证主程序能加载库、创建窗口；图形失败就停在这一层排查。
3. 第六章从宿主明确指定代理入口，验证真实请求，而不仅看 GUI 状态。
4. 第七章处理本例需要的增强模式，验证真实应用的权限请求。
5. 第八、九章根据运行和认证的分工，确定哪些进程需要保留，并封装日常入口。

这是一条逐步增加验证范围的路线。下一章先解决最基础的一关：建立并确认我们要使用的新用户空间。

---

## 四、开始实施：创建、确认容器并准备应用文件

### 为什么第一件事是确认命令在哪里运行

先前容器初始化报告成功，随后 apt 输出却出现 focal 和宿主原有的 ROS 软件源。focal 对应 20.04，与当时准备进入的 22.04 不符。这是一个矛盾：要么没有留在容器，要么环境或软件源配置有异常。

此时不应立刻换源，因为那会在“还不知道自己在哪里”的情况下改系统。先读 /etc/os-release、glibc 版本和命令实际位置；实际输出仍是宿主环境，才转向检查进入方式。改用不读取个人配置的 Bash 后，输出变成目标发行版，说明已经进入正确环境。它支持“启动配置可能参与了异常”，却没有证明具体是哪一行配置出错。

下面是重建流程，**不是每次打开软件都要做一遍**。已有同名容器时先检查，不要重复创建。没有安装过工具时，从第 0 步开始；已安装时检查通过后跳到第 1 步。

### 第 0 步：从未安装工具的宿主开始

这一节在 **Ubuntu 20.04 的桌面终端**执行，目标架构是 amd64/x86_64，有 sudo 权限。先准备可用网络和服务商提供的 Linux amd64 AppImage；安装包需要从服务商官方页面下载，登录或订阅凭据由你自己填写。文件名以下载结果为准，本文以 1.4.5 为例，不能把 ARM 包改名当作 amd64 包。

```bash
cat /etc/os-release
uname -m
id
df -h "$HOME" /var/lib
sudo apt-get check
command -v docker
```

预期架构是 x86_64，磁盘能容纳镜像、容器依赖与应用解包后的文件。apt-get check 应成功；若它被另一篇里的 chatgpt 坏依赖阻挡，先完成那篇的迁移与 APT 修复，再回来安装工具，不能跳过错误继续。已有 Docker 并能执行 sudo docker info 时，保留已有安装，不混装 docker.io 与 docker-ce。

**没有 Docker 时，使用宿主发行版提供的包：**

```bash
sudo apt-get update
apt-cache policy docker.io
sudo apt-get install docker.io ca-certificates curl desktop-file-utils policykit-1
sudo systemctl start docker
sudo docker version
sudo docker info
command -v pkttyagent
```

apt-cache 的 Candidate 应是具体版本而非 (none)；docker version 应同时显示 Client 和 Server。只有 Client 表示客户端安装了，但守护进程尚不可用；先看 sudo systemctl status docker 和 sudo journalctl -u docker -n 80，再继续。policykit-1 提供本例宿主的认证工具，desktop-file-utils 用于后面的菜单校验。

这里选择 Ubuntu 软件源中的 docker.io，避免给旧系统直接套用新版 Docker CE 仓库教程。若源已经不可用或没有候选版本，应先恢复与你发行版匹配的软件源；不要把 focal 改成 noble。当前 Docker CE 官方安装页的支持范围不包含 20.04，所以也不能把最新版安装命令写成在旧系统上必然成功。[Docker 安装与发行版要求](https://docs.docker.com/engine/install/ubuntu/)

**安装 Distrobox 到自己的用户目录：**

```bash
mkdir -p "$HOME/.local/bin" "$HOME/.cache/distrobox-install"
curl -fL https://raw.githubusercontent.com/89luca89/distrobox/main/install \
  -o "$HOME/.cache/distrobox-install/install"
less "$HOME/.cache/distrobox-install/install"
sh "$HOME/.cache/distrobox-install/install" --prefix "$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
"$HOME/.local/bin/distrobox" --version
```

less 用方向键翻页，按 q 退出。下载失败就停下，不执行残缺文件。这里按官方用户目录安装方法，先下载再执行；不需要 sudo。后文使用绝对路径，因此新终端没有刚才的 PATH 设置也能调用。记下实际安装的 Distrobox 版本，安装器会随上游更新，不能把它当作永久固定的版本。[Distrobox 安装说明](https://distrobox.it/#installation)

**先验证能下载最终使用的镜像：**

```bash
sudo docker pull docker.io/library/ubuntu:26.04
sudo docker image inspect docker.io/library/ubuntu:26.04 --format '{{json .RepoDigests}}'
```

看到下载完成且 inspect 返回镜像摘要，再进入创建步骤。网页能打开却 pull 超时，可能是 Docker 守护进程没采用桌面代理；它与当前终端是不同进程。先保留旧代理可用，再按下面分支处理，不要为了测试新代理提前断掉下载通道。

<details>
<summary>只有 Docker 拉取失败且需要 HTTP 代理时：给守护进程配置代理</summary>

以下示例假设旧代理的 HTTP 入口已验证为 127.0.0.1:7890；必须换成自己的实际入口。已有 Docker 任务时先安排可重启服务的时间。先用 sudo systemctl cat docker 检查既有配置，已有代理配置就修改原配置，不叠加互相冲突的文件。

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/sakuracat-download-proxy.conf
```

在新文件中写入：

```ini
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1"
```

nano 中 Ctrl+O、回车保存，Ctrl+X 退出。然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
sudo systemctl show --property=Environment docker
sudo docker pull docker.io/library/ubuntu:26.04
```

这只解决守护进程下载，不会自动给容器内 apt 配代理。以后退出旧代理前，删除本节新建的临时配置文件并 daemon-reload；在可中断 Docker 任务时重启服务使其生效。不要让未来下载一直依赖已关闭的 7890。[Docker 守护进程代理说明](https://docs.docker.com/engine/daemon/proxy/)

</details>

### 第 1 步：确认“宿主终端”

宿主终端就是尚未执行 distrobox enter 的普通终端。不能只凭提示符颜色判断。

```bash
cat /etc/os-release
ldd --version | head -n 1
command -v docker
command -v "$HOME/.local/bin/distrobox"
sudo docker ps -a
```

本例应为 Ubuntu 20.04、glibc 2.31。sudo 提示的密码是宿主登录密码。

### 第 2 步：保留下载网络，创建并进入

先保持现有代理，完成镜像和依赖准备，再切换新代理，避免下载到一半失去联网手段。在宿主执行：

```bash
DBX_CONTAINER_MANAGER=docker "$HOME/.local/bin/distrobox" create \
  --root --name sakuracat26 \
  --image docker.io/library/ubuntu:26.04

DBX_CONTAINER_MANAGER=docker "$HOME/.local/bin/distrobox" enter \
  --root --name sakuracat26 -- /bin/bash --noprofile --norc
```

- 命令前的 `DBX_CONTAINER_MANAGER=docker` 指定这次使用 Docker 后端。
- `--name` 是实例名，`--image` 是模板。
- `--noprofile --norc` 不读取个人 Bash 启动文件，减少共享启动配置干扰。本例这样进入后成功，但没有最终定位到哪条配置造成原来的异常。

首次进入会安装基础包。很慢时另开宿主终端：

```bash
sudo docker logs --tail 80 sakuracat26
```

不要在初始化安装还运行时并发执行另一条 apt 安装，也不要删除锁文件强行并发。

首次进入如果询问是否安装基础包，确认后等待；rootful 初始化若要求设置容器用户密码，按提示设置，它与宿主 sudo 密码的用途不同。不要使用跳过密码的特殊选项来绕过初始化。进入后执行第 3 步；看到目标系统版本和普通用户身份才算完成。

第 4 步要回到宿主：可以在当前容器 shell 输入 exit，或者另开一个明确的宿主终端。不要把下面的 docker exec 命令误当作必须在容器里面执行。

### 第 3 步：在容器检查实际环境

```bash
cat /etc/os-release
ldd --version | head -n 1
id
printenv CONTAINER_ID
type -a sudo apt
```

目标是 Ubuntu 26.04。若仍显示 20.04、glibc 2.31，先解决进入问题，不要把宿主 focal 软件源硬改成新代号。

`cat /etc/os-release` 看用户空间，`uname -r` 看内核。所以容器里显示“新 Ubuntu”加“宿主内核”是正常的。

### 第 4 步：从宿主以容器 root 安装依赖

前面已确认目标环境，才可以安装依赖。本例容器内 sudo 验证失败，但宿主可以通过 Docker 管理该容器，因此把安装任务交给容器管理接口执行，不必先改变容器用户密码。`--root` 选择 rootful 容器管理方式；`docker exec -u 0` 才明确指定这一次容器命令以 UID 0 执行。它们都不要求 GUI 长期以 root 运行。

以下是排障完成后整理的依赖清单，包含第五章定位到的图形库和第七章用到的授权工具。真实排障并非最初就一次猜出了全部包；重建时集中准备它们，是为了避免重复已知缺项。在**宿主终端**执行：

```bash
sudo docker exec -u 0 sakuracat26 apt-get update
sudo docker exec -u 0 sakuracat26 apt-get install -y \
  ca-certificates curl \
  libgtk-3-0t64 libayatana-appindicator3-1 libsecret-1-0 \
  libnss3 libasound2t64 libgbm1 libgl1 libgles2 libegl1 \
  libgl1-mesa-dri libglx-mesa0 libegl-mesa0 \
  libcanberra-gtk3-module libglib2.0-bin \
  gsettings-desktop-schemas mesa-utils pkexec libcap2-bin
```

`docker exec` 在已有容器里执行命令，`-u 0` 以容器 root 执行。软件安装在容器里，不是在宿主替换这些库。

GTK、托盘、声音库负责桌面功能；GLES、EGL、Mesa 负责图形；`libglib2.0-bin` 提供 gsettings；pkexec 是授权入口。包名对应本例 26.04，22.04 的 GTK/ALSA 包名不同，不能跨版本照搬。

安装结束后，在宿主检查容器内的工具和库：

```bash
sudo docker exec -u 0 sakuracat26 /bin/sh -ec '
  command -v gsettings
  command -v glxinfo
  command -v pkexec
  command -v setcap
  command -v getcap
  ldconfig -p | grep libGLESv2.so.2
'
```

应看到命令路径和 libGLESv2.so.2 的解析路径。libcap2-bin 提供 setcap/getcap；仅装 pkexec 不会自动补出所有被授权执行的工具。若 apt 报 Unable to locate package，先确认容器是 26.04 且 update 成功；若是下载超时，先修复容器下载路径，不在宿主安装同名库代替。

若旧代理只有显式 HTTP 入口、容器 apt 无法直接下载，可在已确认 host 网络的前提下，给这次 apt 命令指定代理，例如：

```bash
sudo docker exec -u 0 sakuracat26 apt-get \
  -o Acquire::http::Proxy=http://127.0.0.1:7890 \
  -o Acquire::https::Proxy=http://127.0.0.1:7890 update
```

安装时也要把相同的两个 -o 参数放在 apt-get 与 install 之间，端口替换为已验证的旧入口。这是一次命令的配置，不会永久把新容器绑在旧代理上。首次 Distrobox 初始化下载失败时也先查看日志与旧代理状态，恢复网络后重新 enter，让初始化继续；不要同时运行另一个 apt。

### 第 5 步：在容器解包

在宿主先用文件管理器确认 AppImage 已下载到 Downloads，下面文件名与真实名字逐字一致；若版本不同，同时修改文件名和解包目录。然后重新进入容器：

```bash
DBX_CONTAINER_MANAGER=docker "$HOME/.local/bin/distrobox" enter \
  --root --name sakuracat26 -- /bin/bash --noprofile --norc
cat /etc/os-release
id -u
ls -lh "$HOME/Downloads/com.sakuracat.app-1.4.5-linux-amd64.AppImage"
```

id -u 应是普通用户编号而不是 0。文件找不到就核对下载位置，不继续执行。下面命令留在这个容器终端里运行：



```bash
mkdir -p "$HOME/.local/opt/sakuracat-1.4.5"
cd "$HOME/.local/opt/sakuracat-1.4.5"
chmod u+x "$HOME/Downloads/com.sakuracat.app-1.4.5-linux-amd64.AppImage"
"$HOME/Downloads/com.sakuracat.app-1.4.5-linux-amd64.AppImage" \
  --appimage-extract
test -x ./squashfs-root/AppRun
```

`$HOME` 是用户主目录，双引号避免路径被空格拆开。行末反斜杠表示下一行继续，后面不要再加空格。test 成功通常无输出，紧接着 `echo $?` 为 0 表示成功。

用独立版本目录，避免新版覆盖旧版。共享主目录也意味着新旧容器可能访问同一份 SakuraCat 数据，不要同时运行两个客户端。

第四章完成后，只能确认“目标用户空间和应用文件已经准备好”。还不能说 GUI 已经可用。下一章开始真正执行应用：如果加载器仍报 GLIBC 错误，先回查是否在正确环境；如果错误变成缺图形库或窗口创建失败，再沿新证据处理图形层。

---

## 五、图形界面：先补库，再定位渲染路径

### 如何从一长串日志里决定下一步

这里不是一次性知道所有图形问题。第一次日志明确说 libGLESv2.so.2 无法打开，随后进程终止，所以先补提供该文件的库。补好后，这条错误消失，出现 GLX BadValue，说明程序比之前走得更远，但在图形路径遇到新障碍。

为什么接着测试 glxinfo？它比整个客户端简单，只测试基础图形上下文。如果它也失败，优先查容器图形环境；如果它成功而 GUI 失败，就把注意力放到应用实际使用的窗口路径。本例软件渲染下 glxinfo 成功，GUI 仍失败，因此又尝试 GTK 的绘制参数，随后窗口打开。

这条证据链支持“这些参数在本机绕过了触发故障的图形路径”。它没有精确证明是某一型号显卡或某一个驱动版本存在 bug；没有相应对照测试时，不应把兼容办法写成已查明的底层根因。

### 1. 缺库和图形错误不是同一种问题

最初的致命错误是：

```text
Couldn't open libGLESv2.so.2
Aborted (core dumped)
```

补 libgles2 后这条消失；接着出现 GLX 的 BadValue，说明执行已经走到窗口/图形上下文创建。继续重装同一个库不能自动解决另一层故障。

`Failed to load module canberra-gtk-module` 是另一条提示。不要根据日志出现顺序就认定第一条警告是崩溃根因。

### 2. 用最小工具验证

在容器执行：

```bash
LIBGL_ALWAYS_SOFTWARE=true \
GALLIUM_DRIVER=llvmpipe \
__GLX_VENDOR_LIBRARY_NAME=mesa \
glxinfo -B
```

期望输出 `OpenGL renderer string: llvmpipe ...`，没有 X 错误。llvmpipe 用 CPU 做图形计算，可绕过部分显卡驱动组合问题。[Mesa 环境变量说明](https://docs.mesa3d.org/envvars.html)

举例：显卡是专门的画图工，CPU 软件渲染是让通用工临时代画，可能更费 CPU，但能帮助判断问题是否来自硬件图形路径。它改变窗口绘制方式，不会改变代理协议。

### 3. 使用实际成功的启动参数

```bash
export SHELL=/bin/bash
unset DBUS_SYSTEM_BUS_ADDRESS
cd "$HOME/.local/opt/sakuracat-1.4.5"

LIBGL_ALWAYS_SOFTWARE=true \
GALLIUM_DRIVER=llvmpipe \
__GLX_VENDOR_LIBRARY_NAME=mesa \
GDK_GL=software-draw \
./squashfs-root/AppRun
```

前三个图形变量选择 Mesa 软件路径；GDK_GL 调整 GTK 窗口表面的绘制路径。本例 glxinfo 已成功，但应用仍崩溃，加入 `GDK_GL=software-draw` 后才打开窗口。**小工具成功不能代替真实应用测试。** 该 GTK 参数是本例验证过的兼容办法，不能保证适用于所有 GTK 版本。

命令前 `变量=值` 只影响这次启动及子进程。export 则影响当前 shell 后续启动的进程。已运行的 GUI 不会自动获得新变量，需要退出再启动。不要给整个 GUI 加 sudo。

窗口出现是本章的验收点，它说明这次启动越过了已遇到的图形障碍。但窗口只负责操作界面，代理核心和宿主应用之间是否连通仍未证明。下一章把测试位置移到宿主，用真实网络请求验证这一点。

---

## 六、普通代理：从宿主明确验证入口

### 为什么“订阅成功、浏览器能用、另一个应用不能用”要分别看

订阅成功只说明客户端访问服务商接口成功；它可能根本没通过所选代理节点。GUI 显示连接也只是客户端状态。要判断宿主是否真的能使用代理，必须从宿主主动发一次经过该入口的请求。

因此先从日志找到 inbound=12450，再检查 host 网络，最后用 curl 明确指定这个端口。这样测试时就不用猜“curl 是否读取了系统代理”。返回 204 后，至少排除了“该时刻宿主完全无法访问容器代理”的说法。

接下来浏览器可用而 Codex 不可用，就说明不能再把所有故障归结为容器没联网。剩余候选包括应用不遵守系统代理、后台进程使用另一套网络配置、目标站点或节点链路异常。仅凭这几个现象还不能选定其中一个，更不能直接归罪于另一篇里的缺库。下一步才是检查应用使用代理的方式和增强模式。

窗口打开后，先按客户端提示登录服务商账号，或在订阅入口导入自己获得的订阅；刷新后应出现节点列表。选择一个节点，先保持增强模式关闭，按第 3 节退出旧代理后点击连接，再按第 4 节测试。账号和订阅不能使用本文示例替代；订阅更新失败应先确认服务商入口和当前下载网络，节点列表为空时不要跳到授权排障。界面名称可能随版本变化，以当前客户端标识为准。

### 1. IP 地址与端口可以怎么理解

IP 地址像楼地址，端口像楼里的窗口编号。`127.0.0.1` 是本机回环地址，不是公网出口 IP。

本例日志：

```text
inbound=12450, clashApi=12440, tun=false
```

12450 是接收代理请求的入口；12440 是控制核心的管理接口，不能拿来填浏览器代理；tun=false 是该记录对应的普通模式状态。随机连接端口也不一定是监听端口。换版本后以新日志为准，不沿用旧软件的 7890。

### 2. 容器里的端口为什么能服务宿主

普通 bridge 容器有独立网络空间，容器本机与宿主本机通常不同。**本例检查为 host 模式**，共享网络命名空间，所以宿主能访问容器程序的回环监听端口，不需另加 -p 映射。[Docker host 网络说明](https://docs.docker.com/engine/network/drivers/host/)

在宿主检查：

```bash
sudo docker inspect --format '{{.HostConfig.NetworkMode}}' sakuracat26
ss -lntp
```

应显示 host，并能找到实际入口监听。共享网络不等于自动获得创建网卡或改路由的权限。

### 3. 切换前先避免两套代理互相干扰

记下旧软件开关和端口。准备完成后，在旧软件中关闭 TUN、关闭系统代理并真正退出；仅关闭窗口可能还留在托盘。然后 SakuraCat 连接固定节点，先不开增强模式。

否则两套软件可能抢同一端口、覆盖系统代理，旧 TUN 还可能替新代理的测试提供网络，造成误判。

**怎样确认旧 TUN 已退出？** 本例普通路由表的默认网关仍是局域网路由器，但同时存在 Mihomo 虚拟网卡。两条信息并不矛盾：系统可能先按策略选择其他路由表。因此，“默认网关没变”不足以排除 TUN，“有虚拟网卡”也不足以证明它正在接管目标请求。

先看旧客户端的 TUN 开关，再结合设备状态、`ip rule show` 与 `ip route show table all` 检查。策略规则像“先按包裹类型选择运输表”，再按所选表找路线；只看默认表，可能漏掉被分到其他表的包裹。这也是为什么要固定一个客户端、一个节点，避免旧代理替新代理完成测试。

### 4. 在宿主指定代理测试

```bash
curl --noproxy "" \
  --proxy http://127.0.0.1:12450 \
  --connect-timeout 10 --max-time 20 \
  -o /dev/null \
  -w '\nHTTP状态=%{http_code} 总耗时=%{time_total}秒\n' \
  https://www.gstatic.com/generate_204
```

--proxy 明确选择入口；--noproxy 清空本次不代理名单，避免 NO_PROXY 干扰；超时避免无限等待；-o 丢弃正文。该地址正常返回 204，意思是请求成功但没有正文。

本例实际返回 204，耗时约 0.31 秒，证明当时**宿主 → 入口 → 节点 → 这个测试目标**成功。它不证明所有目标、所有应用和长期稳定性。

- Connection refused：先查进程、监听地址、端口、网络模式。
- 建立连接后超时：再查节点、DNS、目标和规则。
- 测试成功但某应用失败：查应用是否采用代理、后台是否有独立网络实现，以及实际目标日志。

更新订阅成功只证明订阅接口可达；浏览器成功也不能证明其他应用采用同一条路径。

### 5. 检查 GNOME 系统代理

在宿主执行：

```bash
gsettings get org.gnome.system.proxy mode
gsettings get org.gnome.system.proxy.https host
gsettings get org.gnome.system.proxy.https port
```

预期 manual、127.0.0.1、12450。若不一致：

```bash
gsettings set org.gnome.system.proxy.http host '127.0.0.1'
gsettings set org.gnome.system.proxy.http port 12450
gsettings set org.gnome.system.proxy.https host '127.0.0.1'
gsettings set org.gnome.system.proxy.https port 12450
gsettings set org.gnome.system.proxy mode 'manual'
```

系统代理像前台贴“请到 12450 号窗口办理”的通知，应用愿意遵守才会采用它。终端工具、后台服务可能有自己的设置。HTTPS 目标可通过 HTTP 代理的 CONNECT 隧道访问，代理 URL 写 http 不表示目标连接被改成明文。

本例早期 gsettings 返回 127，提示命令执行环境有问题；补工具后返回 0。退出码成功仍不能代替从宿主读取配置和联网测试。

还要注意配置生效的时间。本例启动日志先出现 `system proxy reset done` 和 `mode none`，随后才有连接与设置代理的记录。因此，即使新 GUI 后来没成功打开，启动过程也可能已经改变宿主代理。反复试图形参数后断网，应重新读取代理设置，不能假定“窗口没出现，所以系统没有变化”。

若采用应用自己的代理环境变量，需要从设置了变量的环境启动新进程；已有后台进程不会因为另一个终端执行 export 就收到新环境。先保存工作并真正退出目标应用，再启动、核对进程和联网结果；只关窗口可能仍保留后台进程。重启是验证配置生效的一步，重启后恢复也不能直接证明节点原来坏了。

### 6. 普通模式通过以后，为什么本例仍要继续

如果用户需要的应用都能通过普通代理工作，到本章就可以先使用，不必为了“更高级”主动引入增强模式。若只有个别程序不采用系统代理，也可以先查它是否支持自己的 HTTP/SOCKS 设置或代理环境变量；优点是影响范围小，代价是逐个配置，且不保证所有后台请求都读取这些设置。

本例用户过去依赖增强模式才能使用部分应用，并明确要求修复当前失败的开关，所以选择继续处理它。TUN 能在路由层覆盖更多请求，但要承担权限、DNS、路由及其他代理冲突的排查成本。这个选择由需求决定，不是因为 curl 已成功就能推断 TUN 必然是唯一解法。

这里还要分清两个开关。**普通代理/TUN 主要回答“请求怎样进入核心”，规则/全局/直连主要回答“进入核心后怎样选出口”。** 本例日志同时出现 `tun=false` 和 `mode: global`，所以“全局”不等于“已接管整台电脑”。一个不读取系统代理的程序，即使客户端选择全局，也未必把请求交给核心；进入 TUN 的请求仍可以按规则直连。排查时先确定请求是否进入，再判断它被送往哪里。

接下来的问题因此变成：普通代理已证明可用，新增的网络接管动作究竟卡在哪一步？这正是第七章检查设备和授权的起点。

---

## 七、增强模式：逐层接通管理员认证

### 为什么这次转向授权，而不是继续换节点

用户说明原来需要增强模式才能使用部分应用，而且现在该开关总是失败。这个现象把问题指向“模式切换需要完成什么额外操作”。程序线索又包含管理员权限、虚拟网卡、pkexec 和网络能力，说明授权是值得检查的一条路径，但字符串本身还不能证明失败点。

于是先检查容器网络、TUN 设备、权限和工具：网络是 host，设备可见，容器已有较宽权限，唯独 pkexec 不存在。此时补 pkexec 有直接根据，继续扩大权限没有同样的证据。

补装后的错误依次变化，正是后续判断的依据：SHELL 被拒绝，说明还没进入认证；修正后找不到 authority 的通信入口，说明要检查系统总线；接通入口后出现 cookie 会话错误，说明已进入认证交互层。最后宿主测试成功、容器找不到认证代理，才选择在宿主为真实 GUI 注册代理。下面每一步对应不同证据，不能把它们当成一次性猜出的固定配方。

### 1. 四个角色分别做什么

- GUI：选择节点、发控制命令。
- core：处理实际网络流量。
- pkexec / polkit：申请并判断特权操作能否执行。
- 认证代理 agent：显示提示，协助用户完成认证。

增强模式涉及虚拟网卡、路由等底层网络处理。TUN 可以理解为内核提供的虚拟网络接口：路由把某些流量交给它，用户空间核心再处理，因此可以覆盖一部分不主动采用普通代理的应用。覆盖范围仍由路由、DNS、排除规则等决定。

本例实际授权显示：客户端通过 pkexec 调用 setcap，为核心文件设置网络 capabilities。不能仅凭“搜索到 TUN 字符串”就当作实际模式已启用。

### 2. 先检查设备、工具和能力

在宿主执行。先获取当前用户名，避免把原电脑的 zzh 直接搬到自己的机器：

```bash
sudo docker inspect --format \
'网络={{.HostConfig.NetworkMode}}
特权={{.HostConfig.Privileged}}
额外能力={{json .HostConfig.CapAdd}}
安全选项={{json .HostConfig.SecurityOpt}}' sakuracat26

sakuracat_user=$(id -un)
sudo docker exec -u "$sakuracat_user" sakuracat26 /bin/sh -c '
  id
  command -v pkexec
  command -v setcap
  command -v getcap
  ls -l /dev/net/tun
  getcap "$HOME/.local/share/com.sakuracat/core"
'
```

本例已有 host、privileged 和 TUN 设备，却缺 pkexec。CapAdd=null 不等于没有权限；有设备也不等于操作必然被允许。不要跳过检查就继续扩大容器权限。

### 3. 第一层：缺少 pkexec

在宿主补装容器软件包：

```bash
sudo docker exec -u 0 sakuracat26 apt-get install -y pkexec
```

它是发起授权的工具。安装包存在不代表授权服务、通信入口、会话代理也都可用。

### 4. 第二层：SHELL 不在合法列表

容器里出现：

```text
The value for the SHELL variable was not found in the /etc/shells file
```

实际变量是 bash，而列表是 /bin/bash 等完整路径。容器中检查并修正：

```bash
printf 'SHELL=%s\n' "$SHELL"
cat /etc/shells
export SHELL=/bin/bash
pkexec /usr/bin/id
```

像登记表要求“B 楼 101”，你只填“101”，字符串核对不会自动补全。先确认 /bin/bash 在列表里，不要随意把任意程序加入合法 shell 列表。

id 只显示身份，不改路由。成功包含 uid=0(root)，但本例随后遇到下一层错误。

### 5. 第三层：系统 D-Bus 默认入口不存在

```text
Error getting authority ... Could not connect: No such file or directory
```

D-Bus 是本机进程调用服务的通信机制。**系统总线**负责系统级服务；**会话总线**服务用户桌面，不能混用。socket 是通信入口，像服务门牌，不是普通文本配置文件。

本例容器中：

```text
/run/dbus/system_bus_socket            不存在
/run/host/run/dbus/system_bus_socket   已映射的宿主 socket
```

曾尝试 export DBUS_SYSTEM_BUS_ADDRESS，但本例 pkexec 实现会清理环境，不能依赖它保留自定义地址。最终让默认路径指向现成入口。[polkit pkexec 源码](https://github.com/polkit-org/polkit/blob/127/src/programs/pkexec.c)

在宿主执行带检查的准备步骤：

```bash
sudo docker exec -u 0 sakuracat26 /bin/sh -ec '
  if test -S /run/dbus/system_bus_socket; then
    exit 0
  fi
  if test -e /run/dbus/system_bus_socket || test -L /run/dbus/system_bus_socket; then
    echo "默认路径已存在但不可用，请先检查，不覆盖" >&2
    exit 1
  fi
  test -S /run/host/run/dbus/system_bus_socket
  mkdir -p /run/dbus
  ln -s /run/host/run/dbus/system_bus_socket /run/dbus/system_bus_socket
'
```

软链接像旧门牌上的“请从旁边入口进入”。它没有复制 socket，也没有启动新的宿主服务。/run 是运行时目录，后续启动需重新检查。此方法只适用于本例已经映射宿主入口的集成环境，不能在任意容器中凭空照搬。

准备命令若因已有路径不可用而退出，先停下检查该路径，不继续授权测试。准备成功后回到容器：

```bash
export SHELL=/bin/bash
unset DBUS_SYSTEM_BUS_ADDRESS
pkexec /usr/bin/id
```

### 6. 第四层：服务可达，认证会话却不匹配

本例又出现 `No session for cookie`，像审批请求已送到，但验证单号找不到对应会话。不能直接解释成密码错了。容器工具与宿主服务跨版本混用，底层原因没有最终完全确定。

对照测试：

```bash
# 宿主终端
pkexec /usr/bin/id

# 容器终端
export SHELL=/bin/bash
pkexec --disable-internal-agent /usr/bin/id
```

宿主成功；容器报 No authentication agent found。--disable-internal-agent 只是关闭内置终端代理，不是取消身份验证。说明宿主链路可用，容器进程却没有适用的认证代理。[pkexec 手册](https://www.freedesktop.org/software/polkit/docs/latest/pkexec.1.html)

### 7. 成功办法：在宿主为真实 GUI 注册代理

前面的 id 是小范围诊断工具：宿主成功、容器缺代理后，就不再靠重复执行它来证明 GUI 授权。因为认证代理可以关联到特定进程，接下来必须用实际客户端做试验。

先在修好环境的容器终端启动 GUI，不点增强模式。新开宿主终端：

```bash
sakuracat_pid=$(pgrep -u "$(id -u)" -f '(^|/)com[.]sakuracat[.]app([[:space:]]|$)')
if [[ "$sakuracat_pid" =~ ^[0-9]+$ ]]; then
  printf '为进程 %s 等待管理员认证\n' "$sakuracat_pid"
  pkttyagent --process "$sakuracat_pid"
else
  printf '没有找到唯一主进程，结果：\n%s\n' "$sakuracat_pid"
fi
```

不要加 sudo。注册后安静等待正常；回 GUI 开增强模式，宿主终端出现密码提示，输入宿主密码。

本例输出 AUTHENTICATION COMPLETE，命令是对核心文件执行 setcap；用户随后确认增强模式开启并恢复通信。这证明实际应用的授权链路跑通。

手工 pgrep 可能误匹配或返回多行；最终启动器读取 /proc/PID/exe 和启动时间。pkttyagent 支持 PID,启动时间，用来减少 PID 复用造成的错误关联。[pkttyagent 手册](https://www.freedesktop.org/software/polkit/docs/latest/pkttyagent.1.html)

不要注册到任意测试进程后，就认定另一 GUI 进程也能获得同样的代理关联。

到这里，实际 GUI 的授权请求已经成功，用户确认增强模式可用。随后出现了一个新观察：关闭认证终端，代理仍能工作。下一章用刚刚验证的授权链解释这个现象，也据此确定以后哪些部分需要常驻、哪些只在授权时参与。

---

## 八、为什么关闭认证终端，代理还能工作

可以类比“验证身份后领到专用钥匙”：

1. GUI 请求授权。
2. 认证代理接收身份验证。
3. 授权后 setcap 把特定能力写入核心文件。
4. 核心利用允许的能力执行网络功能。

认证代理只负责办理，不持续转发流量。它退出，不会自动撤销已经写入的能力，也不会主动停止 core。

Linux capabilities 把 root 权力拆成小项，例如 CAP_NET_ADMIN 涉及网络管理。文件能力通常放在扩展属性中，可用 getcap 查看，不表示整个 GUI 都成为 root。

能力是否生效还受文件系统、挂载和执行条件影响。更新核心、替换文件或改变复制方式都可能让能力丢失，所以之后仍可能再次请求授权。

手工认证终端按 Ctrl+C 通常只退出前台认证代理；停止代理仍应在客户端操作。不能把“关终端”当作通用停止代理方法。

因此日常入口需要同时管理两种生命周期：GUI／核心持续工作，认证代理按请求参与；退出认证代理不能被设计成顺便停止网络。带着这个分工，下一章才把手工过程整理成按需点击的入口。

---

## 九、按需静默启动与菜单入口

### 为什么到这里才封装脚本

前面人工步骤已经证明 GUI、宿主端口和真实授权请求能跑通，用户又提出重启后按需点击、无需常驻终端、更新时少改路径的需求。这时才有足够信息确定启动器的职责：重复执行环境准备，保留密码认证，管理后台进程，写出可查日志，发现应用路径。

如果还没有验证手工链路就先隐藏终端，启动失败只会更难观察。因此这里的脚本封装是把已经有证据的操作收起来；排障方法仍然是前面的检查，不需要读者先掌握整份源码。

### 0. 新电脑先建立可直接使用的基础菜单入口

下面提供一条不依赖本机自定义 Python 启动器的完整路径：菜单负责打开客户端，增强模式仍按第七章在另一个宿主终端完成认证。先得到能稳定重复使用的入口，再决定是否开发无终端认证界面。这里的基础入口会显示终端；后面记录的静默入口是原案例的额外定制，不是执行本教程的前提。

**在宿主创建短启动脚本。** 它只封装已经说明的准备和启动命令。已有同名文件时先备份，不直接覆盖：

```bash
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
nano "$HOME/.local/bin/sakuracat-container-basic"
```

写入以下内容，保存退出；应用版本不同就改 cd 那行：

```bash
#!/bin/bash
set -e
sudo systemctl start docker
sudo docker start sakuracat26 >/dev/null
sudo docker exec -u 0 sakuracat26 /bin/sh -ec '
  if ! test -S /run/dbus/system_bus_socket; then
    if test -e /run/dbus/system_bus_socket || test -L /run/dbus/system_bus_socket; then
      echo "系统总线路径存在但不可用，请按第七章检查" >&2
      exit 1
    fi
    test -S /run/host/run/dbus/system_bus_socket
    mkdir -p /run/dbus
    ln -s /run/host/run/dbus/system_bus_socket /run/dbus/system_bus_socket
  fi
'
exec env DBX_CONTAINER_MANAGER=docker "$HOME/.local/bin/distrobox" enter \
  --root --name sakuracat26 -- /bin/bash --noprofile --norc -c '
    export SHELL=/bin/bash
    unset DBUS_SYSTEM_BUS_ADDRESS
    cd "$HOME/.local/opt/sakuracat-1.4.5"
    export LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=llvmpipe
    export __GLX_VENDOR_LIBRARY_NAME=mesa GDK_GL=software-draw
    exec ./squashfs-root/AppRun
  '
```

set -e 让准备步骤失败时停止；脚本每次重查 /run 的入口，因为它属于运行时状态。sudo 仅用于服务和容器准备，Distrobox 仍以当前普通用户进入并运行 GUI。这个简版不实现自动选版本或单实例锁：先退出已有客户端，不反复双击。

```bash
chmod u+x "$HOME/.local/bin/sakuracat-container-basic"
"$HOME/.local/bin/sakuracat-container-basic"
```

窗口打开后，先退出客户端，再创建菜单文件：

```bash
cat > "$HOME/.local/share/applications/sakuracat-container-basic.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SakuraCat（容器基础入口）
Exec="$HOME/.local/bin/sakuracat-container-basic"
Icon=network-workgroup
Terminal=true
Categories=Network;
EOF
desktop-file-validate "$HOME/.local/share/applications/sakuracat-container-basic.desktop"
update-desktop-database "$HOME/.local/share/applications"
```

这里 EOF 没有单引号，写入时就把 HOME 展开成你自己的绝对路径。使用系统图标名，避免指向未复制的 icon.png。Terminal=true 保留 sudo 提示和应用日志；不能只改成 false 就指望密码输入继续可用。

按 Super 搜索“SakuraCat（容器基础入口）”。打开后选择节点连接；需要增强模式时，另开宿主终端执行第七章第 7 节的 pkttyagent 命令，再回客户端开增强模式并输入密码。认证成功后可按第八章结束认证代理；运行 GUI 的终端先保留。退出时先在客户端关闭增强模式、断开并退出，再关终端。

**从关机后的状态验收：** 保存工作后重启，点击菜单，完成准备密码提示，检查窗口、普通代理 204 请求、增强模式认证与实际目标应用，再退出并重新打开一次。缺少哪一项就回到对应章节，不把“菜单显示出来”当作全部通过。本节脚本是从已验证手工命令整理的可复现简版，尚未在另一台空白机器实测；原案例的验证范围见第十章。

### 后续各节：原案例的静默启动器设计记录

以下文件仅在原电脑部署过，基础入口不调用它们。若还要实现“无常驻终端、图形密码提示、自动发现新版”，需要额外部署完整启动器并验证；它们不属于下面几个调用命令就能自动生成的系统功能。

### 1. 本机已有的封装与可迁移的思路

```text
~/.local/opt/sakuracat-launcher/start-sakuracat.sh
~/.local/opt/sakuracat-launcher/sakuracat-desktop.py
~/.local/share/applications/sakuracat-container.desktop
~/.config/sakuracat-launcher/settings.json
~/.local/state/sakuracat-container/
~/.local/share/sakuracat-launcher/apps/
```

```text
点击菜单
 → 文件锁避免重复启动
 → 复用已有 GUI，或发现安装包
 → 宿主 pkexec 按需准备 Docker 和容器
 → 检查 host 网络及 D-Bus 默认入口
 → 普通用户后台启动 GUI，日志写文件
 → 宿主认证代理等待，需要时显示密码框
```

Docker 服务启动与 SakuraCat 应用启动是两件事。本例没有为 SakuraCat 添加开机自启；点击入口才运行客户端。准备容器与增强模式也是两类请求，可能分别需要认证。

### 2. 没有终端窗口，如何认证

Python 组件用 PTY（伪终端）运行宿主 pkttyagent，再用 GTK 密码框呈现交互。PTY 像后台终端接口，工具仍能按终端模式工作，用户不需要看到常驻终端。

代码关闭输入回显，不把密码写到配置或日志，也没有添加免密规则。它是本例自定义的图形包装，不是系统通用认证代理的官方安装方案；换版本需重新验证提示格式等行为。

GUI 通过 docker exec -d 后台运行；日志与认证 PTY 分开。静默不是把所有错误吞掉，而是把正常后台输出写到能找到的日志。

### 3. 日常命令

以下命令仅适用于已经部署了本例启动器的电脑。前面手工流程不会自动生成这些文件；其他机器可以先使用手工入口，或按本章职责另行实现和验证启动器。本篇保留调用示例而不存放整份实现源码。

在宿主执行：

```bash
bash "$HOME/.local/opt/sakuracat-launcher/start-sakuracat.sh"
bash "$HOME/.local/opt/sakuracat-launcher/start-sakuracat.sh" --check
bash "$HOME/.local/opt/sakuracat-launcher/start-sakuracat.sh" --choose-app
bash "$HOME/.local/opt/sakuracat-launcher/start-sakuracat.sh" --agent-check
```

依次是启动、检查发现结果、选择安装包、验证认证代理注册。agent-check 需要已有 GUI；另一个启动器持有文件锁时可能直接返回，不能把“无输出”都算通过。它不做完整密码认证或完整冷启动。

日志在 `~/.local/state/sakuracat-container/`：desktop-prepare.log 是准备过程，sakuracat-时间.log 是应用输出。启动失败先读日志，避免连续双击。

### 4. 如何适应版本更新

没有手选时，程序比较 Downloads 中匹配的 AppImage 和已有解包目录；有手选时优先指定路径。数字版本按数字序列比较，例如 1.10.0 高于 1.9.0。

新 AppImage 按 SHA-256 内容摘要建立独立缓存。像给内容做指纹：同一版本文件被替换，也能区分缓存。**这不是官方签名验证**，安装包仍需来自可信来源。

更新操作：退出旧 GUI → 下载新版或重新选择文件 → 再启动。已有进程会复用，所以仅下载新版不会替换正在运行的进程；手动选过旧文件时也不会被自动发现的新文件覆盖。

它解决固定 1.4.5 路径的问题，不能保证未来主程序名、AppRun 结构、依赖和授权逻辑改变后仍通用。

### 5. 应用菜单与 Dock

.desktop 文件像应用名片，记录名称、图标、命令。放进 `~/.local/share/applications/`，就能被菜单发现，不必桌面再放一份。

```ini
[Desktop Entry]
Type=Application
Name=SakuraCat（容器）
Exec=/home/zzh/.local/opt/sakuracat-launcher/start-sakuracat.sh
Icon=/home/zzh/.local/opt/sakuracat-launcher/icon.png
Terminal=false
StartupNotify=false
Categories=Network;
Actions=ChooseApp;

[Desktop Action ChooseApp]
Name=选择 SakuraCat 安装包
Exec=/usr/bin/python3 /home/zzh/.local/opt/sakuracat-launcher/sakuracat-desktop.py --choose-app
```

Terminal=false 不额外开终端，但不会替脚本自动处理密码、后台进程和日志。Exec 也不是普通 shell 命令，不要假定 ~ 和 $HOME 会展开，使用实际绝对路径。

```bash
desktop-file-validate "$HOME/.local/share/applications/sakuracat-container.desktop"
update-desktop-database "$HOME/.local/share/applications"
```

按 Super 键搜索 SakuraCat（容器），右键添加到收藏夹即可固定 Dock。本例桌面副本后来移入回收站，只保留菜单入口。

菜单入口解决的是重复操作的便利性，不会扩大前面测试覆盖的范围。最后一章把运行、停止、更新和失败恢复联系起来，说明日后遇到变化时该回到哪一层检查。

---

## 十、常见坑、恢复和复用边界

### 1. 关闭终端是否删除容器

不会。关闭 shell、退出 GUI、结束 core、停止容器、删除容器分别是不同动作。前台 GUI 可能随终端退出，后台 core 未必退出。

```bash
sudo docker ps -a
sudo docker start sakuracat26
sudo docker stop -t 30 sakuracat26
```

停止保留可写层，删除会移除可写层；共享主目录另有生命周期。先在客户端关闭增强模式、断开并退出，不要依赖强停容器可靠清理宿主路由。

重建时还要区分基础镜像、容器可写层、共享主目录。在现有容器内安装 libgles2，改的是这个容器的可写层，不会自动修改原来的 Ubuntu 镜像。停止再启动通常还在；删除后从基础镜像重建，需要重新安装。

共享 HOME 里的应用设置却可能仍在，于是出现“账号和配置还在，程序又报缺库”。原因是两类文件存放位置不同。为了恢复环境，应另记基础镜像版本、安装过的软件包、挂载与网络设置、启动环境变量，必要时整理成构建和初始化步骤。只备份 HOME 或只记容器名字，都不足以重建本例环境。

### 2. 恢复旧代理

先关闭 SakuraCat 增强模式、系统代理并退出，再打开旧软件恢复原设置。若只是 GNOME 还指向已退出的端口，可在宿主：

```bash
gsettings set org.gnome.system.proxy mode 'none'
```

这只改 GNOME，不清理 TUN 路由、不结束 core。网络仍异常时先查 `ip rule show`、`ip route show table all` 和客户端状态，不要批量清空路由或防火墙。

### 3. 规则下载失败不等于全部断网

geoip-cn.srs / geosite-cn.srs 失败影响规则更新；IP 查询超时影响界面显示；核心重载时管理接口可能短暂拒绝。分别验证实际目标，不能由一条警告推出整个服务持续崩溃。

**测速失败还要比较内外两层超时。** 本例管理接口测速请求带着 `delay?timeout=5000`，外层却报告 `TimeoutException after 0:00:03`。前者表达给核心的 5 秒测试上限，后者说明调用方等了 3 秒就放弃。因此界面超时不能当作“测得节点延迟是 3 秒”，也不能证明节点在完整的 5 秒内一定失败。

例如核心假如在第 4 秒返回，外层第 3 秒已不再等待；这是说明机制的假设例子，不是本例测出的延迟。后续应固定节点和目标，分别检查管理接口响应和实际代理请求。如果可以配置，外层等待应覆盖内层处理预算与通信开销；但延长超时不能修复真正不可达的目标。本例没有验证调整超时后的效果，不能把它写成已成功实施的修复。

**日志还要与人的操作对齐。** 本例末尾 `gsettings ... mode none ... returns 0` 与用户手动中断代理相符，不能据此判断程序自行崩溃。复现时记录启动、连接、切换模式、主动停止的时间，再看前后的连续日志。同一条“关闭代理”记录，出现在启动重置、用户退出或异常清理时，含义可能不同。

### 4. 当前验证边界

已验证：环境版本、GUI 打开、宿主指定代理返回 204、宿主认证成功、用户确认增强模式可用；新版发现、desktop 配置与认证代理注册有检查记录。

未验证：电脑实际重启后的完整冷启动、所有未来版本、所有功能、所有网络目标和长期稳定性。后续在有旧代理可恢复时，按“启动 → 连接 → 宿主测试 → 增强模式 → 退出 → 再打开”验收。

### 5. 换场景时复用哪一层

新版 CAD 缺 glibc，可以复用容器与图形排障；不做网络接管，就没必要照搬 TUN、setcap 和系统总线集成。服务端口通而应用不通，可以复用“从调用方指定入口测试”。GUI 授权失败，则按“工具 → 环境 → 服务入口 → 认证代理 → 实际命令”检查。

复用的是故障对应机制，不能把案例里的全部权限和配置无差别搬给任何软件。

---
