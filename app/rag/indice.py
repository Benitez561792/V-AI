"""Vector store simples em numpy: busca exata por similaridade de cosseno.

Com alguns milhares de trechos, multiplicar a consulta por toda a matriz leva menos de um
milissegundo, então não há ganho em usar uma biblioteca de busca aproximada (e o numpy
funciona em qualquer versão do Python).

Arquivos salvos em DIR_INDICE:
- vetores.npy    vetores normalizados
- trechos.json   texto e metadados de cada trecho, na mesma ordem
- meta.json      modelo de embedding, dimensão, data e fontes (para reprodução)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.rag.chunking import Trecho


class IndiceIndisponivel(RuntimeError):
    pass


def normalizar(vetores: np.ndarray) -> np.ndarray:
    vetores = np.asarray(vetores, dtype="float32")
    if vetores.ndim == 1:
        vetores = vetores[None, :]
    normas = np.linalg.norm(vetores, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return vetores / normas


@dataclass
class Resultado:
    trecho: Trecho
    similaridade: float


class IndiceVetorial:
    def __init__(self, vetores: np.ndarray, trechos: list[Trecho], meta: dict | None = None):
        if len(vetores) != len(trechos):
            raise ValueError("Número de vetores e de trechos diferente.")
        self._vetores = normalizar(vetores)
        self.trechos = trechos
        self.meta = meta or {}

    @property
    def tamanho(self) -> int:
        return len(self.trechos)

    def buscar(self, vetor_consulta: np.ndarray, k: int) -> list[Resultado]:
        k = min(k, self.tamanho)
        if k == 0:
            return []
        consulta = normalizar(vetor_consulta)[0]
        if consulta.shape[0] != self._vetores.shape[1]:
            raise IndiceIndisponivel("Dimensão da consulta diferente da do índice. Rode: python -m app.rag.ingestao")
        scores = self._vetores @ consulta
        melhores = np.argsort(-scores, kind="stable")[:k]
        return [Resultado(self.trechos[p], float(scores[p])) for p in melhores]

    def secoes_conhecidas(self) -> set[str]:
        return {t.secao for t in self.trechos if t.secao}

    def referencia_existe(self, norma: str | None, secao: str | None) -> bool | None:
        """A seção citada existe na base? Se a referência cita uma norma pelo número
        ("NBR 16537 6.8"), procura só nas fontes com esse número no nome. Uma seção-mãe sem
        texto próprio (ex.: "6.3.4 Desníveis") existe se tiver subseções (6.3.4.1...)."""
        if not secao:
            return None
        numeros = set(re.findall(r"\d{4,5}", norma or ""))
        fontes = {t.fonte for t in self.trechos if numeros & set(re.findall(r"\d{4,5}", t.fonte))}
        return any(t.secao == secao or t.secao.startswith(secao + ".")
                   for t in self.trechos if t.secao and (not fontes or t.fonte in fontes))

    def salvar(self, diretorio: Path, modelo_embedding: str, extras: dict | None = None) -> None:
        diretorio.mkdir(parents=True, exist_ok=True)
        np.save(diretorio / "vetores.npy", self._vetores)
        (diretorio / "trechos.json").write_text(
            json.dumps([t.para_dict() for t in self.trechos], ensure_ascii=False, indent=1), encoding="utf-8")
        self.meta = {
            "modeloEmbedding": modelo_embedding,
            "dimensao": int(self._vetores.shape[1]),
            "totalTrechos": self.tamanho,
            "fontes": sorted({t.fonte for t in self.trechos}),
            "criadoEm": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **(extras or {}),
        }
        (diretorio / "meta.json").write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def carregar(cls, diretorio: Path) -> "IndiceVetorial":
        arq = diretorio / "vetores.npy"
        if not arq.exists():
            raise IndiceIndisponivel(f"Índice não encontrado em {diretorio}. Rode: python -m app.rag.ingestao")
        vetores = np.load(arq)
        trechos = [Trecho(**d) for d in json.loads((diretorio / "trechos.json").read_text(encoding="utf-8"))]
        meta = json.loads((diretorio / "meta.json").read_text(encoding="utf-8"))
        return cls(vetores, trechos, meta)


def carregar_compativel(diretorio: Path, id_embedding: str) -> IndiceVetorial:
    """Carrega o índice e confere se foi gerado com o mesmo embedding do provedor atual.

    Vetores de modelos diferentes não são comparáveis (e podem ter dimensões diferentes),
    então trocar de provedor ou de modelo de embedding exige rodar a ingestão de novo.
    """
    indice = IndiceVetorial.carregar(diretorio)
    gerado_com = indice.meta.get("modeloEmbedding")
    if gerado_com != id_embedding:
        raise IndiceIndisponivel(
            f"Índice gerado com '{gerado_com}', mas o provedor atual usa '{id_embedding}'. "
            "Rode de novo: python -m app.rag.ingestao")
    return indice


_NUMERO = re.compile(r"\d{1,2}(?:\.\d{1,3})+|\b\d{1,2}\b")


def extrair_secao(referencia: str | None) -> str | None:
    """'NBR 9050 item 6.12.1' -> '6.12.1'; 'Lei 13.146/2015 art. 46' -> 'art. 46'.
    Ignora o número da norma ou da lei."""
    if not referencia:
        return None
    artigo = re.search(r"\bart(?:igo)?\.?\s*(\d{1,4})", referencia, re.IGNORECASE)
    if artigo:
        return f"art. {artigo.group(1)}"
    texto = re.sub(r"\b\d{1,2}\.\d{3}/\d{4}\b", " ", referencia)        # 13.146/2015
    texto = re.sub(r"\b\d{4,5}(?::\d{4})?\b", " ", texto)                  # 9050, 16537:2024
    m = _NUMERO.search(texto)
    return m.group(0) if m else None
