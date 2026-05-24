# Arquitetura

## Visao geral

O projeto combina coleta local de vagas, processamento em Python, exportacao de snapshots e um painel web estatico para revisao manual.

Agora a configuracao tambem pode conter uma lista declarativa `jobs` para cadastrar vagas, fontes ou URLs de acompanhamento sem alterar o codigo principal.

## Componentes principais

- um servico systemd inicia um script shell de bootstrap;
- o script ativa a virtualenv local e chama o servidor do painel em Python;
- o servidor le arquivos CSV e JSON locais;
- o frontend e servido como arquivos estaticos HTML, CSS e JavaScript;
- o pipeline de coleta gera novos snapshots e atualiza o estado local.

## Fluxo de dados

1. coleta e normalizacao;
2. deduplicacao e score;
3. exportacao local;
4. leitura pelo painel;
5. revisao manual de status e observacoes;
6. persistencia do status separado do CSV principal.

As vagas declarativas entram no mesmo pipeline das fontes existentes e preservam compatibilidade com o painel.

## Observacao sobre o servico

O servico systemd do ambiente real aponta para um script de inicializacao local do projeto. Nesta pasta publica, o foco e manter apenas o desenho arquitetural e o codigo seguro para compartilhamento.

## Interface

O painel usa:

- HTML para estrutura;
- CSS para apresentacao;
- JavaScript para filtragem, resumo e chamada aos endpoints locais.
