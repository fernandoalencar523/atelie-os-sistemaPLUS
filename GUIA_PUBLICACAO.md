# Ateliê OS — guia de publicação (GitHub + Render)

## 1. Envie o projeto para o GitHub
1. Extraia o ZIP; abra a pasta `estofados_sistema`.
2. Crie um repositório **privado** no GitHub.
3. Envie **o conteúdo da pasta**, inclusive `render.yaml`, `wsgi.py`, `requirements.txt`, `templates/` e `static/`.
4. **Nunca envie** `.env`, banco `.db`, contratos, uploads, dados reais ou senhas. Confira os arquivos antes de enviar.
5. Convide seu amigo no repositório pelas configurações de acesso.

## 2. Publique no Render
1. Entre em https://dashboard.render.com e conecte sua conta do GitHub.
2. Clique em **New > Blueprint**, selecione o repositório e siga a implantação pelo `render.yaml`.
3. Defina `ADMIN_PASSWORD` como uma senha **forte e inédita** quando solicitado. `SECRET_KEY` será gerada pela plataforma.
4. Este Blueprint usa um **disco persistente e plano pago**, pois o SQLite e os anexos não podem ficar em armazenamento temporário. Confira preços e condições no painel Render antes de aprovar.
5. Aguarde o build e copie o endereço `https://...onrender.com` fornecido pelo Render. Ele é o link para abrir no Chrome ou celular.
6. Entre usando `admin@estofados.local` e a senha que você criou. Em **Usuários e acessos**, crie os logins vinculados às respectivas empresas.

## 3. Teste antes de colocar clientes reais
- Verifique login, separação entre as duas empresas, orçamento, alteração de status, PDFs, anexos e agenda.
- O app requer mais revisão de segurança, cópias de segurança, LGPD, recuperação de senha e revisão jurídica dos contratos antes de operar com dados reais. Não publique para clientes reais sem uma revisão técnica.
- WhatsApp automático e assinatura eletrônica por link **não estão implementados**.
- Evite aumentar `workers` acima de 1 sem revisar a abordagem de armazenamento SQLite; também mantenha backups externos.
- Alterar `ADMIN_PASSWORD` depois que o banco já foi criado **não troca** a senha da conta existente.

## 4. Teste local (opcional)
```bash
python -m pip install -r requirements.txt
python app.py
```
Abra http://127.0.0.1:5000.

## Atenção
O repositório GitHub sozinho **não hospeda** este backend Python. O Render hospeda e fornece um link. Este pacote é uma versão **preparada para implantação/testes**, não um produto auditado pronto para produção.
