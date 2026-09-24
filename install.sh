#!/usr/bin/env bash
# ==============================================================================
# System 1 Reflexive - Universal Shell Installer
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Executa o instalador Python inteligente com suporte a argumentos ou modo interativo
python3 "${SCRIPT_DIR}/src/installer.py" "$@"
