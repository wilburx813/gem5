#!/usr/bin/env python3
import re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = ROOT / 'configs' / 'class' / 'experiments' / 'cache_capacity'
RES_DIR = ROOT / 'configs' / 'class' / 'result' / 'cache_capacity'
OUT_PNG = Path(__file__).resolve().parent / 'cache_capacity_l1d_miss.png'

SIZE_RE = re.compile(r"l1d_size:\s*(\d+)\s*(KiB|MiB)")
MISS_RE = re.compile(r"L1D\s+Miss rate\s+([0-9.]+)%")

def parse_size(text: str) -> int:
    m = SIZE_RE.search(text)
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    if unit == 'KiB':
        return val
    if unit == 'MiB':
        return val * 1024
    return val

def read_yaml_size(path: Path) -> int:
    return parse_size(path.read_text())

def read_l1d_miss(path: Path) -> float:
    text = path.read_text()
    m = MISS_RE.search(text)
    if not m:
        raise RuntimeError(f"L1D Miss rate not found in {path}")
    return float(m.group(1))

def main():
    pairs = []
    for y in sorted(EXP_DIR.glob('config*.yaml')):
        name = y.stem  # e.g., config1
        size_kib = read_yaml_size(y)
        if size_kib is None:
            continue
        s = RES_DIR / f"{name}.stats"
        if not s.exists():
            continue
        miss_pct = read_l1d_miss(s)
        pairs.append((size_kib, miss_pct))

    if not pairs:
        raise SystemExit("No data found to plot.")

    pairs.sort(key=lambda t: t[0])
    sizes_kib = [p[0] for p in pairs]
    sizes_label = [f"{v}KiB" if v < 1024 else f"{v//1024}MiB" for v in sizes_kib]
    miss = [p[1] for p in pairs]

    plt.figure(figsize=(10, 5.5), dpi=150)
    plt.plot(sizes_label, miss, marker='o', color=(0/255,85/255,170/255))
    plt.title('Cache Capacity vs L1D Miss Rate')
    plt.xlabel('L1D size')
    plt.ylabel('L1D Miss rate (%)')
    plt.grid(True, linestyle='--', alpha=0.4)
    for x, y in zip(sizes_label, miss):
        plt.annotate(f"{y:.2f}%", (x, y), textcoords="offset points", xytext=(0,8), ha='center', fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_PNG)
    print(f"Wrote {OUT_PNG}")

if __name__ == '__main__':
    main()

