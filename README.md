# job-hunter

Projeto para apoiar a busca e a organização de vagas de tecnologia com um fluxo local de coleta, normalização, score e revisão manual.

O painel web mostra vagas consolidadas em arquivos locais, permite revisar status de candidatura e registrar observações sem alterar a exportação principal.

## O que o projeto resolve

- centraliza vagas vindas de diferentes fontes;
- normaliza campos como título, empresa, localidade e modalidade;
- calcula score e classificação;
- mantém um painel local para revisão manual;
- guarda o estado de revisão em um arquivo JSON separado do CSV principal.

## Como funciona em alto nível

1. um pipeline em Python coleta e trata vagas;
2. os dados consolidados são exportados em CSV e XLSX;
3. o painel local lê o snapshot mais recente;
4. o painel exibe lista, filtros, resumo e detalhes;
5. o status de candidatura é salvo separadamente em JSON.

## Stack técnica

- Python 3;
- servidor HTTP da biblioteca padrão;
- frontend estático em HTML, CSS e JavaScript;
- bibliotecas auxiliares para coleta, normalização e exportação;
- Playwright para automação auxiliar em fontes compatíveis.

## Como rodar localmente

Pré-requisitos:

- Python 3.13 ou compatível;
- virtualenv local;
- dependências do arquivo `requirements.txt`.

Exemplo:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
bash ./run_panel.sh
```

O painel expõe a interface em `http://127.0.0.1:8781` por padrão.

`config.yaml` é um arquivo local. Para publicar no GitHub, mantenha apenas `config.example.yaml` e gere `config.yaml` na sua máquina.

## Autenticação do painel

O painel usa HTTP Basic Auth.

As credenciais devem ser configuradas por variáveis de ambiente:

```bash
export JOB_HUNTER_PANEL_USER="usuario-local"
export JOB_HUNTER_PANEL_PASSWORD="senha-forte-local"
```

Opcionalmente, o painel também pode ler credenciais de um `config.yaml` local nao versionado.

Nao coloque senha no código e nao versione `config.yaml`.

Modo inseguro de desenvolvimento, apenas para uso local e explicitamente opt-in:

```bash
export JOB_HUNTER_PANEL_AUTH_DISABLED=true
```

Nao use esse modo em ambiente exposto.

## Como cadastrar novas vagas

1. Copie `config.example.yaml` para `config.yaml`.
2. Adicione uma nova entrada na lista `jobs`.
3. Preencha `id`, `title`, `company`, `platform` e `url`.
4. Marque `enabled: true` para manter a vaga ativa.
5. Rode o coletor ou reinicie o processo local conforme o seu fluxo.
6. Abra o painel para revisar a vaga cadastrada.

Exemplo:

```yaml
jobs:
  - id: analista-infra-exemplo
    title: Analista de Infraestrutura
    company: Empresa Exemplo A
    platform: exemplo
    url: https://example.com/vaga/123
    enabled: true
    tags:
      - infraestrutura
      - suporte
      - redes
    notes: Vaga ficticia para exemplo.
```

## Testes

Para instalar dependências e executar os testes:

```bash
pip install -r requirements.txt
python3 -m pytest -q
```

A suíte mínima cobre:

- validação declarativa de jobs;
- geração de `job_key`;
- campos obrigatórios;
- ids duplicados;
- `enabled=false`.

## Estrutura de pastas

- `panel/`: interface estática do painel;
- `sources/`: módulos de coleta por fonte;
- `tests/`: testes automatizados;
- `docs/`: documentação técnica;
- `examples/`: exemplos fictícios para demonstração;
- `run_panel.sh`: inicialização do painel;
- `job_panel_server.py`: servidor HTTP do painel;
- `run_jobs.py`: pipeline principal de coleta e exportação;
- `job_hunter_collect.py`: coleta incremental;
- `data/`: dados locais gerados em execução.

## Cuidados de segurança

- não publicar `data/output/`, `data/state/` ou `data/status/` reais;
- não publicar `browser_profiles/` se houver sessão de navegador;
- não publicar `.env`, tokens, cookies, senhas ou chaves de API;
- não publicar logs, exports brutos ou bancos locais;
- não inserir dados pessoais ou links privados nos exemplos.

## O que não automatiza

Este projeto não automatiza candidaturas, não burla CAPTCHA e não tenta contornar restrições de plataformas.

## Roadmap futuro

- separar de forma ainda mais clara código e dados;
- adicionar modo demo com dados 100% fictícios;
- criar exportação sanitizada para publicação;
- melhorar o painel de revisão;
- adicionar histórico de movimentações;
- permitir arquivamento de vagas;
- ampliar a documentação pública com prints limpos.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
