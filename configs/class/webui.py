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
DEBUG_ENABLED = False
COMMAND_DIR = REPO_ROOT / "tests" / "class" / "bin" / "x86"
EXPERIMENTS_DIR = REPO_ROOT / "configs" / "class" / "experiments"
MEMORY_TYPE_CHOICES = [
    "DDR3_1600_8x8",
    "DDR3_2133_8x8",
    "DDR4_2400_8x8",
    "DDR4_2400_16x4",
    "HBM_2000_4H_1x64",
    "SimpleMemory",
]
REPLACEMENT_POLICY_SUGGESTIONS = [
    "LRURP",
    "RandomRP",
    "FIFORP",
    "TreePLRURP",
    "MRURP",
    "LFURP",
    "BRRIPRP",
    "SecondChanceRP",
]
BOOL_SELECT_OPTIONS = ["inherit", "true", "false"]
ASSOC_KEYS = ["l1d_assoc", "l1i_assoc", "l2_assoc", "l3_assoc"]
# field_name -> (level, attribute, value_kind)
# level: l1d/l1i/l2/l3, attribute: BaseCache param, value_kind: 'bool' or 'string'
CACHE_PARAM_FIELDS = {
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
    ),
    FieldSpec(
        "num-cpus",
        "CPU cores",
        "number",
        "CPU",
        default=1,
    ),
    FieldSpec(
        "sys-clock",
        "System clock",
        "text",
        "CPU",
        default="1GHz",
    ),
    FieldSpec(
        "cpu-clock",
        "CPU clock",
        "text",
        "CPU",
        default="2GHz",
    ),
    FieldSpec(
        "mem-type",
        "Memory type",
        "select",
        "Memory",
        default="DDR3_1600_8x8",
        options=MEMORY_TYPE_CHOICES,
    ),
    FieldSpec(
        "mem-size",
        "Memory size",
        "text",
        "Memory",
        default="512MiB",
    ),
    FieldSpec(
        "mem-channels",
        "Memory channels",
        "number",
        "Memory",
    ),
    FieldSpec(
        "mem-channels-intlv",
        "Memory channel interleave",
        "number",
        "Memory",
    ),
    FieldSpec(
        "mem-ranks",
        "Memory ranks",
        "number",
        "Memory",
    ),
    FieldSpec(
        "mem_device_size",
        "DRAM device size",
        "text",
        "Memory",
        placeholder="512MiB",
    ),
    FieldSpec(
        "mem_device_bus_width",
        "DRAM device bus width (bits)",
        "number",
        "Memory",
        placeholder="8",
    ),
    FieldSpec(
        "mem_devices_per_rank",
        "Devices per rank",
        "number",
        "Memory",
        placeholder="8",
    ),
    FieldSpec(
        "mem_ranks_per_channel",
        "Ranks per channel",
        "number",
        "Memory",
        placeholder="2",
    ),
    FieldSpec(
        "mem_banks_per_rank",
        "Banks per rank",
        "number",
        "Memory",
        placeholder="8",
    ),
    FieldSpec(
        "mem_bank_groups_per_rank",
        "Bank groups per rank",
        "number",
        "Memory",
        placeholder="0",
    ),
    FieldSpec(
        "mem_page_policy",
        "Page policy",
        "select",
        "Memory",
        options=["open", "open_adaptive", "close", "close_adaptive"],
        default="open_adaptive",
    ),
    FieldSpec(
        "mem_param_overrides",
        "Advanced memory parameter",
        "textarea",
        "Memory",
        placeholder="system.mem_ctrl.dram.tCL=14\nsystem.mem_ctrl.dram.tRCD=14",
        help_text="See DRAMCtrl in src/mem/DRAMCtrl.py for advanced DRAM options.",
    ),
    FieldSpec(
        "caches",
        "Enable private L1 caches",
        "checkbox",
        "Cache",
        default=True,
    ),
    FieldSpec(
        "l2cache",
        "Enable shared L2 cache",
        "checkbox",
        "Cache",
        default=True,
    ),
    FieldSpec(
        "l3cache",
        "Enable shared L3 cache",
        "checkbox",
        "Cache",
        default=False,
    ),
    FieldSpec(
        "l1d_size",
        "L1D size",
        "text",
        "Cache",
        placeholder="64KiB",
    ),
    FieldSpec(
        "l1i_size",
        "L1I size",
        "text",
        "Cache",
        placeholder="32KiB",
    ),
    FieldSpec(
        "l2_size",
        "L2 size",
        "text",
        "Cache",
        placeholder="1MiB",
    ),
    FieldSpec(
        "l3_size",
        "L3 size",
        "text",
        "Cache",
        placeholder="32MiB",
    ),
    FieldSpec(
        "num-dirs",
        "Directory controllers",
        "number",
        "Cache",
        placeholder="1",
    ),
    FieldSpec(
        "num-l2caches",
        "L2 cache tiles",
        "number",
        "Cache",
        placeholder="1",
    ),
    FieldSpec(
        "num-l3caches",
        "L3 cache tiles",
        "number",
        "Cache",
        placeholder="1",
    ),
    FieldSpec(
        "cacheline_size",
        "Cache line",
        "number",
        "Cache",
        default=64,
    ),
    FieldSpec(
        "cache_assoc",
        "Cache associativity (ways)",
        "number",
        "Cache",
        placeholder="4",
    ),
    FieldSpec(
        "cache_replacement",
        "Cache replacement policy",
        "datalist",
        "Cache",
        options=REPLACEMENT_POLICY_SUGGESTIONS,
        placeholder="LRURP",
    ),
    FieldSpec(
        "cache_is_read_only",
        "Cache read-only",
        "select",
        "Cache",
        options=BOOL_SELECT_OPTIONS,
        default="inherit",
    ),
    FieldSpec(
        "cache_writeback_clean",
        "Cache writeback clean",
        "select",
        "Cache",
        options=BOOL_SELECT_OPTIONS,
        default="inherit",
    ),
    FieldSpec(
        "cache_param_overrides",
        "Cache parameter overrides",
        "textarea",
        "Cache",
        placeholder="system.cpu[0:4].dcache.writeback_clean=true\nsystem.l2.write_buffers=16",
    ),
    FieldSpec(
        "cmd",
        "Command",
        COMMAND_FIELD_TYPE,
        "Workload",
        default=DEFAULT_COMMAND,
        options=COMMAND_OPTIONS,
    ),
    FieldSpec(
        "options",
        "Command arguments",
        "text",
        "Workload",
        placeholder="e.g. 20000",
    ),
]


