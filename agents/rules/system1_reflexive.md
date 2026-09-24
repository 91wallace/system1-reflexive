---
description: Diretrizes obrigatórias de execução reflexiva System 1, memória de trabalho e prevenção contra repetição de erros
globs: "**/*"
always_on: true
---

# Diretrizes Operacionais System 1 Reflexive

Para máxima eficiência, baixa latência e zero repetição de erros, utilize o **System 1**:

1. **Triagem de Intenção (<10ms):**
   - Antes de iniciar tarefas ambíguas ou comandos, utilize a ferramenta MCP `classify` ou `system1 classify "<prompt>"`.
   - Se a confiança for alta (>= 0.70) e `requires_system2_fallback` for falso, adote o plano reflexivo sugerido.

2. **Prevenção contra Repetição de Erros (Negative Constraints & Graveyard):**
   - Sempre que uma solução, comando ou abordagem falhar, registre-a imediatamente via ferramenta MCP `record_failure` ou `system1 fail "<abordagem>" "<motivo>"`.
   - Antes de propor uma nova solução, valide com `validate_action` para garantir que não colide com hipóteses já vetadas.

3. **Injeção de Contexto Sintetizado (Alto SNR):**
   - Recupere o contexto livre de ruído com `get_synthesized_context` para manter a memória de trabalho focada.

4. **Ciclo de Aprendizado Contínuo:**
   - Após conclusões bem-sucedidas de tarefas complexas, utilize `learn_system2_execution` ou `record_feedback` para registrar o padrão no banco semântico do projeto.
