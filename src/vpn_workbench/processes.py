"""Linux 进程身份 —— 用 UID、可执行名称和启动时间关联认证主体。

不通过模糊命令行匹配杀进程，不修改 VPN 状态。
"""
import os
from pathlib import Path


def start_time(pid):
    """读取 /proc 启动时间，处理进程名中含空格的情况。

    :param pid: Linux 进程编号。
    :return: 内核时钟 tick 形式的启动时间。
    """
    return int(Path("/proc", str(pid), "stat").read_text().rsplit(") ", 1)[1].split()[19])


def find_subject(executable, uid):
    """寻找唯一符合条件的进程。

    :param executable: 精确主程序文件名。
    :param uid: 宿主普通用户编号。
    :return: (PID, 启动时间)，没有进程时为 None。
    :raises RuntimeError: 同时存在多个符合条件的进程。
    """
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid == uid and Path(os.readlink(proc / "exe")).name == executable:
                found.append((int(proc.name), start_time(int(proc.name))))
        except (OSError, ValueError, IndexError):
            continue
    if len(found) > 1:
        raise RuntimeError("检测到多个主程序，请先退出重复实例。")
    return found[0] if found else None
