# ATELIÊ OS — Correção de login, rotas e publicação Vercel

## Atualização
1. Faça backup do repositório e dos dados existentes.
2. Substitua os arquivos dentro de `estofados_sistema` pelos deste pacote, inclusive `api/index.py` e `vercel.json`.
3. Na Vercel, confira **Root Directory = estofados_sistema**. Caso tenha enviado os arquivos na raiz do repositório, deixe Root Directory vazio.
4. Em **Settings > Environment Variables**, crie `SECRET_KEY` com uma sequência longa e aleatória (mínimo 32 caracteres); mantenha a mesma chave entre publicações.
5. Configure `ADMIN_PASSWORD` com senha forte **antes do primeiro acesso**. O e-mail inicial é `admin@estofados.local`.
6. Faça **Redeploy**. Abra `/login` (ou `/app/login` nos links antigos). O menu **Usuários e acessos** permite criar contas como `owner` ou `staff`, associadas a Abreu ou Luiz. Cadastre você mesmo o e-mail e senha iniciais; não há e-mail de confirmação.

## O que foi corrigido
- A aplicação inicializa o esquema do banco também quando importada pela hospedagem (antes funcionava apenas com `python app.py`).
- Sessões usam `SECRET_KEY` estável, evitando novo login a cada rota/instância.
- URLs antigas `/app/...` são aceitas.
- Mantidos os painéis responsivos e as permissões por empresa.

## Limitação CRÍTICA para testes na Vercel
O SQLite e as imagens gravados em `/tmp` **NÃO são persistentes**. Reinício, outra instância ou redeploy podem apagar os cadastros e criar contas novas; em instâncias diferentes podem aparecer erros de login. NÃO usar dados reais, CPF, contratos ou fotos de clientes. Para uso efetivo, é necessário migrar para um banco externo persistente e armazenamento de arquivos dedicado e realizar testes de segurança. Este pacote NÃO resolve essas limitações estruturais da hospedagem serverless.

Se houver erro 500, abra **Vercel > projeto > Logs** e capture o traceback, sem mostrar senhas ou chaves.
