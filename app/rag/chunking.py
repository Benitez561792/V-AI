"""Leitura das fontes e divisão em trechos (chunks) pela numeração das seções.

Por que por seção: o número da seção (ex.: 6.12.1) vira metadado do trecho. A referência
normativa devolvida pela API sai desse metadado, não do texto gerado pelo modelo, então
não tem como ser inventada.

Leis e decretos (linhas "Art. 46.") são divididos por artigo e recebem seção "art. 46".
Documentos sem numeração (guias municipais, por exemplo) são divididos por parágrafos e
recebem seção "parte N".
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from app import miniyaml

# "6.12.1 Calçadas" -> número + título começando com maiúscula.
# Exigir maiúscula evita confundir linhas de corpo como "1 m de largura" com seções.
PADRAO_SECAO = re.compile(
    r"^\s*((?:[A-H]\.)?\d{1,2}(?:\.\d{1,3}){0,5})\.?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{0,160})$"
)
# Número de seção sozinho na linha (alguns PDFs separam "6.6.2.1" do texto que vem depois)
PADRAO_SO_NUMERO = re.compile(r"^\s*((?:[A-H]\.)?\d{1,2}(?:\.\d{1,3}){1,5})\s*$")
# "Art. 46." / "Art. 9º A pessoa..." -> artigo de lei. O texto depois do número é corpo.
PADRAO_ARTIGO = re.compile(r"^\s*Art\.\s*(\d{1,4})\s*(?:º|°|o)?\s*[-–.]?\s*(.*)$")
MIN_ARTIGOS = 3  # documentos com pelo menos 3 artigos são tratados como lei
EXTENSOES = {".txt", ".md", ".pdf"}


@dataclass
class Trecho:
    id: str
    fonte: str
    secao: str | None
    titulo: str | None
    texto: str

    def texto_para_embedding(self) -> str:
        cabecalho = " ".join(p for p in (self.secao, self.titulo) if p)
        return f"{self.fonte} | {cabecalho}\n{self.texto}" if cabecalho else f"{self.fonte}\n{self.texto}"

    def para_dict(self) -> dict:
        return asdict(self)


def ler_documento(caminho: Path) -> str:
    if caminho.suffix.lower() == ".pdf":
        import logging

        import pdfplumber

        logging.getLogger("pdfminer").setLevel(logging.ERROR)  # avisos de fonte, sem efeito no texto
        with pdfplumber.open(str(caminho)) as pdf:
            texto = "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)
        return limpar_texto(texto)
    return caminho.read_text(encoding="utf-8")


_LINHA_SUMARIO = re.compile(r"\.{5,}|…{2,}")
_LINHA_DE_FIGURA = re.compile(r"^[\d\s,.:;()%×=+\-–/°<>≤≥'\"]*(?:mm|cm|m|%)?[\d\s,.]*$")


def limpar_texto(texto: str, repeticoes: int = 4) -> str:
    """Remove o que atrapalha a busca em PDFs de normas.

    - linhas de sumário (com pontilhado);
    - cabeçalhos e rodapés: linhas curtas que se repetem em várias páginas, comparadas sem os
      números (assim "© ABNT 2020 ... 57" e "... 58" contam como a mesma linha);
    - restos de figuras: linhas só com cotas e números ("0,75 0,90", "42 mm") ou com até 3 caracteres.
    Números de seção sozinhos na linha são mantidos.
    """
    linhas = texto.splitlines()
    # números e numeração romana de página ("iii", "iv") não contam na comparação
    chave = lambda l: re.sub(r"\b[ivxlc]+\b|\d+", "#", l.strip().lower())  # noqa: E731
    contagem: dict[str, int] = {}
    for l in linhas:
        if l.strip() and len(l) < 100:
            contagem[chave(l)] = contagem.get(chave(l), 0) + 1
    limpas = []
    for l in linhas:
        t = l.strip()
        if PADRAO_SO_NUMERO.match(t):
            limpas.append(t)
            continue
        if (not t or _LINHA_SUMARIO.search(t) or len(t) <= 3 or _LINHA_DE_FIGURA.match(t)
                or (len(t) < 100 and contagem.get(chave(t), 0) >= repeticoes)):
            continue
        limpas.append(t)
    return "\n".join(limpas)


def _dividir_texto(texto: str, maximo: int) -> list[str]:
    """Divide por parágrafos (ou linhas) acumulando até `maximo` caracteres."""
    blocos = [b.strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]
    if len(blocos) <= 1:
        blocos = [b.strip() for b in texto.splitlines() if b.strip()]
    partes, atual = [], ""
    for bloco in blocos:
        while len(bloco) > maximo:  # bloco gigante sem quebra
            if atual:
                partes.append(atual)
                atual = ""
            partes.append(bloco[:maximo])
            bloco = bloco[maximo:]
        if atual and len(atual) + len(bloco) + 1 > maximo:
            partes.append(atual)
            atual = bloco
        else:
            atual = f"{atual}\n{bloco}" if atual else bloco
    if atual:
        partes.append(atual)
    return partes


def _secoes_por_artigo(texto: str) -> list[tuple[str, str | None, list[str]]] | None:
    linhas = texto.splitlines()
    if sum(1 for l in linhas if PADRAO_ARTIGO.match(l)) < MIN_ARTIGOS:
        return None
    secoes: list[tuple[str, str | None, list[str]]] = []
    for linha in linhas:
        m = PADRAO_ARTIGO.match(linha)
        if m:
            secoes.append((f"art. {m.group(1)}", None, [m.group(2)] if m.group(2) else []))
        elif secoes:
            secoes[-1][2].append(linha)
    return secoes


def dividir_por_secoes(texto: str, fonte: str, maximo: int = 1500) -> list[Trecho]:
    secoes = _secoes_por_artigo(texto)
    if secoes is None:
        secoes = []
        linhas_doc = texto.splitlines()
        # Capa, sumário, prefácio e introdução ficam antes da seção 1. Começar nela evita que
        # títulos do sumário que quebraram em duas linhas virem seções falsas.
        # A seção 1 verdadeira é a primeira cuja linha seguinte já é texto, e não outro título
        # (no sumário, "1 Escopo" vem seguido de "2 Referências normativas").
        def _eh_titulo(l: str) -> bool:
            return bool(PADRAO_SECAO.match(l) or PADRAO_SO_NUMERO.match(l))

        inicio = next((i for i, l in enumerate(linhas_doc)
                       if (m := PADRAO_SECAO.match(l)) and m.group(1) == "1"
                       and not any(_eh_titulo(p) for p in linhas_doc[i + 1:i + 2] if p.strip())), 0)
        capitulo = 0
        for linha in linhas_doc[inicio:]:
            m = PADRAO_SECAO.match(linha)
            so_numero = PADRAO_SO_NUMERO.match(linha)
            if m and m.group(1).isdigit():
                # Capítulo novo só na sequência (1, 2, 3...). Itens numerados de legendas de
                # figura ("5 Guia") não são capítulos e continuam no corpo da seção atual.
                if int(m.group(1)) != capitulo + 1:
                    if secoes:
                        secoes[-1][2].append(linha)
                    continue
                capitulo += 1
            if m:
                titulo = m.group(2).strip()
                # o título também fica no corpo: em normas, a "linha de título" costuma ser
                # o começo do requisito ("6.6.2.1 As rampas devem ter...")
                secoes.append((m.group(1), titulo, [titulo]))
            elif so_numero:
                secoes.append((so_numero.group(1), None, []))
            elif secoes:
                secoes[-1][2].append(linha)
            # texto antes da primeira seção (capa) é descartado. Linhas do sumário viram
            # seções sem corpo e também são descartadas abaixo.

    trechos: list[Trecho] = []
    if not secoes:  # documento sem numeração
        for i, parte in enumerate(_dividir_texto(texto, maximo), start=1):
            trechos.append(Trecho(f"{fonte}#parte-{i}", fonte, f"parte {i}", None, parte))
        return trechos

    ids_usados: set[str] = set()
    for numero, titulo, linhas in secoes:
        conteudo = linhas[1:] if titulo else linhas  # sem contar a linha do título
        if not "\n".join(conteudo).strip():
            continue  # sumário ou título sem corpo (ex.: "6 Acessos"); o conteúdo está nas subseções
        corpo = "\n".join(linhas).strip()
        for j, parte in enumerate(_dividir_texto(corpo, maximo), start=1):
            id_base = f"{fonte}#{numero}" + (f"-{j}" if j > 1 else "")
            id_trecho, n = id_base, 2
            while id_trecho in ids_usados:  # mesma numeração repetida no documento
                id_trecho, n = f"{id_base}~{n}", n + 1
            ids_usados.add(id_trecho)
            trechos.append(Trecho(id_trecho, fonte, numero, titulo, parte))
    return trechos


def carregar_nomes_fontes(diretorio: Path) -> dict[str, str]:
    """fontes.yaml opcional: nome do arquivo -> nome exibido (ex.: 'ABNT NBR 9050:2020')."""
    arq = diretorio / "fontes.yaml"
    if not arq.exists():
        return {}
    return miniyaml.loads(arq.read_text(encoding="utf-8"))


def carregar_trechos(diretorio: Path, maximo: int = 1500) -> list[Trecho]:
    nomes = carregar_nomes_fontes(diretorio)
    trechos: list[Trecho] = []
    for caminho in sorted(diretorio.iterdir()):
        if caminho.suffix.lower() not in EXTENSOES or caminho.name.lower() == "readme.md":
            continue
        fonte = nomes.get(caminho.name, caminho.stem)
        trechos.extend(dividir_por_secoes(ler_documento(caminho), fonte, maximo))
    return trechos
