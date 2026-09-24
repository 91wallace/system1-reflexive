# Diretrizes do Projeto - System 1 Reflexive

Este repositório possui o motor **System 1 Reflexive** integrado para triagem de intenções sub-milissegundo, memória de trabalho dinâmica e catálogo de soluções invalidadas.

## Princípios Fundamentais de Segurança (Anti-Corrupção)
1. **Separação de Papéis:** O System 1 e Laya são motores **consultivos** de triagem, telemetria e classificação de intenção (<10ms). **Eles nunca geram código nem substituem a leitura direta de arquivos de código-fonte.**
2. **Inspeção Completa de Código (System 2):** Sempre inspecione os arquivos de código reais com `view_file` antes de fazer alterações em componentes, rotas ou banco de dados. Nunca deduza a estrutura do código baseando-se apenas em resumos sintéticos.
3. **Avisos Consultivos vs Bloqueios:** O histórico de falhas (`graveyard`) serve como lição aprendida e aviso consultivo, nunca como veto rígido para impedir edições legítimas em arquivos do projeto.

## Protocolo de Decisão e Memória
1. **Triagem Rápida:** Utilize a ferramenta MCP `classify` ou comando CLI `system1 classify "<prompt>"`.
2. **Registro de Falhas (Graveyard):** Registre falhas reais e objetivas com `record_failure` para documentar lições aprendidas.
3. **Validação de Ação:** Valide planos críticos ou destrutivos com `validate_action` e `analyze_action_safety`.
4. **Contexto Ativo:** Obtenha o resumo do estado ativo com `get_synthesized_context`.
5. **Armazenamento de Dados:** Dados do projeto e sessões locais são salvos exclusivamente no diretório `.system1/` isolado.
