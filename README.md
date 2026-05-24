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
