"""Consulta: perguntas sobre acessibilidade respondidas com base nas normas e leis (RAG).

Com RAG:
1. A pergunta vira embedding e o índice devolve os trechos mais parecidos acima do limiar.
2. O modelo responde só com esses trechos e cita cada informação com o número do trecho: [1].
3. O sistema troca cada [n] pela referência real do trecho (ex.: "ABNT NBR 9050:2020 6.12.3"),
   tirada dos metadados. Números inválidos são removidos. Assim nenhuma referência é inventada.

Sem RAG: o modelo responde de memória e lista as referências que acha que se aplicam. Serve só
para medir, na avaliação, quanto o RAG reduz referências inventadas.
"""
from __future__ import annotations

import re
import time

from app.config import Config
from app.prompts import renderizar
from app.provedores import ModeloIA
from app.rag.indice import IndiceIndisponivel, IndiceVetorial, Resultado
from app.schemas import (
    ConsultarRequest,
    ConsultarResponse,
    FonteConsulta,
    ReferenciaConsultada,
    RespostaConsultaRag,
    RespostaConsultaSemRag,
)
from app.services.classificacao import _formatar_trechos

_CITACAO = re.compile(r"\s?\[(\d{1,2})\]")


def referencia(r: Resultado) -> str:
    t = r.trecho
    return (f"{t.fonte} {t.secao}" if t.secao else t.fonte)[:200]


def trocar_citacoes(texto: str, relevantes: list[Resultado]) -> tuple[str, list[int]]:
    """Troca [n] pela referência do trecho n. Citações repetidas em sequência viram uma só."""
    citados: list[int] = []

    def troca(m: re.Match) -> str:
        n = int(m.group(1))
        if not 1 <= n <= len(relevantes):
            return ""
        if n not in citados:
            citados.append(n)
        return f" [{referencia(relevantes[n - 1])}]"

    novo = _CITACAO.sub(troca, texto)
    novo = re.sub(r"(\[[^\]]+\])(?:\s?\1)+", r"\1", novo)  # "[X] [X]" -> "[X]"
    return novo.strip(), citados


def consultar(ia: ModeloIA, indice: IndiceVetorial | None, cfg: Config,
              req: ConsultarRequest) -> ConsultarResponse:
    inicio = time.perf_counter()
    pergunta = req.pergunta.strip()

    if req.modo == "sem_rag":
        r = ia.gerar_json(renderizar("consulta_sem_rag"), f"Pergunta: {pergunta}", RespostaConsultaSemRag)
        refs = [x.strip()[:200] for x in r.referencias if x.strip()]
        return ConsultarResponse(
            pergunta=pergunta, resposta=r.resposta.strip(), fontes=[], referenciasCitadas=refs,
            respondidaPelaBase=bool(refs), modo="sem_rag", referenciasConsultadas=[],
            modelo=ia.nome_modelo, latenciaMs=round((time.perf_counter() - inicio) * 1000))

    if indice is None:
        raise IndiceIndisponivel("Índice do RAG não carregado. Rode: python -m app.rag.ingestao")

    vetor = ia.embeddings([pergunta], "RETRIEVAL_QUERY")
    candidatos = indice.buscar(vetor, cfg.consulta_top_k)
    relevantes = [c for c in candidatos if c.similaridade >= cfg.rag_limiar]

    r = ia.gerar_json(renderizar("consulta_rag"),
                      f"Pergunta: {pergunta}\n\n{_formatar_trechos(relevantes)}", RespostaConsultaRag)
    resposta, citados = trocar_citacoes(r.resposta, relevantes)
    for n in r.trechosUsados:  # trechos declarados como usados, mesmo sem [n] no texto
        if 1 <= n <= len(relevantes) and n not in citados:
            citados.append(n)

    fontes = [FonteConsulta(referencia=referencia(relevantes[n - 1]), fonte=relevantes[n - 1].trecho.fonte,
                            secao=relevantes[n - 1].trecho.secao, trecho=relevantes[n - 1].trecho.texto,
                            similaridade=round(relevantes[n - 1].similaridade, 4)) for n in citados]
    return ConsultarResponse(
        pergunta=pergunta,
        resposta=resposta,
        fontes=fontes,
        referenciasCitadas=[f.referencia for f in fontes],
        respondidaPelaBase=r.respondidaPelaBase and bool(fontes),
        modo="rag",
        referenciasConsultadas=[ReferenciaConsultada(fonte=c.trecho.fonte, secao=c.trecho.secao,
                                                     titulo=c.trecho.titulo,
                                                     similaridade=round(c.similaridade, 4)) for c in candidatos],
        modelo=ia.nome_modelo,
        latenciaMs=round((time.perf_counter() - inicio) * 1000),
    )
