"""Leitura e escrita do YAML simples usado nos arquivos de configuração do projeto.

Substitui o PyYAML, que não tem pacote pronto para todas as versões do Python e, sem ele,
exige compilador C++ no Windows. Aceita só o formato dos nossos arquivos:

    # comentário
    secao:
      chave: "valor"      # dois níveis, com recuo de espaços
    chave: valor          # ou um nível só

Valores podem vir com ou sem aspas (simples ou duplas).
"""
from __future__ import annotations

import re

_LINHA = re.compile(r"^(?P<recuo>\s*)(?P<chave>[^:#][^:]*?)\s*:\s*(?P<valor>.*?)\s*$")


def _valor(bruto: str) -> str:
    bruto = bruto.strip()
    if bruto[:1] in ("'", '"'):
        aspa = bruto[0]
        fim = bruto.find(aspa, 1)
        while fim != -1 and aspa == '"' and bruto[fim - 1] == "\\":
            fim = bruto.find(aspa, fim + 1)
        if fim == -1:
            raise ValueError(f"Aspas sem fechamento: {bruto}")
        texto = bruto[1:fim]
        return texto.replace('\\"', '"') if aspa == '"' else texto.replace("''", "'")
    return bruto.split(" #", 1)[0].strip()  # comentário no fim da linha


def loads(texto: str) -> dict:
    resultado: dict = {}
    secao: dict | None = None
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        m = _LINHA.match(linha)
        if not m:
            raise ValueError(f"Linha {numero} fora do formato 'chave: valor': {linha}")
        chave, valor = m.group("chave").strip().strip("'\""), m.group("valor")
        if m.group("recuo"):
            if secao is None:
                raise ValueError(f"Linha {numero} com recuo fora de uma seção: {linha}")
            secao[chave] = _valor(valor)
        elif valor == "" or valor.startswith("#"):
            secao = resultado[chave] = {}
        else:
            resultado[chave] = _valor(valor)
            secao = None
    return resultado


def dumps(dados: dict) -> str:
    """Grava um dicionário de um nível (chave -> texto)."""
    def aspas(v: str) -> str:
        return '"' + str(v).replace('"', '\\"') + '"'
    return "".join(f"{k}: {aspas(v)}\n" for k, v in dados.items())
