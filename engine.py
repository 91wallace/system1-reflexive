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
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field
from laya_adapter import LayaNeuralAdapter
from context_memory import ContextMemoryEngine
from config_manager import get_memory_file, get_session_memory_file, atomic_save_json, normalize_text


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
    def __init__(self, memory_path: Optional[str] = None, session_path: Optional[str] = None):
        self.memory_path = memory_path or get_memory_file()
        self.taxonomy = DEFAULT_TAXONOMY
        self.temperature = 1.15
        self.confidence_threshold = 0.70
        self.memory = self._load_memory()
        self.laya = LayaNeuralAdapter()
        self.context_memory = ContextMemoryEngine(storage_path=session_path)
        self._build_index()

    def _build_index(self):
        """Compila índice invertido em memória para classificação reflexiva O(1) por token."""
        patterns = self.memory.get("patterns", {})
        self._term_freq: Dict[str, int] = {}
        for label, keywords in patterns.items():
            for kw in keywords:
                k_norm = normalize_text(kw)
                self._term_freq[k_norm] = self._term_freq.get(k_norm, 0) + 1

        self._single_word_map: Dict[str, List[Tuple[int, float]]] = {}
        self._multi_word_patterns: List[Tuple[str, int, float, Set[str]]] = []

        for idx, label in enumerate(self.taxonomy):
            keywords = patterns.get(label, [])
            for kw in keywords:
                kw_norm = normalize_text(kw)
                if " " in kw_norm:
                    tokens = set(kw_norm.split())
                    self._multi_word_patterns.append((kw_norm, idx, 7.0, tokens))
                else:
                    freq = self._term_freq.get(kw_norm, 1)
                    weight = max(1.0, 5.0 - (freq - 1) * 1.5)
                    self._single_word_map.setdefault(kw_norm, []).append((idx, weight))

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
            atomic_save_json(self.memory_path, data)
        except Exception as e:
            print(f"Erro ao salvar memória: {e}", file=sys.stderr)

    def _save(self):
        self._save_memory_data(self.memory)
        self._build_index()

    def _check_non_latin(self, text: str) -> bool:
        for char in text:
            name = unicodedata.name(char, "")
            if any(s in name for s in ["CYRILLIC", "CJK", "ARABIC", "HEBREW", "THAI", "HANGUL"]):
                return True
        return False

    def classify(self, text: str, temperature: Optional[float] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        t = temperature or self.memory.get("temperature", self.temperature)
        text_norm = normalize_text(text)
        has_non_latin = self._check_non_latin(text)

        logits = [0.0] * len(self.taxonomy)
        matched = False
        words = set(re.findall(r'\b\w+\b', text_norm))

        # 1. Busca O(1) no índice invertido de termos simples
        for token in words:
            if token in self._single_word_map:
                for idx, weight in self._single_word_map[token]:
                    logits[idx] += weight
                    matched = True

        # 2. Casamento de frases multi-palavras pré-indexadas
        for kw_norm, idx, weight, tokens in self._multi_word_patterns:
            if kw_norm in text_norm:
                logits[idx] += 7.0
                matched = True
            elif len(tokens) > 1 and tokens.issubset(words):
                logits[idx] += 6.0
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

        # Rastreia telemetria local e verifica sugestão inteligente de Laya
        self.laya.record_query_metric(requires_system2)
        laya_sug = self.laya.check_laya_suggestion()

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
                "calibrated_rlcd": True,
                "installed": laya_eval.get("installed", False)
            },
            "laya_suggestion": laya_sug if laya_sug.get("should_suggest") else None,
            "meta": {
                "has_non_latin_script": has_non_latin,
                "temperature": t,
                "system1_version": self.memory.get("version", "1.0.0"),
                "architecture": "hybrid_system1_laya_with_working_memory"
            }
        }

    # ==========================================
    # Integração de Memória de Trabalho, Playbooks e Segurança
    # ==========================================
    def record_failure(
        self,
        approach: str,
        failure_reason: str,
        root_cause: str = "",
        veto_rule: str = "",
        category: str = "CODE_BUGFIX"
    ) -> Dict[str, Any]:
        """Registra uma falha e gera regra de veto mandatória no Graveyard."""
        return self.context_memory.record_failure(
            approach=approach,
            failure_reason=failure_reason,
            root_cause=root_cause,
            veto_rule=veto_rule,
            category=category
        )

    def validate_action(self, proposed_action: str) -> Dict[str, Any]:
        """Valida ação contra histórico de falhas e guardrails de segurança."""
        return self.context_memory.validate_action(proposed_action)

    def analyze_action_safety(self, action_text: str) -> Dict[str, Any]:
        """Analisa reflexivamente se a ação possui risco de destruição de dados ou shell inseguro."""
        from context_memory import analyze_action_safety
        return analyze_action_safety(action_text)

    def record_playbook(
        self,
        title: str,
        description: str,
        solution_steps: List[str],
        category: str = "FEATURE_IMPLEMENTATION",
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Registra solução canônica confirmada no catálogo de Playbooks (Hall of Fame)."""
        return self.context_memory.record_playbook(
            title=title,
            description=description,
            solution_steps=solution_steps,
            category=category,
            keywords=keywords
        )

    def recommend_playbooks(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Recomenda Playbooks canônicos usando pontuação BM25."""
        return self.context_memory.recommend_playbooks(query=query, limit=limit)

    def switch_session(self, session_id: str) -> Dict[str, Any]:
        """Alterna a memória de trabalho para outro branch ou identificador de sessão."""
        return self.context_memory.switch_session(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lista todas as sessões registradas no projeto."""
        return self.context_memory.list_sessions()

    def get_synthesized_context(
        self,
        query: str = "",
        max_tokens: int = 800,
        include_negative_constraints: bool = True,
        include_playbooks: bool = True,
        include_state: bool = True
    ) -> str:
        """Retorna bloco de contexto otimizado pelo Token Budget Optimizer."""
        return self.context_memory.get_synthesized_context(
            current_query=query,
            max_tokens=max_tokens,
            include_negative_constraints=include_negative_constraints,
            include_playbooks=include_playbooks,
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

    def learn_system2_execution(
        self,
        prompt: str,
        system2_output: str = "",
        task_category: str = "FEATURE_IMPLEMENTATION",
        execution_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Destilação do System 2:
        Sempre que o LLM generativo conclui uma tarefa complexa, o System 1 absorve
        a correlação e os termos-chave para que na próxima vez possa resolver ou pré-rotear como System 1.
        """
        summary_text = system2_output or execution_summary or ""
        if task_category not in self.taxonomy:
            task_category = "FEATURE_IMPLEMENTATION"

        distillation_entry = {
            "timestamp": time.time(),
            "prompt": prompt,
            "task_category": task_category,
            "summary": summary_text[:300]
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

    def learn_laya_decision(self, prompt: str, category: str, confidence: float = 0.95) -> Dict[str, Any]:
        """
        Aprendizado contínuo com Laya:
        Absorve a predição neural do Laya para refinar os padrões do System 1,
        permitindo que o System 1 responda reflexivamente da próxima vez em <0.5ms.
        """
        if category not in self.taxonomy:
            category = "FEATURE_IMPLEMENTATION"

        res = self.record_feedback(
            text=prompt,
            actual_label=category,
            success=True,
            feedback_note=f"Aprendido da inferência neural Laya (confiança: {confidence})"
        )

        return {
            "status": "laya_learned",
            "category": category,
            "learned_patterns": res.get("added_keywords", [])
        }

    def get_laya_status(self) -> Dict[str, Any]:
        """Retorna status de instalação, telemetria de uso e sugestão do Laya."""
        telemetry = self.laya._load_telemetry()
        suggestion = self.laya.check_laya_suggestion()
        return {
            "installed": self.laya.is_installed(),
            "telemetry": telemetry,
            "suggestion": suggestion
        }

    def install_laya(self) -> Dict[str, Any]:
        """Instala o pacote laya no ambiente."""
        return self.laya.install_laya()

    def dismiss_laya_suggestion(self) -> Dict[str, Any]:
        """Descarta sugestão do Laya para não perguntar mais neste projeto."""
        return self.laya.dismiss_suggestion()


def main():
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
            q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            print(engine.get_synthesized_context(query=q))
        elif cmd == "goal" and len(sys.argv) > 2:
            g = " ".join(sys.argv[2:])
            print(json.dumps(engine.set_active_goal(g), indent=2))
        elif cmd == "feedback" and len(sys.argv) > 3:
            lbl = sys.argv[2]
            txt = " ".join(sys.argv[3:])
            print(json.dumps(engine.record_feedback(txt, lbl, True), indent=2))
        elif cmd == "learn" and len(sys.argv) > 4:
            prompt = sys.argv[2]
            out = sys.argv[3]
            cat = sys.argv[4]
            print(json.dumps(engine.learn_system2_execution(prompt, out, cat), indent=2))
        elif cmd == "graveyard":
            failed = engine.context_memory.state.get("failed_hypotheses", [])
            if not failed:
                print("Nenhuma hipótese invalidada registrada (Graveyard vazio).")
            else:
                print(f"=== SYSTEM 1 GRAVEYARD ({len(failed)} hipóteses invalidadas) ===")
                for fh in failed:
                    print(f"[{fh['id']}] Categoria: {fh['category']} | Tentativa: {fh['approach']}")
                    print(f"    Motivo da Falha: {fh['failure_reason']}")
                    print(f"    Regra de Veto: {fh['veto_rule']}")
                    print("-" * 50)
        elif cmd == "stats":
            patterns = engine.memory.get("patterns", {})
            total_patterns = sum(len(v) for v in patterns.values())
            failed = len(engine.context_memory.state.get("failed_hypotheses", []))
            distillations = len(engine.memory.get("system2_distillations", []))
            history = len(engine.memory.get("history_log", []))
            print("=" * 45)
            print(" 📊 SYSTEM 1 REFLEXIVE - ESTATÍSTICAS DO MOTOR")
            print("=" * 45)
            print(f" • Versão                : {engine.memory.get('version', '1.0.0')}")
            print(f" • Total de Padrões       : {total_patterns}")
            for cat, kws in patterns.items():
                print(f"   - {cat:<26}: {len(kws)} termos")
            print(f" • Graveyard (Vetos)     : {failed} hipóteses invalidadas")
            print(f" • Destilações System 2  : {distillations} registros")
            print(f" • Histórico de Feedback : {history} iterações")
            print(f" • Objetivo Ativo        : {engine.context_memory.state.get('active_goal') or '[Nenhum]'}")
            print("=" * 45)
        elif cmd == "safety" and len(sys.argv) > 2:
            act = " ".join(sys.argv[2:])
            print(json.dumps(engine.analyze_action_safety(act), indent=2))
        elif cmd == "playbook" and len(sys.argv) > 4:
            t = sys.argv[2]
            d = sys.argv[3]
            steps = sys.argv[4].split(";")
            print(json.dumps(engine.record_playbook(t, d, steps), indent=2))
        elif cmd == "recommend" and len(sys.argv) > 2:
            q = " ".join(sys.argv[2:])
            print(json.dumps(engine.recommend_playbooks(q), indent=2))
        elif cmd == "playbooks":
            pbs = engine.context_memory.playbooks.get("playbooks", [])
            if not pbs:
                print("Nenhum playbook registrado no Hall of Fame.")
            else:
                print(f"=== SYSTEM 1 PLAYBOOKS - HALL OF FAME ({len(pbs)} soluções canônicas) ===")
                for pb in pbs:
                    print(f"[{pb['id']}] [{pb['category']}] {pb['title']}")
                    print(f"    Descrição: {pb['description']}")
                    print(f"    Passos: {' -> '.join(pb['solution_steps'])}")
                    print("-" * 50)
        elif cmd == "sessions":
            sess = engine.list_sessions()
            print("=== SESSÕES REGISTRADAS NO PROJETO ===")
            for s in sess:
                current_mark = " (ATIVA)" if s["session_id"] == (engine.context_memory.session_id or "default") else ""
                print(f" • Sessão: {s['session_id']}{current_mark}")
                print(f"   Objetivo: {s['active_goal'] or '[Vazio]'} | Vetos: {s['failed_count']} | Restrições: {s['constraints_count']}")
        elif cmd == "switch" and len(sys.argv) > 2:
            sid = sys.argv[2]
            print(json.dumps(engine.switch_session(sid), indent=2))
        elif cmd == "benchmark":
            from benchmarker import run_benchmark
            runs = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 100
            run_benchmark(runs)
        elif cmd == "laya-status":
            print(json.dumps(engine.get_laya_status(), indent=2, ensure_ascii=False))
        elif cmd == "install-laya":
            print(json.dumps(engine.install_laya(), indent=2, ensure_ascii=False))
        elif cmd == "dismiss-laya":
            print(json.dumps(engine.dismiss_laya_suggestion(), indent=2, ensure_ascii=False))
        elif cmd == "learn-laya" and len(sys.argv) > 3:
            p = sys.argv[2]
            cat = sys.argv[3]
            print(json.dumps(engine.learn_laya_decision(p, cat), indent=2, ensure_ascii=False))
        elif cmd == "clear":
            print(json.dumps(engine.clear_working_memory(), indent=2))
        else:
            print("Uso: system1 [classify | fail | validate | safety | context | goal | playbook | recommend | playbooks | sessions | switch | feedback | learn | learn-laya | laya-status | install-laya | dismiss-laya | graveyard | stats | benchmark | clear]")
    else:
        print(json.dumps(engine.classify("iniciar um novo projeto com scaffolding"), indent=2))


if __name__ == "__main__":
    main()
