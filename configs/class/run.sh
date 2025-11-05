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
cache_assoc_value=""
cache_is_read_only_value=""
cache_writeback_clean_value=""
num_cpus_value=""
caches_enabled=""
l2cache_enabled=""

normalise_bool() {
    local raw="${1:-}"
    local lowered
    lowered=$(printf "%s" "$raw" | tr "[:upper:]" "[:lower:]")
    case "$lowered" in
        ""|"inherit") return 1 ;;
        "true"|"1"|"yes"|"on") printf "%s" "True" ;;
        "false"|"0"|"no"|"off") printf "%s" "False" ;;
        *) return 1 ;;
    esac
}

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

    if [[ "$key" == "cache_assoc" ]]; then
        cache_assoc_value="$value"
        continue
    fi

    if [[ "$key" == "cache_is_read_only" ]]; then
        cache_is_read_only_value="$value"
        continue
    fi

    if [[ "$key" == "cache_writeback_clean" ]]; then
        cache_writeback_clean_value="$value"
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
    if [[ "$key" == "num-cpus" ]]; then
        num_cpus_value="$value"
    elif [[ "$key" == "caches" ]]; then
        caches_enabled="$value_lower"
    elif [[ "$key" == "l2cache" ]]; then
        l2cache_enabled="$value_lower"
    fi

    if [[ "$key" == "l3cache" ]]; then
        continue
    fi

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

if [[ -n "$cache_assoc_value" ]]; then
    if [[ "$caches_enabled" == "true" ]]; then
        args+=(--l1d_assoc "$cache_assoc_value" --l1i_assoc "$cache_assoc_value")
    fi
    if [[ "$l2cache_enabled" == "true" ]]; then
        args+=(--l2_assoc "$cache_assoc_value")
    fi
fi

if [[ -z "$num_cpus_value" ]]; then
    num_cpus_value="1"
fi

bool_value=""
if bool_value=$(normalise_bool "$cache_is_read_only_value"); then
    if [[ "$caches_enabled" == "true" ]]; then
        for ((i = 0; i < num_cpus_value; i++)); do
            param_args+=("system.cpu[$i].dcache.is_read_only=$bool_value")
            param_args+=("system.cpu[$i].icache.is_read_only=$bool_value")
        done
    fi
    if [[ "$l2cache_enabled" == "true" ]]; then
        param_args+=("system.l2.is_read_only=$bool_value")
    fi
fi

if bool_value=$(normalise_bool "$cache_writeback_clean_value"); then
    if [[ "$caches_enabled" == "true" ]]; then
        for ((i = 0; i < num_cpus_value; i++)); do
            param_args+=("system.cpu[$i].dcache.writeback_clean=$bool_value")
            param_args+=("system.cpu[$i].icache.writeback_clean=$bool_value")
        done
    fi
    if [[ "$l2cache_enabled" == "true" ]]; then
        param_args+=("system.l2.writeback_clean=$bool_value")
    fi
fi

# 附加 --param 覆盖
for p in "${param_args[@]}"; do
    args+=(--param "$p")
done

# 选择 gem5 可执行：优先使用构建产物，找不到则回退到预编译路径
if [[ ! -x "$GEM5_BIN" ]]; then
    if [[ -x "gem5-X86/bin/gem5.opt" ]]; then
        GEM5_BIN="gem5-X86/bin/gem5.opt"
    else
        echo "[error] 未找到 gem5 可执行文件：./build/X86/gem5.opt 或 gem5-X86/bin/gem5.opt" >&2
        exit 1
    fi
fi

echo "$GEM5_BIN $GEM5_SCRIPT ${args[*]}"
# exec $GEM5_BIN $GEM5_SCRIPT "${args[@]}"
$GEM5_BIN $GEM5_SCRIPT "${args[@]}"

if [[ -z "${SKIP_PARSE_STATS:-}" ]]; then
    python3 configs/class/parse_stats.py
fi
