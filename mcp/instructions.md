# System 1 Global MCP Server Instructions

Este servidor MCP provê inferência reflexiva de alta performance (<10ms), calibração estatística, memória de trabalho ativa e prevenção contra repetição de erros.

## Ferramentas Disponíveis:
1. `classify`: Use no início de cada instrução para triagem instantânea e avaliação de riscos.
2. `record_failure`: Registre imediatamente qualquer tentativa que não resolveu o problema para criar uma regra de veto mandatória.
3. `validate_action`: Valide em <1ms se uma solução que você pretende propor colide com erros anteriores.
4. `get_synthesized_context`: Recupere o contexto de trabalho comprimido (objetivos ativos + vetos negativos) para manter o raciocínio focado.
5. `record_feedback`: Chame após tarefas bem-sucedidas para reforçar os padrões aprendidos.
6. `learn_system2_execution`: Chame ao concluir raciocínios generativos complexos para destilar o aprendizado no System 1.
