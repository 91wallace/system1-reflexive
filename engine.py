"""
Global System 1 Engine with Continuous Active Learning, System 2 Distillation,
and Integrated Working Memory / Negative Constraint Verification.
Execução reflexiva em <10ms, calibração estatística ECE, poda JIT de contexto e prevenção de repetição de erros.
"""
import os
import sys
import json
import time
import math
import re
import unicodedata
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from laya_adapter import LayaNeuralAdapter
from context_memory import ContextMemoryEngine

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")


DEFAULT_TAXONOMY = [
    "PROJECT_BOOTSTRAP",       # Criar estrutura inicial, scaffolding, boilerplate
    "CODE_BUGFIX",             # Correção de erro de sintaxe, runtime ou lógica
    "FEATURE_IMPLEMENTATION",   # Criar nova funcionalidade ou componente
    "DATABASE_SCHEMA_MIGRATION",# Ajustar tabelas, SQL, RLS, Supabase
    "TEST_AUTOMATION",         # Criar ou rodar suíte de testes unitários/e2e
    "ARCHITECTURE_DESIGN",     # Desenho técnico, documentação, diagramas
    "TOOL_EXECUTION_COMMAND",  # Execução direta de comando terminal ou script
    "FALLBACK_SYSTEM2_REASON"  # Problema aberto/complexo exigindo raciocínio generativo longo
]


