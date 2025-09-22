#!/usr/bin/env python3
"""Summarize key metrics from a gem5 stats.txt file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Union

Number = Union[int, float]

# Metrics we always try to display (key, label, unit, ratio?)
GENERAL_METRICS = (
    ("simSeconds", "Simulated time", "s", False),
    ("simTicks", "Simulated ticks", None, False),
    ("simInsts", "Simulated instructions", None, False),
    ("hostSeconds", "Host time", "s", False),
    ("hostInstRate", "Host instruction rate", "inst/s", False),
)

CPU_METRICS = (
    ("numCycles", "Cycles", None, False),
    ("ipc", "IPC", None, False),
    ("cpi", "CPI", None, False),
    ("commitStats0.numInsts", "Committed instructions", None, False),
    ("commitStats0.numMemRefs", "Committed memory references", None, False),
)

CACHE_METRICS = (
    ("icache", "L1I"),
    ("dcache", "L1D"),
)

L2_METRICS = (
    ("overallAccesses::total", "Accesses", False),
    ("overallMisses::total", "Misses", False),
    ("overallMissRate::total", "Miss rate", True),
)


def parse_stats_file(path: Path) -> Dict[str, str]:
    stats: Dict[str, str] = {}
    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if "Begin Simulation Statistics" in line:
                continue
            if "End Simulation Statistics" in line:
                continue
            if "#" in line:
                line = line.split("#", 1)[0].rstrip()
            tokens = line.split()
            if len(tokens) < 2:
                continue
            key, value = tokens[0], tokens[1]
            stats[key] = value
    return stats


def normalise_number(token: str) -> Optional[Number]:
    token = token.replace(",", "").strip()
    if token.lower() in {"", "inf", "-inf", "nan"}:
        try:
            return float(token)
        except ValueError:
            return None
    try:
        if any(c in token for c in (".", "e", "E")):
            return float(token)
        return int(token)
    except ValueError:
        return None


def format_value(value: Optional[Number], unit: Optional[str], ratio: bool) -> str:
    if value is None:
        return "<n/a>"
    if ratio:
        try:
            return f"{value * 100:.2f}%"
        except TypeError:
            return "<n/a>"
    if isinstance(value, int):
        formatted = f"{value:,}"
    else:
        formatted = f"{value:.6g}"
    if unit:
        return f"{formatted} {unit}"
    return formatted


def collect_cpu_ids(stats: Dict[str, str]) -> Iterable[Optional[int]]:
    cpu_regex = re.compile(r"^system\.cpu(\d+)\.")
    cpu_ids = sorted({int(match.group(1)) for key in stats for match in [cpu_regex.match(key)] if match})
    if cpu_ids:
        return cpu_ids
    if any(key.startswith("system.cpu.") for key in stats):
        return [None]
    return []


def extract(metrics: Iterable[Tuple[str, str, Optional[str], bool]], prefix: str, stats: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    for suffix, label, unit, ratio in metrics:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        yield label, format_value(value, unit, ratio)


def collect_cache_metrics(cache_name: str, cache_label: str, cpu_prefix: str, stats: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    base = f"{cpu_prefix}{cache_name}."
    keys = {
        "Accesses": f"{base}overallAccesses::total",
        "Misses": f"{base}overallMisses::total",
        "Miss rate": f"{base}overallMissRate::total",
    }
    for label, key in keys.items():
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        yield f"{cache_label} {label}", format_value(value, None, label == "Miss rate")


def collect_l2(stats: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    prefix = "system.l2."
    for suffix, label, ratio in L2_METRICS:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        yield f"L2 {label}", format_value(value, None, ratio)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize gem5 stats.txt")
    parser.add_argument(
        "--stats",
        type=Path,
        default=Path("m5out/stats.txt"),
        help="Path to stats.txt (default: m5out/stats.txt)",
    )
    args = parser.parse_args()

    stats_path = args.stats
    if not stats_path.is_file():
        raise SystemExit(f"Stats file not found: {stats_path}")

    stats = parse_stats_file(stats_path)
    if not stats:
        raise SystemExit("No statistics parsed from file")

    # 前分隔符
    print("\n================= statistics =================\n")

    print("Simulation summary")
    for label, value in extract(GENERAL_METRICS, "", stats):
        print(f"  {label:28} {value}")

    for cid in collect_cpu_ids(stats):
        prefix = f"system.cpu{cid}." if cid is not None else "system.cpu."
        cpu_label = f"CPU{cid}" if cid is not None else "CPU"
        print(f"\n{cpu_label} stats")
        for label, value in extract(CPU_METRICS, prefix, stats):
            print(f"  {label:28} {value}")
        for cache_name, cache_label in CACHE_METRICS:
            for label, value in collect_cache_metrics(cache_name, cache_label, prefix, stats):
                if value == "<n/a>":
                    continue
                print(f"  {label:28} {value}")

    l2_data = list(collect_l2(stats))
    if any(value != "<n/a>" for _, value in l2_data):
        print("\nShared cache stats")
        for label, value in l2_data:
            if value == "<n/a>":
                continue
            print(f"  {label:28} {value}")

    
    print("\n================= end of statistics =================\n")


if __name__ == "__main__":
    main()
