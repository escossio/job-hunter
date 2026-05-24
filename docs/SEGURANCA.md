# Seguranca

## O que nao publicar

- arquivos `.env`;
- tokens;
- cookies;
- senhas;
- chaves de API;
- credenciais de acesso;
- logs brutos;
- bancos locais;
- exportacoes reais;
- backups reais;
- dados pessoais;
- URLs privadas;
- IPs internos;
- sessoes de navegador;
- `browser_profiles/`.

## Como lidar com dados reais

- manter dados reais fora da pasta publica;
- guardar snapshots e status operacionais apenas no repositório privado ou no ambiente local;
- criar exemplos ficticios para qualquer publicacao externa;
- revisar planilhas, JSON e Markdown antes de compartilhar.

## Como criar exemplos ficticios

Use nomes e URLs neutros, por exemplo:

- `Empresa Exemplo A`;
- `Empresa Exemplo B`;
- `Analista de Infraestrutura`;
- `Pessoa Candidata`;
- `https://example.com/vaga/123`.

## Cuidados com browser_profiles

- nunca copiar perfis de navegador com sessao ativa para o repositório publico;
- tratar o diretorio como sensivel mesmo quando estiver vazio;
- manter esse diretório fora do Git.

## Cuidados com segredos

- não inserir segredos em documentação, exemplos ou comentários;
- mascarar valores se algum campo precisar ser citado;
- revisar qualquer arquivo exportado antes de publicar.

