"""
Integration test suite for System 1 + Context Memory & Negative Constraint Engine.
"""
import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import System1ContinuousEngine
from context_memory import ContextMemoryEngine


class TestSystem1MemoryIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = System1ContinuousEngine()
        self.engine.clear_working_memory()

    def test_01_classify_normal(self):
        # Warmup
        _ = self.engine.classify("warmup")
        res = self.engine.classify("corrigir erro de sintaxe no arquivo index.js")
        self.assertEqual(res["predicted_label"], "CODE_BUGFIX")
        self.assertGreater(res["confidence"], 0.8)
        self.assertFalse(res["action_validation"]["vetoed"])
        self.assertLess(res["latency_ms"], 50.0)

    def test_02_set_goal_and_state(self):
        goal_res = self.engine.set_active_goal("Otimizar queries do Postgres para o endpoint /pedidos")
        self.assertEqual(goal_res["status"], "goal_set")

        self.engine.set_state_var("target_table", "orders")
        self.engine.add_constraint("Não alterar schema em produção sem migração")

        ctx = self.engine.get_synthesized_context()
        self.assertIn("Otimizar queries do Postgres", ctx)
        self.assertIn("target_table=orders", ctx)
        self.assertIn("Não alterar schema em produção", ctx)

    def test_03_record_failure_and_veto_action(self):
        # 1. Registra falha de abordagem
        fail_res = self.engine.record_failure(
            approach="Adicionar cache Redis no controller antes da query",
            failure_reason="Dados retornados ficaram defasados e causou race condition",
            root_cause="A rota exige consistência transacional imediata",
            category="FEATURE_IMPLEMENTATION"
        )
        self.assertEqual(fail_res["status"], "failure_recorded")

        # 2. Testa validação de ação idêntica / similar
        val_res = self.engine.validate_action("vamos adicionar cache redis no controller para resolver a lentidão")
        self.assertTrue(val_res["vetoed"])
        self.assertEqual(val_res["status"], "ACTION_BLOCKED")
        self.assertEqual(val_res["risk_score"], 1.0)
        self.assertIn("Adicionar cache Redis", val_res["matching_vetos"][0]["approach"])

        # 3. Testa ação diferente (deve ser permitida)
        allowed_res = self.engine.validate_action("criar índice B-tree na coluna created_at da tabela orders")
        self.assertFalse(allowed_res["vetoed"])
        self.assertEqual(allowed_res["status"], "ACTION_ALLOWED")
        self.assertLess(allowed_res["risk_score"], 0.5)

    def test_04_synthesized_context_contains_negative_rules(self):
        self.engine.record_failure(
            approach="Reiniciar o pod do Kubernetes para destravar o banco",
            failure_reason="O pod reiniciou mas o lock no Postgres continuou",
            root_cause="Transação órfã bloqueando a tabela"
        )
        ctx = self.engine.get_synthesized_context()
        self.assertIn("[RESTRIÇÕES NEGATIVAS MANDATÓRIAS - NÃO REPETIR]", ctx)
        self.assertIn("Reiniciar o pod do Kubernetes", ctx)

    def test_05_log_compression(self):
        raw_traceback = """
        Traceback (most recent call last):
          File "/app/main.py", line 120, in handle_request
            res = db.execute_query(sql)
          File "/app/db.py", line 45, in execute_query
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
        psycopg2.OperationalError: server closed the connection unexpectedly
        """
        compressed = self.engine.context_memory.compress_logs(raw_traceback)
        self.assertIn("psycopg2.OperationalError", compressed)
        self.assertLess(len(compressed), 400)

    def test_06_playbooks_recording_and_bm25_recommendation(self):
        # 1. Registra playbook de sucesso
        pb_res = self.engine.record_playbook(
            title="Fix Supabase RLS Recursion",
            description="Resolver loop infinito de recursão na policy do Supabase",
            solution_steps=[
                "Criar função security definer get_auth_user_id()",
                "Substituir auth.uid() pela chamada direta da função na policy",
                "Recarregar schema cache do PostgREST"
            ],
            category="DATABASE_SCHEMA_MIGRATION",
            keywords=["supabase", "rls", "policy", "recursion"]
        )
        self.assertEqual(pb_res["status"], "playbook_recorded")
        self.assertGreater(pb_res["id"], 0)

        # 2. Testa recomendação BM25 com query relacionada
        recs = self.engine.recommend_playbooks("como resolver loop de recursão no supabase rls")
        self.assertTrue(len(recs) > 0)
        self.assertEqual(recs[0]["title"], "Fix Supabase RLS Recursion")
        self.assertIn("get_auth_user_id()", recs[0]["solution_steps"][0])

    def test_07_action_safety_guardrails(self):
        # Test dangerous bash deletion
        res_del = self.engine.analyze_action_safety("rm -rf /var/log/app/*")
        self.assertTrue(res_del["blocked"])
        self.assertEqual(res_del["risk_level"], "CRITICAL")

        # Test dangerous SQL DROP
        res_drop = self.engine.analyze_action_safety("DROP TABLE users CASCADE;")
        self.assertTrue(res_drop["blocked"])
        self.assertIn("SQL destrutivo", res_drop["reasons"][0])

        # Test safe action
        res_safe = self.engine.analyze_action_safety("SELECT id, name FROM users WHERE active = true;")
        self.assertTrue(res_safe["safe"])
        self.assertFalse(res_safe["blocked"])

        # Test validate_action blocking dangerous command directly
        val_block = self.engine.validate_action("rm -rf /")
        self.assertTrue(val_block["vetoed"])
        self.assertEqual(val_block["status"], "ACTION_BLOCKED_SAFETY")

    def test_08_multi_session_isolation(self):
        # Session A
        self.engine.switch_session("feature_auth")
        self.engine.set_active_goal("Implementar OAuth2 com Google")
        self.engine.record_failure("Usar cookie sem Secure flag", "Bloqueado pelo Chrome")
        
        ctx_a = self.engine.get_synthesized_context()
        self.assertIn("Implementar OAuth2 com Google", ctx_a)
        self.assertIn("Usar cookie sem Secure flag", ctx_a)

        # Switch to Session B (deve estar isolada)
        self.engine.switch_session("bugfix_payment")
        self.engine.set_active_goal("Corrigir webhook do Stripe")
        
        ctx_b = self.engine.get_synthesized_context()
        self.assertIn("Corrigir webhook do Stripe", ctx_b)
        self.assertNotIn("Implementar OAuth2 com Google", ctx_b)

        # List sessions
        sessions = self.engine.list_sessions()
        session_ids = [s["session_id"] for s in sessions]
        self.assertIn("feature_auth", session_ids)
        self.assertIn("bugfix_payment", session_ids)

    def test_09_laya_suggestion_and_learning(self):
        # 1. Reset telemetry
        data = {
            "total_queries": 0,
            "fallback_count": 0,
            "laya_prompted": False,
            "laya_installed_at": None
        }
        self.engine.laya._save_telemetry(data)

        status = self.engine.get_laya_status()
        self.assertFalse(status["installed"])
        self.assertFalse(status["suggestion"]["should_suggest"])

        # 2. Simulate 10 queries requiring system2
        for i in range(10):
            self.engine.laya.record_query_metric(required_system2=True)

        status_after_10 = self.engine.get_laya_status()
        self.assertTrue(status_after_10["suggestion"]["should_suggest"])
        self.assertIn("Laya (ModernBERT)", status_after_10["suggestion"]["message"])

        # 3. Dismiss suggestion
        dismiss_res = self.engine.dismiss_laya_suggestion()
        self.assertEqual(dismiss_res["status"], "suggestion_dismissed")

        # Verify it won't suggest again even with more fallback queries
        for _ in range(5):
            self.engine.laya.record_query_metric(required_system2=True)
        status_dismissed = self.engine.get_laya_status()
        self.assertFalse(status_dismissed["suggestion"]["should_suggest"])
        self.assertEqual(status_dismissed["suggestion"]["reason"], "already_prompted")

        # 4. Continuous learning from Laya decision
        learn_res = self.engine.learn_laya_decision(
            prompt="otimizar query postgres com CTE recursivo",
            category="DATABASE_SCHEMA_MIGRATION",
            confidence=0.98
        )
        self.assertEqual(learn_res["status"], "laya_learned")
        self.assertEqual(learn_res["category"], "DATABASE_SCHEMA_MIGRATION")


if __name__ == "__main__":
    unittest.main()

