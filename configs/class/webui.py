#!/usr/bin/env python3
"""Lightweight web UI for configuring and launching class_test_se simulations."""

from __future__ import annotations

import argparse
import html
import os
import subprocess
import sys
import tempfile
import textwrap
import urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONFIG_DIR.parent.parent
RUN_SCRIPT = REPO_ROOT / "configs" / "class" / "run.sh"
DEFAULT_CONFIG = CONFIG_DIR / "config.yaml"
PARSE_STATS = CONFIG_DIR / "parse_stats.py"
DEFAULT_PORT = 8080
COMMAND_DIR = REPO_ROOT / "tests" / "class" / "bin" / "x86"
MEMORY_TYPE_CHOICES = [
    "DDR3_1600_8x8",
    "DDR3_2133_8x8",
    "DDR4_2400_8x8",
    "DDR4_2400_16x4",
    "HBM_2000_4H_1x64",
    "SimpleMemory",
]
REPLACEMENT_POLICY_SUGGESTIONS = [
    "LRURP()",
    "RandomRP()",
    "FIFORP()",
    "TreePLRURP()",
    "MRURP()",
    "LFURP()",
    "BRRIPRP()",
    "SecondChanceRP()",
]
BOOL_SELECT_OPTIONS = ["inherit", "true", "false"]
CACHE_PARAM_HELP = (
    "One override per line; each becomes a gem5 --param. "
    "Example: system.cpu[0:4].dcache.writeback_clean=true to alter the write policy."
)
ASSOC_KEYS = ["l1d_assoc", "l1i_assoc", "l2_assoc", "l3_assoc"]
# field_name -> (level, attribute, value_kind)
# level: l1d/l1i/l2/l3, attribute: BaseCache param, value_kind: 'bool' or 'string'
CACHE_PARAM_FIELDS = {
    "cache_replacement": ("all", "replacement_policy", "string"),
    "cache_is_read_only": ("all", "is_read_only", "bool"),
    "cache_writeback_clean": ("all", "writeback_clean", "bool"),
}


def _discover_command_options() -> List[str]:
    if not COMMAND_DIR.is_dir():
        return []

    options: List[str] = []
    for entry in sorted(COMMAND_DIR.iterdir()):
        if entry.is_file():
            # Present binaries as repo-relative paths so run.sh can locate them.
            options.append(str(entry.relative_to(REPO_ROOT)))
    return options
COMMAND_OPTIONS = _discover_command_options()
COMMAND_FIELD_TYPE = "select" if COMMAND_OPTIONS else "text"
DEFAULT_COMMAND = (
    COMMAND_OPTIONS[0]
    if COMMAND_OPTIONS
    else "tests/test-progs/hello/bin/x86/linux/hello"
)


