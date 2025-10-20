#!/bin/bash
set -e

# 第一个参数：配置文件
YAML_FILE=${1:-configs/class/config.yaml}
# 第二个参数：可选，覆盖 cmd
OVERRIDE_CMD=$2

GEM5_BIN="./build/X86/gem5.opt"
GEM5_SCRIPT="configs/class/class_test_se.py"

args=()
param_args=()

trim() {
    local s="$1"
    # 删除开头空白
    s="${s#"${s%%[![:space:]]*}"}"
    # 删除结尾空白
    s="${s%"${s##*[![:space:]]}"}"
    printf "%s" "$s"
}

while IFS= read -r line || [[ -n "$line" ]]; do
    # 去掉首尾空白
    line=$(trim "$line")
    # 跳过空行和注释
    if [[ -z "$line" || "${line:0:1}" == "#" ]]; then
        continue
    fi

    if [[ "$line" != *:* ]]; then
        echo "Warning: 忽略无法解析的配置行: $line" >&2
        continue
    fi

    key="${line%%:*}"
    value="${line#*:}"
    key=$(trim "$key")
    value=$(trim "$value")

    if [[ -z "$key" ]]; then
        continue
    fi

    # 支持 param_* 键，将其转成 --param
    if [[ "$key" =~ ^param ]]; then
        if [[ -n "$value" ]]; then
            param_args+=("$value")
        fi
        continue
    fi

    # 如果传了 OVERRIDE_CMD，就跳过 yaml 中的 cmd
    if [[ "$key" == "cmd" && -n "$OVERRIDE_CMD" ]]; then
        continue
    fi

    # 移除行尾注释
    value_no_comment="${value%%#*}"
    value=$(trim "$value_no_comment")

    if [[ -z "$value" ]]; then
        continue
    fi

    value_lower=$(printf "%s" "$value" | tr "[:upper:]" "[:lower:]")
    if [[ "$value_lower" == "true" ]]; then
        args+=(--"$key")
    elif [[ "$value_lower" == "false" ]]; then
        continue
    else
        args+=(--"$key" "$value")
    fi
done < "$YAML_FILE"

# 如果指定了覆盖 cmd，就加在最后
if [[ -n "$OVERRIDE_CMD" ]]; then
    args+=(--cmd "$OVERRIDE_CMD")
fi

# 附加 --param 覆盖
for p in "${param_args[@]}"; do
    args+=(--param "$p")
done

echo "$GEM5_BIN $GEM5_SCRIPT ${args[*]}"
# exec $GEM5_BIN $GEM5_SCRIPT "${args[@]}"
$GEM5_BIN $GEM5_SCRIPT "${args[@]}"

if [[ -z "${SKIP_PARSE_STATS:-}" ]]; then
    python3 configs/class/parse_stats.py
fi
