#!/usr/bin/env python3
"""
直接使用 class_test_se.py 运行单个 YAML 配置的便捷脚本（无需 webui）。

示例：
    python3 configs/class/run_yaml.py configs/class/config.yaml
    python3 configs/class/run_yaml.py configs/class/config.yaml --override-cmd "tests/class/bin/x86/class_hello"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_SCRIPT = REPO_ROOT / "configs" / "class" / "run.sh"


def resolve_path(base: Path, target: Path) -> Path:
    return target if target.is_absolute() else (base / target)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="用 class_test_se.py 运行单个 YAML 配置（无需 webui）。"
    )
    parser.add_argument(
        "config",
        type=Path,
        help="YAML 配置文件路径（可相对或绝对）",
    )
    parser.add_argument(
        "--override-cmd",
        help="覆盖 YAML 中的 cmd 字段，传入具体 workload 命令",
    )
    parser.add_argument(
        "--run-script",
        type=Path,
        default=DEFAULT_RUN_SCRIPT,
        help="运行脚本路径，默认 configs/class/run.sh",
    )
    parser.add_argument(
        "--skip-parse",
        action="store_true",
        help="仅运行 gem5，不调用 parse_stats.py 摘要统计",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印完整命令行",
    )
    args = parser.parse_args(argv)

    run_script = resolve_path(REPO_ROOT, args.run_script)
    config_path = resolve_path(REPO_ROOT, args.config)

    if not run_script.exists():
        raise SystemExit(f"未找到运行脚本: {run_script}")
    if not config_path.exists():
        raise SystemExit(f"未找到配置文件: {config_path}")

    run_args = ["bash", str(run_script), str(config_path.relative_to(REPO_ROOT))]
    if args.override_cmd:
        run_args.append(args.override_cmd)

    env = os.environ.copy()
    if args.skip_parse:
        env["SKIP_PARSE_STATS"] = "1"

    if args.verbose:
        print(f"[run] {' '.join(run_args)}")

    try:
        subprocess.run(run_args, cwd=REPO_ROOT, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
