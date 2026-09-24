#!/usr/bin/env python3
"""
Repository Sanitizer & Pre-Commit Security Validator for System 1 Reflexive.
Garante isolamento absoluto entre código-fonte público/open-source e dados pessoais/sessões do usuário.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


FORBIDDEN_TRACKED_PATTERNS = [
    ".system1/",
    "session_working_memory.json",
    "user_profile.json",
    "memory.local.json",
    ".env",
    "history.jsonl",
    ".sqlite",
    ".sqlite3"
]

REQUIRED_TEMPLATES = [
    os.path.join(REPO_ROOT, "data", "default_memory.json"),
    os.path.join(REPO_ROOT, "data", "default_session_memory.json")
]


def check_git_tracked_files() -> List[str]:
    """Verifica se algum arquivo privado ou de sessão está inadvertidamente rastreado no Git."""
    violations = []
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            tracked = res.stdout.strip().split("\n")
            for f in tracked:
                f_strip = f.strip()
                if not f_strip:
                    continue
                for pattern in FORBIDDEN_TRACKED_PATTERNS:
                    if pattern in f_strip or f_strip.endswith(pattern):
                        violations.append(f_strip)
    except Exception as e:
        print(f"[!] Erro executando git ls-files: {e}", file=sys.stderr)

    return list(set(violations))


def validate_templates() -> bool:
    """Valida se os templates padrão estão íntegros e são JSON válidos."""
    for tmpl in REQUIRED_TEMPLATES:
        if not os.path.exists(tmpl):
            print(f"[❌] Template obrigatório ausente: {tmpl}", file=sys.stderr)
            return False
        try:
            with open(tmpl, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            print(f"[❌] Erro no JSON do template {tmpl}: {e}", file=sys.stderr)
            return False
    return True


def sanitize():
    print("=" * 60)
    print(" 🛡️  SYSTEM 1 REFLEXIVE - SANITIZADOR DE REPOSITÓRIO")
    print("=" * 60)

    # 1. Valida templates
    if not validate_templates():
        sys.exit(1)
    print(" [✓] Templates oficiais validados (data/default_*.json)")

    # 2. Checa arquivos rastreados indevidamente
    violations = check_git_tracked_files()
    if violations:
        print("\n [⚠️] ATENÇÃO: Os seguintes arquivos de sessão/dados pessoais estão rastreados no Git:")
        for v in violations:
            print(f"     - {v}")
        print("\n Removendo-os do rastreamento do Git (preservando cópias locais)...")
        for v in violations:
            subprocess.run(["git", "rm", "--cached", v], cwd=REPO_ROOT, capture_output=True)
            print(f"     [✓] Desvinculado do Git: {v}")
    else:
        print(" [✓] Nenhum arquivo de sessão do usuário está rastreado no Git.")

    # 3. Limpeza de arquivos residuais no root
    root_legacy = [
        os.path.join(REPO_ROOT, "session_working_memory.json"),
        os.path.join(REPO_ROOT, "user_profile.json")
    ]
    for rf in root_legacy:
        if os.path.exists(rf):
            try:
                os.remove(rf)
                print(f" [✓] Arquivo temporário residual no root limpo: {os.path.basename(rf)}")
            except Exception:
                pass

    print("\n" + "=" * 60)
    print(" ✅ REPOSITÓRIO SANITIZADO E PRONTO PARA COMMIT NO GITHUB")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    sanitize()
