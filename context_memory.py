"""
Context Memory, Negative Constraint (Graveyard), Playbooks (Hall of Fame),
and Action Safety Engine for System 1.
Gerencia memória de trabalho multi-sessão por Git branch, catálogo de soluções invalidadas,
recomendações de soluções canônicas via BM25, guardrails de segurança e poda JIT de tokens.
"""

import os
import sys
import json
import time
import math
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field

from config_manager import (
    get_session_memory_file,
    get_playbooks_file,
    list_available_sessions,
    atomic_save_json,
    normalize_text,
    find_project_root
)


# ==============================================================================
# BM25 Lightweight In-Memory Scoring Engine (<1ms)
# ==============================================================================
def tokenize_text(text: str) -> List[str]:
    """Tokeniza texto normalizado removendo stopwords e pontuação."""
    norm = normalize_text(text)
    raw = re.findall(r'\b[a-zA-Z0-9_\-\.]{3,}\b', norm)
    stop_words = {
        "com", "para", "que", "uma", "nao", "por", "dos", "das", "the", "and", "for",
        "with", "this", "that", "from", "into", "vamos", "tentar", "fazer", "usar"
    }
    return [w for w in raw if w not in stop_words]


def compute_bm25_score(
    query_tokens: List[str],
    doc_tokens: List[str],
    avg_doc_len: float,
    num_docs: int,
    df_map: Dict[str, int],
    k1: float = 1.5,
    b: float = 0.75
) -> float:
    """Calcula pontuação BM25 entre consulta e documento."""
    if not query_tokens or not doc_tokens:
        return 0.0

    doc_len = len(doc_tokens)
    doc_tf: Dict[str, int] = {}
    for t in doc_tokens:
        doc_tf[t] = doc_tf.get(t, 0) + 1

    score = 0.0
    for q in query_tokens:
        if q not in doc_tf:
            continue
        tf = doc_tf[q]
        df = df_map.get(q, 1)
        idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
        numerator = tf * (k1 + 1.0)
        denominator = tf + k1 * (1.0 - b + b * (doc_len / (avg_doc_len or 1.0)))
        score += idf * (numerator / max(0.001, denominator))

    return max(0.0, score)


