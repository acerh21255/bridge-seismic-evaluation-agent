#!/usr/bin/env python3
"""Run the bridge drawing implementation from a repository or installed package."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _add_repository_path() -> None:
    candidates = []
    configured = os.environ.get("BRIDGE_DRAWING_AGENT_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend([
        Path.cwd(),
        Path(__file__).resolve().parents[3],
    ])
    for root in candidates:
        source = root / "src"
        if (source / "bridge_drawing_agent").is_dir():
            sys.path.insert(0, str(source))
            return


try:
    from bridge_drawing_agent.cli import main
except ImportError:
    _add_repository_path()
    try:
        from bridge_drawing_agent.cli import main
    except ImportError as error:
        raise SystemExit(
            "未找到 bridge_drawing_agent。请安装本项目 Python 包，或设置 "
            "BRIDGE_DRAWING_AGENT_ROOT 指向仓库根目录。"
        ) from error

if __name__ == "__main__":
    raise SystemExit(main())
