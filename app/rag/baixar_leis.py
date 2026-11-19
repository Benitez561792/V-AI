"""Baixa leis e decretos de acessibilidade do site do Planalto e salva como .txt em data/fontes/.

    python -m app.rag.baixar_leis

Trechos revogados (riscados no site) são descartados. O script também registra os nomes
exibidos em data/fontes/fontes.yaml, sem apagar o que já estiver lá.

As normas ABNT (NBR 9050 e NBR 16537) não podem ser baixadas assim: coloquem o PDF obtido
legalmente na mesma pasta (veja data/fontes/README.md).
"""
from __future__ import annotations

import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from app import miniyaml

from app.config import carregar_config

LEIS = {
    "lei13146.txt": ("Lei 13.146/2015",
                     "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm"),
    "lei10098.txt": ("Lei 10.098/2000",
                     "https://www.planalto.gov.br/ccivil_03/leis/l10098.htm"),
    "decreto5296.txt": ("Decreto 5.296/2004",
                        "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/decreto/d5296.htm"),
}

_BLOCOS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}
_IGNORAR = {"script", "style", "strike", "s", "del", "head"}  # strike/s/del = texto revogado


class _Extrator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in _IGNORAR:
            self._ignorando += 1
        elif tag in _BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in _IGNORAR:
            self._ignorando = max(0, self._ignorando - 1)
        elif tag in _BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._ignorando:
            self.partes.append(data)


def html_para_texto(html: str) -> str:
    extrator = _Extrator()
    extrator.feed(html)
    texto = "".join(extrator.partes).replace("\xa0", " ")
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    texto = "\n".join(l for l in linhas if l)
    return re.sub(r"\n{3,}", "\n\n", texto)


def _decodificar(bruto: bytes, charset: str | None) -> str:
    for cod in filter(None, (charset, "utf-8", "windows-1252")):
        try:
            return bruto.decode(cod)
        except (UnicodeDecodeError, LookupError):
            continue
    return bruto.decode("latin-1")


def baixar(url: str) -> str:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (VeAI - FIAP)"})
    with urllib.request.urlopen(pedido, timeout=20) as resp:
        return _decodificar(resp.read(), resp.headers.get_content_charset())


def main(argv: list[str] | None = None) -> int:
    pasta = carregar_config().dir_fontes
    pasta.mkdir(parents=True, exist_ok=True)
    arq_nomes = pasta / "fontes.yaml"
    nomes = miniyaml.loads(arq_nomes.read_text(encoding="utf-8")) if arq_nomes.exists() else {}
    nomes = nomes or {}

    falhas = 0
    for arquivo, (nome, url) in LEIS.items():
        try:
            texto = html_para_texto(baixar(url))
        except Exception as e:
            falhas += 1
            print(f"Falha ao baixar {nome}: {e}\n  Baixe manualmente: abra {url}, copie o texto e salve em {pasta / arquivo}",
                  file=sys.stderr)
            continue
        artigos = len(re.findall(r"^Art\. ?\d+", texto, flags=re.M))
        (pasta / arquivo).write_text(f"{nome}\nFonte: {url}\n\n{texto}\n", encoding="utf-8")
        nomes[arquivo] = nome
        print(f"{nome}: {artigos} artigos salvos em {pasta / arquivo}")

    novo = miniyaml.dumps(nomes)
    if not arq_nomes.exists() or arq_nomes.read_text(encoding="utf-8") != novo:
        arq_nomes.write_text(novo, encoding="utf-8")  # só grava se mudou: evita refazer o índice à toa
        print(f"\nNomes registrados em {arq_nomes}.")
    print("Próximos passos: coloquem os PDFs da NBR 9050 e da NBR 16537 nesta pasta (se tiverem), "
          "confiram com 'python -m app.rag.ingestao --listar' e gerem o índice com 'python -m app.rag.ingestao'.")
    return 1 if falhas == len(LEIS) else 0


if __name__ == "__main__":
    raise SystemExit(main())
