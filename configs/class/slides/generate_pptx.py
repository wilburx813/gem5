#!/usr/bin/env python3
"""
生成课程实验的 PPTX（约 7 分钟，10-12 张页）。

依赖: python-pptx（已在环境中可用）。
输出: configs/class/slides/gem5_class_experiment.pptx
"""
from __future__ import annotations

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# 将输出直接放在当前脚本所在目录
OUT_PATH = Path(__file__).resolve().parent / "gem5_class_experiment.pptx"


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
    tf.text = "在此替换为图表/截图"
    tf.paragraphs[0].font.size = Pt(16)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    cap = slide.shapes.add_textbox(left, top + height + Inches(0.1), width, Inches(0.5))
    cap.text_frame.text = caption


def build() -> None:
    prs = Presentation()

    add_title_slide(
        prs,
        title="gem5 课程实验：gem5、WebUI 与缓存参数",
        subtitle="configs/class | ~7 分钟模板",
    )

    add_bullets(
        prs,
        title="目录",
        bullets=[
            "gem5 简介",
            "仓库与脚本",
            "WebUI 使用",
            "缓存参数实验主题与方法",
            "结果占位与关键观察",
            "复现实验与Q&A",
        ],
    )

    add_bullets(
        prs,
        title="什么是 gem5",
        bullets=[
            "模块化系统模拟器，学术/工业通用",
            "多 ISA（X86/ARM/RISC-V…）与缓存/内存模型",
            "SE/FS 两种模式；本实验采用 X86+SE",
            "聚焦缓存层次结构与参数影响",
        ],
    )

    add_bullets(
        prs,
        title="仓库与关键脚本",
        bullets=[
            "单次运行: configs/class/run.sh",
            "批量实验: configs/class/run_all_experiments.py",
            "统计解析: configs/class/parse_stats.py",
            "WebUI: configs/class/webui.py",
        ],
    )

    add_bullets(
        prs,
        title="WebUI 启动与访问",
        bullets=[
            "python3 configs/class/webui.py --host 127.0.0.1 --port 8080",
            "浏览器访问 http://127.0.0.1:8080",
            "选择实验/配置或手动填写参数，点击运行",
        ],
    )

    add_two_content(
        prs,
        title="WebUI 表单要点",
        left_title="CPU/Memory",
        right_title="Cache/Workload",
        left_lines=["核数、主/系统频率", "内存类型和容量"],
        right_lines=[
            "cacheline_size、cache_assoc、replacement",
            "is_read_only、writeback_clean",
            "cmd: tests/class/bin/x86/class_matrixmul",
        ],
    )

    add_bullets(
        prs,
        title="缓存参数主题",
        bullets=[
            "相联度、容量、层次、行大小",
            "替换策略、只读、clean 写回",
            "统一负载：class_matrixmul",
        ],
    )

    add_bullets(
        prs,
        title="方法与流程",
        bullets=[
            "固定 CPU/内存与多数缓存参数",
            "单因素变化，每次只改一个参数",
            "run_all_experiments.py 批跑汇总",
        ],
    )

    add_image_placeholder(
        prs,
        title="结果占位：IPC vs 参数",
        caption="请用 configs/class/result/*/*.stats 绘制折线/柱状图并粘贴",
    )

    add_image_placeholder(
        prs,
        title="结果占位：Miss Rate/MPKI vs 参数",
        caption="同上，分别展示 L1D/L2 Miss Rate 与 MPKI",
    )

    add_bullets(
        prs,
        title="关键观察（示例）",
        bullets=[
            "相联度：2→4 收益明显，8 路后趋缓",
            "容量：L1/L2 增大显著降 MPKI、提 IPC",
            "行大小：更大行降低 Miss，IPC 稳步提升",
            "替换策略：LRU/TreePLRU 更稳；MRU/LFU 对抖动负载敏感",
        ],
    )

    add_bullets(
        prs,
        title="如何复现",
        bullets=[
            "单个配置: bash configs/class/run.sh <yaml>",
            "批量: python3 configs/class/run_all_experiments.py",
            "解析: python3 configs/class/parse_stats.py --stats m5out/stats.txt",
        ],
    )

    add_bullets(
        prs,
        title="Q&A",
        bullets=["感谢！欢迎提问。"],
    )

    prs.save(OUT_PATH)
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    build()