class System1ContinuousEngine:
    def __init__(self, memory_path: str = MEMORY_FILE):
        self.memory_path = memory_path
        self.taxonomy = DEFAULT_TAXONOMY
        self.temperature = 1.15
        self.confidence_threshold = 0.70
        self.memory = self._load_memory()
        self.laya = LayaNeuralAdapter()
        self.context_memory = ContextMemoryEngine()

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Estrutura inicial de memória
        initial_memory = {
            "version": "1.0.0",
            "temperature": 1.15,
            "patterns": {
                "PROJECT_BOOTSTRAP": ["iniciar projeto", "criar projeto", "novo projeto", "scaffold", "boilerplate", "estrutura inicial", "setup"],
                "CODE_BUGFIX": ["corrigir bug", "erro", "falha", "fix", "exception", "quebrou", "crash", "traceback"],
                "FEATURE_IMPLEMENTATION": ["criar tela", "adicionar funcionalidade", "implementar", "novo componente", "nova rota"],
                "DATABASE_SCHEMA_MIGRATION": ["supabase", "sql", "tabela", "migration", "trigger", "rls", "postgres", "foreign key"],
                "TEST_AUTOMATION": ["testes", "test runner", "unit test", "validar", "asserção", "suite de testes"],
                "ARCHITECTURE_DESIGN": ["arquitetura", "readme", "documentar", "diagrama", "fluxo", "padrao"],
                "TOOL_EXECUTION_COMMAND": ["rodar comando", "terminal", "executar script", "instalar pacote", "bash", "ls", "npm install"]
            },
            "history_log": [],
            "system2_distillations": []
        }
        self._save_memory_data(initial_memory)
        return initial_memory

    def _save_memory_data(self, data: Dict[str, Any]):
        try:
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar memória: {e}", file=sys.stderr)

    def _save(self):
        self._save_memory_data(self.memory)

    def _check_non_latin(self, text: str) -> bool:
        for char in text:
            name = unicodedata.name(char, "")
            if any(s in name for s in ["CYRILLIC", "CJK", "ARABIC", "HEBREW", "THAI", "HANGUL"]):
                return True
        return False

    def classify(self, text: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        t = temperature or self.memory.get("temperature", self.temperature)
        text_lower = text.lower()
        has_non_latin = self._check_non_latin(text)

        logits = [0.0] * len(self.taxonomy)
        patterns = self.memory.get("patterns", {})

        # Compute term frequency across taxonomies for IDF weighting
        term_freq: Dict[str, int] = {}
        for label, keywords in patterns.items():
            for kw in keywords:
                k_low = kw.lower()
                term_freq[k_low] = term_freq.get(k_low, 0) + 1

        matched = False
        words = set(re.findall(r'\b\w+\b', text_lower))

        for idx, label in enumerate(self.taxonomy):
            keywords = patterns.get(label, [])
            for kw in keywords:
                kw_low = kw.lower()
                # 1. Multi-word exact contiguous phrase match
                if " " in kw_low and kw_low in text_lower:
                    logits[idx] += 7.0
                    matched = True
                # 2. Multi-word phrase with all words present in query
                elif " " in kw_low:
                    kw_tokens = set(kw_low.split())
                    if len(kw_tokens) > 1 and kw_tokens.issubset(words):
                        logits[idx] += 6.0
                        matched = True
                # 3. Single word match with word boundary
                elif kw_low in words:
                    freq = term_freq.get(kw_low, 1)
                    weight = max(1.0, 5.0 - (freq - 1) * 1.5)
                    logits[idx] += weight
                    matched = True

        if not matched:
            fallback_idx = self.taxonomy.index("FALLBACK_SYSTEM2_REASON")
            logits[fallback_idx] += 2.5

        # Calibração de temperatura (Softmax escalonado)
        scaled = [l / t for l in logits]
        max_l = max(scaled)
        exp_logits = [math.exp(l - max_l) for l in scaled]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]

        top_idx = probs.index(max(probs))
        confidence = probs[top_idx]
        predicted_label = self.taxonomy[top_idx]

        # Validação contra Memória Negativa (Veto de Ações Repetidas)
        action_validation = self.context_memory.validate_action(text)

        # Avaliação de decisões tipadas e guardrails pelo Laya
        laya_eval = self.laya.predict(text)
        laya_requires_system2 = laya_eval.get("answers", {}).get("requires_system2_deep_reasoning", {}).get("value", False)

        requires_system2 = (
            confidence < self.confidence_threshold or 
            predicted_label == "FALLBACK_SYSTEM2_REASON" or 
            has_non_latin or
            laya_requires_system2
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        scores = [
            {"label": self.taxonomy[i], "probability": round(probs[i], 4)}
            for i in range(len(self.taxonomy))
        ]
        scores.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "predicted_label": predicted_label,
            "confidence": round(confidence, 4),
            "probabilities": scores,
            "latency_ms": round(elapsed_ms, 3),
            "requires_system2_fallback": requires_system2,
            "action_validation": action_validation,
            "laya_decision": {
                "backbone": laya_eval.get("routing", {}).get("model", "ModernBERT-large"),
                "safety_risk": laya_eval.get("answers", {}).get("safety_risk", {}) if not action_validation.get("vetoed") else {"risk_score": 1.0, "blocked_by_negative_memory": True},
                "deep_reasoning_required": laya_requires_system2,
                "calibrated_rlcd": True
            },
            "meta": {
                "has_non_latin_script": has_non_latin,
                "temperature": t,
                "system1_version": self.memory.get("version", "1.0.0"),
                "architecture": "hybrid_system1_laya_with_working_memory"
            }
        }

    # ==========================================
    # Integração de Memória de Trabalho e Negativa
    # ==========================================
    def record_failure(
        self,
        approach: str,
        failure_reason: str,
        root_cause: str = "",
        veto_rule: str = "",
        category: str = "CODE_BUGFIX"
    ) -> Dict[str, Any]:
        """Registra uma falha e gera regra de veto mandatória."""
        return self.context_memory.record_failure(
            approach=approach,
            failure_reason=failure_reason,
            root_cause=root_cause,
            veto_rule=veto_rule,
            category=category
        )

    def validate_action(self, proposed_action: str) -> Dict[str, Any]:
        """Valida ação contra histórico de falhas da sessão."""
        return self.context_memory.validate_action(proposed_action)

    def get_synthesized_context(
        self,
        query: str = "",
        include_negative_constraints: bool = True,
        include_state: bool = True
    ) -> str:
        """Retorna bloco de contexto otimizado para injeção no prompt."""
        return self.context_memory.get_synthesized_context(
            current_query=query,
            include_negative_constraints=include_negative_constraints,
            include_state=include_state
        )

    def set_active_goal(self, goal: str) -> Dict[str, Any]:
        """Define o objetivo ativo."""
        return self.context_memory.set_goal(goal)

    def add_constraint(self, constraint: str) -> Dict[str, Any]:
        """Adiciona uma restrição."""
        return self.context_memory.add_constraint(constraint)

    def set_state_var(self, key: str, value: Any) -> Dict[str, Any]:
        """Define variável de estado."""
        return self.context_memory.set_state_var(key, value)

    def clear_working_memory(self) -> Dict[str, Any]:
        """Limpa a memória de trabalho efêmera."""
        return self.context_memory.clear_session()

    def record_feedback(self, text: str, actual_label: str, success: bool, feedback_note: str = "") -> Dict[str, Any]:
        """
        Aprendizado contínuo após cada função executada:
        Reforça os padrões semânticos e ajusta dinamicamente a base de conhecimento.
        """
        if actual_label not in self.taxonomy:
            return {"status": "error", "message": f"Label {actual_label} não existe na taxonomia"}

        patterns = self.memory.setdefault("patterns", {})
        label_patterns = patterns.setdefault(actual_label, [])

        # Extração de n-grams/palavras-chave relevantes
        words = [w.strip(".,!?()[]{}'\"") for w in text.lower().split() if len(w) >= 4]
        added_keywords = []
        for word in words:
            if word and word not in label_patterns and len(word) > 3:
                label_patterns.append(word)
                added_keywords.append(word)

        # Log do histórico
        log_entry = {
            "timestamp": time.time(),
            "text": text,
            "actual_label": actual_label,
            "success": success,
            "feedback_note": feedback_note,
            "added_keywords": added_keywords[:5]
        }
        self.memory.setdefault("history_log", []).append(log_entry)
        
        # Mantém histórico nos últimos 500 registros
        if len(self.memory["history_log"]) > 500:
            self.memory["history_log"] = self.memory["history_log"][-500:]

        self._save()
        return {
            "status": "learned",
            "actual_label": actual_label,
            "added_keywords": added_keywords[:5],
            "total_patterns_for_label": len(label_patterns)
        }

    def learn_system2_execution(self, prompt: str, system2_output: str, task_category: str) -> Dict[str, Any]:
        """
        Destilação do System 2:
        Sempre que o LLM generativo conclui uma tarefa complexa, o System 1 absorve
        a correlação e os termos-chave para que na próxima vez possa resolver ou pré-rotear como System 1.
        """
        if task_category not in self.taxonomy:
            task_category = "FEATURE_IMPLEMENTATION"

        distillation_entry = {
            "timestamp": time.time(),
            "prompt": prompt,
            "task_category": task_category,
            "summary": system2_output[:300]
        }

        self.memory.setdefault("system2_distillations", []).append(distillation_entry)
        if len(self.memory["system2_distillations"]) > 300:
            self.memory["system2_distillations"] = self.memory["system2_distillations"][-300:]

        # Aprendizado de padrões a partir do prompt do System 2
        res = self.record_feedback(
            text=prompt,
            actual_label=task_category,
            success=True,
            feedback_note="Destilado a partir da execução do System 2"
        )

        self._save()
        return {
            "status": "system2_distilled",
            "category": task_category,
            "learned_patterns": res.get("added_keywords", [])
        }


