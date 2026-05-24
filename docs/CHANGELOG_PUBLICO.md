# CHANGELOG PUBLICO

## Cadastro declarativo de vagas

- Adicionado suporte a multiplas vagas via lista jobs.
- Criado validador central em job_registry.py.
- Adicionado suporte a job_key para rastreamento por vaga.
- Atualizados exemplos ficticios em config.example.yaml e examples/.
- Atualizada documentacao de cadastro de novas vagas.

## Suíte mínima de testes

- Adicionados testes automatizados para o cadastro declarativo de vagas.
- Cobertura inicial para validação de jobs, job_key, enabled=false, campos obrigatórios e ids duplicados.

## Autenticação do painel

- Adicionado suporte a HTTP Basic Auth no painel.
- Credenciais configuráveis por variáveis de ambiente.
- Modo inseguro de desenvolvimento disponível apenas de forma explícita.
- Adicionados testes automatizados para autenticação.
