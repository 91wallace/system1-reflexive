#!/usr/bin/env bash
# ==============================================================================
# System 1 Reflexive - Universal Global Installer
# Configures CLI, MCP Server, and Agent Skills in one command.
# ==============================================================================
set -e

INSTALL_DIR="${HOME}/.system1-reflexive"
BIN_DIR="${HOME}/.local/bin"

echo "=== [System 1 Reflexive Engine Installer] ==="

# 1. Ensure directory structure
mkdir -p "${INSTALL_DIR}"
mkdir -p "${BIN_DIR}"

# 2. Copy core files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "${SCRIPT_DIR}"/* "${INSTALL_DIR}/" 2>/dev/null || true

# 3. Create global CLI executable wrapper
cat << 'EOF' > "${BIN_DIR}/system1"
#!/usr/bin/env bash
INSTALL_PATH="${HOME}/.system1-reflexive"
python3 "${INSTALL_PATH}/engine.py" "$@"
EOF
chmod +x "${BIN_DIR}/system1"

# 4. Configure MCP definitions if Antigravity or Claude is present
AGY_MCP_DIR="${HOME}/.gemini/antigravity-cli/mcp/system1"
if [ -d "${HOME}/.gemini/antigravity-cli" ]; then
    mkdir -p "${AGY_MCP_DIR}"
    if [ -d "${SCRIPT_DIR}/mcp" ]; then
        cp -r "${SCRIPT_DIR}/mcp"/* "${AGY_MCP_DIR}/" 2>/dev/null || true
    fi
    # Link global engine
    ln -sfn "${INSTALL_DIR}" "${HOME}/.gemini/antigravity-cli/system1_global"
fi

# 5. Configure Skills if Agent directory exists
AGENTS_DIR="${HOME}/.agents/skills/system1"
if [ -d "${HOME}/.agents" ]; then
    mkdir -p "${AGENTS_DIR}"
    if [ -f "${SCRIPT_DIR}/SKILL.md" ]; then
        cp "${SCRIPT_DIR}/SKILL.md" "${AGENTS_DIR}/" 2>/dev/null || true
    fi
fi

echo "[✓] System 1 instalado com sucesso!"
echo "    • CLI: ${BIN_DIR}/system1"
echo "    • Core: ${INSTALL_DIR}"
echo ""
echo "Execute: system1 classify 'sua instrução aqui'"
