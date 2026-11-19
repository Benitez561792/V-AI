"""Fixtures dos testes. Nenhum teste chama a API da OpenAI."""
from __future__ import annotations

import hashlib
import io
import re
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import carregar_config
from app.main import criar_app
from app.rag.chunking import carregar_trechos
from app.rag.ingestao import construir_indice
from app.schemas import (
    Barreira, Descricao, Perigo, QualidadeImagem,
    RespostaClassificacaoRag, RespostaClassificacaoSemRag, RespostaConsultaRag, RespostaConsultaSemRag,
)

FONTES = Path(__file__).parent / "fixtures" / "fontes"
DIM = 4096


def _embedding_bag_of_words(texto: str) -> np.ndarray:
    """Embedding determinístico por hashing de palavras: suficiente para testar a busca."""
    v = np.zeros(DIM, dtype="float32")
    for palavra in re.findall(r"\w{4,}", texto.lower()):
        h = int(hashlib.md5(palavra.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0
    return v


class IAFalsa:
    nome_modelo = "modelo-falso"
    id_embedding = "teste:hash"

    def __init__(self):
        self.descricao: Descricao = descricao_exemplo()
        self.trecho_escolhido: int | None = 1
        self.norma_sem_rag: str | None = "NBR 9050 9.9.9"
        self.chamadas: list[dict] = []
        self.resposta_consulta = RespostaConsultaRag(
            resposta="O piso tátil de alerta é exigido antes de rampas [1]. Também não pode estar danificado [1][9].",
            trechosUsados=[1], respondidaPelaBase=True)

    def gerar_json(self, sistema, texto, schema, imagem=None, mime=None):
        self.chamadas.append({"schema": schema.__name__, "texto": texto, "tem_imagem": imagem is not None})
        if schema is Descricao:
            return self.descricao
        if schema is RespostaClassificacaoRag:
            return RespostaClassificacaoRag(tipo="PISO_TATIL", gravidade="ALTA",
                                            trechoEscolhido=self.trecho_escolhido,
                                            justificativa="O piso tátil está interrompido.")
        if schema is RespostaClassificacaoSemRag:
            return RespostaClassificacaoSemRag(tipo="PISO_TATIL", gravidade="ALTA",
                                               normaReferencia=self.norma_sem_rag,
                                               justificativa="Justificativa sem RAG.")
        if schema is RespostaConsultaRag:
            return self.resposta_consulta
        if schema is RespostaConsultaSemRag:
            return RespostaConsultaSemRag(resposta="Resposta de memória.", referencias=["NBR 9050 9.9.9"])
        raise AssertionError(schema)

    def embeddings(self, textos, tarefa):
        return np.stack([_embedding_bag_of_words(t) for t in textos])


def descricao_exemplo(**alteracoes) -> Descricao:
    base = dict(
        qualidadeImagem=QualidadeImagem(adequada=True, problema="nenhum"),
        perigos=[
            Perigo(categoria="obstaculo_fixo", descricao="Lixeira no meio da calçada", posicao="direita", urgencia="atencao"),
            Perigo(categoria="buraco_ou_desnivel", descricao="Buraco grande", posicao="frente", urgencia="imediata"),
        ],
        resumo="Calçada estreita com comércio à esquerda.",
        objetos=["lixeira", "poste"],
        textoLido=None,
        barreira=Barreira(detectada=True, tipo="CALCADA_DANIFICADA", descricao="Buracos e desníveis na faixa livre", confianca=0.9),
        avisos=[],
    )
    base.update(alteracoes)
    return Descricao(**base)


def png_minimo() -> bytes:
    def bloco(tipo, dados):
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + bloco(b"IEND", b""))


@pytest.fixture(autouse=True)
def sem_credenciais_reais(monkeypatch):
    """Os testes nunca usam o .env de quem roda: nada de chave real nem chamadas à OpenAI."""
    monkeypatch.setenv("IA_PROVEDOR", "falso")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def cfg(tmp_path):
    return replace(carregar_config(), dir_fontes=FONTES, dir_indice=tmp_path / "indice", rag_limiar=0.30)


@pytest.fixture
def ia():
    return IAFalsa()


@pytest.fixture
def indice(ia, cfg):
    return construir_indice(carregar_trechos(cfg.dir_fontes), ia)


@pytest.fixture
def cliente(ia, indice, cfg):
    with TestClient(criar_app(ia=ia, indice=indice, cfg=cfg)) as c:
        yield c
