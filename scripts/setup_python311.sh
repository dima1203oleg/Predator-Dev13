#!/usr/bin/env bash
set -euo pipefail

echo "== setup_python311.sh =="
echo "This helper creates or guides creation of a Python 3.11 virtualenv for the project."

if command -v pyenv >/dev/null 2>&1; then
  PY_VERSION=${PY_VERSION:-3.11.4}
  echo "pyenv found. Ensuring Python ${PY_VERSION} is installed..."
  if ! pyenv versions --bare | grep -q "^${PY_VERSION}$"; then
    echo "Installing Python ${PY_VERSION} via pyenv (this may take a while)..."
    pyenv install "${PY_VERSION}"
  fi

  VENV_NAME=${VENV_NAME:-predator-venv-3.11}
  echo "Creating/ensuring virtualenv ${VENV_NAME}..."
  pyenv virtualenv "${PY_VERSION}" "${VENV_NAME}" || true
  echo
  echo "To activate the environment run:"
  echo "  pyenv activate ${VENV_NAME}"
  echo "Then install deps: pip install -r requirements-dev.txt"
  exit 0
fi

if command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 found on PATH. Creating venv at .venv311..."
  python3.11 -m venv .venv311
  echo "Activate it with: source .venv311/bin/activate"
  echo "Then: pip install -r requirements-dev.txt"
  exit 0
fi

echo "No pyenv and no python3.11 found."
echo "Install via Homebrew: brew install pyenv  # then follow pyenv setup instructions, or"
echo "Install Python 3.11 directly: brew install python@3.11"
exit 2
#!/usr/bin/env bash
set -euo pipefail

echo "== setup_python311.sh =="
echo "This helper creates or guides creation of a Python 3.11 virtualenv for the project."

if command -v pyenv >/dev/null 2>&1; then
  PY_VERSION=${PY_VERSION:-3.11.4}
  echo "pyenv found. Ensuring Python ${PY_VERSION} is installed..."
  if ! pyenv versions --bare | grep -q "^${PY_VERSION}$"; then
    echo "Installing Python ${PY_VERSION} via pyenv (this may take a while)..."
    pyenv install "${PY_VERSION}"
  fi

  VENV_NAME=${VENV_NAME:-predator-venv-3.11}
  echo "Creating/ensuring virtualenv ${VENV_NAME}..."
  pyenv virtualenv "${PY_VERSION}" "${VENV_NAME}" || true
  echo
  echo "To activate the environment run:"
  echo "  pyenv activate ${VENV_NAME}"
  echo "Then install deps: pip install -r requirements-dev.txt"
  exit 0
fi

if command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 found on PATH. Creating venv at .venv311..."
  python3.11 -m venv .venv311
  echo "Activate it with: source .venv311/bin/activate"
  echo "Then: pip install -r requirements-dev.txt"
  exit 0
fi

echo "No pyenv and no python3.11 found."
echo "Install via Homebrew: brew install pyenv  # then follow pyenv setup instructions, or"
echo "Install Python 3.11 directly: brew install python@3.11"
exit 2
