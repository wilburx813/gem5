#!/bin/bash
set -e

# 第一个参数：配置文件
YAML_FILE=${1:-configs/class/config.yaml}
# 第二个参数：可选，覆盖 cmd
OVERRIDE_CMD=$2

GEM5_BIN="./build/X86/gem5.opt"
GEM5_SCRIPT="configs/class/class_test_se.py"

args=()

while IFS=":" read -r key value; do
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    if [[ -z "$key" || "$key" =~ ^# ]]; then
        continue
    fi

    # 如果传了 OVERRIDE_CMD，就跳过 yaml 中的 cmd
    if [[ "$key" == "cmd" && -n "$OVERRIDE_CMD" ]]; then
        continue
    fi

    if [[ "$value" == "true" ]]; then
        args+=(--"$key")
    elif [[ "$value" == "false" || -z "$value" ]]; then
        continue
    else
        args+=(--"$key" "$value")
    fi
done < "$YAML_FILE"

# 如果指定了覆盖 cmd，就加在最后
if [[ -n "$OVERRIDE_CMD" ]]; then
    args+=(--cmd "$OVERRIDE_CMD")
fi

echo "$GEM5_BIN $GEM5_SCRIPT ${args[*]}"
# exec $GEM5_BIN $GEM5_SCRIPT "${args[@]}"
$GEM5_BIN $GEM5_SCRIPT "${args[@]}"

if [[ -z "${SKIP_PARSE_STATS:-}" ]]; then
    python3 configs/class/parse_stats.py
fi
