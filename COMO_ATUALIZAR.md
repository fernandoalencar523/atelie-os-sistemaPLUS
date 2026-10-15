# Ateliê OS — atualização de acessos e celular

## O que mudou
- Um login mantém a sessão ativa por até 7 dias, desde que o navegador guarde o cookie e o SECRET_KEY do servidor continue o mesmo. Sair encerra a sessão.
- Administrador alterna entre Abreu e Luiz; a escolha é mantida ao navegar pelas páginas.
- Usuário `staff` acessa somente a operação da empresa dele e não acessa Financeiro, Configurações, Histórico nem usuários.
- Usuário `owner` acessa sua própria empresa e seu financeiro, mas não a outra empresa.
- Menu adaptado ao celular (botão Menu), botões maiores, tabelas roláveis e formulários ajustados.

## Para criar os três acessos
1. Entre com a conta de administrador e abra **Usuários e acessos**.
2. Crie um usuário perfil **Equipe (operacional)**, empresa **Abreu Estofados**.
3. Crie outro usuário perfil **Equipe (operacional)**, empresa **Luiz Estofados**.
4. O administrador já existente tem acesso às duas empresas. Se necessário, crie outro admin com uma senha diferente.
5. Cada usuário usa seu próprio e-mail e senha. Nunca compartilhe o acesso administrativo.

## Atualizar o repositório
1. Faça backup do banco e uploads existentes antes de substituir qualquer arquivo.
2. Envie **o conteúdo** da pasta `estofados_sistema` para o mesmo local no repositório (mantendo as pastas `templates` e `static`). Não envie `.env`, banco `.db`, arquivos privados nem senhas.
3. Na hospedagem Python, mantenha `SECRET_KEY` como variável de ambiente fixa e aleatória (32+ caracteres). Alterá-la desconecta todos os usuários.
4. Reinicie/reimplante a aplicação e teste com três contas em janelas anônimas distintas.

## Atenção à hospedagem
O sistema usa Flask + SQLite. **GitHub Pages não executa Flask/Python**, então este ZIP não pode ser publicado só pelo Pages. Use hospedagem Python para esta versão.
Sem disco persistente, o SQLite, usuários criados e anexos podem desaparecer a cada reinicialização/deploy. Não use o Render gratuito para dados reais; antes de uso real migre para banco persistente e armazenamento de documentos, habilite HTTPS e revise segurança (incluindo permissões e backups).
