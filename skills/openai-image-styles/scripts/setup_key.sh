#!/usr/bin/env bash
# One-time onboarding: store your OpenAI API key securely for the openai-image-styles skill.
# Run this in YOUR OWN terminal window, not through Claude, so the key never enters a chat transcript.
#
#   ~/.claude/skills/openai-image-styles/scripts/setup_key.sh          # regular API key
#   ~/.claude/skills/openai-image-styles/scripts/setup_key.sh --admin  # optional admin key (api.usage.read) for exact billing
#
# macOS: saved in your login Keychain (service "openai-image-styles"), encrypted and unlocked with your login.
# Other OSes: saved to ~/.config/openai-image-styles/<name> with permissions 600.
set -euo pipefail

SERVICE="openai-image-styles"
ACCOUNT="api-key"
LABEL="OpenAI API key"
if [[ "${1:-}" == "--admin" ]]; then ACCOUNT="admin-key"; LABEL="OpenAI admin key"; fi
CONFIG_DIR="${OPENAI_IMAGE_STYLES_HOME:-$HOME/.config/openai-image-styles}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -t 0 ]]; then
  echo "This script must be run interactively in your own terminal (it reads the key with hidden input)." >&2
  exit 1
fi

echo "Storing your $LABEL for the openai-image-styles skill."
echo "Create a key at https://platform.openai.com/api-keys (a project key restricted to the Images API is safest)."
echo "Typing is hidden: paste the key once and press Enter."
echo

read -r -s -p "Paste your $LABEL (input hidden), then press Enter: " KEY; echo
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
[[ -n "$KEY" ]] || { echo "No key entered." >&2; exit 1; }
# OpenAI keys are only letters, digits, '-' and '_'; anything else means a bad paste.
if [[ ! "$KEY" =~ ^sk-[A-Za-z0-9_-]+$ ]]; then echo "That doesn't look like an OpenAI key (should start with sk-). Nothing saved." >&2; exit 1; fi
echo "Read ${#KEY} characters (key ends ...${KEY: -4})."

if [[ "$(uname)" == "Darwin" ]]; then
  # Note: `security add-generic-password -w` (interactive prompt) truncates input at 128 chars,
  # which breaks ~164-char project keys. Instead feed the command to `security -i` on stdin:
  # printf is a bash builtin, so the key never appears in any process's argv or in shell history.
  printf 'add-generic-password -U -s %s -a %s -l "%s (openai-image-styles)" -w %s\n' \
    "$SERVICE" "$ACCOUNT" "$LABEL" "$KEY" | security -i >/dev/null
  echo "Saved to your login Keychain."
else
  umask 077
  mkdir -p "$CONFIG_DIR"
  printf '%s' "$KEY" > "$CONFIG_DIR/${ACCOUNT//-/_}"
  chmod 600 "$CONFIG_DIR/${ACCOUNT//-/_}"
  echo "Saved to $CONFIG_DIR/${ACCOUNT//-/_} (mode 600)."
fi
unset KEY

if [[ "$ACCOUNT" == "api-key" ]]; then
  echo
  python3 "$HERE/imagegen.py" check-key
fi
