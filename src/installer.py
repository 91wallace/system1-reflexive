#!/usr/bin/env python3
"""
Universal Installer & Environment Configurator for System 1 Reflexive.
Configura isolamento de dados (.system1/), servidor MCP stdio, Skills e Agentes.
Suporta instalação Global, Local (por projeto) ou Completa.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
HOME_DIR = os.path.expanduser("~")

INSTALL_GLOBAL_DIR = os.path.join(HOME_DIR, ".system1-reflexive")
BIN_DIR = os.path.join(HOME_DIR, ".local", "bin")
GEMINI_CONFIG_DIR = os.path.join(HOME_DIR, ".gemini", "config")
GEMINI_MCP_FILE = os.path.join(GEMINI_CONFIG_DIR, "mcp_config.json")
GEMINI_CLI_MCP_DIR = os.path.join(HOME_DIR, ".gemini", "antigravity-cli", "mcp", "system1")
GLOBAL_AGENTS_SKILL_DIR = os.path.join(HOME_DIR, ".agents", "skills", "system1")


def print_banner():
    print("\n" + "=" * 65)
    print(" 🚀  SYSTEM 1 REFLEXIVE - INSTALADOR E CONFIGURADOR AUTOMÁTICO")
    print("=" * 65)


def setup_local_project(project_path: str):
    """Configura o isolamento de dados e assets no projeto especificado."""
    print(f"\n[+] Configurando ambiente local no projeto: {project_path}")
    
    # 1. Diretório isolado de dados pessoais e de sessão
    data_dir = os.path.join(project_path, ".system1")
    os.makedirs(data_dir, exist_ok=True)
    print(f"  [✓] Diretório de dados pessoais/sessão criado: {data_dir}")

    # 2. Inicializa templates de memória se não existirem
    template_mem = os.path.join(PROJECT_ROOT, "data", "default_memory.json")
    local_mem = os.path.join(data_dir, "memory.json")
    if not os.path.exists(local_mem) and os.path.exists(template_mem):
        shutil.copy(template_mem, local_mem)
        print(f"  [✓] Memória inicial instanciada: {local_mem}")

    template_sess = os.path.join(PROJECT_ROOT, "data", "default_session_memory.json")
    local_sess = os.path.join(data_dir, "session_working_memory.json")
    if not os.path.exists(local_sess) and os.path.exists(template_sess):
        shutil.copy(template_sess, local_sess)
        print(f"  [✓] Memória de trabalho de sessão criada: {local_sess}")

    local_prof = os.path.join(data_dir, "user_profile.json")
    if not os.path.exists(local_prof):
        with open(local_prof, "w", encoding="utf-8") as f:
            json.dump({
                "user_preferences": {},
                "global_constraints": [],
                "preferred_languages": ["pt-BR", "en"],
                "safety_strictness": "high"
            }, f, indent=2, ensure_ascii=False)
        print(f"  [✓] Perfil de usuário criado: {local_prof}")

    # 3. Configura .agents/skills e .agents/rules locais
    proj_agent_skills = os.path.join(project_path, ".agents", "skills", "system1")
    proj_agent_rules = os.path.join(project_path, ".agents", "rules")
    os.makedirs(proj_agent_skills, exist_ok=True)
    os.makedirs(proj_agent_rules, exist_ok=True)

    skill_src = os.path.join(PROJECT_ROOT, "SKILL.md")
    if os.path.exists(skill_src):
        shutil.copy(skill_src, os.path.join(proj_agent_skills, "SKILL.md"))
        print(f"  [✓] Skill configurada em .agents/skills/system1/SKILL.md")

    rule_src = os.path.join(PROJECT_ROOT, "agents", "rules", "system1_reflexive.md")
    if os.path.exists(rule_src):
        shutil.copy(rule_src, os.path.join(proj_agent_rules, "system1_reflexive.md"))
        print(f"  [✓] Regra configurada em .agents/rules/system1_reflexive.md")

    # 4. Atualiza .gitignore local para proteger .system1/
    gitignore_path = os.path.join(project_path, ".gitignore")
    ignore_entries = [
        "\n# System 1 Local Isolated Data & Personal Sessions",
        ".system1/",
        "session_working_memory.json",
        "memory.local.json",
        "user_profile.json",
        "*.local.json\n"
    ]
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        if ".system1/" not in content:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n".join(ignore_entries))
            print(f"  [✓] .gitignore atualizado para proteger .system1/")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ignore_entries))
        print(f"  [✓] .gitignore criado com proteção de dados pessoais")


def setup_global_system(target_server_script: str):
    """Configura o System 1 globalmente no sistema e na IDE/MCP."""
    print(f"\n[+] Configurando instalação global no sistema...")

    # 1. Cria diretórios base
    os.makedirs(INSTALL_GLOBAL_DIR, exist_ok=True)
    os.makedirs(BIN_DIR, exist_ok=True)

    # 2. Sincroniza arquivos do core para ~/.system1-reflexive/
    for item in os.listdir(PROJECT_ROOT):
        if item in (".git", ".system1", "__pycache__"):
            continue
        src = os.path.join(PROJECT_ROOT, item)
        dst = os.path.join(INSTALL_GLOBAL_DIR, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    print(f"  [✓] Core sincronizado em: {INSTALL_GLOBAL_DIR}")

    # 3. Cria CLI executável em ~/.local/bin/system1
    cli_wrapper = os.path.join(BIN_DIR, "system1")
    with open(cli_wrapper, "w", encoding="utf-8") as f:
        f.write(f"""#!/usr/bin/env bash
