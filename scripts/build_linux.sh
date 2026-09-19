#!/usr/bin/env bash
# Build the Linux x86_64 one-file AutoTyper executable from a checked-out tree.
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-"${project_dir}/.venv-build/bin/python"}"

if [[ ! -x "${python_bin}" ]]; then
    printf 'Build Python not found or not executable: %s\n' "${python_bin}" >&2
    printf 'Set PYTHON_BIN to a Python environment with PyInstaller installed.\n' >&2
    exit 1
fi

cd "${project_dir}"
exec "${python_bin}" -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "${project_dir}/dist" \
    --workpath "${project_dir}/build/linux" \
    "${project_dir}/packaging/autotyper.spec"
