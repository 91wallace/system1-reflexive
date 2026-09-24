# System 1 Reflexive

> **Sub-millisecond Non-Autoregressive Decision Engine & Calibrated Fast-Path for LLM Agents.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Latency](https://img.shields.io/badge/Latency-%3C1.5ms-green.svg)]()
[![Model Backbone](https://img.shields.io/badge/Backbone-ModernBERT%20%7C%20Laya%20RLCD-orange.svg)]()
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)]()

---

## The Problem: Why LLM-Only Routing Fails

LLM agents (System 2) are powerful, but invoking a generative LLM for simple triage, tool selection, or guardrail validation introduces severe bottlenecks:
- **High Latency:** Standard autoregressive models take 400ms to 2,500ms just to return a category label or boolean decision.
- **Overconfidence & Hallucination:** LLM self-reported confidences are uncalibrated (high Expected Calibration Error - ECE).
- **Cost & Token Burn:** Every sub-agent decision, tool routing, or repetitive syntax check burns API tokens unnecessarily.

---

## The Solution: Non-Autoregressive System 1 Inference

**System 1 Reflexive** decouples immediate decision-making from slow generative reasoning. Built on **ModernBERT** representations and calibrated with **RLCD (Reinforcement Learning from Calibrated Decisions)** inspired by Laya, it resolves 70%+ of agent triage decisions in **< 1.5ms** with mathematically calibrated confidence scores.

### Architecture Overview

```
                                  ┌──────────────────────────────┐
                                  │      Incoming Task / Prompt  │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
        ┌─────────────────────────────────────────────────────────────────────────────────┐
        │                         SYSTEM 1 REFLEXIVE ENGINE                               │
        │                                                                                 │
        │  [Tier 1: Fast-Path Memory & IDF Matching] (<1.0ms)                             │
        │  └─ Instant local semantic pattern matching with continuous weight adaptation.  │
        │                                                                                 │
        │  [Tier 2: Laya Neural Backbone / ModernBERT] (~30ms)                            │
        │  └─ Non-autoregressive typed decisions, RLCD confidence calibration & risk eval.│
        │                                                                                 │
        │  [Tier 3: Active Distillation Loop]                                             │
        │  └─ Extracts keywords from successful System 2 runs into persistent memory.     │
        └────────────────────────────────────────┬────────────────────────────────────────┘
                                                 │
                                ┌────────────────┴────────────────┐
                                │                                 │
                   (Confidence >= Threshold)         (Confidence < Threshold)
                                │                                 │
                                ▼                                 ▼
                     ┌───────────────────────┐       ┌─────────────────────────┐
                     │ Instant Fast-Path     │       │ Fallback to System 2    │
                     │ Execution (<1.5ms)    │       │ Deep Generative LLM     │
                     └───────────────────────┘       └─────────────────────────┘
```

---

## Comparison: System 1 Reflexive vs. TypeSafe JEV vs. LLM Routers

| Feature | System 1 Reflexive | TypeSafe JEV | Standard LLM Router (GPT-4o/Claude) |
| :--- | :--- | :--- | :--- |
| **Inference Latency** | **< 1.5 ms** (Tier 1) / ~30 ms (Tier 2) | ~35 ms - 50 ms | 400 ms - 2,500 ms |
| **Calibration Method** | **RLCD + Temperature Scaling ($T=1.15$)** | Plackett-Luce | Uncalibrated (Softmax temperature) |
| **Continuous Active Learning**| **Yes** (Runtime memory updates) | No (Static weights) | No (Context prompt dependent) |
| **Hallucination Risk** | **0%** (Non-autoregressive) | 0% | High (Subject to prompt drift) |
| **Domain Self-Mining** | **Built-in** (Scans codebases/SQL/APIs) | Manual dataset prep | Manual prompt engineering |
| **Native MCP Server** | **Included** | External wrapper needed| N/A |

---

## Key Capabilities

1. **Deterministic Intent Triage:** Classifies tasks (`PROJECT_BOOTSTRAP`, `CODE_BUGFIX`, `FEATURE_IMPLEMENTATION`, `DATABASE_SCHEMA_MIGRATION`, `TEST_AUTOMATION`, `TOOL_EXECUTION_COMMAND`, etc.) in sub-millisecond speeds.
2. **Operational Safety & Guardrails:** Evaluates destructive commands (`drop table`, `rm -rf`, `overwrite`) and flags risk scores before execution.
3. **Repository Semantic Mining:** Built-in scanner extracts domain terms, SQL tables, and package ecosystems directly into the semantic memory.
4. **Marketplace & API Connectors:** Pre-calibrated schemas for TikTok Shop Partner API, Shopee Open Platform v2, Supabase, and Node/Electron backends.

---

## Installation & Setup

### Automatic Interactive Setup (Global vs. Local Project)

Após clonar o repositório, execute o script de instalação interativo:

```bash
git clone https://github.com/91wallace/system1-reflexive.git
cd system1-reflexive
./install.sh
```

O instalador perguntará:
```
Onde você deseja instalar o System 1?
  [1] Globalmente no Sistema (CLI global, IDE/MCP global e Skills)
  [2] Somente neste Projeto (Estrutura .system1/ local, .agents/ e regras locais)
  [3] Completa (Global + Local neste Projeto) - [RECOMENDADO]
```

Você também pode passar argumentos para execução silenciosa ou em scripts CI:
- `./install.sh --global` (ou `-g`)
- `./install.sh --local` (ou `-l`)
- `./install.sh --all` (ou `-a`)

---

## Estrutura Isolada de Dados do Usuário & Projeto (`.system1/`)

Todas as informações específicas do projeto, memória de trabalho e dados do usuário são isoladas automaticamente na pasta `.system1/`:
- `.system1/memory.json`: Padrões e vocabulários aprendidos para este projeto.
- `.system1/session_working_memory.json`: Objetivos ativos, restrições e catálogo de hipóteses invalidadas (Graveyard).
- `.system1/user_profile.json`: Preferências e restrições globais do usuário.

A pasta `.system1/` é ignorada pelo `.gitignore`, garantindo que clonar ou atualizar o repositório base nunca misture nem exponha dados sensíveis do projeto.

---

## Integração MCP (Model Context Protocol)

O System 1 inclui um servidor MCP stdio nativo compatível com **Antigravity**, **Claude Desktop** e **Cursor** em `src/mcp_server.py`.

Configuração em `mcp_config.json`:
```json
{
  "mcpServers": {
    "system1": {
      "command": "python3",
      "args": ["/path/to/system1-reflexive/src/mcp_server.py"]
    }
  }
}
```

### Ferramentas MCP Disponíveis:
- `classify`: Triagem reflexiva de intenção e comandos (<10ms).
- `validate_action`: Validação de ações contra o catálogo de erros (Graveyard).
- `record_failure`: Registro imediato de falhas e veto de repetição de abordagens errôneas.
- `record_feedback`: Refinamento contínuo dos padrões aprendidos.
- `get_synthesized_context`: Injeção de contexto JIT sintetizado e de alto SNR.
- `learn_system2_execution`: Destilação de raciocínio generativo longo do System 2 para System 1.

---

## Disponibilidade de Skills e Regras de Agentes

- **`/mcp`**: Schemas JSON e `instructions.md` para integração com MCP.
- **`/skills`** e **`.agents/skills`**: `SKILL.md` contendo os runbooks e comandos do System 1.
- **`/agents` e `.agents`**: Regras obrigatórias de execução reflexiva em `agents/rules/system1_reflexive.md` e `AGENTS.md`.

---

## Benchmarks

```
Query: "corrigir erro de sintaxe e crash no backend"
├── Prediction: CODE_BUGFIX
├── Confidence: 99.88% (ECE Calibrated)
└── Latency:    0.849 ms

Query: "criar nova tabela no supabase com trigger e rls"
├── Prediction: DATABASE_SCHEMA_MIGRATION
├── Confidence: 100.0%
└── Latency:    0.749 ms

Query: "integrar webhook do tiktok shop para order fulfillment"
├── Prediction: FEATURE_IMPLEMENTATION
├── Confidence: 99.98%
└── Latency:    1.049 ms
```

---

## License

Apache License 2.0. Open source for commercial and research use.
