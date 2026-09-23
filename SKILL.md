---
name: system1
description: >-
  Ativa o motor de inteligência reflexiva System 1 (Lia Engine / ModernBERT) com latência <10ms,
  triagem automática, memória de trabalho ativa, prevenção contra repetição de erros e poda JIT de contexto.
---

# System 1 Reflexive Engine, Working Memory & Negative Constraint System

Esta skill integra o motor reflexivo do System 1 com a gestão dinâmica de memória de trabalho e catálogo de soluções invalidadas.

---

## ⚡ Comandos e Ações Rápidas

1. **Triagem Imediata (<10ms):**
   * Classificar o comando do usuário e verificar colisões com erros passados:
   ```bash
   python3 /root/.gemini/antigravity-cli/system1_global/engine.py classify "<comando_ou_objetivo>"
   ```

2. **Registro de Falha & Criação de Veto (Evitar Repetições):**
   * Se uma abordagem falhar ou não surtir efeito, registre-a imediatamente no Graveyard:
   ```bash
   python3 /root/.gemini/antigravity-cli/system1_global/engine.py fail "<abordagem_testada>" "<motivo_do_erro>"
   ```

3. **Validação Prévia de Ação (<1ms):**
   * Antes de propor ou executar uma solução crítica, verifique se ela está liberada:
   ```bash
   python3 /root/.gemini/antigravity-cli/system1_global/engine.py validate "<acao_planejada>"
   ```

4. **Injeção de Contexto Sintetizado (Alto SNR):**
   * Recupere apenas os estados ativos e as regras de restrições negativas mandatórias:
   ```bash
   python3 /root/.gemini/antigravity-cli/system1_global/engine.py context
   ```

5. **Ciclo de Aprendizado Ativo & Destilação:**
   * **Após cada função bem-sucedida:** Registrar feedback (`record_feedback`).
   * **Após raciocínio generativo longo (System 2):** Destilar o resultado no banco (`learn_system2_execution`).

---

## 🔄 Formatos de Uso: Skill vs. MCP

- **Skill (`system1`):** Protocolos de fluxo, governança de memória ativa e diretrizes de raciocínio.
- **MCP (`/root/.gemini/antigravity-cli/mcp/system1`):** Tools atômicas:
  - `classify`, `record_failure`, `validate_action`, `get_synthesized_context`, `record_feedback`, `learn_system2_execution`.
