# Diretrizes do Projeto - System 1 Reflexive

Este repositório possui o motor **System 1 Reflexive** integrado para triagem de intenções sub-milissegundo, memória de trabalho dinâmica e catálogo de soluções invalidadas.

## Protocolo de Decisão e Memória
1. **Triagem Rápida:** Utilize a ferramenta MCP `classify` ou comando CLI `system1 classify "<prompt>"`.
2. **Registro de Falhas (Graveyard):** Registre falhas com `record_failure` para impedir sugestões repetidas.
3. **Validação de Ação:** Valide planos críticos com `validate_action`.
4. **Contexto Ativo:** Obtenha o resumo do estado ativo e restrições com `get_synthesized_context`.
5. **Armazenamento de Dados:** Dados do projeto e sessões locais são salvos exclusivamente no diretório `.system1/` isolado.