SECTION_ORDER = ["CPU", "Memory", "Cache", "Workload"]
CHECKBOX_NAMES = {spec.name for spec in FIELD_SPECS if spec.field_type == "checkbox"}
FIELD_NAME_SET = {spec.name for spec in FIELD_SPECS}


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


def _discover_experiment_configs() -> "OrderedDict[str, OrderedDict[str, List[str]]]":
    """
    Discover experiment YAML files, grouped by category and experiment name.

    Returns a nested dictionary: {category: {experiment_path: [config_paths]}}
    """
    # Category -> Experiment -> List of config paths
    experiments: "OrderedDict[str, OrderedDict[str, List[str]]]" = OrderedDict()
    if not EXPERIMENTS_DIR.is_dir():
        return experiments

    yaml_files = sorted(EXPERIMENTS_DIR.rglob("*.yaml"))
    for yaml_path in yaml_files:
        if not yaml_path.is_file():
            continue
        try:
            rel_repo_path = yaml_path.relative_to(REPO_ROOT)
            rel_exp_path = yaml_path.relative_to(EXPERIMENTS_DIR)
        except ValueError:
            continue

        parts = rel_exp_path.parts
        if len(parts) < 3:  # Expect category/experiment/config.yaml
            continue

        category, experiment_name = parts[0], parts[1]
        experiment_key = Path("configs", "class", "experiments", category, experiment_name)
        experiment_str = str(experiment_key)

        experiments.setdefault(category, OrderedDict())
        experiments[category].setdefault(experiment_str, [])
        experiments[category][experiment_str].append(str(rel_repo_path))

    # Sort configs within each experiment
    for category in experiments:
        for key in experiments[category]:
            experiments[category][key].sort()
        # Sort experiments within each category
        experiments[category] = OrderedDict(sorted(experiments[category].items()))

    # Sort top-level categories
    return OrderedDict(sorted(experiments.items()))


