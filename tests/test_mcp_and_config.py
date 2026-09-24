"""
Tests for Config Manager and MCP Stdio Server.
"""
import unittest
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import get_data_dir, get_memory_file, get_session_memory_file
from src.mcp_server import System1MCPServer


class TestMCPAndConfig(unittest.TestCase):
    def test_01_config_paths(self):
        data_dir = get_data_dir()
        self.assertTrue(os.path.exists(data_dir))
        self.assertTrue(data_dir.endswith(".system1"))

        mem_file = get_memory_file()
        self.assertTrue(os.path.exists(mem_file))

        sess_file = get_session_memory_file()
        self.assertTrue(os.path.exists(sess_file))

    def test_02_mcp_server_initialize(self):
        server = System1MCPServer()
        res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        self.assertEqual(res["result"]["serverInfo"]["name"], "system1-reflexive")

    def test_03_mcp_server_tools_list(self):
        server = System1MCPServer()
        res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("classify", tool_names)
        self.assertIn("validate_action", tool_names)
        self.assertIn("record_failure", tool_names)
        self.assertIn("record_feedback", tool_names)
        self.assertIn("get_synthesized_context", tool_names)
        self.assertIn("learn_system2_execution", tool_names)

    def test_04_mcp_server_tools_call(self):
        server = System1MCPServer()
        res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "classify",
                "arguments": {"text": "corrigir syntax error no node.js"}
            }
        })
        self.assertFalse(res["result"]["isError"])
        content = json.loads(res["result"]["content"][0]["text"])
        self.assertEqual(content["predicted_label"], "CODE_BUGFIX")

    def test_05_mcp_server_learn_and_context(self):
        server = System1MCPServer()
        
        # Test learn_system2_execution tool
        learn_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "learn_system2_execution",
                "arguments": {
                    "prompt": "otimizar indice b-tree no postgresql para relatorios",
                    "system2_output": "Criado indice composto nas colunas date e store_id",
                    "task_category": "DATABASE_SCHEMA_MIGRATION"
                }
            }
        })
        self.assertFalse(learn_res["result"]["isError"])
        learn_data = json.loads(learn_res["result"]["content"][0]["text"])
        self.assertEqual(learn_data["status"], "system2_distilled")

        # Test set_active_goal tool
        goal_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "set_active_goal",
                "arguments": {"goal": "Migrar banco de dados para PostgreSQL 16"}
            }
        })
        self.assertFalse(goal_res["result"]["isError"])

        # Test get_synthesized_context tool
        ctx_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_synthesized_context",
                "arguments": {}
            }
        })
        self.assertFalse(ctx_res["result"]["isError"])
        ctx_data = json.loads(ctx_res["result"]["content"][0]["text"])
        self.assertIn("Migrar banco de dados para PostgreSQL 16", ctx_data["synthesized_context"])

    def test_06_mcp_resources(self):
        server = System1MCPServer()

        # 1. Test resources/list
        list_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/list",
            "params": {}
        })
        self.assertIn("resources", list_res["result"])
        uris = [r["uri"] for r in list_res["result"]["resources"]]
        self.assertIn("system1://context", uris)
        self.assertIn("system1://graveyard", uris)
        self.assertIn("system1://patterns", uris)

        # 2. Test resources/read on system1://patterns
        read_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {"uri": "system1://patterns"}
        })
        self.assertIn("contents", read_res["result"])
        patt_json = json.loads(read_res["result"]["contents"][0]["text"])
        self.assertIn("CODE_BUGFIX", patt_json)

    def test_07_mcp_playbooks_safety_and_sessions(self):
        server = System1MCPServer()

        # 1. Test record_playbook
        pb_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "record_playbook",
                "arguments": {
                    "title": "Optimizing Redis Connection Pool",
                    "description": "Configurar max_connections e pool timeout no redis-py",
                    "solution_steps": ["Usar ConnectionPool(max_connections=20)", "Configurar health_check_interval=30"],
                    "category": "FEATURE_IMPLEMENTATION"
                }
            }
        })
        self.assertFalse(pb_res["result"]["isError"])

        # 2. Test recommend_playbooks
        rec_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "recommend_playbooks",
                "arguments": {"query": "redis connection pool timeout"}
            }
        })
        self.assertFalse(rec_res["result"]["isError"])
        rec_data = json.loads(rec_res["result"]["content"][0]["text"])
        self.assertTrue(len(rec_data) > 0)
        self.assertEqual(rec_data[0]["title"], "Optimizing Redis Connection Pool")

        # 3. Test analyze_action_safety
        safe_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "analyze_action_safety",
                "arguments": {"action_text": "rm -rf /var/lib/data"}
            }
        })
        self.assertFalse(safe_res["result"]["isError"])
        safe_data = json.loads(safe_res["result"]["content"][0]["text"])
        self.assertTrue(safe_data["blocked"])

        # 4. Test switch_session and list_sessions
        sw_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "switch_session",
                "arguments": {"session_id": "test_mcp_session"}
            }
        })
        self.assertFalse(sw_res["result"]["isError"])

        list_res = server.handle_request({
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "list_sessions",
                "arguments": {}
            }
        })
        self.assertFalse(list_res["result"]["isError"])
        list_data = json.loads(list_res["result"]["content"][0]["text"])
        s_ids = [s["session_id"] for s in list_data["sessions"]]
        self.assertIn("test_mcp_session", s_ids)


if __name__ == "__main__":
    unittest.main()
