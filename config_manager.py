"""
Config and Path Resolution Manager for System 1 Reflexive.
Isola dados do projeto e do usuário em diretório dedicado (.system1/ ou SYSTEM1_DATA_DIR),
separando o código-fonte base do repositório dos dados de memória persistente e sessão ativa.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_TEMPLATE_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_MEMORY_TEMPLATE = os.path.join(DATA_TEMPLATE_DIR, "default_memory.json")
DEFAULT_SESSION_TEMPLATE = os.path.join(DATA_TEMPLATE_DIR, "default_session_memory.json")


def find_project_root(start_path: Optional[str] = None) -> str:
    """Busca a raiz do projeto atual a partir do CWD ou caminho fornecido."""
    if start_path is None:
        start_path = os.getcwd()

    current = os.path.abspath(start_path)
    while True:
        if (
            os.path.exists(os.path.join(current, ".git")) or
            os.path.exists(os.path.join(current, ".system1")) or
            os.path.exists(os.path.join(current, "package.json")) or
            os.path.exists(os.path.join(current, "engine.py"))
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start_path)


def get_data_dir(start_path: Optional[str] = None) -> str:
    """
    Retorna o diretório isolado de dados do usuário/projeto (.system1/).
    Prioridades:
    1. Variável de ambiente SYSTEM1_DATA_DIR
    2. Pasta .system1/ na raiz do projeto detectado
    3. Fallback: ~/.system1-reflexive/data/ se global
    """
    env_dir = os.environ.get("SYSTEM1_DATA_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return os.path.abspath(env_dir)

    proj_root = find_project_root(start_path)
    system1_dir = os.path.join(proj_root, ".system1")
    os.makedirs(system1_dir, exist_ok=True)
    return system1_dir


def get_memory_file(start_path: Optional[str] = None) -> str:
    """Retorna o caminho do arquivo de memória persistente (memory.json)."""
    data_dir = get_data_dir(start_path)
    target = os.path.join(data_dir, "memory.json")
    if not os.path.exists(target):
        # Inicializa a partir do template padrão
        _initialize_file_from_template(target, DEFAULT_MEMORY_TEMPLATE, {
            "version": "1.0.0",
            "temperature": 1.15,
            "patterns": {},
            "history_log": [],
            "system2_distillations": []
        })
    return target


def get_current_git_branch(start_path: Optional[str] = None) -> str:
    """Detecta o branch Git atual do projeto ou retorna 'default'."""
    import subprocess
    proj_root = find_project_root(start_path)
    head_file = os.path.join(proj_root, ".git", "HEAD")
    if os.path.exists(head_file):
        try:
            with open(head_file, "r", encoding="utf-8") as f:
                ref = f.read().strip()
                if ref.startswith("ref: refs/heads/"):
                    return ref.replace("ref: refs/heads/", "").replace("/", "_")
        except Exception:
            pass

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=proj_root,
            capture_output=True,
            text=True,
            timeout=2
        )
        if res.returncode == 0:
            branch = res.stdout.strip()
            if branch and branch != "HEAD":
                return branch.replace("/", "_")
    except Exception:
        pass

    return "default"


def get_sessions_dir(start_path: Optional[str] = None) -> str:
    """Retorna o diretório de sessões isoladas (.system1/sessions/)."""
    data_dir = get_data_dir(start_path)
    sessions_dir = os.path.join(data_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    return sessions_dir


def get_session_memory_file(start_path: Optional[str] = None, session_id: Optional[str] = None) -> str:
    """
    Retorna o caminho da memória de trabalho da sessão.
    Isola por session_id explícito, variável de ambiente SYSTEM1_SESSION ou branch Git atual.
    """
    data_dir = get_data_dir(start_path)
    sessions_dir = get_sessions_dir(start_path)
    
    sid = session_id or os.environ.get("SYSTEM1_SESSION") or get_current_git_branch(start_path)
    # Sanitiza o nome do arquivo de sessão
    import re
    clean_sid = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', sid)
    if not clean_sid:
        clean_sid = "default"

    target = os.path.join(sessions_dir, f"{clean_sid}.json")
    
    # Se o arquivo de sessão não existe mas existe o legado session_working_memory.json, migra suavemente
    legacy_file = os.path.join(data_dir, "session_working_memory.json")
    if not os.path.exists(target) and os.path.exists(legacy_file):
        try:
            with open(legacy_file, "r", encoding="utf-8") as lf:
                legacy_data = json.load(lf)
            atomic_save_json(target, legacy_data)
        except Exception:
            pass

    if not os.path.exists(target):
        _initialize_file_from_template(target, DEFAULT_SESSION_TEMPLATE, {
            "version": "1.0.0",
            "session_id": clean_sid,
            "active_goal": "",
            "active_constraints": [],
            "state_variables": {},
            "failed_hypotheses": [],
            "recent_actions": []
        })
    return target


def get_playbooks_file(start_path: Optional[str] = None) -> str:
    """Retorna o caminho do catálogo de playbooks (Hall of Fame) do projeto (.system1/playbooks.json)."""
    data_dir = get_data_dir(start_path)
    target = os.path.join(data_dir, "playbooks.json")
    if not os.path.exists(target):
        initial = {
            "version": "1.0.0",
            "playbooks": []
        }
        atomic_save_json(target, initial)
    return target


def list_available_sessions(start_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todas as sessões ativas e seu resumo no projeto."""
    sessions_dir = get_sessions_dir(start_path)
    sessions = []
    if os.path.exists(sessions_dir):
        for f in os.listdir(sessions_dir):
            if f.endswith(".json"):
                sid = f[:-5]
                fpath = os.path.join(sessions_dir, f)
                try:
                    with open(fpath, "r", encoding="utf-8") as sf:
                        sdata = json.load(sf)
                    sessions.append({
                        "session_id": sid,
                        "file_path": fpath,
                        "active_goal": sdata.get("active_goal", ""),
                        "constraints_count": len(sdata.get("active_constraints", [])),
                        "failed_count": len(sdata.get("failed_hypotheses", [])),
                        "modified_time": os.path.getmtime(fpath)
                    })
                except Exception:
                    pass
    return sorted(sessions, key=lambda x: x["modified_time"], reverse=True)


