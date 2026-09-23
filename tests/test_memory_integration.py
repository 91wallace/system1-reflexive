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
        res = self.engine.classify("corrigir erro de sintaxe no arquivo index.js")
        self.assertEqual(res["predicted_label"], "CODE_BUGFIX")
        self.assertGreater(res["confidence"], 0.8)
        self.assertFalse(res["action_validation"]["vetoed"])
        self.assertLess(res["latency_ms"], 20.0)

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


if __name__ == "__main__":
    unittest.main()
