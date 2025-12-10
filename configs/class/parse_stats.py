#!/usr/bin/env python3
"""Summarize key metrics from a gem5 stats.txt file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Union, List

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
    ("overallHits::total", "Hits", False),
    ("overallMisses::total", "Misses", False),
    ("overallMissRate::total", "Miss rate", True),
)

L2_EXTRA_METRICS = (
    ("writebacks", "Writebacks"),
)

MEMORY_CONTROLLER_PRIMARY = (
    ("dram__num_reads::total", "DRAM read requests", None),
    ("dram__num_writes::total", "DRAM write requests", None),
    ("dram__bytes_read::total", "DRAM bytes read", "B"),
    ("dram__bytes_written::total", "DRAM bytes written", "B"),
)

MEMORY_CONTROLLER_LATENCY = (
    ("dram__avg_mem_access_latency", "Avg mem access latency"),
    ("dram__avg_queueing_latency", "Avg queue delay"),
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


def calculate_mpki(misses: Optional[Number], instructions: Optional[Number]) -> Optional[float]:
    if misses is None or instructions is None:
        return None
    try:
        misses_f = float(misses)
        inst_f = float(instructions)
    except (TypeError, ValueError):
        return None
    if inst_f <= 0:
        return None
    return (misses_f * 1000.0) / inst_f


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


def collect_cache_metrics(
    cache_name: str,
    cache_label: str,
    cpu_prefix: str,
    stats: Dict[str, str],
    instructions: Optional[Number],
) -> Iterable[Tuple[str, str]]:
    base = f"{cpu_prefix}{cache_name}."
    misses_value: Optional[Number] = None

    metrics = [
        ("overallAccesses::total", "Accesses", False),
        ("overallHits::total", "Hits", False),
        ("overallMisses::total", "Misses", False),
        ("overallMissRate::total", "Miss rate", True),
        ("writebacks", "Writebacks", False),
    ]

    for suffix, label, ratio in metrics:
        key = f"{base}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        if suffix == "overallMisses::total":
            misses_value = value
        if value is None:
            continue
        yield f"{cache_label} {label}", format_value(value, None, ratio)

    mpki = calculate_mpki(misses_value, instructions)
    if mpki is not None:
        yield f"{cache_label} MPKI", format_value(mpki, None, False)


def collect_l2(stats: Dict[str, str], instructions: Optional[Number]) -> Iterable[Tuple[str, str]]:
    prefix = "system.l2."
    misses_value: Optional[Number] = None
    for suffix, label, ratio in L2_METRICS:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        if suffix == "overallMisses::total":
            misses_value = value
        if value is None:
            continue
        yield f"L2 {label}", format_value(value, None, ratio)

    for suffix, label in L2_EXTRA_METRICS:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        if value is None:
            continue
        yield f"L2 {label}", format_value(value, None, False)

    mpki = calculate_mpki(misses_value, instructions)
    if mpki is not None:
        yield "L2 MPKI", format_value(mpki, None, False)


def discover_memory_controllers(stats: Dict[str, str]) -> List[Tuple[str, str]]:
    ctrl_regex = re.compile(r"^system\.(mem_ctrls\[\d+\]|mem_ctrl)\.")
    controllers: Dict[str, str] = {}
    for key in stats.keys():
        match = ctrl_regex.match(key)
        if not match:
            continue
        suffix = match.group(1)
        prefix = f"system.{suffix}."
        controllers.setdefault(suffix, prefix)
    if not controllers:
        return []
    sorted_items = sorted(controllers.items(), key=lambda item: item[0])
    return [
        (
            f"MemCtrl[{suffix.split('[')[1].rstrip(']')}]" if "[" in suffix else "MemCtrl",
            prefix,
        )
        for suffix, prefix in sorted_items
    ]


def collect_memory_controller_stats(prefix: str, stats: Dict[str, str]) -> Iterable[Tuple[str, str]]:
    for suffix, label, unit in MEMORY_CONTROLLER_PRIMARY:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        if value is None:
            continue
        yield label, format_value(value, unit, False)

    for suffix, label in MEMORY_CONTROLLER_LATENCY:
        key = f"{prefix}{suffix}"
        raw = stats.get(key)
        value = normalise_number(raw) if raw is not None else None
        if value is None:
            continue
        yield label, format_value(value, None, False)


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

    total_instructions: float = 0.0
    have_instruction_data = False

    for cid in collect_cpu_ids(stats):
        prefix = f"system.cpu{cid}." if cid is not None else "system.cpu."
        cpu_label = f"CPU{cid}" if cid is not None else "CPU"
        print(f"\n{cpu_label} stats")
        inst_key = f"{prefix}commitStats0.numInsts"
        inst_raw = stats.get(inst_key)
        instructions = normalise_number(inst_raw) if inst_raw is not None else None
        if instructions is None:
            fallback_inst = stats.get(f"{prefix}numInsts")
            instructions = normalise_number(fallback_inst) if fallback_inst is not None else None
        if instructions is not None:
            have_instruction_data = True
            try:
                total_instructions += float(instructions)
            except (TypeError, ValueError):
                pass
        for label, value in extract(CPU_METRICS, prefix, stats):
            print(f"  {label:28} {value}")
        for cache_name, cache_label in CACHE_METRICS:
            for label, value in collect_cache_metrics(cache_name, cache_label, prefix, stats, instructions):
                print(f"  {label:28} {value}")

    total_instructions_value: Optional[Number] = total_instructions if have_instruction_data else None

    l2_data = list(collect_l2(stats, total_instructions_value))
    if any(value != "<n/a>" for _, value in l2_data):
        print("\nShared cache stats")
        for label, value in l2_data:
            if value == "<n/a>":
                continue
            print(f"  {label:28} {value}")

    mem_ctrls = discover_memory_controllers(stats)
    for ctrl_label, prefix in mem_ctrls:
        entries = list(collect_memory_controller_stats(prefix, stats))
        if not entries:
            continue
        print(f"\nMemory controller ({ctrl_label})")
        for label, value in entries:
            print(f"  {label:28} {value}")


    print("\n================= end of statistics =================\n")


if __name__ == "__main__":
    main()
