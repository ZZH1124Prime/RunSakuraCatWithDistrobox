#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主认证界面 —— 从原机验证过的 GTK + PTY 认证实现拆出。

职责：为指定 PID 与启动时间注册原生 pkttyagent，把密码交互呈现为 GTK 窗口。
不保存密码、不记录 PTY 内容、不设置免密策略，也不负责停止 VPN 核心。
依赖：宿主 python3-gi、gir1.2-gtk-3.0 和 pkttyagent。
限制：原生提示格式依赖 LC_ALL=C；新 polkit 版本需重新验收。
"""
import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import subprocess
import termios

def load_gtk():
    """延迟加载 GTK，使纯检查命令不依赖图形会话。
    """
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib
    return Gtk, GLib


def message(text, error=True):
    """显示启动错误或操作结果，不显示密码内容。

    :param text: 用户可见消息。
    :param error: 是否显示错误样式。
    """
    Gtk, _ = load_gtk()
    dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO,
                               buttons=Gtk.ButtonsType.OK, text='VPN 工作台')
    dialog.format_secondary_text(text)
    dialog.run()
    dialog.destroy()


def terminal_setup():
    # New session + controlling terminal, so native pkttyagent behaves exactly
    # like the working host-terminal version. Its output is never written to logs.
    """为原生认证代理建立独立控制终端。
    """
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class GraphicalAgent:
    """原生认证代理的 GTK 包装；只保留当前会话内存。
    """
    def __init__(self, subject, ready_check=False, title="VPN"):
        """创建私有 PTY、注册通知管道及 GTK 事件监听。

        :param subject: 目标 (PID, 启动时间)。
        :param ready_check: 只验证注册，不请求密码。
        :param title: 当前 VPN 的显示名称。
        """
        self.title = title
        self.Gtk, self.GLib = load_gtk()
        self.subject = subject
        self.master, slave = pty.openpty()
        # Disable echo even before pkttyagent begins reading any secret.
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        notify_read, notify_write = os.pipe()
        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        env.pop('DBUS_SYSTEM_BUS_ADDRESS', None)
        try:
            self.proc = subprocess.Popen(
                ['/usr/bin/pkttyagent', '--process', f'{subject[0]},{subject[1]}',
                 '--notify-fd', str(notify_write)],
                stdin=slave, stdout=slave, stderr=slave, env=env,
                pass_fds=(notify_write,), preexec_fn=terminal_setup)
        finally:
            os.close(slave)
            os.close(notify_write)
        os.set_blocking(self.master, False)
        os.set_blocking(notify_read, False)
        self.notify_read = notify_read
        self.buffer = ''
        self.dialog = None
        self.registered = False
        self.failed = False
        self.stopping = False
        self.ready_check = ready_check
        self.sources = []
        self.sources.append(self.GLib.io_add_watch(self.master, self.GLib.IO_IN | self.GLib.IO_HUP, self.read_output))
        self.sources.append(self.GLib.io_add_watch(notify_read, self.GLib.IO_IN | self.GLib.IO_HUP, self.ready))
        self.sources.append(self.GLib.timeout_add(1000, self.monitor))
        self.sources.append(self.GLib.timeout_add_seconds(15, self.registration_timeout))

    def registration_timeout(self):
        """注册超时时退出认证循环。
        """
        if not self.registered:
            self.failed = True
            if not self.ready_check:
                message('等待认证代理注册超时。请退出旧的认证终端，再双击快捷方式。')
            self.Gtk.main_quit()
        return False

    def ready(self, fd, condition):
        """读取 pkttyagent 注册就绪通知。

        :param fd: 被 GTK 监听的文件描述符。
        :param condition: GTK I/O 事件标记。
        """
        try:
            data = os.read(fd, 32)
            if data:
                return True
        except BlockingIOError:
            return True
        if self.proc.poll() is None:
            self.registered = True
            if self.ready_check:
                self.GLib.idle_add(self.Gtk.main_quit)
        return False

    def read_output(self, fd, condition):
        """读取认证提示；内容只留在内存，不写日志。

        :param fd: 被 GTK 监听的文件描述符。
        :param condition: GTK I/O 事件标记。
        """
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            return True
        except OSError as exc:
            if exc.errno != errno.EIO:
                raise
            return False
        if not data:
            return False
        # Only authentication messages are kept temporarily in memory, never log
        # the PTY transcript or password responses.
        self.buffer = (self.buffer + data.decode('utf-8', 'replace'))[-6000:]
        if self.dialog is None and re.search(r'Password:\s*$', self.buffer, re.I):
            self.prompt()
        return True

    def prompt(self):
        """创建隐藏输入的密码对话框。
        """
        Gtk = self.Gtk
        dialog = Gtk.Dialog(title=self.title + ' 管理员认证', flags=Gtk.DialogFlags.MODAL)
        self.dialog = dialog
        dialog.add_button('取消', Gtk.ResponseType.CANCEL)
        dialog.add_button('认证', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_keep_above(True)
        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_border_width(18)
        transcript = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', self.buffer).strip()
        label = Gtk.Label(label=self.title + ' 请求管理员授权。\n请输入宿主 Ubuntu 的登录密码。')
        label.set_xalign(0)
        box.pack_start(label, False, False, 0)
        details = Gtk.Label(label=transcript[-2500:])
        details.set_line_wrap(True)
        details.set_max_width_chars(75)
        details.set_xalign(0)
        box.pack_start(details, False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        dialog.connect('response', self.response, entry)
        dialog.show_all()
        entry.grab_focus()
        dialog.present()

    def response(self, dialog, response_id, entry):
        """发送用户响应或取消认证，并清空输入控件。

        :param dialog: 当前认证对话框。
        :param response_id: GTK 响应编号。
        :param entry: 密码输入控件。
        """
        password = entry.get_text() if response_id == self.Gtk.ResponseType.OK else None
        entry.set_text('')
        dialog.destroy()
        self.dialog = None
        self.buffer = ''
        if password is None:
            # Ctrl+C in this private PTY cancels only the authentication agent.
            os.write(self.master, b'\x03')
            self.stopping = True
        else:
            os.write(self.master, (password + '\n').encode())
            password = None

    def monitor(self):
        """检查代理和目标进程生命周期。
        """
        if self.proc.poll() is not None:
            if not self.stopping:
                self.failed = True
                text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', self.buffer).strip()
                if not self.ready_check:
                    message('增强模式认证工具已退出。代理未被启动器停止。\n'
                            '需要再次授权时，可重新双击快捷方式。\n\n' + text[-1800:])
            self.Gtk.main_quit()
            return False
        try:
            stat = Path(f'/proc/{self.subject[0]}/stat').read_text()
            current_start = int(stat.rsplit(') ', 1)[1].split()[19])
            alive = current_start == self.subject[1]
        except (OSError, IndexError, ValueError):
            alive = False
        if not alive:
            self.Gtk.main_quit()
            return False
        return True

    def run(self):
        """运行 GTK 循环并在退出时清理认证进程和描述符。
        """
        try:
            self.Gtk.main()
            return self.registered and not self.failed
        finally:
            self.stopping = True
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            os.close(self.master)
            os.close(self.notify_read)