class FieldSpec:
    """Describe a form field and how it maps to the YAML config."""

    def __init__(
        self,
        name: str,
        label: str,
        field_type: str,
        section: str,
        *,
        options: Iterable[str] | None = None,
        default: str | int | bool | None = None,
        placeholder: str | None = None,
        help_text: str | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self.field_type = field_type
        self.section = section
        self.options = list(options or [])
        self.default = default
        self.placeholder = placeholder
        self.help_text = help_text


FIELD_SPECS: List[FieldSpec] = [
    FieldSpec(
        "cpu-type",
        "CPU type",
        "select",
        "CPU",
        options=["X86TimingSimpleCPU", "X86O3CPU", "X86AtomicSimpleCPU"],
        default="X86TimingSimpleCPU",
        help_text="Maps to --cpu-type",
    ),
    FieldSpec(
        "num-cpus",
        "CPU cores",
        "number",
        "CPU",
        default=1,
        help_text="Maps to --num-cpus",
    ),
    FieldSpec(
        "sys-clock",
        "System clock",
        "text",
        "CPU",
        default="1GHz",
        help_text="Maps to --sys-clock (e.g. 1GHz)",
    ),
    FieldSpec(
        "cpu-clock",
        "CPU clock",
        "text",
        "CPU",
        default="2GHz",
        help_text="Maps to --cpu-clock (e.g. 2GHz)",
    ),
    FieldSpec(
        "mem-type",
        "Memory type",
        "select",
        "Memory",
        default="DDR3_1600_8x8",
        options=MEMORY_TYPE_CHOICES,
        help_text="Maps to --mem-type",
    ),
    FieldSpec(
        "mem-size",
        "Memory size",
        "text",
        "Memory",
        default="512MiB",
        help_text="Maps to --mem-size (e.g. 2GB, 512MiB)",
    ),
    FieldSpec(
        "mem-channels",
        "Memory channels",
        "number",
        "Memory",
        help_text="Optional --mem-channels override",
    ),
    FieldSpec(
        "mem-channels-intlv",
        "Memory channel interleave",
        "number",
        "Memory",
        help_text="Optional --mem-channels-intlv",
    ),
    FieldSpec(
        "mem-ranks",
        "Memory ranks",
        "number",
        "Memory",
        help_text="Optional --mem-ranks",
    ),
    FieldSpec(
        "caches",
        "Enable private L1 caches",
        "checkbox",
        "Cache",
        default=True,
        help_text="Maps to --caches",
    ),
    FieldSpec(
        "l2cache",
        "Enable shared L2 cache",
        "checkbox",
        "Cache",
        default=True,
        help_text="Maps to --l2cache",
    ),
    FieldSpec(
        "l3cache",
        "Enable shared L3 cache",
        "checkbox",
        "Cache",
        default=False,
        help_text="Maps to --l3cache",
    ),
    FieldSpec(
        "l1d_size",
        "L1D size",
        "text",
        "Cache",
        placeholder="64KiB",
        help_text="Optional --l1d_size",
    ),
    FieldSpec(
        "l1i_size",
        "L1I size",
        "text",
        "Cache",
        placeholder="32KiB",
        help_text="Optional --l1i_size",
    ),
    FieldSpec(
        "l2_size",
        "L2 size",
        "text",
        "Cache",
        placeholder="1MiB",
        help_text="Optional --l2_size",
    ),
    FieldSpec(
        "l3_size",
        "L3 size",
        "text",
        "Cache",
        placeholder="32MiB",
        help_text="Optional --l3_size",
    ),
    FieldSpec(
        "num-dirs",
        "Directory controllers",
        "number",
        "Cache",
        placeholder="1",
        help_text="Optional --num-dirs",
    ),
    FieldSpec(
        "num-l2caches",
        "L2 cache tiles",
        "number",
        "Cache",
        placeholder="1",
        help_text="Optional --num-l2caches",
    ),
    FieldSpec(
        "num-l3caches",
        "L3 cache tiles",
        "number",
        "Cache",
        placeholder="1",
        help_text="Optional --num-l3caches",
    ),
    FieldSpec(
        "cacheline_size",
        "Cache line",
        "number",
        "Cache",
        default=64,
        help_text="Maps to --cacheline_size",
    ),
    FieldSpec(
        "cache_assoc",
        "Cache associativity (ways)",
        "number",
        "Cache",
        placeholder="4",
        help_text="Applies the same associativity to L1/L2/L3 caches",
    ),
    FieldSpec(
        "cache_replacement",
        "Cache replacement policy",
        "datalist",
        "Cache",
        options=REPLACEMENT_POLICY_SUGGESTIONS,
        placeholder="LRURP()",
        help_text="Applies to all configured caches via gem5 --param",
    ),
    FieldSpec(
        "cache_is_read_only",
        "Cache read-only",
        "select",
        "Cache",
        options=BOOL_SELECT_OPTIONS,
        default="inherit",
        help_text="Set is_read_only for every cache level (inherit keeps defaults)",
    ),
    FieldSpec(
        "cache_writeback_clean",
        "Cache writeback clean",
        "select",
        "Cache",
        options=BOOL_SELECT_OPTIONS,
        default="inherit",
        help_text="Set writeback_clean for every cache level",
    ),
    FieldSpec(
        "cache_param_overrides",
        "Cache parameter overrides",
        "textarea",
        "Cache",
        placeholder="system.cpu[0:4].dcache.writeback_clean=true\nsystem.l2.write_buffers=16",
        help_text=CACHE_PARAM_HELP,
    ),
    FieldSpec(
        "cmd",
        "Command",
        COMMAND_FIELD_TYPE,
        "Workload",
        default=DEFAULT_COMMAND,
        options=COMMAND_OPTIONS,
        help_text="Binary to run; maps to --cmd",
    ),
    FieldSpec(
        "options",
        "Command arguments",
        "text",
        "Workload",
        placeholder="e.g. 20000",
        help_text="Optional --options string",
    ),
]


SECTION_ORDER = ["CPU", "Memory", "Cache", "Workload"]
CHECKBOX_NAMES = {spec.name for spec in FIELD_SPECS if spec.field_type == "checkbox"}


def _load_default_values() -> Dict[str, str]:
    values: Dict[str, str] = {}
    if DEFAULT_CONFIG.is_file():
        for raw_line in DEFAULT_CONFIG.read_text().splitlines():
            if ":" not in raw_line:
                continue
            key, _, value = raw_line.partition(":")
            cleaned_key = key.strip()
            if not cleaned_key or cleaned_key.startswith("#"):
                continue
            values[cleaned_key] = value.strip()
    return values


DEFAULT_VALUES = _load_default_values()


def _coerce_checkbox(default: object) -> bool:
    if isinstance(default, bool):
        return default
    if isinstance(default, str):
        return default.lower() in {"true", "1", "yes", "on"}
    if isinstance(default, (int, float)):
        return bool(default)
    return False


def _ordered_config_from_form(
    form_values: Dict[str, str]
) -> Tuple[OrderedDict[str, object], List[str], str]:
    config = OrderedDict()
    errors: List[str] = []
    param_lines: List[str] = []
    cache_param_inputs: Dict[str, object] = {}
    global_assoc_value: int | None = None

    for spec in FIELD_SPECS:
        raw_value = form_values.get(spec.name, "")
        is_checkbox = spec.field_type == "checkbox"

        if is_checkbox:
            selected = raw_value.lower() in {"true", "on", "1", "yes"}
            if spec.name in CACHE_PARAM_FIELDS:
                cache_param_inputs[spec.name] = selected
                continue
            config[spec.name] = selected
            continue

        trimmed = raw_value.strip()

        if spec.field_type == "textarea":
            if spec.name == "cache_param_overrides":
                if trimmed:
                    for line in trimmed.splitlines():
                        candidate = line.strip()
                        if not candidate or candidate.startswith("#"):
                            continue
                        param_lines.append(candidate)
                continue

            if trimmed:
                config[spec.name] = trimmed
            continue

        if not trimmed:
            continue

        if spec.name in CACHE_PARAM_FIELDS:
            # Treat "inherit" as skipping for select helpers
            if spec.field_type == "select" and trimmed.lower() == "inherit":
                continue
            cache_param_inputs[spec.name] = trimmed
            continue

        if spec.name == "cache_assoc":
            try:
                global_assoc_value = int(trimmed)
            except ValueError:
                errors.append(f"{spec.label} must be a number, received {trimmed!r}")
            continue

        if spec.field_type == "number":
            try:
                config[spec.name] = int(trimmed)
            except ValueError:
                errors.append(f"{spec.label} must be a number, received {trimmed!r}")
        else:
            config[spec.name] = trimmed

    if "cpu-type" not in config:
        errors.append("CPU type is required")
    if "num-cpus" not in config:
        errors.append("CPU cores are required")
    if "cmd" not in config:
        errors.append("Command is required")

    extra_lines = form_values.get("extra_lines", "")

    if errors:
        raise ValueError("\n".join(errors))

    if global_assoc_value is not None:
        for assoc_key in ASSOC_KEYS:
            config[assoc_key] = global_assoc_value

    param_lines.extend(_generate_cache_param_lines(config, cache_param_inputs))

    return config, param_lines, extra_lines


def _config_to_yaml(
    config: OrderedDict[str, object], param_lines: List[str], extra_lines: str
) -> str:
    lines: List[str] = []
    for key, value in config.items():
        if isinstance(value, bool):
            yaml_value = "true" if value else "false"
        else:
            yaml_value = str(value)
        lines.append(f"{key}: {yaml_value}")
    for idx, param_line in enumerate(param_lines):
        lines.append(f"param_cache_{idx}: {param_line}")
    extra = [line.rstrip() for line in extra_lines.splitlines() if line.strip()]
    if extra:
        lines.extend(extra)
    return "\n".join(lines) + "\n"


def _normalize_bool_param_value(raw_value: object) -> str | None:
    if isinstance(raw_value, bool):
        return "true" if raw_value else "false"
    text = str(raw_value).strip().lower()
    if text in {"", "inherit"}:
        return None
    if text in {"true", "1", "yes", "on"}:
        return "true"
    if text in {"false", "0", "no", "off"}:
        return "false"
    return None


def _generate_cache_param_lines(
    config: Dict[str, object], cache_inputs: Dict[str, object]
) -> List[str]:
    if not cache_inputs:
        return []

    num_cpus = int(config.get("num-cpus", 0) or 0)
    caches_enabled = bool(config.get("caches", False))
    l2_enabled = bool(config.get("l2cache", False))
    l3_enabled = bool(config.get("l3cache", False))

    lines: List[str] = []

    for field_name, raw_value in cache_inputs.items():
        level, attribute, value_kind = CACHE_PARAM_FIELDS[field_name]

        if value_kind == "bool":
            normalized = _normalize_bool_param_value(raw_value)
            if normalized is None:
                continue
            value = normalized
        else:
            value = str(raw_value).strip()
            if not value:
                continue

        if level == "all":
            if caches_enabled and num_cpus > 0:
                for cpu_idx in range(num_cpus):
                    lines.append(
                        f"system.cpu[{cpu_idx}].dcache.{attribute}={value}"
                    )
                    lines.append(
                        f"system.cpu[{cpu_idx}].icache.{attribute}={value}"
                    )
            if l2_enabled:
                lines.append(f"system.l2.{attribute}={value}")
            if l3_enabled:
                lines.append(f"system.l3.{attribute}={value}")

    return lines


def _run_simulation(yaml_text: str) -> Tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="gem5-class-") as tmpdir:
        tmp_path = Path(tmpdir) / "config.yaml"
        tmp_path.write_text(yaml_text)

        env = os.environ.copy()
        env["SKIP_PARSE_STATS"] = "1"

        proc = subprocess.run(
            ["bash", str(RUN_SCRIPT), str(tmp_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
        )

    return proc.returncode, proc.stdout, proc.stderr


def _collect_stats() -> str:
    if not (REPO_ROOT / "m5out" / "stats.txt").is_file():
        return ""

    proc = subprocess.run(
        ["python3", str(PARSE_STATS)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return proc.stderr or proc.stdout
    return proc.stdout


def _html_escape_pre(text: str) -> str:
    return "<pre>" + html.escape(text) + "</pre>" if text.strip() else ""


def _render_sections(form_values: Dict[str, str]) -> str:
    sections_html: List[str] = []
    for section in SECTION_ORDER:
        specs = [spec for spec in FIELD_SPECS if spec.section == section]
        if not specs:
            continue

        rows: List[str] = []
        for spec in specs:
            current_value = form_values.get(spec.name)
            if current_value is None:
                default_value = DEFAULT_VALUES.get(spec.name)
                if spec.field_type == "checkbox":
                    default_bool = (
                        _coerce_checkbox(default_value)
                        if default_value is not None
                        else _coerce_checkbox(spec.default)
                    )
                    current_value = "true" if default_bool else ""
                else:
                    current_value = (
                        default_value
                        if default_value is not None
                        else (str(spec.default) if spec.default is not None else "")
                    )

            rows.append(_render_field(spec, current_value or ""))

        sections_html.append(
            f"<fieldset><legend>{html.escape(section)}</legend>{''.join(rows)}</fieldset>"
        )

    return "\n".join(sections_html)


def _render_field(spec: FieldSpec, value: str) -> str:
    label = html.escape(spec.label)
    help_text = (
        f'<div class="help">{html.escape(spec.help_text)}</div>'
        if spec.help_text
        else ""
    )

    if spec.field_type == "select":
        options_html = []
        for opt in spec.options:
            selected = " selected" if opt == value else ""
            options_html.append(
                f'<option value="{html.escape(opt)}"{selected}>{html.escape(opt)}</option>'
            )
        control = f'<select name="{html.escape(spec.name)}">{"".join(options_html)}</select>'
    elif spec.field_type == "checkbox":
        checked = " checked" if value.lower() in {"true", "on", "1", "yes"} else ""
        control = (
            f'<input type="checkbox" name="{html.escape(spec.name)}" value="true"{checked}>'
        )
    elif spec.field_type == "textarea":
        placeholder = (
            f' placeholder="{html.escape(spec.placeholder)}"'
            if spec.placeholder
            else ""
        )
        control = (
            f'<textarea name="{html.escape(spec.name)}"{placeholder}>'
            f"{html.escape(value)}</textarea>"
        )
    elif spec.field_type == "datalist":
        list_id = f"{spec.name}-list"
        placeholder = (
            f' placeholder="{html.escape(spec.placeholder)}"'
            if spec.placeholder
            else ""
        )
        option_values = []
        seen = set()
        for opt in spec.options + ([value] if value else []):
            if opt and opt not in seen:
                seen.add(opt)
                option_values.append(f'<option value="{html.escape(opt)}"></option>')
        control = (
            f'<input type="text" name="{html.escape(spec.name)}" '
            f'value="{html.escape(value)}" list="{html.escape(list_id)}"{placeholder}>'
            f'<datalist id="{html.escape(list_id)}">{"".join(option_values)}</datalist>'
        )
    else:
        placeholder = (
            f' placeholder="{html.escape(spec.placeholder)}"'
            if spec.placeholder
            else ""
        )
        control = (
            f'<input type="{html.escape(spec.field_type)}" '
            f'name="{html.escape(spec.name)}" value="{html.escape(value)}"{placeholder}>'
        )

    return f'<label>{label}{help_text}{control}</label>'


class ConfigUIHandler(BaseHTTPRequestHandler):
    """Serve the configuration form and handle simulation runs."""

    server_version = "Gem5ClassUI/1.0"

    def do_GET(self) -> None:
        content = self._render_page(
            {},
            "Ready to launch a simulation.",
            "",
            "",
            "",
        )
        self._send_response(content)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_data = self.rfile.read(length).decode("utf-8")
        parsed = urllib.parse.parse_qs(raw_data)

        form_values = {
            key: values[0] if values else ""
            for key, values in parsed.items()
        }

        for checkbox in CHECKBOX_NAMES:
            if checkbox not in form_values:
                form_values[checkbox] = ""

        yaml_text = ""
        stdout = ""
        stderr = ""
        stats = ""
        message = "Simulation launched successfully."
        is_error = False

        try:
            ordered_config, param_lines, extra_lines = _ordered_config_from_form(form_values)
            yaml_text = _config_to_yaml(ordered_config, param_lines, extra_lines)
            code, stdout, stderr = _run_simulation(yaml_text)
            stats = _collect_stats() if code == 0 else ""
            if code != 0:
                message = f"Simulation failed (exit code {code})."
                is_error = True
        except Exception as exc:
            message = f"Form processing failed: {exc}"
            is_error = True

        content = self._render_page(form_values, message, yaml_text, stdout, stats, stderr, is_error)
        self._send_response(content)

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write(
            "%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args)
        )

    def _send_response(self, html_body: str) -> None:
        payload = html_body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _render_page(
        self,
        form_values: Dict[str, str],
        message: str,
        yaml_text: str,
        stdout: str,
        stats: str,
        stderr: str = "",
        is_error: bool = False,
    ) -> str:
        sections_html = _render_sections(form_values)
        yaml_block = _html_escape_pre(yaml_text)
        stdout_block = _html_escape_pre(stdout)
        stderr_block = _html_escape_pre(stderr)
        stats_block = _html_escape_pre(stats)
        extra_lines = html.escape(form_values.get("extra_lines", ""))

        status_class = "status error" if is_error else "status ok"

        return textwrap.dedent(
            f"""\
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>gem5 class webui</title>
                <style>
                    body {{
                        font-family: sans-serif;
                        margin: 0;
                        padding: 0;
                        background: #f3f4f6;
                    }}
                    header {{
                        padding: 1rem 2rem;
                        background: #111827;
                        color: #fff;
                    }}
                    main {{
                        padding: 1.5rem 2rem 3rem;
                    }}
                    form {{
                        display: grid;
                        gap: 1rem;
                    }}
                    fieldset {{
                        border: 1px solid #d1d5db;
                        border-radius: 0.5rem;
                        padding: 1rem 1.5rem;
                        background: #fff;
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                        gap: 0.8rem 1.2rem;
                    }}
                    legend {{
                        font-weight: 600;
                        padding: 0 0.5rem;
                    }}
                    label {{
                        font-size: 0.95rem;
                        display: flex;
                        flex-direction: column;
                        gap: 0.25rem;
                    }}
                    label input,
                    label select {{
                        padding: 0.35rem 0.5rem;
                        border-radius: 0.375rem;
                        border: 1px solid #9ca3af;
                        font-size: 0.95rem;
                    }}
                    label input[type="checkbox"] {{
                        width: auto;
                        align-self: flex-start;
                    }}
                    .help {{
                        font-size: 0.75rem;
                        color: #6b7280;
                    }}
                    textarea {{
                        width: 100%;
                        min-height: 6rem;
                        border-radius: 0.375rem;
                        border: 1px solid #9ca3af;
                        padding: 0.5rem;
                        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                        font-size: 0.85rem;
                    }}
                    button {{
                        justify-self: start;
                        padding: 0.5rem 1rem;
                        border-radius: 0.5rem;
                        border: none;
                        background: #2563eb;
                        color: #fff;
                        font-size: 1rem;
                        cursor: pointer;
                    }}
                    button:hover {{
                        background: #1d4ed8;
                    }}
                    .status {{
                        padding: 0.75rem 1rem;
                        border-radius: 0.5rem;
                        font-weight: 500;
                        transition: background 0.2s ease, color 0.2s ease;
                    }}
                    .status.ok {{
                        background: #dcfce7;
                        color: #166534;
                    }}
                    .status.error {{
                        background: #fee2e2;
                        color: #991b1b;
                    }}
                    .status.running {{
                        background: #dbeafe;
                        color: #1e3a8a;
                    }}
                    h2 {{
                        margin-top: 2rem;
                        font-size: 1.2rem;
                    }}
                    pre {{
                        background: #111827;
                        color: #f9fafb;
                        padding: 1rem;
                        border-radius: 0.5rem;
                        overflow-x: auto;
                        font-size: 0.85rem;
                    }}
                    .grid-two {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                        gap: 1.2rem;
                    }}
                </style>
            </head>
            <body>
                <header>
                    <h1>gem5 class Web UI</h1>
                </header>
                <main>
                    <div class="{status_class}" id="status-msg">{html.escape(message)}</div>
                    <form method="post">
                        {sections_html}
                        <label>
                            Additional YAML lines
                            <div class="help">Appended to the generated config; ideal for quick custom overrides.</div>
                            <textarea name="extra_lines" placeholder="Example:&#10;ruby: true">{extra_lines}</textarea>
                        </label>
                        <button type="submit">Run gem5</button>
                    </form>
                    <section>
                        <h2>Generated YAML</h2>
                        {yaml_block or "<p>Submit the form to see the generated configuration.</p>"}
                    </section>
                    <section class="grid-two">
                        <div>
                            <h2>gem5 stdout</h2>
                            {stdout_block or "<p>Awaiting run.</p>"}
                        </div>
                        <div>
                            <h2>Stats summary</h2>
                            {stats_block or "<p>No stats yet.</p>"}
                        </div>
                    </section>
                    <section>
                        <h2>stderr</h2>
                        {stderr_block or "<p>stderr is empty.</p>"}
                    </section>
                </main>
                <script>
                    document.addEventListener("DOMContentLoaded", function () {{
                        var form = document.querySelector("form");
                        var statusBox = document.getElementById("status-msg");
                        if (!form || !statusBox) {{
                            return;
                        }}
                        form.addEventListener("submit", function () {{
                            statusBox.textContent = "Simulation running…";
                            statusBox.className = "status running";
                            var submit = form.querySelector('button[type="submit"]');
                            if (submit) {{
                                submit.disabled = true;
                                submit.textContent = "Running…";
                                submit.style.opacity = "0.7";
                                submit.style.cursor = "wait";
                            }}
                        }});
                    }});
                </script>
            </body>
            </html>
            """
        )


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ConfigUIHandler)
    print(f"Serving on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server…", flush=True)
    finally:
        server.server_close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simple web UI for configs/class flows")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT})")
    args = parser.parse_args(argv)

    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