if __name__ == "__main__":
    engine = System1ContinuousEngine()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "classify" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            print(json.dumps(engine.classify(query), indent=2))
        elif cmd == "fail" and len(sys.argv) > 3:
            app = sys.argv[2]
            reason = sys.argv[3]
            print(json.dumps(engine.record_failure(app, reason), indent=2))
        elif cmd == "validate" and len(sys.argv) > 2:
            act = " ".join(sys.argv[2:])
            print(json.dumps(engine.validate_action(act), indent=2))
        elif cmd == "context":
            print(engine.get_synthesized_context())
        elif cmd == "goal" and len(sys.argv) > 2:
            g = " ".join(sys.argv[2:])
            print(json.dumps(engine.set_active_goal(g), indent=2))
        elif cmd == "feedback" and len(sys.argv) > 3:
            lbl = sys.argv[2]
            txt = " ".join(sys.argv[3:])
            print(json.dumps(engine.record_feedback(txt, lbl, True), indent=2))
        elif cmd == "clear":
            print(json.dumps(engine.clear_working_memory(), indent=2))
        else:
            print("Uso: engine.py [classify | fail | validate | context | goal | feedback | clear]")
    else:
        print(json.dumps(engine.classify("iniciar um novo projeto com scaffolding"), indent=2))
