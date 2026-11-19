"""Classificação do relato com RAG (padrão) ou sem RAG (linha de base para a avaliação).

Com RAG:
1. A consulta (relato + tipo sugerido + objetos) vira embedding.
2. O índice devolve os top-k trechos; ficam só os que passam do limiar de similaridade.
3. O modelo classifica e escolhe o número do trecho que fundamenta (ou null).
4. normaReferencia, fonte e trecho saem dos METADADOS do trecho escolhido, nunca do texto
   gerado. Se nenhum trecho passa do limiar, a resposta vem com semNormaAplicavel = true.

Sem RAG: o modelo classifica e cita o item da norma de memória. Serve só para medir,
na avaliação, quanto o RAG reduz referências inventadas.
"""
from __future__ import annotations

import time

from app.config import Config
from app.provedores import ModeloIA
from app.prompts import renderizar
from app.rag.indice import IndiceIndisponivel, IndiceVetorial, Resultado, extrair_secao
from app.taxonomia import TAXONOMIA
from app.schemas import (
    ClassificarRequest,
    ClassificarResponse,
    ReferenciaConsultada,
    RespostaClassificacaoRag,
    RespostaClassificacaoSemRag,
)


def _texto_relato(req: ClassificarRequest) -> str:
    linhas = [f"Relato: {req.texto.strip()}"]
    if req.tipoSugerido:
        linhas.append(f"Tipo escolhido no relato: {req.tipoSugerido.value}")
    if req.gravidadeSugerida:
        linhas.append(f"Gravidade escolhida no relato: {req.gravidadeSugerida.value}")
    if req.objetos:
        linhas.append("Objetos detectados na foto: " + ", ".join(req.objetos))
    return "\n".join(linhas)


def _consulta_embedding(req: ClassificarRequest) -> str:
    """Texto usado na busca: o relato mais a descrição em palavras do tipo escolhido.
    Chaves de enum (PISO_TATIL) e gravidade não ajudam a busca semântica."""
    partes = [req.texto.strip()]
    if req.tipoSugerido:
        partes.append(TAXONOMIA["barreiras"][req.tipoSugerido.value])
    if req.objetos:
        partes.append(", ".join(req.objetos))
    return "\n".join(partes)


def _formatar_trechos(resultados: list[Resultado]) -> str:
    if not resultados:
        return "Trechos: nenhum trecho relevante foi encontrado na base."
    blocos = []
    for i, r in enumerate(resultados, start=1):
        t = r.trecho
        cabecalho = f"[{i}] Fonte: {t.fonte}"
        if t.titulo:
            cabecalho += f" | {t.titulo}"
        blocos.append(f"{cabecalho}\n{t.texto}")
    return "Trechos:\n\n" + "\n\n".join(blocos)


def _referencia(r: Resultado) -> ReferenciaConsultada:
    return ReferenciaConsultada(
        fonte=r.trecho.fonte, secao=r.trecho.secao, titulo=r.trecho.titulo,
        similaridade=round(r.similaridade, 4),
    )


def classificar(ia: ModeloIA, indice: IndiceVetorial | None, cfg: Config,
                req: ClassificarRequest) -> ClassificarResponse:
    inicio = time.perf_counter()
    relato = _texto_relato(req)

    if req.modo == "sem_rag":
        r = ia.gerar_json(renderizar("classificacao_sem_rag"), relato, RespostaClassificacaoSemRag)
        return ClassificarResponse(
            relatoId=req.relatoId, tipo=r.tipo, gravidade=r.gravidade,
            normaReferencia=r.normaReferencia, fonte=None,
            secao=extrair_secao(r.normaReferencia), trecho=None,
            justificativa=r.justificativa, semNormaAplicavel=r.normaReferencia is None,
            modo="sem_rag", referenciasConsultadas=[], modelo=ia.nome_modelo,
            latenciaMs=round((time.perf_counter() - inicio) * 1000),
        )

    if indice is None:
        raise IndiceIndisponivel("Índice do RAG não carregado. Rode: python -m app.rag.ingestao")

    vetor = ia.embeddings([_consulta_embedding(req)], "RETRIEVAL_QUERY")
    candidatos = indice.buscar(vetor, cfg.rag_top_k)
    relevantes = [c for c in candidatos if c.similaridade >= cfg.rag_limiar]

    r = ia.gerar_json(
        renderizar("classificacao_rag"),
        f"{relato}\n\n{_formatar_trechos(relevantes)}",
        RespostaClassificacaoRag,
    )

    escolhido: Resultado | None = None
    if r.trechoEscolhido is not None and 1 <= r.trechoEscolhido <= len(relevantes):
        escolhido = relevantes[r.trechoEscolhido - 1]

    norma = None
    if escolhido:
        t = escolhido.trecho
        norma = (f"{t.fonte} {t.secao}" if t.secao else t.fonte)[:200]  # limite da coluna no Oracle

    return ClassificarResponse(
        relatoId=req.relatoId,
        tipo=r.tipo,
        gravidade=r.gravidade,
        normaReferencia=norma,
        fonte=escolhido.trecho.fonte if escolhido else None,
        secao=escolhido.trecho.secao if escolhido else None,
        trecho=escolhido.trecho.texto if escolhido else None,
        justificativa=r.justificativa,
        semNormaAplicavel=escolhido is None,
        modo="rag",
        referenciasConsultadas=[_referencia(c) for c in candidatos],
        modelo=ia.nome_modelo,
        latenciaMs=round((time.perf_counter() - inicio) * 1000),
    )