def _resolve_config_path(raw_path: str) -> Path:
    cleaned = raw_path.strip()
    if not cleaned:
        raise ValueError("Configuration file path must not be empty")

    candidate = Path(cleaned)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError("Configuration file must remain inside the repository") from exc

    if not candidate.is_file():
        raise FileNotFoundError(f"Configuration file not found: {candidate}")

    return candidate


def _load_form_values_from_yaml(path: Path) -> Dict[str, str]:
    cache_overrides: List[str] = []
    mem_overrides: List[str] = []
    extra_lines: List[str] = []
    form_values: Dict[str, str] = {}

    text = path.read_text()
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if ":" not in raw_line:
            extra_lines.append(raw_line.rstrip())
            continue

        key, _, value = raw_line.partition(":")
        key = key.strip()
        value = value.strip()

        if key.startswith("param_cache_"):
            if value:
                cache_overrides.append(value)
            continue
        if key.startswith("param_mem_"):
            if value:
                mem_overrides.append(value)
            continue

        if key in FIELD_NAME_SET:
            if key in CHECKBOX_NAMES:
                lowered = value.lower()
                form_values[key] = "true" if lowered in {"true", "1", "yes", "on"} else ""
            else:
                if key == "cmd":
                    form_values["cmd_raw"] = value
                    value = _normalize_cmd_value(value)
                form_values[key] = value
        else:
            extra_lines.append(raw_line.rstrip())

    form_values["cache_param_overrides"] = "\n".join(cache_overrides)
    form_values["mem_param_overrides"] = "\n".join(mem_overrides)
    form_values["extra_lines"] = "\n".join(extra_lines)

    return form_values


def _ordered_config_from_form(
    form_values: Dict[str, str]
) -> Tuple[OrderedDict[str, object], List[str], List[str], str]:
    config = OrderedDict()
    errors: List[str] = []
    cache_param_lines: List[str] = []
    mem_param_lines: List[str] = []
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

        if spec.name == "cmd":
            raw_cmd_input = form_values.get("cmd_raw", raw_value)
            trimmed = str(raw_cmd_input).strip()
            if trimmed:
                config[spec.name] = trimmed
            continue

        if spec.name == "cache_replacement":
            sanitized = _sanitize_replacement_policy(trimmed)
            if sanitized:
                config[spec.name] = sanitized
            continue

        if spec.field_type == "textarea":
            if spec.name == "cache_param_overrides":
                if trimmed:
                    for line in trimmed.splitlines():
                        candidate = line.strip()
                        if not candidate or candidate.startswith("#"):
                            continue
                        cache_param_lines.append(candidate)
                continue
            if spec.name == "mem_param_overrides":
                if trimmed:
                    for line in trimmed.splitlines():
                        candidate = line.strip()
                        if not candidate or candidate.startswith("#"):
                            continue
                        mem_param_lines.append(candidate)
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

    cache_param_lines.extend(_generate_cache_param_lines(config, cache_param_inputs))

    return config, cache_param_lines, mem_param_lines, extra_lines


def _config_to_yaml(
    config: OrderedDict[str, object],
    cache_param_lines: List[str],
    mem_param_lines: List[str],
    extra_lines: str,
) -> str:
    lines: List[str] = []
    for key, value in config.items():
        if isinstance(value, bool):
            yaml_value = "true" if value else "false"
        else:
            yaml_value = str(value)
        lines.append(f"{key}: {yaml_value}")
    for idx, param_line in enumerate(cache_param_lines):
        lines.append(f"param_cache_{idx}: {param_line}")
    for idx, param_line in enumerate(mem_param_lines):
        lines.append(f"param_mem_{idx}: {param_line}")
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


