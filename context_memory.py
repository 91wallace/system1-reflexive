"""
Context Memory & Negative Constraint Engine for System 1.
Gerencia a memória de trabalho ativa, o catálogo de soluções invalidadas (Graveyard),
a compressão JIT de contexto e a validação de ações contra repetição de erros.
"""

import os
import sys
import json
import time
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_MEMORY_FILE = os.path.join(DATA_DIR, "session_working_memory.json")


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


class ContextMemoryEngine:
    def __init__(self, storage_path: str = SESSION_MEMORY_FILE):
        self.storage_path = storage_path
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        initial_state = {
            "version": "1.0.0",
            "active_goal": "",
            "active_constraints": [],
            "state_variables": {},
            "failed_hypotheses": [],
            "recent_actions": []
        }
        self._save(initial_state)
        return initial_state

    def _save(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = self.state
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar session_working_memory: {e}", file=sys.stderr)

    def set_goal(self, goal: str) -> Dict[str, Any]:
        """Define o objetivo ativo da sessão."""
        self.state["active_goal"] = goal
        self._save()
        return {"status": "goal_set", "active_goal": goal}

    def set_state_var(self, key: str, value: Any) -> Dict[str, Any]:
        """Define ou atualiza uma variável de estado ativo."""
        self.state.setdefault("state_variables", {})[key] = value
        self._save()
        return {"status": "state_updated", "key": key, "value": value}

    def add_constraint(self, constraint: str) -> Dict[str, Any]:
        """Adiciona uma restrição operacional ativa."""
        constraints = self.state.setdefault("active_constraints", [])
        if constraint not in constraints:
            constraints.append(constraint)
            self._save()
        return {"status": "constraint_added", "total_constraints": len(constraints)}

    def record_failure(
        self,
        approach: str,
        failure_reason: str,
        root_cause: str = "",
        veto_rule: str = "",
        category: str = "CODE_BUGFIX"
    ) -> Dict[str, Any]:
        """
        Registra uma abordagem testada que falhou, criando uma regra de veto definitiva
        para impedir que a LLM repita a mesma solução.
        """
        failed_list = self.state.setdefault("failed_hypotheses", [])
        next_id = len(failed_list) + 1

        # Extrai palavras-chave essenciais da abordagem
        raw_words = re.findall(r'\b[a-zA-Z0-9_\-\.]{3,}\b', approach.lower())
        stop_words = {"com", "para", "que", "uma", "não", "por", "com", "the", "and", "for", "with"}
        keywords = list(set([w for w in raw_words if w not in stop_words]))

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
        self._save()

        return {
            "status": "failure_recorded",
            "id": next_id,
            "veto_rule": veto_rule,
            "total_failed_hypotheses": len(failed_list)
        }

    def validate_action(self, proposed_action: str) -> Dict[str, Any]:
        """
        Verifica instantaneamente (<2ms) se a ação proposta pelo modelo coincide com
        alguma hipótese previamente invalidada. Retorna score de risco e veto.
        """
        start = time.perf_counter()
        action_lower = proposed_action.lower()
        action_tokens = set(re.findall(r'\b[a-zA-Z0-9_\-\.]{3,}\b', action_lower))

        failed_list = self.state.get("failed_hypotheses", [])
        
        matches = []
        for fh in failed_list:
            fh_kw = set(fh.get("keywords", []))
            if not fh_kw:
                continue

            intersection = action_tokens.intersection(fh_kw)
            match_ratio = len(intersection) / len(fh_kw) if fh_kw else 0

            # Caso haja match exato da frase ou alta sobreposição de palavras-chave (>60%)
            is_phrase_match = fh.get("approach", "").lower() in action_lower
            if is_phrase_match or (match_ratio >= 0.6 and len(intersection) >= 2):
                matches.append({
                    "failed_id": fh["id"],
                    "approach": fh["approach"],
                    "failure_reason": fh["failure_reason"],
                    "root_cause": fh["root_cause"],
                    "veto_rule": fh["veto_rule"],
                    "match_ratio": round(match_ratio, 2)
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

    def compress_logs(self, raw_log: str, max_chars: int = 400) -> str:
        """
        Comprime logs extensos de execução/terminal em uma síntese densa com alta relação sinal-ruído.
        """
        if len(raw_log) <= max_chars:
            return raw_log.strip()

        # Detecção de erros comuns e stack traces
        lines = raw_log.strip().split("\n")
        error_lines = [l for l in lines if re.search(r'(error|exception|fail|traceback|fatal|errno|4\d\d|5\d\d)', l, re.IGNORECASE)]
        
        if error_lines:
            summary = " | ".join([l.strip() for l in error_lines[-3:]])
            return f"[Log comprimido - {len(lines)} linhas -> Erro detectado]: {summary}"[:max_chars]

        # Caso seja log de sucesso ou saída longa sem erros
        return f"[Log comprimido - {len(lines)} linhas]: Início: {lines[0][:100]} ... Fim: {lines[-1][:100]}"[:max_chars]

    def get_synthesized_context(
        self,
        current_query: str = "",
        include_negative_constraints: bool = True,
        include_state: bool = True
    ) -> str:
        """
        Gera um bloco de contexto conciso e estruturado pronto para injeção no prompt da LLM.
        """
        sections = []

        # 1. Estado Ativo & Objetivo
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

        # 2. Restrições Negativas (Graveyard de Soluções Falhas)
        if include_negative_constraints:
            failed_list = self.state.get("failed_hypotheses", [])
            if failed_list:
                neg_lines = ["⚠️ AS SEGUINTES ABORDAGENS JÁ FORAM TESTADAS E FALHARAM. É EXPRESSAMENTE PROIBIDO REPETI-LAS:"]
                for fh in failed_list[-5:]:  # Mostra as 5 mais recentes
                    neg_lines.append(
                        f"  ❌ [{fh['category']}] Tentativa: \"{fh['approach']}\"\n"
                        f"     Motivo da Falha: {fh['failure_reason']}\n"
                        f"     Causa Raiz: {fh['root_cause']}\n"
                        f"     Regra de Veto: {fh['veto_rule']}"
                    )
                sections.append("### [RESTRIÇÕES NEGATIVAS MANDATÓRIAS - NÃO REPETIR]\n" + "\n".join(neg_lines))

        if not sections:
            return ""

        return "\n\n".join(sections)

    def clear_session(self) -> Dict[str, Any]:
        """Limpa a memória de trabalho efêmera da sessão atual."""
        self.state = {
            "version": "1.0.0",
            "active_goal": "",
            "active_constraints": [],
            "state_variables": {},
            "failed_hypotheses": [],
            "recent_actions": []
        }
        self._save()
        return {"status": "session_cleared"}


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
        elif cmd == "context":
            print(c.get_synthesized_context())
        elif cmd == "clear":
            print(json.dumps(c.clear_session(), indent=2))
        else:
            print("Comandos: fail, validate, context, clear")
    else:
        print(c.get_synthesized_context())