# ==============================================================================
# Action Safety & Deterministic Guardrails (AST / Regex Safety Analyzer)
# ==============================================================================
DANGEROUS_SHELL_PATTERNS = [
    (r'\brm\s+-(?:r|f|rf|fr)\s+(?:/|/\*|\~|\$HOME|\.\.)', "Exclusão recursiva em raiz, home ou diretório superior"),
    (r'\bmkfs(?:\.\w+)?\s+', "Formatação destrutiva de partição ou filesystem"),
    (r'\bdd\s+if=.*of=(?:/dev/sd|/dev/nvme|/dev/hd)', "Sobrescrita binária direta de dispositivo de bloco"),
    (r'\bchmod\s+(?:-R\s+)?(?:777|666)\s+/', "Abertura indiscriminada de permissões em diretório de sistema"),
    (r'>\s*(?:/dev/sd|/dev/nvme|/dev/null\s*;\s*reboot)', "Redirecionamento destrutivo de hardware"),
    (r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:', "Execução de Fork Bomb"),
    (r'\b(?:killall|pkill)\s+-9\s+(?:init|systemd|dockerd|postgres|mysqld)', "Finalização forçada de serviços essenciais de sistema"),
    (r'curl\s+[^\|]+\|\s*(?:sudo\s+)?(?:bash|sh|zsh)', "Execução direta de script remoto não verificado via pipe para shell")
]

DANGEROUS_SQL_PATTERNS = [
    (r'\bDROP\s+DATABASE\b', "Destruição integral de banco de dados"),
    (r'\bDROP\s+TABLE\b', "Exclusão de tabela de banco de dados"),
    (r'\bTRUNCATE\s+(?:TABLE\s+)?', "Esvaziamento irreversível de dados da tabela"),
    (r'\bALTER\s+TABLE\s+\w+\s+DROP\s+COLUMN\b', "Exclusão de coluna em tabela sem plano de migração")
]


def analyze_action_safety(action_text: str) -> Dict[str, Any]:
    """
    Analisa reflexivamente se a ação ou comando possui risco de destruição de dados,
    execução perigosa no shell ou mutação SQL não intencional.
    """
    start = time.perf_counter()
    reasons = []
    risk_level = "LOW"
    blocked = False

    # 1. Shell Safety Checks
    for pattern, desc in DANGEROUS_SHELL_PATTERNS:
        if re.search(pattern, action_text, re.IGNORECASE):
            reasons.append(f"Shell inseguro: {desc}")
            risk_level = "CRITICAL"
            blocked = True

    # 2. SQL Safety Checks
    for pattern, desc in DANGEROUS_SQL_PATTERNS:
        if re.search(pattern, action_text, re.IGNORECASE):
            reasons.append(f"SQL destrutivo: {desc}")
            risk_level = "HIGH" if risk_level != "CRITICAL" else "CRITICAL"
            blocked = True

    # DELETE / UPDATE sem WHERE
    if re.search(r'\bDELETE\s+FROM\s+\w+', action_text, re.IGNORECASE) and not re.search(r'\bWHERE\b', action_text, re.IGNORECASE):
        reasons.append("SQL destrutivo: DELETE FROM sem cláusula WHERE")
        risk_level = "HIGH" if risk_level != "CRITICAL" else "CRITICAL"
        blocked = True

    if re.search(r'\bUPDATE\s+\w+\s+SET\b', action_text, re.IGNORECASE) and not re.search(r'\bWHERE\b', action_text, re.IGNORECASE):
        reasons.append("SQL destrutivo: UPDATE sem cláusula WHERE")
        risk_level = "HIGH" if risk_level != "CRITICAL" else "CRITICAL"
        blocked = True

    latency = (time.perf_counter() - start) * 1000.0

    return {
        "safe": not blocked,
        "blocked": blocked,
        "risk_level": risk_level,
        "reasons": reasons,
        "latency_ms": round(latency, 3)
    }


# ==============================================================================
# Dataclasses para Graveyard e Playbooks
# ==============================================================================
@dataclass
class FailedHypothesis:
    id: int
    approach: str
    failure_reason: str
    root_cause: str
    veto_rule: str
    category: str
    keywords: List[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class Playbook:
    id: int
    title: str
    description: str
    solution_steps: List[str]
    category: str
    keywords: List[str]
    success_count: int = 1
    timestamp: float = field(default_factory=time.time)


# ==============================================================================
# Context Memory Engine Principal
# ==============================================================================
class ContextMemoryEngine:
    def __init__(self, storage_path: Optional[str] = None, session_id: Optional[str] = None):
        self.session_id = session_id
        self.storage_path = storage_path or get_session_memory_file(session_id=session_id)
        self.playbooks_path = get_playbooks_file()
        self.state = self._load_session()
        self.playbooks = self._load_playbooks()

    def _load_session(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        initial_state = {
            "version": "1.0.0",
            "session_id": self.session_id or "default",
            "active_goal": "",
            "active_constraints": [],
            "state_variables": {},
            "failed_hypotheses": [],
            "recent_actions": []
        }
        self._save_session(initial_state)
        return initial_state

    def _save_session(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = self.state
        try:
            atomic_save_json(self.storage_path, data)
        except Exception as e:
            print(f"Erro ao salvar session memory: {e}", file=sys.stderr)

    def _load_playbooks(self) -> Dict[str, Any]:
        if os.path.exists(self.playbooks_path):
            try:
                with open(self.playbooks_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        initial_playbooks = {"version": "1.0.0", "playbooks": []}
        atomic_save_json(self.playbooks_path, initial_playbooks)
        return initial_playbooks

    def _save_playbooks(self):
        try:
            atomic_save_json(self.playbooks_path, self.playbooks)
        except Exception as e:
            print(f"Erro ao salvar playbooks: {e}", file=sys.stderr)

    # --------------------------------------------------------------------------
    # Gestão de Sessões e Multi-Escopo
    # --------------------------------------------------------------------------
    def switch_session(self, new_session_id: str) -> Dict[str, Any]:
        """Alterna a memória de trabalho para outra sessão/branch."""
        self.session_id = new_session_id
        self.storage_path = get_session_memory_file(session_id=new_session_id)
        self.state = self._load_session()
        return {
            "status": "session_switched",
            "session_id": new_session_id,
            "storage_path": self.storage_path,
            "active_goal": self.state.get("active_goal", ""),
            "failed_hypotheses_count": len(self.state.get("failed_hypotheses", []))
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lista todas as sessões registradas no projeto."""
        return list_available_sessions()

    # --------------------------------------------------------------------------
    # Estado Ativo e Restrições
    # --------------------------------------------------------------------------
    def set_goal(self, goal: str) -> Dict[str, Any]:
        """Define o objetivo ativo da sessão."""
        self.state["active_goal"] = goal
        self._save_session()
        return {"status": "goal_set", "active_goal": goal}

    def set_state_var(self, key: str, value: Any) -> Dict[str, Any]:
        """Define ou atualiza uma variável de estado ativo."""
        self.state.setdefault("state_variables", {})[key] = value
        self._save_session()
        return {"status": "state_updated", "key": key, "value": value}

    def add_constraint(self, constraint: str) -> Dict[str, Any]:
        """Adiciona uma restrição operacional ativa."""
        constraints = self.state.setdefault("active_constraints", [])
        if constraint not in constraints:
            constraints.append(constraint)
            self._save_session()
        return {"status": "constraint_added", "total_constraints": len(constraints)}

    # --------------------------------------------------------------------------
    # Graveyard de Soluções Falhas (Memória Negativa com BM25)
    # --------------------------------------------------------------------------
    def record_failure(
        self,
        approach: str,
        failure_reason: str,
        root_cause: str = "",
        veto_rule: str = "",
        category: str = "CODE_BUGFIX"
    ) -> Dict[str, Any]:
        """
        Registra uma abordagem testada que falhou, criando uma regra de veto definitiva.
        """
        failed_list = self.state.setdefault("failed_hypotheses", [])
        next_id = len(failed_list) + 1
        keywords = tokenize_text(approach)

        if not veto_rule:
            veto_rule = f"Proibido repetir: '{approach}'. Causa da falha: {failure_reason}."

        hypothesis = {
            "id": next_id,
            "approach": approach,
            "failure_reason": failure_reason,
            "root_cause": root_cause or "Solução inadequada ou erro de execução",
            "veto_rule": veto_rule,
            "category": category,
            "keywords": keywords,
            "timestamp": time.time()
        }

        failed_list.append(hypothesis)
        self._save_session()

        return {
            "status": "failure_recorded",
            "id": next_id,
            "veto_rule": veto_rule,
            "total_failed_hypotheses": len(failed_list)
        }

    def validate_action(self, proposed_action: str) -> Dict[str, Any]:
        """
        Valida reflexivamente a ação usando análise estática de segurança e
        correspondência BM25 com soluções invalidadas do Graveyard.
        """
        start = time.perf_counter()

        # 1. Checagem de Segurança Estática
        safety_eval = analyze_action_safety(proposed_action)
        if safety_eval.get("blocked"):
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "vetoed": True,
                "risk_score": 1.0,
                "status": "ACTION_BLOCKED_SAFETY",
                "message": f"Ação bloqueada pelo Guardrail de Segurança: {'; '.join(safety_eval['reasons'])}",
                "safety_reasons": safety_eval["reasons"],
                "matching_vetos": [],
                "latency_ms": round(latency, 3)
            }

        # 2. Checagem Semântica BM25 no Graveyard
        query_tokens = tokenize_text(proposed_action)
        failed_list = self.state.get("failed_hypotheses", [])
        action_norm = normalize_text(proposed_action)

        if not failed_list or not query_tokens:
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "vetoed": False,
                "risk_score": 0.05,
                "status": "ACTION_ALLOWED",
                "message": "Nenhuma colisão com soluções invalidadas.",
                "latency_ms": round(latency, 3)
            }

        # Prepara estatísticas de DF e comprimento médio para BM25
        num_docs = len(failed_list)
        df_map: Dict[str, int] = {}
        total_len = 0
        docs_tokens = []

        for fh in failed_list:
            doc_kws = tokenize_text(fh.get("approach", "") + " " + " ".join(fh.get("keywords", [])))
            docs_tokens.append(doc_kws)
            total_len += len(doc_kws)
            for w in set(doc_kws):
                df_map[w] = df_map.get(w, 0) + 1

        avg_doc_len = total_len / max(1, num_docs)

        matches = []
        for idx, fh in enumerate(failed_list):
            doc_kws = docs_tokens[idx]
            bm25_score = compute_bm25_score(query_tokens, doc_kws, avg_doc_len, num_docs, df_map)
            
            # Match exato de frase ou alta relevância BM25 (>1.8)
            app_norm = normalize_text(fh.get("approach", ""))
            is_phrase_match = app_norm in action_norm or action_norm in app_norm

            if is_phrase_match or bm25_score >= 1.5:
                matches.append({
                    "failed_id": fh["id"],
                    "approach": fh["approach"],
                    "failure_reason": fh["failure_reason"],
                    "root_cause": fh["root_cause"],
                    "veto_rule": fh["veto_rule"],
                    "bm25_score": round(bm25_score, 3)
                })

        latency = (time.perf_counter() - start) * 1000.0

        if matches:
            return {
                "vetoed": True,
                "risk_score": 1.0,
                "status": "ACTION_BLOCKED",
                "message": "Ação bloqueada pelo Sistema de Memória Negativa: esta abordagem já foi testada e falhou.",
                "matching_vetos": matches,
                "latency_ms": round(latency, 3)
            }

        return {
            "vetoed": False,
            "risk_score": 0.05,
            "status": "ACTION_ALLOWED",
            "message": "Nenhuma colisão com soluções invalidadas.",
            "latency_ms": round(latency, 3)
        }

    # --------------------------------------------------------------------------
    # Hall of Fame / Playbooks (Soluções Canônicas de Sucesso)
    # --------------------------------------------------------------------------
    def record_playbook(
        self,
        title: str,
        description: str,
        solution_steps: List[str],
        category: str = "FEATURE_IMPLEMENTATION",
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Registra uma solução canônica bem-sucedida (Playbook) no projeto.
        """
        playbook_list = self.playbooks.setdefault("playbooks", [])
        next_id = len(playbook_list) + 1
        
        extracted_kw = tokenize_text(f"{title} {description} {' '.join(solution_steps)}")
        if keywords:
            for k in keywords:
                k_tok = tokenize_text(k)
                extracted_kw.extend(k_tok)
        extracted_kw = list(set(extracted_kw))

        pb = {
            "id": next_id,
            "title": title,
            "description": description,
            "solution_steps": solution_steps,
            "category": category,
            "keywords": extracted_kw,
            "success_count": 1,
            "timestamp": time.time()
        }

        playbook_list.append(pb)
        self._save_playbooks()

        return {
            "status": "playbook_recorded",
            "id": next_id,
            "title": title,
            "total_playbooks": len(playbook_list)
        }

    def recommend_playbooks(self, query: str, limit: int = 3, min_score: float = 1.0) -> List[Dict[str, Any]]:
        """
        Recomenda Playbooks canônicos usando BM25 para resolver a tarefa na primeira tentativa.
        """
        playbook_list = self.playbooks.get("playbooks", [])
        if not playbook_list:
            return []

        query_tokens = tokenize_text(query)
        if not query_tokens:
            return []

        num_docs = len(playbook_list)
        df_map: Dict[str, int] = {}
        total_len = 0
        docs_tokens = []

        for pb in playbook_list:
            doc_kws = tokenize_text(f"{pb['title']} {pb['description']} {' '.join(pb['keywords'])}")
            docs_tokens.append(doc_kws)
            total_len += len(doc_kws)
            for w in set(doc_kws):
                df_map[w] = df_map.get(w, 0) + 1

        avg_doc_len = total_len / max(1, num_docs)

        scored = []
        for idx, pb in enumerate(playbook_list):
            doc_kws = docs_tokens[idx]
            score = compute_bm25_score(query_tokens, doc_kws, avg_doc_len, num_docs, df_map)
            if score >= min_score:
                scored.append({
                    "id": pb["id"],
                    "title": pb["title"],
                    "description": pb["description"],
                    "solution_steps": pb["solution_steps"],
                    "category": pb["category"],
                    "bm25_score": round(score, 3)
                })

        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored[:limit]

    # --------------------------------------------------------------------------
    # Sintetizador JIT de Contexto com Token Budget Optimizer
    # --------------------------------------------------------------------------
    def compress_logs(self, raw_log: str, max_chars: int = 400) -> str:
        """Comprime logs extensos de execução em síntese densa com alta SNR."""
        if len(raw_log) <= max_chars:
            return raw_log.strip()

        lines = raw_log.strip().split("\n")
        error_lines = [l for l in lines if re.search(r'(error|exception|fail|traceback|fatal|errno|4\d\d|5\d\d)', l, re.IGNORECASE)]
        
        if error_lines:
            summary = " | ".join([l.strip() for l in error_lines[-3:]])
            return f"[Log comprimido - {len(lines)} linhas -> Erro detectado]: {summary}"[:max_chars]

        return f"[Log comprimido - {len(lines)} linhas]: Início: {lines[0][:100]} ... Fim: {lines[-1][:100]}"[:max_chars]

    def get_synthesized_context(
        self,
        current_query: str = "",
        max_tokens: int = 800,
        include_negative_constraints: bool = True,
        include_playbooks: bool = True,
        include_state: bool = True
    ) -> str:
        """
        Gera um bloco de contexto conciso e estruturado aplicando Token Budget Optimizer.
        Distribui o orçamento de tokens inteligentemente entre Estado, Playbooks e Graveyard.
        """
        # Estimativa heurística de 4 caracteres por token
        max_chars = max_tokens * 4
        sections = []

        # 1. Estado Ativo & Objetivo (~25% do orçamento)
        if include_state:
            state_lines = []
            if self.state.get("active_goal"):
                state_lines.append(f"• Objetivo Principal: {self.state['active_goal']}")
            
            constraints = self.state.get("active_constraints", [])
            if constraints:
                state_lines.append("• Restrições Operacionais: " + "; ".join(constraints))

            state_vars = self.state.get("state_variables", {})
            if state_vars:
                formatted_vars = ", ".join([f"{k}={v}" for k, v in state_vars.items()])
                state_lines.append(f"• Variáveis de Estado: {formatted_vars}")

            if state_lines:
                sections.append("### [ESTADO ATIVO DA SESSÃO]\n" + "\n".join(state_lines))

        # 2. Playbooks Recomendados / Hall of Fame (~35% do orçamento)
        if include_playbooks and current_query:
            rec_playbooks = self.recommend_playbooks(current_query, limit=2)
            if rec_playbooks:
                pb_lines = ["🏆 SOLUÇÕES COMPROVADAS ANTERIORMENTE NESTE PROJETO (PLAYBOOKS):"]
                for pb in rec_playbooks:
                    steps = " -> ".join(pb["solution_steps"][:3])
                    pb_lines.append(f"  ✓ [{pb['category']}] {pb['title']}: {pb['description']}\n    Passos: {steps}")
                sections.append("### [PLAYBOOKS RECOMENDADOS - RESOLUÇÃO CANÔNICA]\n" + "\n".join(pb_lines))

        # 3. Restrições Negativas (Graveyard) (~40% do orçamento)
        if include_negative_constraints:
            failed_list = self.state.get("failed_hypotheses", [])
            if failed_list:
                neg_lines = ["⚠️ AS SEGUINTES ABORDAGENS JÁ FORAM TESTADAS E FALHARAM. É EXPRESSAMENTE PROIBIDO REPETI-LAS:"]
                
                # Se há query, prioriza por BM25, caso contrário pega as mais recentes
                if current_query:
                    query_tokens = tokenize_text(current_query)
                    num_docs = len(failed_list)
                    df_map = {w: 1 for w in query_tokens}
                    ranked_failed = sorted(
                        failed_list,
                        key=lambda fh: (
                            compute_bm25_score(query_tokens, tokenize_text(fh["approach"]), 10.0, num_docs, df_map),
                            fh["timestamp"]
                        ),
                        reverse=True
                    )
                else:
                    ranked_failed = list(reversed(failed_list))

                for fh in ranked_failed[:5]:
                    neg_lines.append(
                        f"  ❌ [{fh['category']}] Tentativa: \"{fh['approach']}\"\n"
                        f"     Motivo da Falha: {fh['failure_reason']}\n"
                        f"     Regra de Veto: {fh['veto_rule']}"
                    )
                sections.append("### [RESTRIÇÕES NEGATIVAS MANDATÓRIAS - NÃO REPETIR]\n" + "\n".join(neg_lines))

        if not sections:
            return ""

        full_context = "\n\n".join(sections)
        if len(full_context) > max_chars:
            return full_context[:max_chars] + "\n... [Contexto sintetizado truncado pelo Token Budget Optimizer]"

        return full_context

    def clear_session(self) -> Dict[str, Any]:
        """Limpa a memória de trabalho efêmera da sessão atual."""
        self.state = {
            "version": "1.0.0",
            "session_id": self.session_id or "default",
            "active_goal": "",
            "active_constraints": [],
            "state_variables": {},
            "failed_hypotheses": [],
            "recent_actions": []
        }
        self._save_session()
        return {"status": "session_cleared", "session_id": self.session_id or "default"}


if __name__ == "__main__":
    c = ContextMemoryEngine()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "fail" and len(sys.argv) > 3:
            app = sys.argv[2]
            reason = sys.argv[3]
            print(json.dumps(c.record_failure(app, reason), indent=2))
        elif cmd == "validate" and len(sys.argv) > 2:
            act = " ".join(sys.argv[2:])
            print(json.dumps(c.validate_action(act), indent=2))
        elif cmd == "safety" and len(sys.argv) > 2:
            act = " ".join(sys.argv[2:])
            print(json.dumps(analyze_action_safety(act), indent=2))
        elif cmd == "playbook" and len(sys.argv) > 4:
            t = sys.argv[2]
            d = sys.argv[3]
            steps = sys.argv[4].split(";")
            print(json.dumps(c.record_playbook(t, d, steps), indent=2))
        elif cmd == "recommend" and len(sys.argv) > 2:
            q = " ".join(sys.argv[2:])
            print(json.dumps(c.recommend_playbooks(q), indent=2))
        elif cmd == "context":
            q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            print(c.get_synthesized_context(current_query=q))
        elif cmd == "sessions":
            print(json.dumps(c.list_sessions(), indent=2))
        elif cmd == "clear":
            print(json.dumps(c.clear_session(), indent=2))
        else:
            print("Comandos: fail, validate, safety, playbook, recommend, context, sessions, clear")
    else:
        print(c.get_synthesized_context())
