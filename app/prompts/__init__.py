"""Prompts versionados como arquivos .md, preenchidos com a taxonomia.

Usa string.Template ($variavel) para não conflitar com chaves de JSON.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

from app.taxonomia import listar

_DIR = Path(__file__).parent


@lru_cache
def renderizar(nome: str) -> str:
    texto = (_DIR / f"{nome}.md").read_text(encoding="utf-8")
    return Template(texto).safe_substitute(
        tipos_barreira=listar("barreiras"),
        categorias_perigo=listar("perigos"),
        gravidades=listar("gravidades"),
    )