def get_user_profile_file(start_path: Optional[str] = None) -> str:
    """Retorna o caminho do perfil de preferências e restrições do usuário."""
    data_dir = get_data_dir(start_path)
    target = os.path.join(data_dir, "user_profile.json")
    if not os.path.exists(target):
        initial = {
            "user_preferences": {},
            "global_constraints": [],
            "preferred_languages": ["pt-BR", "en"],
            "safety_strictness": "high"
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2, ensure_ascii=False)
    return target


def _initialize_file_from_template(target: str, template: str, fallback_data: Dict[str, Any]):
    """Copia template inicial ou cria com dados de fallback."""
    if os.path.exists(template):
        try:
            with open(template, "r", encoding="utf-8") as tf:
                content = json.load(tf)
            atomic_save_json(target, content)
            return
        except Exception:
            pass

    atomic_save_json(target, fallback_data)


def load_json_file(file_path: str, default: Any = None) -> Any:
    """Carrega arquivo JSON com aceleração de alta performance (orjson quando disponível)."""
    if not os.path.exists(file_path):
        return default
    try:
        try:
            import orjson
            with open(file_path, "rb") as f:
                return orjson.loads(f.read())
        except ImportError:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return default


def atomic_save_json(file_path: str, data: Any):
    """Salva dados em formato JSON de maneira atômica e ultra-rápida (orjson/json)."""
    dir_name = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(dir_name, exist_ok=True)
    temp_file = f"{file_path}.tmp.{os.getpid()}"
    try:
        try:
            import orjson
            serialized = orjson.dumps(data, option=orjson.OPT_INDENT_2)
            with open(temp_file, "wb") as f:
                f.write(serialized)
        except ImportError:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, file_path)
    except Exception:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise


def normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos/diacríticos e convertendo para minúsculas."""
    import unicodedata
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()