INSTALL_PATH="{INSTALL_GLOBAL_DIR}"
python3 "${{INSTALL_PATH}}/engine.py" "$@"
""")
    os.chmod(cli_wrapper, 0o755)
    print(f"  [✓] Executável CLI criado: {cli_wrapper}")

    # 4. Configura o MCP Server em ~/.gemini/config/mcp_config.json
    os.makedirs(GEMINI_CONFIG_DIR, exist_ok=True)
    mcp_config = {"mcpServers": {}}
    if os.path.exists(GEMINI_MCP_FILE):
        try:
            with open(GEMINI_MCP_FILE, "r", encoding="utf-8") as f:
                mcp_config = json.load(f)
        except Exception:
            mcp_config = {"mcpServers": {}}

    mcp_config.setdefault("mcpServers", {})
    mcp_config["mcpServers"]["system1"] = {
        "command": "python3",
        "args": [target_server_script]
    }

    with open(GEMINI_MCP_FILE, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)
    print(f"  [✓] Servidor MCP registrado em: {GEMINI_MCP_FILE}")

    # 5. Configura Schemas MCP do Antigravity CLI
    os.makedirs(GEMINI_CLI_MCP_DIR, exist_ok=True)
    mcp_src_dir = os.path.join(PROJECT_ROOT, "mcp")
    if os.path.exists(mcp_src_dir):
        for item in os.listdir(mcp_src_dir):
            s = os.path.join(mcp_src_dir, item)
            d = os.path.join(GEMINI_CLI_MCP_DIR, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
        print(f"  [✓] Schemas MCP sincronizados em: {GEMINI_CLI_MCP_DIR}")

    # 6. Configura Skills globais em ~/.agents/skills/system1
    os.makedirs(GLOBAL_AGENTS_SKILL_DIR, exist_ok=True)
    skill_src = os.path.join(PROJECT_ROOT, "SKILL.md")
    if os.path.exists(skill_src):
        shutil.copy(skill_src, os.path.join(GLOBAL_AGENTS_SKILL_DIR, "SKILL.md"))
        print(f"  [✓] Skill global registrada em: {GLOBAL_AGENTS_SKILL_DIR}/SKILL.md")


def test_installation(server_script: str):
    """Executa um teste rápido para certificar o funcionamento do MCP e da CLI."""
    print("\n[+] Executando auto-teste de validação...")
    try:
        # Testa inferência reflexiva via subprocess
        proc = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "engine.py"), "classify", "testar instalacao do sistema"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if proc.returncode == 0 and "predicted_label" in proc.stdout:
            print("  [✓] Motor System 1 (engine.py): Funcionando com sucesso!")
        else:
            print(f"  [!] Aviso na execução do engine: {proc.stderr}")

        # Testa servidor MCP stdio
        p_mcp = subprocess.Popen(
            [sys.executable, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        p_mcp.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
        p_mcp.stdin.flush()
        line = p_mcp.stdout.readline()
        p_mcp.terminate()
        
        if line and "system1-reflexive" in line:
            print("  [✓] Servidor MCP stdio (mcp_server.py): Respondendo perfeitamente!")
        else:
            print("  [!] Aviso no teste do servidor MCP.")

    except Exception as e:
        print(f"  [!] Erro durante o teste: {e}")


def main():
    print_banner()

    # Identifica modo a partir de argumentos ou pergunta interativa
    choice = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--global", "-g", "global", "1"):
            choice = "1"
        elif arg in ("--local", "--project", "-l", "-p", "local", "project", "2"):
            choice = "2"
        elif arg in ("--all", "--both", "-a", "all", "both", "3"):
            choice = "3"

    if choice is None:
        print("\nOnde você deseja instalar o System 1?")
        print("  [1] Globalmente no Sistema (CLI global, IDE/MCP global e Skills)")
        print("  [2] Somente neste Projeto (Estrutura .system1/ local, .agents/ e regras locais)")
        print("  [3] Completa (Global + Local neste Projeto) - [RECOMENDADO]")
        print("")
        try:
            choice = input("Escolha uma opção [1/2/3] (padrão: 3): ").strip() or "3"
        except (EOFError, KeyboardInterrupt):
            choice = "3"

    target_server_script = os.path.join(INSTALL_GLOBAL_DIR, "src", "mcp_server.py")
    if choice == "2":
        target_server_script = os.path.join(PROJECT_ROOT, "src", "mcp_server.py")

    if choice in ("1", "3"):
        setup_global_system(target_server_script)

    if choice in ("2", "3"):
        setup_local_project(PROJECT_ROOT)
        # Se foi apenas local, ainda garantimos registro do MCP para uso na sessão
        if choice == "2":
            setup_global_system(target_server_script)

    test_installation(target_server_script)

    print("\n" + "=" * 65)
    print(" 🎉  INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 65)
    print(" Recursos disponíveis imediatamente:")
    print(f"  • Dados Pessoais/Projeto : {os.path.join(PROJECT_ROOT, '.system1')}")
    print(f"  • Servidor MCP stdio    : {target_server_script}")
    print(f"  • Schemas MCP           : {os.path.join(PROJECT_ROOT, 'mcp')}")
    print(f"  • Skills do Agente      : {os.path.join(PROJECT_ROOT, 'SKILL.md')}")
    print(f"  • Regras & Agentes      : {os.path.join(PROJECT_ROOT, 'AGENTS.md')}")
    print(f"  • CLI Global            : system1 classify 'sua instrução aqui'")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
