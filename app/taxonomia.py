"""Carrega app/taxonomia.yaml e gera os Enums usados nos schemas."""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from app import miniyaml

_ARQUIVO = Path(__file__).with_name("taxonomia.yaml")

with _ARQUIVO.open(encoding="utf-8") as f:
    TAXONOMIA: dict[str, dict[str, str]] = miniyaml.loads(f.read())

TipoBarreira = Enum("TipoBarreira", {k: k for k in TAXONOMIA["barreiras"]}, type=str)
CategoriaPerigo = Enum("CategoriaPerigo", {k: k for k in TAXONOMIA["perigos"]}, type=str)
Gravidade = Enum("Gravidade", {k: k for k in TAXONOMIA["gravidades"]}, type=str)


def listar(secao: str) -> str:
    """Lista 'chave: descrição', uma por linha, para inserir nos prompts."""
    return "\n".join(f"- {k}: {v}" for k, v in TAXONOMIA[secao].items())
