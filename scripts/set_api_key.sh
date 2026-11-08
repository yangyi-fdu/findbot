#!/usr/bin/env bash
# Save an LLM API key to ~/.findbot/<provider>.env (readable only by you; input is hidden).
#   bash scripts/set_api_key.sh zhipu     # Zhipu GLM key, looks like xxxxxxxx.yyyyyyyy
#   bash scripts/set_api_key.sh claude    # Anthropic key, starts with sk-ant-
provider=${1:-zhipu}
case "$provider" in
  zhipu)  var=ZAI_API_KEY;       check() { [[ "$1" == *.* ]]; };      hint="xxxxxxxx.yyyyyyyy" ;;
  claude) var=ANTHROPIC_API_KEY; check() { [[ "$1" == sk-ant-* ]]; }; hint="sk-ant-..." ;;
  *) echo "usage: bash set_api_key.sh zhipu|claude"; exit 1 ;;
esac
mkdir -p ~/.findbot
read -rsp "Paste your $provider API key (hidden), then press Enter: " k; echo
if ! check "$k"; then echo "That doesn't look like a $provider key ($hint); nothing saved."; exit 1; fi
umask 077
printf 'export %s=%q\n' "$var" "$k" > ~/.findbot/$provider.env
unset k
echo "Saved to ~/.findbot/$provider.env (mode $(stat -c %a ~/.findbot/$provider.env)). Open a new terminal to use it."
