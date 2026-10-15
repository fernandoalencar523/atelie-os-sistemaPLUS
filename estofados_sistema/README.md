# Ateliê OS - Abreu Estofados e Luiz Estofados

Sistema web local de demonstração funcional, em Flask + SQLite. Possui logins com isolamento de empresa no servidor, cadastro de clientes, catálogo editável, orçamentos automáticos, acompanhamento de ordens de serviço, PDFs de orçamento/contrato/entrega, anexos, agenda de visitas, despesas, métricas, auditoria e painel administrativo.

## Rodar no computador
1. Instale Python 3.11 ou superior.
2. Abra um terminal nesta pasta e execute `python -m pip install -r requirements.txt`.
3. Defina as variáveis `ADMIN_PASSWORD` (senha inicial forte) e `SECRET_KEY` (chave aleatória estável). Para um teste local rápido, pode iniciar sem definir, mas **não publique assim**.
4. Execute `python app.py`.
5. Abra `http://127.0.0.1:5000` no navegador.
6. Login inicial: `admin@estofados.local`; senha: valor de `ADMIN_PASSWORD` ou `Trocar@12345` se não foi definida.
7. Como administrador, crie contas em **Usuários e acessos** e vincule cada pessoa à empresa apropriada.

## O que existe e o que ainda exige implementação
- **Já funciona localmente:** contas isoladas por empresa, dados persistidos em SQLite, cadastros, orçamento automático por custo e margem, parcelas exibidas como total cartão, registros de custos, PDF simples, upload de documentos, agenda sem sobreposição, movimentação das etapas, painel financeiro básico.
- **Ainda não integrado:** recepção/envio automático de mensagens no WhatsApp (requer WhatsApp Business Platform/API e configuração), assinatura eletrônica via link com validade jurídica, envio automático de e-mail, gateway de pagamento, alerta por notificações push, controle completo de estoque e custos trabalhistas, cálculo robusto de capacidade por horas e tipos de serviço, relatório mensal detalhado, recuperação de senha e autenticação multifator.
- **Antes de hospedagem pública:** migrar para banco gerenciado, colocar HTTPS e backup automatizado, implementar rate limit, reset de senha, revisão de acessos e auditoria de segurança, verificar base legal LGPD e revisar contratos com advogado. Flask dev server não é servidor de produção.
- **Financeiro:** painel considera faturamento de serviços com status Entregue e custos previstos/reais. Despesas gerais (sem serviço) entram no custo. Despesas vinculadas a um serviço precisam ser consolidadas em seu custo real: não são deduzidas separadamente para evitar duplicidade. Parcelamento exibido no preço de cartão, sem simulação de juros por parcela. Sua comissão é uma estimativa, sujeita à definição contratual de “lucro”.
- **Prazos:** sugestão simples de data usa quantidade de serviços prometidos por semana e dias úteis; não substitui planejamento de carga por horas e tamanhos. Visitas em horário comercial fixo (seg-sex, 8h-18h) nesta versão.
- **PDFs:** modelos operacionais, precisam revisão jurídica e consentimento para dados/fotos.

## Estrutura
- `app.py`: rotas, regras de permissão, lógica, banco.
- `templates/`: telas HTML.
- `static/`: visual e cálculo de prévia.
- `uploads/`: fotos e documentos anexados (privados, servidos somente após autenticação).
- `estofados.db`: criado automaticamente no primeiro uso. Salve backups com o app parado e backups da pasta `uploads/`.

O produto é uma **base funcional para testar**, não uma publicação em nuvem pronta para clientes reais sem as melhorias acima.
