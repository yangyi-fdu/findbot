#!/usr/bin/env bash
# 保存 Claude API key 到 ~/.findbot/anthropic.env（只有你自己能读；输入时屏幕不显示）
mkdir -p ~/.findbot
read -rsp "粘贴你的 Claude API key（屏幕上不会显示），然后按回车: " k; echo
case "$k" in
  sk-ant-*) ;;
  *) echo "看起来不像 Claude 的 key（应该以 sk-ant- 开头），没有保存。"; exit 1 ;;
esac
umask 077
printf 'export ANTHROPIC_API_KEY=%q\n' "$k" > ~/.findbot/anthropic.env
unset k
echo "已保存到 ~/.findbot/anthropic.env（权限 $(stat -c %a ~/.findbot/anthropic.env)）。重新打开终端即可生效。"
