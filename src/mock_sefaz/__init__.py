"""Mock SEFAZ - simula a Receita Federal para testes locais.

Simula os endpoints do NFeDistribuicaoDFe:
- Consulta por NSU (retorna resumo ou XML completo)
- Recepcao de eventos (manifestacao do destinatario)
- Status do servico

Sem certificado digital, sem CNPJ real, sem internet.
"""
