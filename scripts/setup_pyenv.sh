#!/usr/bin/env bash
set -euo pipefail

echo "== setup_pyenv.sh =="
echo "Helper to guide installing pyenv and Python 3.11, and to create a virtualenv for the project."

PY_VERSION=${PY_VERSION:-3.11.4}
VENV_NAME=${VENV_NAME:-predator-venv-3.11}
DRY_RUN=1

usage(){
  cat <<EOF
Usage: $0 [--install]

Options:
  --install   Actually run installation commands (pyenv install / pyenv virtualenv). By default the script only prints recommended commands.
  --help      Show this help.

This script is conservative: it will not modify your system unless you pass --install.
EOF
}

if [[ ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

if [[ ${1:-} == "--install" ]]; then
  DRY_RUN=0
fi

if ! command -v pyenv >/dev/null 2>&1; then
  echo "pyenv not found. Recommended install steps (macOS/Homebrew):"
  echo "  brew update && brew install pyenv"
  echo "Then follow pyenv post-install steps (shell init)."
  echo
  echo "If you prefer not to use pyenv, install Python 3.11 (e.g. brew install python@3.11) and use setup_python311.sh"
  exit 1
fi

echo "pyenv detected. Target Python: ${PY_VERSION}, virtualenv name: ${VENV_NAME}"

if pyenv versions --bare | grep -q "^${PY_VERSION}$"; then
  echo "Python ${PY_VERSION} already installed in pyenv."
else
  echo "Python ${PY_VERSION} is not installed under pyenv."
  echo "Command to install: pyenv install ${PY_VERSION}"
  if [[ $DRY_RUN -eq 0 ]]; then
    echo "Running: pyenv install ${PY_VERSION}"
    pyenv install "${PY_VERSION}"
  fi
fi

if pyenv virtualenvs --bare | grep -q "^${VENV_NAME}$"; then
  echo "Virtualenv ${VENV_NAME} already exists. To use it:"
  echo "  pyenv activate ${VENV_NAME}"
else
  echo "Virtualenv ${VENV_NAME} does not exist. Command to create: pyenv virtualenv ${PY_VERSION} ${VENV_NAME}"
  if [[ $DRY_RUN -eq 0 ]]; then
    echo "Creating virtualenv: pyenv virtualenv ${PY_VERSION} ${VENV_NAME}"
    pyenv virtualenv "${PY_VERSION}" "${VENV_NAME}" || true
  fi
fi

echo
echo "Next steps (after activation):"
echo "  pip install -r requirements-dev.txt"
echo "  pytest -q --maxfail=1"

if [[ $DRY_RUN -eq 1 ]]; then
  echo
  echo "Run with --install to perform the actual pyenv install/virtualenv creation."
fi
