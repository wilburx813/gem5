#!/usr/bin/env python3
"""
Generate an English PPTX (~7 minutes, 10–12 slides) for the gem5 class lab:
 - What is gem5
 - WebUI usage
 - Cache parameter experiments

Output: configs/class/slides/gem5_class_experiment_en.pptx
Requires: python-pptx
"""
from __future__ import annotations

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

OUT_PATH = Path(__file__).resolve().parent / "gem5_class_experiment_en.pptx"


def add_title_slide(prs: Presentation, title: str, subtitle: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle


def add_bullets(
    prs: Presentation,
    title: str,
    bullets: list[str],
    notes: str | None = None,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    tf = slide.shapes.placeholders[1].text_frame
    tf.clear()
    for i, line in enumerate(bullets):
        p = tf.add_paragraph() if i else tf.paragraphs[0]
        p.text = line
        p.level = 0
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def add_two_content(
    prs: Presentation,
    title: str,
    left_title: str,
    right_title: str,
    left_lines: list[str] | None = None,
    right_lines: list[str] | None = None,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[3])
    slide.shapes.title.text = title
    left = slide.shapes.placeholders[1].text_frame
    right = slide.shapes.placeholders[2].text_frame
    left.text = left_title
    if left_lines:
        for s in left_lines:
            p = left.add_paragraph()
            p.text = s
            p.level = 1
    right.text = right_title
    if right_lines:
        for s in right_lines:
            p = right.add_paragraph()
            p.text = s
            p.level = 1


def add_image_placeholder(prs: Presentation, title: str, caption: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = title
    left = Inches(1.0)
    top = Inches(1.6)
    width = Inches(10.0)
    height = Inches(4.5)
    rect = slide.shapes.add_shape(1, left, top, width, height)  # 1=MSO_SHAPE_RECTANGLE
    fill = rect.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(230, 230, 230)
    line = rect.line
    line.color.rgb = RGBColor(160, 160, 160)
    tf = rect.text_frame
    tf.text = "Replace with charts/screenshots"
    tf.paragraphs[0].font.size = Pt(16)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    cap = slide.shapes.add_textbox(left, top + height + Inches(0.1), width, Inches(0.5))
    cap.text_frame.text = caption


def build() -> None:
    prs = Presentation()

    add_title_slide(
        prs,
        title="gem5 Class Lab: gem5, WebUI, and Cache Parameters",
        subtitle="configs/class | ~7-minute template",
    )

    add_bullets(
        prs,
        title="Agenda",
        bullets=[
            "What is gem5",
            "Repo & key scripts",
            "Using the WebUI",
            "Cache parameter experiments (methods)",
            "Results placeholders & takeaways",
            "Repro steps & Q&A",
        ],
    )

    add_bullets(
        prs,
        title="What is gem5",
        bullets=[
            "Modular and extensible system simulator",
            "Multiple ISAs (X86/ARM/RISC-V...) and memory/cache models",
            "SE and FS modes; this lab uses X86 + SE",
            "Focus: cache hierarchy and parameter impacts",
        ],
    )

    add_bullets(
        prs,
        title="Repo & key scripts",
        bullets=[
            "Single run: configs/class/run.sh",
            "Batch runs: configs/class/run_all_experiments.py",
            "Stats summary: configs/class/parse_stats.py",
            "Web UI: configs/class/webui.py",
        ],
    )

    add_bullets(
        prs,
        title="WebUI: launch & access",
        bullets=[
            "python3 configs/class/webui.py --host 127.0.0.1 --port 8080",
            "Open http://127.0.0.1:8080",
            "Pick an experiment/config or edit fields; click Run",
        ],
    )

    add_two_content(
        prs,
        title="WebUI form essentials",
        left_title="CPU/Memory",
        right_title="Cache/Workload",
        left_lines=["Core count, CPU/system clocks", "Memory type & size"],
        right_lines=[
            "cacheline_size, cache_assoc, replacement",
            "is_read_only, writeback_clean",
            "cmd: tests/class/bin/x86/class_matrixmul",
        ],
    )

    add_bullets(
        prs,
        title="Cache parameters (themes)",
        bullets=[
            "Associativity, capacity, hierarchy, line size",
            "Replacement, read-only, writeback-clean",
            "Unified workload: class_matrixmul",
        ],
    )

    add_bullets(
        prs,
        title="Methodology",
        bullets=[
            "Fix CPU/memory and most cache knobs",
            "Single-factor change per run",
            "Use run_all_experiments.py for batch runs",
        ],
    )

    add_image_placeholder(
        prs,
        title="Results placeholder: IPC vs parameter",
        caption="Create charts from configs/class/result/*/*.stats and paste here",
    )

    add_image_placeholder(
        prs,
        title="Results placeholder: Miss/MPKI vs parameter",
        caption="Show L1D/L2 miss rates and MPKI",
    )

    add_bullets(
        prs,
        title="Key takeaways (examples)",
        bullets=[
            "Associativity: big drop from 2→4, diminishing returns beyond 8",
            "Capacity: larger L1/L2 greatly reduce MPKI and boost IPC",
            "Line size: larger lines improve spatial locality and IPC",
            "Replacement: LRU/TreePLRU stable; MRU/LFU workload-sensitive",
        ],
    )

    add_bullets(
        prs,
        title="Reproducing runs",
        bullets=[
            "Single config: bash configs/class/run.sh <yaml>",
            "Batch: python3 configs/class/run_all_experiments.py",
            "Summary: python3 configs/class/parse_stats.py --stats m5out/stats.txt",
        ],
    )

    add_bullets(
        prs,
        title="Q&A",
        bullets=["Thanks!"],
    )

    prs.save(OUT_PATH)
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    build()

