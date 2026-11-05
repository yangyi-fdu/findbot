#!/usr/bin/env bash
# 保存 LLM API key 到 ~/.findbot/<provider>.env（只有你自己能读；输入时屏幕不显示）
#   bash set_api_key.sh zhipu     # 智谱 GLM，key 形如 xxxxxxxx.yyyyyyyy
#   bash set_api_key.sh claude    # Claude，key 以 sk-ant- 开头
provider=${1:-zhipu}
case "$provider" in
  zhipu)  var=ZAI_API_KEY;       check() { [[ "$1" == *.* ]]; };       hint="形如 xxxxxxxx.yyyyyyyy（中间有一个点）" ;;
  claude) var=ANTHROPIC_API_KEY; check() { [[ "$1" == sk-ant-* ]]; };  hint="以 sk-ant- 开头" ;;
  *) echo "用法: bash set_api_key.sh zhipu|claude"; exit 1 ;;
esac
mkdir -p ~/.findbot
read -rsp "粘贴你的 $provider API key（屏幕上不会显示），然后按回车: " k; echo
if ! check "$k"; then echo "看起来不像 $provider 的 key（应该$hint），没有保存。"; exit 1; fi
umask 077
printf 'export %s=%q\n' "$var" "$k" > ~/.findbot/$provider.env
unset k
echo "已保存到 ~/.findbot/$provider.env（权限 $(stat -c %a ~/.findbot/$provider.env)）。重新打开终端即可生效。"
