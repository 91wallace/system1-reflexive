#!/usr/bin/env python3
"""
Native Model Context Protocol (MCP) stdio Server for System 1 Reflexive.
Permite integração direta com Antigravity, Claude Desktop, Cursor e outros clientes MCP.
Implementa o protocolo JSON-RPC 2.0 com suporte a ferramentas de classificação reflexiva,
restrições negativas (Graveyard) e memória de trabalho.
"""

import sys
import os
import json
import logging
import traceback
from typing import Dict, Any, Optional

# Adiciona diretório raiz ao sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine import System1ContinuousEngine
from config_manager import get_data_dir

# Configuração de logger seguro em stderr (stdout é reservado exclusivamente para JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="[System1 MCP] %(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)

# Definições de ferramentas nativas do System 1
MCP_TOOLS = [
    {
        "name": "classify",
        "description": "Classifica reflexivamente em <10ms a intenção, tarefa ou comando do usuário com probabilidades calibradas (System 1 Lia Engine). Retorna a categoria tipada, confiança, validação de risco e se requer fallback para System 2.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texto, comando ou objetivo a ser classificado pelo System 1."
                },
                "temperature": {
                    "type": "number",
                    "description": "Fator de temperatura para calibração de softmax (padrão: 1.15).",
                    "default": 1.15
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "validate_action",
        "description": "Verifica em <1ms se uma ação ou comando proposto coincide com abordagens já invalidadas na sessão (Graveyard). Retorna se a ação foi vetada e o risco associado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposed_action": {
                    "type": "string",
                    "description": "Ação, comando ou solução que o agente planeja sugerir ou executar."
                }
            },
            "required": ["proposed_action"]
        }
    },
    {
        "name": "record_failure",
        "description": "Registra uma tentativa ou abordagem que falhou, criando uma regra de veto definitiva (Negative Constraint) para impedir que o modelo repita a mesma solução ineficaz.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "approach": {
                    "type": "string",
                    "description": "Descrição clara da abordagem testada (ex: 'Aumentar timeout no Nginx para 300s')."
                },
                "failure_reason": {
                    "type": "string",
                    "description": "Sintoma ou mensagem de erro observada após tentar a solução."
                },
                "root_cause": {
                    "type": "string",
                    "description": "Causa raiz identificada (opcional, ex: 'Gargalo é a query do banco, não o proxy').",
                    "default": ""
                },
                "veto_rule": {
                    "type": "string",
                    "description": "Regra mandatória que proíbe essa abordagem.",
                    "default": ""
                },
                "category": {
                    "type": "string",
                    "description": "Categoria da tarefa (ex: CODE_BUGFIX, DATABASE_SCHEMA_MIGRATION).",
                    "default": "CODE_BUGFIX"
                }
            },
            "required": ["approach", "failure_reason"]
        }
    },
    {
        "name": "record_feedback",
        "description": "Registra feedback de aprendizado após cada ação executada com sucesso, refinando a matriz de probabilidade e as palavras-chave do System 1.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "O texto ou comando executado."
                },
                "actual_label": {
                    "type": "string",
                    "description": "A categoria real correspondente (ex: PROJECT_BOOTSTRAP, CODE_BUGFIX, FEATURE_IMPLEMENTATION, DATABASE_SCHEMA_MIGRATION, TEST_AUTOMATION, ARCHITECTURE_DESIGN, TOOL_EXECUTION_COMMAND)."
                },
                "success": {
                    "type": "boolean",
                    "description": "Indica se a execução foi bem-sucedida.",
                    "default": True
                },
                "feedback_note": {
                    "type": "string",
                    "description": "Nota contextual opcional sobre o feedback.",
                    "default": ""
                }
            },
            "required": ["text", "actual_label"]
        }
    },
    {
        "name": "get_synthesized_context",
        "description": "Retorna o bloco de contexto de trabalho sintetizado e livre de ruído (estado ativo, variáveis e restrições negativas mandatórias) para injeção imediata no prompt da LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Instrução ou consulta atual (opcional).",
                    "default": ""
                },
                "include_negative_constraints": {
                    "type": "boolean",
                    "description": "Se deve incluir o Graveyard de soluções invalidadas (padrão: true).",
                    "default": True
                },
                "include_playbooks": {
                    "type": "boolean",
                    "description": "Se deve incluir playbooks e soluções comprovadas (padrão: true).",
                    "default": True
                },
                "include_state": {
                    "type": "boolean",
                    "description": "Se deve incluir o estado e variáveis ativas (padrão: true).",
                    "default": True
                },
                "max_tokens": {
                    "type": "number",
                    "description": "Orçamento máximo de tokens para compressão JIT (padrão: 800).",
                    "default": 800
                }
            }
        }
    },
    {
        "name": "record_playbook",
        "description": "Registra uma solução canônica bem-sucedida (Playbook / Hall of Fame) para acelerar a resolução de problemas futuros semelhantes na primeira tentativa.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título claro da solução ou procedimento testado e aprovado."
                },
                "description": {
                    "type": "string",
                    "description": "Resumo do problema resolvido e contexto."
                },
                "solution_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista ordenada de passos ou comandos que executam a solução."
                },
                "category": {
                    "type": "string",
                    "description": "Categoria da tarefa (ex: CODE_BUGFIX, FEATURE_IMPLEMENTATION, DATABASE_SCHEMA_MIGRATION).",
                    "default": "FEATURE_IMPLEMENTATION"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Palavras-chave adicionais para indexação BM25."
                }
            },
            "required": ["title", "description", "solution_steps"]
        }
    },
    {
        "name": "recommend_playbooks",
        "description": "Recomenda playbooks canônicos já testados e comprovados neste projeto usando pontuação BM25.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Instrução, erro ou objetivo atual para buscar playbooks correspondentes."
                },
                "limit": {
                    "type": "number",
                    "description": "Número máximo de recomendações (padrão: 3).",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_action_safety",
        "description": "Analisa reflexivamente se um comando de terminal ou query SQL contém operações destrutivas ou de alto risco.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_text": {
                    "type": "string",
                    "description": "Comando Bash, script ou consulta SQL a ser inspecionada."
                }
            },
            "required": ["action_text"]
        }
    },
    {
        "name": "switch_session",
        "description": "Alterna a memória de trabalho para outra branch do Git ou identificador de sessão isolada.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Identificador da sessão ou nome da branch (ex: feature_checkout, bugfix_login)."
                }
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "list_sessions",
        "description": "Lista todas as sessões isoladas registradas no projeto com contagem de vetos e objetivos.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "learn_system2_execution",
        "description": "Destila o conhecimento de raciocínio complexo executado pelo System 2 (LLM), salvando os pares de instrução e padrão semântico para que o System 1 aprenda e execute mais rápido em iterações futuras.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "O prompt ou objetivo complexo que foi processado pelo System 2."
                },
                "system2_output": {
                    "type": "string",
                    "description": "Resumo ou saída gerada pelo System 2."
                },
                "task_category": {
                    "type": "string",
                    "description": "Categoria da tarefa destilada (ex: FEATURE_IMPLEMENTATION, CODE_BUGFIX)."
                }
            },
            "required": ["prompt", "system2_output", "task_category"]
        }
    },
    {
        "name": "set_active_goal",
        "description": "Define o objetivo principal ativo da sessão de trabalho na memória de trabalho do System 1.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "O objetivo ou meta principal a ser alcançada."
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "add_constraint",
        "description": "Adiciona uma restrição operacional à memória de trabalho da sessão.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "constraint": {
                    "type": "string",
                    "description": "A restrição ou diretriz mandatória a ser respeitada."
                }
            },
            "required": ["constraint"]
        }
    },
    {
        "name": "clear_working_memory",
        "description": "Limpa a memória de trabalho efêmera da sessão atual (objetivo, variáveis e restrições da sessão).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


class System1MCPServer:
    def __init__(self):
        self.engine = System1ContinuousEngine()
        logging.info(f"System 1 MCP Server iniciado. Data dir: {get_data_dir()}")

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        logging.info(f"Recebida mensagem MCP: method={method}, id={req_id}")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "system1-reflexive",
                        "version": "1.0.0"
                    }
                }
            }

        elif method in ("notifications/initialized", "initialized"):
            logging.info("Cliente MCP inicializado.")
            return None

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }

        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": "system1://context",
                            "name": "Working Memory Synthesized Context",
                            "description": "Bloco de contexto de trabalho ativo (objetivo, variáveis e restrições) para injeção JIT.",
                            "mimeType": "text/plain"
                        },
                        {
                            "uri": "system1://graveyard",
                            "name": "Negative Constraints Graveyard",
                            "description": "Catálogo de hipóteses e abordagens que falharam com regras de veto associadas.",
                            "mimeType": "application/json"
                        },
                        {
                            "uri": "system1://patterns",
                            "name": "Learned Semantic Patterns & Taxonomy",
                            "description": "Dicionário de palavras-chave, taxonomia e termos aprendidos pelo System 1.",
                            "mimeType": "application/json"
                        }
                    ]
                }
            }

        elif method == "resources/read":
            uri = params.get("uri", "")
            if uri == "system1://context":
                content_text = self.engine.get_synthesized_context()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "text/plain",
                                "text": content_text or "[Nenhum contexto ativo definido no momento]"
                            }
                        ]
                    }
                }
            elif uri == "system1://graveyard":
                failed = self.engine.context_memory.state.get("failed_hypotheses", [])
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(failed, indent=2, ensure_ascii=False)
                            }
                        ]
                    }
                }
            elif uri == "system1://patterns":
                patterns = self.engine.memory.get("patterns", {})
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(patterns, indent=2, ensure_ascii=False)
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": f"Recurso MCP não encontrado: {uri}"
                    }
                }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": MCP_TOOLS
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            return self._execute_tool(req_id, tool_name, tool_args)

        else:
            if req_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Método não encontrado: {method}"
                    }
                }
            return None

    def _execute_tool(self, req_id: Any, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result_data = None

            if name == "classify":
                text = args.get("text", "")
                result_data = self.engine.classify(text)

            elif name == "validate_action":
                action = args.get("proposed_action", "")
                result_data = self.engine.validate_action(action)

            elif name == "record_failure":
                result_data = self.engine.record_failure(
                    approach=args.get("approach", ""),
                    failure_reason=args.get("failure_reason", ""),
                    root_cause=args.get("root_cause", ""),
                    veto_rule=args.get("veto_rule", ""),
                    category=args.get("category", "CODE_BUGFIX")
                )

            elif name == "record_feedback":
                result_data = self.engine.record_feedback(
                    text=args.get("text", ""),
                    actual_label=args.get("actual_label", ""),
                    success=args.get("success", True),
                    feedback_note=args.get("feedback_note", "")
                )

            elif name == "get_synthesized_context":
                ctx_text = self.engine.get_synthesized_context(
                    query=args.get("query", ""),
                    max_tokens=args.get("max_tokens", 800),
                    include_negative_constraints=args.get("include_negative_constraints", True),
                    include_playbooks=args.get("include_playbooks", True),
                    include_state=args.get("include_state", True)
                )
                result_data = {"synthesized_context": ctx_text}

            elif name == "record_playbook":
                result_data = self.engine.record_playbook(
                    title=args.get("title", ""),
                    description=args.get("description", ""),
                    solution_steps=args.get("solution_steps", []),
                    category=args.get("category", "FEATURE_IMPLEMENTATION"),
                    keywords=args.get("keywords", [])
                )

            elif name == "recommend_playbooks":
                result_data = self.engine.recommend_playbooks(
                    query=args.get("query", ""),
                    limit=args.get("limit", 3)
                )

            elif name == "analyze_action_safety":
                result_data = self.engine.analyze_action_safety(args.get("action_text", ""))

            elif name == "switch_session":
                result_data = self.engine.switch_session(args.get("session_id", "default"))

            elif name == "list_sessions":
                result_data = {"sessions": self.engine.list_sessions()}

            elif name == "learn_system2_execution":
                result_data = self.engine.learn_system2_execution(
                    prompt=args.get("prompt", ""),
                    system2_output=args.get("system2_output", ""),
                    task_category=args.get("task_category", "FEATURE_IMPLEMENTATION")
                )

            elif name == "set_active_goal":
                result_data = self.engine.set_active_goal(args.get("goal", ""))

            elif name == "add_constraint":
                result_data = self.engine.add_constraint(args.get("constraint", ""))

            elif name == "clear_working_memory":
                result_data = self.engine.clear_working_memory()

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Ferramenta desconhecida: {name}"}],
                        "isError": True
                    }
                }

            formatted_output = json.dumps(result_data, indent=2, ensure_ascii=False)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": formatted_output
                        }
                    ],
                    "isError": False
                }
            }

        except Exception as e:
            err_msg = f"Erro executando {name}: {str(e)}\n{traceback.format_exc()}"
            logging.error(err_msg)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": err_msg}],
                    "isError": True
                }
            }

    def run(self):
        """Loop principal lendo JSON-RPC da entrada padrão (stdin)."""
        logging.info("Aguardando conexões MCP via stdin...")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                msg = json.loads(line_str)
                resp = self.handle_request(msg)
                if resp is not None:
                    out_line = json.dumps(resp, ensure_ascii=False)
                    sys.stdout.write(out_line + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError as jde:
                logging.error(f"Erro decodificando JSON-RPC: {jde} - Linha: {line_str}")
            except Exception as ex:
                logging.error(f"Exceção no loop MCP: {ex}")


if __name__ == "__main__":
    server = System1MCPServer()
    server.run()
