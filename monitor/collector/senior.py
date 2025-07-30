#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Name   : senior.py
Author      : wzw
Date Created: 2025/7/16
Description : Add your script's purpose here.
"""
import os
import platform
import subprocess
import json
import sys

import psutil
import inspect
import traceback
import faulthandler
from typing import Dict, Any, List, Optional


class SeniorCollector:
    """
    集成：
    1. 软件包安装/版本检测优化
    2. 获取进程调用栈信息（Python 内部和原生栈）
    """

    def __init__(self):
        self.distro = platform.system().lower()

    # -------- 软件包检测优化 --------
    def get_package_status(self, pkg_name: str) -> Dict[str, str]:
        """
        返回包是否安装及其版本。
        支持 Debian(dpkti)/RPM 系统及 Python pip 包。
        返回格式：{
            'pkg_name': pkg_name,
            'manager': 'dpkg'|'rpm'|'pip',
            'status': 'installed'|'not installed',
            'version': version or ''
        }
        """
        # 先检测系统包
        if self._is_debian_like():
            cmd = ["dpkg-query", "-W", "-f=${Version}", pkg_name]
            mgr = 'dpkg'
        else:
            cmd = ["rpm", "-q", pkg_name]
            mgr = 'rpm'
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            version = out if mgr == 'dpkg' else out.split('-')[-1]
            status = 'installed'
        except subprocess.CalledProcessError:
            version = ''
            status = 'not installed'

        # 同名 pip 包检测
        pip_version = ''
        try:
            pip_list = subprocess.check_output(
                [sys.executable, '-m', 'pip', 'show', pkg_name], text=True, stderr=subprocess.DEVNULL
            )
            for line in pip_list.splitlines():
                if line.startswith('Version:'):
                    pip_version = line.split(':', 1)[1].strip()
                    break
        except Exception:
            pass

        return {
            'pkg_name': pkg_name,
            'manager': mgr,
            'status': status,
            'version': version,
            'pip_version': pip_version
        }

    # 内部判断
    def _is_debian_like(self) -> bool:
        return any(x in platform.platform().lower() for x in ['ubuntu', 'debian', 'mint'])

    # -------- 调用栈信息采集 --------
    def get_native_stack(self, pid: int) -> str:
        """
        使用 gstack 获取某个进程的 C/C++ 原生栈信息（需安装 gdb/gstack），要求有权限
        """
        try:
            return subprocess.check_output(
                ["gstack", str(pid)], text=True, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            return f"Error getting native stack for PID {pid}: {e}"

    def get_kernel_stack(self, pid: int) -> Dict[int, List[str]]:
        """
        读取 /proc/<pid>/task/<tid>/stack，以获取内核栈信息
        返回格式：{tid: [stack lines]}
        """
        stacks = {}
        base = f"/proc/{pid}/task"
        if not os.path.isdir(base):
            return {pid: ["PID not found or insufficient permissions"]}
        for tid in os.listdir(base):
            stack_file = os.path.join(base, tid, 'stack')
            try:
                with open(stack_file, 'r') as f:
                    lines = [line.strip() for line in f]
                stacks[int(tid)] = lines
            except Exception:
                stacks[int(tid)] = ["cannot read stack"]
        return stacks


# -------- 使用示例 --------
if __name__ == '__main__':
    collector = SeniorCollector()
    # 软件包检测
    print(collector.get_package_status('nginx'))

    # 原生栈
    pid = os.getpid()
    print(f"Native stack for PID {pid}:")
    print(collector.get_native_stack(pid))

    # 内核栈
    print(f"Kernel stacks for PID {pid}:")
    print(collector.get_kernel_stack(pid))
