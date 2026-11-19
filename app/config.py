"""Configuração do serviço, lida de variáveis de ambiente (ou do arquivo .env).

Nenhuma credencial fica no código. Veja .env.example. Os nomes das variáveis da OpenAI
são os mesmos da API Java, para o grupo configurar os dois serviços do mesmo jeito.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent


def _opcional(nome: str, tipo=str):
    valor = os.getenv(nome, "").strip()
    return tipo(valor) if valor else None


@dataclass(frozen=True)
class Config:
    provedor: str
    openai_api_key: str
    modelo_geracao: str
    modelo_embedding: str
    dimensao_embedding: int | None
    temperatura: float | None
    reasoning_effort: str | None
    timeout_s: float
    rag_top_k: int
    consulta_top_k: int
    rag_limiar: float
    limiar_sugerir_relato: float
    dir_fontes: Path
    dir_indice: Path
    chunk_max_caracteres: int
    imagem_max_bytes: int


def carregar_config() -> Config:
    return Config(
        provedor=os.getenv("IA_PROVEDOR", "falso").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        modelo_geracao=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        modelo_embedding=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        dimensao_embedding=_opcional("OPENAI_EMBEDDING_DIMENSOES", int),
        temperatura=_opcional("OPENAI_TEMPERATURE", float),
        reasoning_effort=_opcional("OPENAI_REASONING_EFFORT") if "OPENAI_REASONING_EFFORT" in os.environ else "none",
        timeout_s=float(os.getenv("OPENAI_TIMEOUT_S", "20")),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        consulta_top_k=int(os.getenv("CONSULTA_TOP_K", "6")),
        rag_limiar=float(os.getenv("RAG_LIMIAR", "0.40")),
        limiar_sugerir_relato=float(os.getenv("LIMIAR_SUGERIR_RELATO", "0.70")),
        dir_fontes=Path(os.getenv("DIR_FONTES", str(RAIZ / "data" / "fontes"))),
        dir_indice=Path(os.getenv("DIR_INDICE", str(RAIZ / "data" / "indice"))),
        chunk_max_caracteres=int(os.getenv("CHUNK_MAX_CARACTERES", "1500")),
        imagem_max_bytes=int(os.getenv("IMAGEM_MAX_BYTES", str(5 * 1024 * 1024))),
    )
