# Radar de editais

Painel com editais e chamadas de fomento abertos (agências federais, FAPs, inovação e
internacionais), atualizado todo dia por um GitHub Action.

**Painel:** https://osmarluiz.github.io/radar-editais/

## Como funciona

1. `scripts/radar.py` baixa a página de editais de cada fonte listada em `config/fontes.yaml`.
2. Se o conteúdo da página mudou desde a última execução, o texto vai para o Claude Code
   (`claude -p`, sem ferramentas, saída validada por JSON Schema), que extrai título, prazo,
   valor, link e a relevância para o perfil definido no topo de `config/fontes.yaml`.
   Páginas sem mudança não gastam chamada ao Claude.
3. O resultado é gravado em `docs/data/editais.json` e o estado de cada fonte em
   `docs/data/status.json`. O workflow faz commit desses arquivos.
4. O GitHub Pages serve a pasta `docs/` (branch `main`); o painel (`docs/index.html`) lê os JSON.

```
config/fontes.yaml          perfil de relevância + lista de fontes
scripts/radar.py            coleta e extração
docs/                       painel estático (GitHub Pages)
docs/data/editais.json      editais extraídos
docs/data/status.json       situação de cada fonte (ok/erro)
.github/workflows/radar.yml execução diária às 06:00 (Brasília)
```

## Configuração

- Secret `CLAUDE_CODE_OAUTH_TOKEN`: gere com `claude setup-token` e cadastre com
  `gh secret set CLAUDE_CODE_OAUTH_TOKEN`.
- GitHub Pages: branch `main`, pasta `/docs`.

## Uso

```bash
gh workflow run "Radar de editais"                  # roda agora
gh workflow run "Radar de editais" -f forcar=true    # reextrai todas as fontes
```

Localmente:

```bash
pip install -r requirements.txt
python scripts/radar.py --sem-claude          # só testa o download das páginas
python scripts/radar.py --fonte capes         # processa uma fonte
python scripts/radar.py --forcar              # reextrai tudo
```

## Adicionar ou corrigir uma fonte

Edite `config/fontes.yaml`. A URL precisa ser a página que **lista** os editais e devolver o
conteúdo em HTML estático (sites que só montam a lista via JavaScript aparecem como
"página quase vazia" no status). Se a página tiver muito ruído, informe um `seletor` CSS
para o bloco de conteúdo. Teste com `python scripts/radar.py --sem-claude --fonte <id>`.

Para mudar o que conta como relevante, edite o `perfil` no topo do mesmo arquivo; a próxima
execução reavalia todas as fontes.

## Domínio próprio

Para servir em um subdomínio (ex.: `editais.oz.tec.br`): crie um CNAME `editais` →
`osmarluiz.github.io` no DNS, rode
`gh api repos/osmarluiz/radar-editais/pages -X PUT -f cname=editais.oz.tec.br`
e, depois que o certificado sair, ative o HTTPS obrigatório nas configurações do Pages.
