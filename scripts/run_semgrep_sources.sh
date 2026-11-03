#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scan_root="$(mktemp -d)"
trap 'rm -rf "$scan_root"' EXIT

cp "$repo_root/manage.py" "$scan_root/manage.py"
while IFS= read -r source_path; do
    target_path="$scan_root/$source_path"
    mkdir -p "$(dirname "$target_path")"
    cp "$repo_root/$source_path" "$target_path"
done < <(cd "$repo_root" && rg --files emporio scripts tests -g '*.py' -g '*.sh')

cd "$repo_root"
uv run --locked semgrep scan \
    --config auto \
    --pro \
    --error \
    --no-git-ignore \
    --scan-unknown-extensions \
    --max-target-bytes 0 \
    --timeout-threshold 0 \
    "$scan_root"
