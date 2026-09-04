"""让本仓库的验证测试能 import template 目录下的 frame 包。

template 的上层目录名 write-pytest-cases 带连字符，不是合法模块名，
因此把 template 目录本身加进 sys.path，之后可直接 `from frame import ...`。
"""
import os
import sys

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills",
    "write-pytest-cases",
    "template",
)

if TEMPLATE_DIR not in sys.path:
    sys.path.insert(0, TEMPLATE_DIR)