def _sanitize_replacement_policy(raw_value: object) -> str:
    text = str(raw_value).strip()
    if not text:
        return ""
    if text.endswith("()"):
        text = text[:-2]
    if "__import__(" in text:
        text = text.split(".")[-1]
    elif "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def _normalize_cmd_value(raw_value: object) -> str:
    """If multiple commands are separated by ';', keep the first non-empty."""
    text = str(raw_value).strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(";")]
    for part in parts:
        if not part:
            continue
        if COMMAND_OPTIONS and part in COMMAND_OPTIONS:
            return part
        return part
    return ""


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
            raw_value = form_values.get("cmd_raw") if spec.name == "cmd" else None
            if spec.name == "cmd":
                current_value = _normalize_cmd_value(raw_value if raw_value is not None else current_value)

            rows.append(_render_field(spec, current_value or "", raw_value))

        sections_html.append(
            f"<fieldset><legend>{html.escape(section)}</legend>{''.join(rows)}</fieldset>"
        )

    return "\n".join(sections_html)


def _render_field(spec: FieldSpec, value: str, raw_value: str | None = None) -> str:
    label = html.escape(spec.label)
    help_text = (
        f'<div class="help">{html.escape(spec.help_text)}</div>'
        if spec.help_text
        else ""
    )

    hidden_raw_html = ""
    if spec.name == "cmd":
        hidden_raw_html = (
            f'<input type="hidden" name="cmd_raw" value="{html.escape(raw_value or value)}">'
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

    return f'<label>{label}{help_text}{control}{hidden_raw_html}</label>'


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

        raw_cmd_field = form_values.get("cmd_raw", "")
        raw_cmd = form_values.get("cmd", "")
        form_values["cmd_raw"] = raw_cmd_field or raw_cmd
        # Keep only the first command if multiple are provided with semicolons for UI selection.
        form_values["cmd"] = _normalize_cmd_value(form_values.get("cmd_raw", ""))

        for checkbox in CHECKBOX_NAMES:
            if checkbox not in form_values:
                form_values[checkbox] = ""

        action = (
            form_values.get("action_override")
            or form_values.get("action")
            or ""
        )

        form_values["action_override"] = ""

        yaml_text = ""
        stdout = ""
        stderr = ""
        stats = ""
        message = "Simulation launched successfully."
        is_error = False

        if action == "select_category":
            picked = form_values.get("experiment_category", "")
            form_values["experiment_choice"] = ""
            form_values["config_path"] = ""
            if picked:
                message = f"Category {picked} selected."
            else:
                message = "Category selection cleared."
            content = self._render_page(
                form_values, message, yaml_text, stdout, stats, stderr, is_error
            )
            self._send_response(content)
            return

        if action == "select_experiment":
            picked = form_values.get("experiment_choice", "")
            form_values["config_path"] = ""
            if picked:
                message = f"Experiment {Path(picked).name} selected."
            else:
                message = "Experiment selection cleared."
            content = self._render_page(
                form_values, message, yaml_text, stdout, stats, stderr, is_error
            )
            self._send_response(content)
            return

        if action == "load":
            config_path_text = form_values.get("config_path", "")
            if not config_path_text.strip():
                message = "Select a configuration file before loading."
                is_error = True
                content = self._render_page(
                    form_values, message, yaml_text, stdout, stats, stderr, is_error
                )
                self._send_response(content)
                return
            try:
                config_path = _resolve_config_path(config_path_text)
                loaded_values = _load_form_values_from_yaml(config_path)
                form_values.update(loaded_values)
                yaml_text = config_path.read_text()
                rel_path = config_path.relative_to(REPO_ROOT)
                message = f"Loaded configuration file {rel_path}"
                form_values["config_path"] = str(rel_path)

                rel_parts = rel_path.parts
                if (
                    len(rel_parts) >= 4
                    and rel_parts[0] == "configs"
                    and rel_parts[1] == "class"
                    and rel_parts[2] == "experiments"
                ):
                    category, experiment_name = rel_parts[3], rel_parts[4]
                    form_values["experiment_category"] = category
                    form_values["experiment_choice"] = str(Path(*rel_parts[:5]))

            except Exception as exc:
                message = f"Failed to read configuration: {exc}"
                is_error = True
            content = self._render_page(form_values, message, yaml_text, stdout, stats, stderr, is_error)
            self._send_response(content)
            return

        try:
            ordered_config, cache_param_lines, mem_param_lines, extra_lines = _ordered_config_from_form(form_values)
            yaml_text = _config_to_yaml(ordered_config, cache_param_lines, mem_param_lines, extra_lines)
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

        selected_category = form_values.get("experiment_category", "")
        selected_experiment = form_values.get("experiment_choice", "")
        selected_config_path = form_values.get("config_path", "")
        experiment_configs = _discover_experiment_configs()

        # Category selection
        category_select_html = ""
        if experiment_configs:
            cat_options: List[str] = []
            placeholder_selected = " selected" if not selected_category else ""
            cat_options.append(
                f'<option value=""{placeholder_selected}>Select category…</option>'
            )
            for cat_name in experiment_configs.keys():
                escaped = html.escape(cat_name)
                selected = " selected" if cat_name == selected_category else ""
                cat_options.append(
                    f'<option value="{escaped}"{selected}>{escaped}</option>'
                )
            category_select_html = (
                f'<select name="experiment_category">{"".join(cat_options)}</select>'
            )

        # Experiment selection
        experiment_select_html = ""
        if selected_category and selected_category in experiment_configs:
            exp_options: List[str] = []
            placeholder_selected = " selected" if not selected_experiment else ""
            exp_options.append(
                f'<option value=""{placeholder_selected}>Select experiment…</option>'
            )
            for exp_path in experiment_configs[selected_category].keys():
                escaped_path = html.escape(exp_path)
                display_name = html.escape(Path(exp_path).name)
                selected = " selected" if exp_path == selected_experiment else ""
                exp_options.append(
                    f'<option value="{escaped_path}"{selected}>{display_name}</option>'
                )
            experiment_select_html = (
                f'<select name="experiment_choice">{"".join(exp_options)}</select>'
            )

        # Config selection
        config_select_html = ""
        if (
            selected_category
            and selected_experiment
            and selected_category in experiment_configs
            and selected_experiment in experiment_configs[selected_category]
        ):
            config_options: List[str] = []
            placeholder_selected = " selected" if not selected_config_path else ""
            config_options.append(
                f'<option value=""{placeholder_selected}>Select configuration…</option>'
            )
            for path in experiment_configs[selected_category][selected_experiment]:
                escaped_value = html.escape(path)
                display_name = html.escape(Path(path).name)
                selected = " selected" if path == selected_config_path else ""
                config_options.append(
                    f'<option value="{escaped_value}"{selected}>{display_name}</option>'
                )
            config_select_html = (
                f'<select name="config_path">{"".join(config_options)}</select>'
            )

        status_class = "status error" if is_error else "status ok"

        if DEBUG_ENABLED:
            yaml_section_html = textwrap.dedent(
                f"""\
                <section>
                    <h2>Generated YAML</h2>
                    {yaml_block or "<p>Submit the form to see the generated configuration.</p>"}
                    <div>
                        <h3>Additional YAML lines</h3>
                        <textarea name="extra_lines" placeholder="Example:&#10;ruby: true">{extra_lines}</textarea>
                    </div>
                </section>
                """
            )
        else:
            yaml_section_html = ""

        if DEBUG_ENABLED:
            run_outputs_html = textwrap.dedent(
                f"""\
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
                """
            )
        else:
            run_outputs_html = textwrap.dedent(
                f"""\
                <section>
                    <h2>Stats summary</h2>
                    {stats_block or "<p>No stats yet.</p>"}
                </section>
                """
            )

        return textwrap.dedent(
            f"""\
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>gem5 class webui</title>
                <style>
                    :root {{
                        --bg: linear-gradient(135deg, #f8fafc 0%, #eef2f7 45%, #e5ebf3 100%);
                        --card: #ffffff;
                        --muted: #6b7280;
                        --border: #e5e7eb;
                        --accent: #2563eb;
                        --accent-strong: #0ea5e9;
                        --ok: #16a34a;
                        --error: #dc2626;
                        --running: #d97706;
                        --text: #0f172a;
                        --heading: #0b1220;
                        --shadow: 0 14px 48px rgba(15, 23, 42, 0.12);
                    }}
                    * {{ box-sizing: border-box; }}
                    body {{
                        font-family: "Inter", "Segoe UI", "Helvetica Neue", sans-serif;
                        margin: 0;
                        padding: 0;
                        min-height: 100vh;
                        background: var(--bg);
                        color: var(--text);
                    }}
                    header {{
                        padding: 1.25rem 2rem;
                        background: rgba(255, 255, 255, 0.85);
                        backdrop-filter: blur(10px);
                        border-bottom: 1px solid var(--border);
                        box-shadow: var(--shadow);
                    }}
                    header h1 {{
                        margin: 0;
                        font-size: 1.6rem;
                        letter-spacing: 0.2px;
                        color: var(--heading);
                    }}
                    main {{
                        padding: 2rem 1.5rem 3rem;
                        max-width: 1440px;
                        margin: 0 auto;
                        display: flex;
                        flex-direction: column;
                        gap: 1.2rem;
                    }}
                    form {{
                        display: grid;
                        gap: 1rem;
                    }}
                    .load-config {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                        gap: 0.9rem 1rem;
                        align-items: end;
                        background: var(--card);
                        border: 1px solid var(--border);
                        border-radius: 0.9rem;
                        padding: 1rem 1.25rem;
                        box-shadow: var(--shadow);
                    }}
                    .load-config label {{
                        margin: 0;
                    }}
                    .load-config p {{
                        margin: 0;
                        font-size: 0.9rem;
                        color: var(--muted);
                    }}
                    fieldset {{
                        border: 1px solid var(--border);
                        border-radius: 0.95rem;
                        padding: 1rem 1.25rem;
                        background: var(--card);
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                        gap: 0.9rem 1.1rem;
                        box-shadow: var(--shadow);
                    }}
                    legend {{
                        font-weight: 700;
                        padding: 0 0.6rem;
                        color: var(--heading);
                        letter-spacing: 0.1px;
                    }}
                    label {{
                        font-size: 0.95rem;
                        display: flex;
                        flex-direction: column;
                        gap: 0.35rem;
                        color: var(--text);
                    }}
                    label input,
                    label select {{
                        padding: 0.55rem 0.65rem;
                        border-radius: 0.55rem;
                        border: 1px solid var(--border);
                        font-size: 0.95rem;
                        background: #f8fafc;
                        color: var(--text);
                        outline: none;
                        transition: border 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
                    }}
                    label input:focus,
                    label select:focus,
                    textarea:focus {{
                        border-color: var(--accent);
                        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
                        background: #ffffff;
                    }}
                    label input[type="checkbox"] {{
                        width: auto;
                        align-self: flex-start;
                        accent-color: var(--accent);
                        box-shadow: none;
                    }}
                    .help {{
                        font-size: 0.82rem;
                        color: var(--muted);
                        line-height: 1.3;
                    }}
                    textarea {{
                        width: 100%;
                        min-height: 7rem;
                        border-radius: 0.65rem;
                        border: 1px solid var(--border);
                        padding: 0.7rem;
                        background: #f8fafc;
                        color: var(--text);
                        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                        font-size: 0.9rem;
                        transition: border 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
                    }}
                    button {{
                        justify-self: start;
                        padding: 0.65rem 1.3rem;
                        border-radius: 0.95rem;
                        border: 1px solid transparent;
                        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
                        color: #fff;
                        font-size: 1rem;
                        font-weight: 700;
                        cursor: pointer;
                        letter-spacing: 0.1px;
                        transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
                        box-shadow: 0 10px 26px rgba(37, 99, 235, 0.25);
                    }}
                    button:hover {{
                        transform: translateY(-1px);
                        filter: brightness(1.03);
                    }}
                    button:active {{
                        transform: translateY(0);
                        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.2);
                    }}
                    .status {{
                        padding: 0.95rem 1.1rem;
                        border-radius: 0.95rem;
                        font-weight: 600;
                        border: 1px solid var(--border);
                        background: var(--card);
                        box-shadow: var(--shadow);
                        display: flex;
                        align-items: center;
                        gap: 0.5rem;
                    }}
                    .status.ok {{
                        border-color: rgba(22, 163, 74, 0.35);
                        color: var(--ok);
                    }}
                    .status.error {{
                        border-color: rgba(220, 38, 38, 0.35);
                        color: var(--error);
                    }}
                    .status.running {{
                        border-color: rgba(217, 119, 6, 0.35);
                        color: var(--running);
                    }}
                    h2 {{
                        margin-top: 1.4rem;
                        font-size: 1.2rem;
                        color: var(--heading);
                        letter-spacing: 0.1px;
                    }}
                    pre {{
                        background: #0f172a;
                        color: #e2e8f0;
                        padding: 1rem 1.1rem;
                        border-radius: 0.8rem;
                        overflow-x: auto;
                        font-size: 0.9rem;
                        border: 1px solid #1f2937;
                        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
                        max-height: 420px;
                        overflow-y: auto;
                        white-space: pre-wrap;
                        word-break: break-word;
                    }}
                    section {{
                        background: var(--card);
                        border: 1px solid var(--border);
                        border-radius: 0.95rem;
                        padding: 1.1rem 1.3rem;
                        box-shadow: var(--shadow);
                    }}
                    .grid-two {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                        gap: 1rem;
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
                        <input type="hidden" name="action_override" value="{html.escape(form_values.get('action_override', ''))}">
                        <div class="load-config">
                            <label>
                                Experiment Category
                                {category_select_html or '<p>No experiment categories found.</p>'}
                            </label>
                            <label>
                                Specific Experiment
                                {experiment_select_html or '<p>Select a category first.</p>'}
                            </label>
                            <label>
                                Load YAML Config
                                {config_select_html or '<p>Select an experiment first.</p>'}
                            </label>
                        </div>
                        {sections_html}
                        <button type="submit" name="action" value="run">Run gem5</button>
                    </form>
                    {yaml_section_html}
                    {run_outputs_html}
                </main>
                <script>
                    document.addEventListener("DOMContentLoaded", function () {{
                        var form = document.querySelector("form");
                        var statusBox = document.getElementById("status-msg");
                        var actionOverride = form ? form.querySelector('input[name="action_override"]') : null;
                        var categorySelect = form ? form.querySelector('select[name="experiment_category"]') : null;
                        var experimentSelect = form ? form.querySelector('select[name="experiment_choice"]') : null;
                        var configSelect = form ? form.querySelector('select[name="config_path"]') : null;
                        var cmdSelect = form ? form.querySelector('[name="cmd"]') : null;
                        var cmdRawInput = form ? form.querySelector('input[name="cmd_raw"]') : null;

                        if (!form || !statusBox || !actionOverride) {{
                            return;
                        }}

                        if (categorySelect) {{
                            categorySelect.addEventListener("change", function () {{
                                actionOverride.value = "select_category";
                                if (experimentSelect) {{ experimentSelect.selectedIndex = 0; }}
                                if (configSelect) {{ configSelect.selectedIndex = 0; }}
                                form.submit();
                            }});
                        }}

                        if (experimentSelect) {{
                            experimentSelect.addEventListener("change", function () {{
                                actionOverride.value = "select_experiment";
                                if (configSelect) {{ configSelect.selectedIndex = 0; }}
                                form.submit();
                            }});
                        }}

                        if (configSelect) {{
                            configSelect.addEventListener("change", function () {{
                                if (!configSelect.value) {{
                                    return;
                                }}
                                actionOverride.value = "load";
                                form.submit();
                            }});
                        }}

                        if (cmdSelect && cmdRawInput) {{
                            cmdSelect.addEventListener("change", function () {{
                                cmdRawInput.value = cmdSelect.value;
                            }});
                        }}

                        form.addEventListener("submit", function (event) {{
                            var submitter = event.submitter;
                            if (cmdSelect && cmdRawInput && !cmdRawInput.value) {{
                                cmdRawInput.value = cmdSelect.value;
                            }}
                            if (!submitter || submitter.value !== "run") {{
                                return;
                            }}
                            statusBox.textContent = "Simulation running…";
                            statusBox.className = "status running";
                            submitter.disabled = true;
                            submitter.textContent = "Running…";
                            submitter.style.opacity = "0.7";
                            submitter.style.cursor = "wait";
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
    global DEBUG_ENABLED

    parser = argparse.ArgumentParser(description="Simple web UI for configs/class flows")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="Show stdout/stderr output in UI")
    args = parser.parse_args(argv)

    DEBUG_ENABLED = args.debug

    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
