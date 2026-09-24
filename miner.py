"""
Refined Semantic Repository Miner for System 1.
"""
import os
import sys
import json
import re
from config_manager import get_memory_file, find_project_root

PROJECTS_DIR = os.environ.get("PROJECTS_DIR") or os.path.dirname(find_project_root())
MEMORY_PATH = get_memory_file()

STOPWORDS = {
    "from", "import", "const", "export", "default", "function", "return", "class",
    "async", "await", "this", "that", "with", "true", "false", "null", "undefined",
    "string", "number", "boolean", "type", "interface", "public", "private", "void",
    "else", "then", "catch", "finally", "throw", "while", "break", "continue", "para",
    "como", "mais", "sobre", "este", "esta", "para", "cada", "onde", "quando", "qual",
    "fazer", "usar", "pode", "deve", "sendo", "todos", "todas", "essas", "esses",
    "section", "title", "header", "table", "index", "content", "version", "projeto",
    "sistema", "criar", "nova", "novo", "dados", "arquivos", "passo", "etapa"
}

INITIAL_BASE = {
    "version": "1.0.0",
    "temperature": 1.15,
    "patterns": {
        "PROJECT_BOOTSTRAP": [
            "iniciar projeto", "criar projeto", "novo projeto", "scaffold", "boilerplate", 
            "estrutura inicial", "setup", "npm init", "npx create", "vite init", "cargo new"
        ],
        "CODE_BUGFIX": [
            "corrigir bug", "erro", "falha", "fix", "exception", "quebrou", "crash", 
            "traceback", "debug", "hotfix", "syntax error", "runtime error", "null pointer", "undefined error"
        ],
        "FEATURE_IMPLEMENTATION": [
            "criar tela", "adicionar funcionalidade", "implementar", "novo componente", 
            "nova rota", "endpoint", "nova pagina", "fluxo de checkout", "novo servico", "hook react"
        ],
        "DATABASE_SCHEMA_MIGRATION": [
            "supabase", "sql", "tabela", "migration", "trigger", "rls", "postgres", 
            "foreign key", "alter table", "create table", "database query", "prisma", "drizzle"
        ],
        "TEST_AUTOMATION": [
            "testes", "test runner", "unit test", "validar", "asserção", "suite de testes", 
            "jest", "vitest", "pytest", "cypress", "playwright", "mock", "spec"
        ],
        "ARCHITECTURE_DESIGN": [
            "arquitetura", "readme", "documentar", "diagrama", "fluxo de dados", "design pattern", 
            "c4 model", "erd", "especificacao tecnica", "rfc", "adr"
        ],
        "TOOL_EXECUTION_COMMAND": [
            "rodar comando", "terminal", "executar script", "instalar pacote", "bash", 
            "ls", "npm install", "pty", "websocket bridge", "sh script", "systemctl"
        ]
    },
    "history_log": [],
    "system2_distillations": []
}

def clean_term(w: str) -> str:
    w = re.sub(r'[^a-zA-Z0-9_\-]', '', w).strip().lower()
    if len(w) >= 4 and w not in STOPWORDS and not w.isdigit():
        return w
    return ""

def mine_repositories():
    print(f"[*] Iniciando mineração precisa em {PROJECTS_DIR}...")
    
    extracted = {k: set() for k in INITIAL_BASE["patterns"].keys()}

    for root, dirs, files in os.walk(PROJECTS_DIR):
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".cache", "__pycache__", "dist", "build", ".next", ".impeccable"]]
        
        for file in files:
            file_lower = file.lower()
            full_path = os.path.join(root, file)
            
            # DATABASE & MIGRATION
            if any(k in file_lower for k in [".sql", "migration", "schema", "supabase", "seed"]):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for match in re.findall(r'(CREATE TABLE|ALTER TABLE|POLICY|TRIGGER|FOREIGN KEY)\s+([a-zA-Z0-9_]+)', f.read(5000), re.IGNORECASE):
                            t = clean_term(match[1])
                            if t and t not in STOPWORDS:
                                extracted["DATABASE_SCHEMA_MIGRATION"].add(f"tabela {t}")
                except Exception:
                    pass

            # TEST AUTOMATION
            if any(k in file_lower for k in [".test.", ".spec.", "test_", "_test"]):
                name = clean_term(os.path.splitext(file)[0])
                if name:
                    extracted["TEST_AUTOMATION"].add(f"teste {name}")

            # BOOTSTRAP / PACKAGES
            if file_lower == "package.json":
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        pkg = json.load(f)
                        for dep in list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys()):
                            dep_clean = dep.replace("@", "").replace("/", " ").strip()
                            if any(t in dep_clean for t in ["jest", "vitest", "test", "mocha"]):
                                extracted["TEST_AUTOMATION"].add(dep_clean)
                            elif any(t in dep_clean for t in ["supabase", "prisma", "sql", "postgres", "typeorm"]):
                                extracted["DATABASE_SCHEMA_MIGRATION"].add(dep_clean)
                            elif any(t in dep_clean for t in ["pty", "ssh", "ws", "term", "express", "cors"]):
                                extracted["TOOL_EXECUTION_COMMAND"].add(dep_clean)
                            else:
                                extracted["PROJECT_BOOTSTRAP"].add(dep_clean)
                except Exception:
                    pass

            # SCRIPTS / CLI / BRIDGES
            if any(file_lower.endswith(ext) for ext in [".sh", ".bash"]) or any(k in file_lower for k in ["bridge", "pty"]):
                clean_f = clean_term(os.path.splitext(file_lower)[0])
                if clean_f:
                    extracted["TOOL_EXECUTION_COMMAND"].add(clean_f)

            # FEATURES / COMPONENTS
            if any(k in full_path.lower() for k in ["components", "screens", "pages", "routes"]):
                comp_name = clean_term(os.path.splitext(file)[0])
                if comp_name and comp_name not in ["index", "app", "layout"]:
                    extracted["FEATURE_IMPLEMENTATION"].add(f"componente {comp_name}")
                    extracted["FEATURE_IMPLEMENTATION"].add(f"tela {comp_name}")

    # Mescla com a base existente ou base inicial
    final_data = dict(INITIAL_BASE)
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, 'r', encoding='utf-8') as f:
                existing_json = json.load(f)
                if isinstance(existing_json, dict) and "patterns" in existing_json:
                    final_data = existing_json
        except Exception:
            pass

    patterns = final_data.setdefault("patterns", {})
    total_added = 0
    for cat, terms in extracted.items():
        existing = set(patterns.get(cat, []))
        new_terms = [t for t in terms if t and t not in existing]
        patterns.setdefault(cat, []).extend(new_terms)
        total_added += len(new_terms)
        print(f" [+] {cat}: +{len(new_terms)} termos minerados (Total: {len(patterns[cat])})")

    with open(MEMORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] Base do System 1 calibrada e atualizada com sucesso (+{total_added} novos termos técnicos)!")
    return total_added

if __name__ == "__main__":
    mine_repositories()
