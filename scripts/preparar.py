"""Cria a pasta local de um edital do radar, já com o edital e os anexos baixados.

Uso: python scripts/preparar.py <id ou parte do título>
     python scripts/preparar.py profix

Cria EDITAIS_DIR/AAAA-MM-DD_FONTE_TITULO (padrão D:/EDITAIS) com edital/ (página ou PDF do
edital, documentos listados pelo radar e os PDF/DOC/DOCX linkados na página), checklist.md e
submetido/, e acrescenta o edital à tabela "Em preparação" do EDITAIS.md.
Roda no seu PC, fora do Actions: nada disso vai para o repositório.
"""

import json
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

RAIZ = Path(__file__).resolve().parent.parent
PASTA = Path(os.environ.get("EDITAIS_DIR", "D:/EDITAIS"))
PAINEL = "https://osmarluiz.github.io/radar-editais/data/editais.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (radar-editais)"}
EXTENSOES = (".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx", ".zip")
MAX_ANEXOS = 20


def carregar_editais():
    try:
        return requests.get(PAINEL, headers=HEADERS, timeout=30).json()["editais"]
    except Exception:  # noqa: BLE001 - sem internet ou Pages fora: usa a cópia local
        dados = json.loads((RAIZ / "docs" / "data" / "editais.json").read_text(encoding="utf-8"))
        return dados["editais"]


def slug(texto, n=40):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_")[:n].rstrip("_")


def nome_arquivo(url, resp, padrao):
    nome = re.findall(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', resp.headers.get("content-disposition", ""))
    nome = unquote(nome[0]) if nome else unquote(Path(urlparse(url).path).name) or padrao
    nome = re.sub(r'[<>:"/\\|?*]+', "_", nome)[:120]
    if resp.content[:5] == b"%PDF-" and not nome.lower().endswith(".pdf"):
        nome += ".pdf"
    elif "html" in resp.headers.get("content-type", "") and not nome.lower().endswith((".html", ".htm")):
        nome += ".html"
    return nome


def baixar(url, destino, padrao):
    resp = requests.get(url, headers=HEADERS, timeout=(15, 120), verify=False)
    resp.raise_for_status()
    caminho = destino / nome_arquivo(url, resp, padrao)
    caminho.write_bytes(resp.content)
    print(f"  baixado: {caminho.name}")
    if zipfile.is_zipfile(caminho):  # o PNCP entrega o edital e os anexos num .zip
        alvo = caminho.with_suffix("")
        with zipfile.ZipFile(caminho) as z:
            for membro in z.infolist():
                final = (alvo / membro.filename).resolve()
                if not membro.is_dir() and final.is_relative_to(alvo.resolve()):
                    try:
                        final.parent.mkdir(parents=True, exist_ok=True)
                        final.write_bytes(z.read(membro))
                    except OSError as e:  # caminho longo demais no Windows, nome inválido...
                        print(f"  não extraiu {membro.filename}: {e}")
        print(f"  extraído em {alvo.name}/")
    return resp, caminho


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    termo = " ".join(sys.argv[1:]).lower()
    editais = carregar_editais()
    achados = [e for e in editais if e["id"] == termo] or \
              [e for e in editais if termo in f"{e['titulo']} {e['fonte']}".lower()]
    if not achados:
        raise SystemExit(f"Nenhum edital com '{termo}' no radar.")
    if len(achados) > 1:
        for e in achados:
            print(f"{e['id']}  {e.get('prazo') or 'sem prazo'}  {e['titulo'][:90]}")
        raise SystemExit("Mais de um edital encontrado: rode de novo com o id.")
    ed = achados[0]

    pasta = PASTA / f"{ed.get('prazo') or 'sem-prazo'}_{slug(ed['fonte'], 20)}_{slug(ed['titulo'])}"
    (pasta / "edital").mkdir(parents=True, exist_ok=True)
    (pasta / "submetido").mkdir(exist_ok=True)
    print(f"Pasta: {pasta}")

    baixados, falhas = set(), []
    urls = [u for u in [ed.get("link"), *ed.get("documentos", [])] if u]
    pncp = re.match(r"https://pncp\.gov\.br/app/editais/(\d+)/(\d+)/(\d+)", ed.get("link") or "")
    if pncp:
        # A página do PNCP é montada por JavaScript; os arquivos vêm da API
        api = "https://pncp.gov.br/api/pncp/v1/orgaos/{}/compras/{}/{}/arquivos".format(*pncp.groups())
        try:
            arquivos = requests.get(api, headers=HEADERS, timeout=60).json()
            urls = [a["url"] for a in arquivos if a.get("statusAtivo")] + urls[1:]
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{api} ({type(e).__name__})")
    for i, url in enumerate(dict.fromkeys(urls)):
        try:
            resp, _ = baixar(url, pasta / "edital", f"documento_{i}")
            baixados.add(url)
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{url} ({type(e).__name__})")
            continue
        if "html" not in resp.headers.get("content-type", ""):
            continue
        # Página do edital: baixa os anexos linkados (edital em PDF, retificações, modelos)
        soup = BeautifulSoup(resp.content, "html.parser")
        anexos = [urljoin(resp.url, a["href"]) for a in soup.find_all("a", href=True)]
        anexos = [a for a in dict.fromkeys(anexos)
                  if urlparse(a).path.lower().endswith(EXTENSOES) or "/documents/d/" in a]
        for a in anexos[:MAX_ANEXOS]:
            if a in baixados:
                continue
            try:
                baixar(a, pasta / "edital", "anexo")
                baixados.add(a)
            except Exception as e:  # noqa: BLE001
                falhas.append(f"{a} ({type(e).__name__})")

    prazo = "/".join(reversed(ed["prazo"].split("-"))) if ed.get("prazo") else "não informado"
    checklist = pasta / "checklist.md"
    if not checklist.exists():
        checklist.write_text(f"""# {ed['titulo']}

{ed.get('fonte_nome', ed['fonte'])} · **prazo {prazo}**{f" · {ed['valor']}" if ed.get('valor') else ""}
Link: {ed.get('link') or '—'}

{ed.get('resumo', '')}

{f"**Mudança:** {ed['mudanca']}" if ed.get('mudanca') else ""}

## Por que entra

{ed.get('motivo') or '—'}

## Requisitos (resumo do radar; confira no edital)

{ed.get('requisitos') or 'O radar não conferiu o edital completo; leia em edital/.'}

## Checklist

- [ ] Ler o edital inteiro e as retificações em `edital/`
- [ ] Listar os documentos obrigatórios e copiar os que já estão em `../_base/`
- [ ] Cadastros na plataforma de submissão
- [ ] Projeto / proposta
- [ ] Cartas e declarações assinadas
- [ ] Submeter e guardar o comprovante em `submetido/`
""".replace("\n\n\n", "\n\n"), encoding="utf-8")

    indice = PASTA / "EDITAIS.md"
    if indice.exists():
        texto = indice.read_text(encoding="utf-8")
        if f"`{pasta.name}`" not in texto:
            linha = f"| {prazo} | {ed['titulo'][:80]} | {', '.join(ed.get('perfis', []))} | começando | `{pasta.name}` |"
            texto = re.sub(r"(## Em preparação\n\n\|.*\n\|[-| ]+\|\n)", lambda m: m.group(1) + linha + "\n", texto, 1)
            indice.write_text(texto, encoding="utf-8")

    print(f"{len(baixados)} arquivos baixados; checklist em {checklist}")
    for f in falhas:
        print(f"  não baixou: {f}")


if __name__ == "__main__":
    main()
