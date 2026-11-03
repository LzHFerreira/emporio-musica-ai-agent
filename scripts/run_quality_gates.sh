#!/usr/bin/env bash
set -uo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/emporio-uv-cache}"
failure_dir="$(mktemp -d)"
failed=0

cleanup() { rm -rf "$failure_dir"; }
trap cleanup EXIT

run_gate() {
    local name="$1"
    shift
    local output="$failure_dir/$name"
    printf '\n[gate] %s\n' "$name"
    if "$@" >"$output" 2>&1; then
        printf '[gate] %s: PASS\n' "$name"
        cat "$output"
        return
    fi
    printf '[gate] %s: FAIL\n' "$name" >&2
    cat "$output" >&2
    failed=1
}

run_gate ruff-format uv run --locked ruff format --check
run_gate ruff-lint uv run --locked ruff check emporio manage.py scripts
run_gate ty uv run --locked ty check --python .venv emporio manage.py scripts
run_gate basedpyright uv run --locked basedpyright --level error
run_gate mypy uv run --locked mypy .
run_gate pydoclint uv run --locked pydoclint .
run_gate pytest-coverage uv run --locked pytest -v
run_gate semgrep-pro bash scripts/run_semgrep_sources.sh
run_gate import-linter uv run --locked lint-imports
run_gate radon-loc uv run --locked python scripts/check_code_size.py
run_gate django-check uv run --locked python manage.py check
run_gate migration-drift uv run --locked python manage.py makemigrations --check --dry-run

exit "$failed"
