"""
版本号管理
"""
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION_FILE = os.path.join(BASE_DIR, "VERSION")


def get_version() -> str:
    """获取当前版本号"""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "1.0.0"


def get_build_info() -> dict:
    """获取构建信息"""
    return {
        "version": get_version(),
        "build_time": datetime.now().isoformat(),
        "commit": get_git_commit(),
    }


def get_git_commit() -> str:
    """获取 Git commit hash"""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# 当前版本
__version__ = get_version()
