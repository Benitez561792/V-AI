"""Métricas da avaliação. Funções puras, testadas em tests/test_metricas.py."""
from __future__ import annotations

import math


def separar(campo: str | None) -> set[str]:
    """'veiculo; pessoa' -> {'veiculo', 'pessoa'}"""
    if not campo:
        return set()
    return {p.strip() for p in str(campo).split(";") if p.strip()}


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil com interpolação linear (mesmo método padrão do numpy)."""
    v = sorted(x for x in valores if x is not None and not math.isnan(x))
    if not v:
        return None
    pos = (len(v) - 1) * p / 100
    baixo, alto = math.floor(pos), math.ceil(pos)
    return v[baixo] + (v[alto] - v[baixo]) * (pos - baixo)


def recall_precisao(esperados: list[set[str]], retornados: list[set[str]]) -> dict:
    """Micro-média por categoria de perigo, somando todas as fotos."""
    acertos = sum(len(e & r) for e, r in zip(esperados, retornados))
    total_esperado = sum(len(e) for e in esperados)
    total_retornado = sum(len(r) for r in retornados)
    return {
        "recall": acertos / total_esperado if total_esperado else None,
        "precisao": acertos / total_retornado if total_retornado else None,
        "acertos": acertos,
        "esperados": total_esperado,
        "retornados": total_retornado,
    }


def taxa(condicoes: list[bool]) -> float | None:
    return sum(condicoes) / len(condicoes) if condicoes else None


def secao_confere(retornada: str | None, esperada: str | None) -> bool:
    """A seção retornada é a esperada ou uma subseção dela (6.12.1 confere com 6.12)."""
    if not retornada or not esperada:
        return False
    return retornada == esperada or retornada.startswith(esperada + ".")


def referencia_confere(norma: str | None, secao: str | None, esperada: str | None) -> bool:
    """Compara a referência retornada com a anotação.

    A anotação aceita várias opções separadas por ";" e pode indicar a norma pelo número:
    "9050 6.12.3; 16537 6.8". Uma opção confere quando a norma retornada contém o número
    indicado (se houver) e a seção é igual ou subseção da anotada.
    """
    if not esperada or not secao:
        return False
    for opcao in esperada.split(";"):
        partes = opcao.split()
        if not partes:
            continue
        fonte, sec = (" ".join(partes[:-1]), partes[-1]) if len(partes) > 1 else (None, partes[0])
        if fonte and (not norma or fonte not in norma):
            continue
        if secao_confere(secao, sec):
            return True
    return False


def fmt(valor, pct: bool = False, casas: int = 0) -> str:
    if valor is None:
        return "n/d"
    if pct:
        return f"{valor * 100:.1f}%"
    return f"{valor:.{casas}f}"
