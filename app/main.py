"""Serviço de IA do Vê AI (FastAPI).

Executar:  uvicorn app.main:app --reload
Swagger:   http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Config, carregar_config
from app.provedores import ErroIA, ModeloIA, criar_provedor
from app.prompts import renderizar
from app.rag.indice import IndiceIndisponivel, IndiceVetorial, carregar_compativel
from app.schemas import (ClassificarRequest, ClassificarResponse, ConsultarRequest, ConsultarResponse,
                         Descricao, DescreverResponse)
from app.services.classificacao import classificar
from app.services.consulta import consultar
from app.services.descricao import descrever
from app.taxonomia import TAXONOMIA

log = logging.getLogger("veai.ia")
MIMES_ACEITOS = {"image/jpeg", "image/png", "image/webp"}


def criar_app(ia: ModeloIA | None = None, indice: IndiceVetorial | None = None,
              cfg: Config | None = None, carregar_indice: bool = True) -> FastAPI:
    cfg = cfg or carregar_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.cfg = cfg
        app.state.erro_ia = None
        app.state.erro_indice = None
        app.state.ia = ia
        if app.state.ia is None:
            try:
                app.state.ia = criar_provedor(cfg)
            except ErroIA as e:
                app.state.erro_ia = str(e)
                log.warning(str(e))
        if getattr(app.state.ia, "nome_modelo", None) == "falso":
            log.warning("IA_PROVEDOR=falso: respostas fixas, sem chamar a OpenAI.")
        app.state.indice = indice
        if app.state.indice is None and carregar_indice and app.state.ia is not None:
            try:
                app.state.indice = carregar_compativel(cfg.dir_indice, app.state.ia.id_embedding)
            except IndiceIndisponivel as e:
                app.state.erro_indice = str(e)
                log.warning(str(e))
        yield

    app = FastAPI(
        title="Vê AI · Serviço de IA",
        version="1.0.0",
        description="IA de consulta sobre acessibilidade para pessoas com deficiência visual: "
                    "responde perguntas e classifica relatos de barreiras com RAG sobre normas e leis.",
        lifespan=lifespan,
    )

    @app.exception_handler(ErroIA)
    async def _erro_ia(_: Request, e: ErroIA):
        return JSONResponse(status_code=502, content={"erro": "falha_ia", "detalhe": str(e)})

    @app.exception_handler(IndiceIndisponivel)
    async def _erro_indice(_: Request, e: IndiceIndisponivel):
        return JSONResponse(status_code=503, content={"erro": "indice_indisponivel", "detalhe": str(e)})

    def _indice(request: Request) -> IndiceVetorial | None:
        if request.app.state.indice is None and request.app.state.erro_indice:
            raise IndiceIndisponivel(request.app.state.erro_indice)
        return request.app.state.indice

    def _ia(request: Request) -> ModeloIA:
        if request.app.state.ia is None:
            raise HTTPException(503, detail=request.app.state.erro_ia or "Modelo indisponível.")
        return request.app.state.ia

    @app.get("/health", tags=["operação"])
    def health(request: Request):
        idx = request.app.state.indice
        ia_atual = request.app.state.ia
        return {
            "status": "ok" if ia_atual is not None and idx is not None else "degradado",
            "provedor": cfg.provedor,
            "modelo": getattr(ia_atual, "nome_modelo", None),
            "embedding": getattr(ia_atual, "id_embedding", None),
            "iaConfigurada": ia_atual is not None,
            "erroIa": request.app.state.erro_ia,
            "indiceCarregado": idx is not None,
            "erroIndice": request.app.state.erro_indice,
            "trechosNoIndice": idx.tamanho if idx else 0,
            "fontes": idx.meta.get("fontes", []) if idx else [],
        }

    @app.get("/taxonomia", tags=["contrato"])
    def taxonomia():
        return TAXONOMIA

    @app.get("/schema/descricao", tags=["contrato"],
             summary="JSON Schema da descrição, para a API Java usar no Spring AI")
    def schema_descricao():
        return Descricao.model_json_schema()

    @app.get("/prompts/{nome}", tags=["contrato"], response_class=PlainTextResponse,
             summary="Prompt renderizado (descricao, classificacao_rag, classificacao_sem_rag)")
    def prompt(nome: Literal["descricao", "classificacao_rag", "classificacao_sem_rag",
                             "consulta_rag", "consulta_sem_rag"]):
        return renderizar(nome)

    @app.post("/descrever", response_model=DescreverResponse, tags=["ia"],
              summary="Descreve a foto: perigos primeiro. A imagem não é armazenada.")
    def endpoint_descrever(
        request: Request,
        imagem: UploadFile = File(..., description="JPEG, PNG ou WEBP"),
        modo: Literal["ambiente", "texto"] = Form("ambiente"),
    ):
        if imagem.content_type not in MIMES_ACEITOS:
            raise HTTPException(415, detail=f"Tipo não suportado: {imagem.content_type}. Use JPEG, PNG ou WEBP.")
        dados = imagem.file.read(cfg.imagem_max_bytes + 1)
        if len(dados) > cfg.imagem_max_bytes:
            raise HTTPException(413, detail="Imagem maior que o limite.")
        if not dados:
            raise HTTPException(400, detail="Imagem vazia.")
        resp = descrever(_ia(request), cfg, dados, imagem.content_type, modo)
        log.info("descrever modo=%s latencia_ms=%d perigos=%d", modo, resp.latenciaMs,
                 len(resp.descricao.perigos))
        return resp

    @app.post("/consultar", response_model=ConsultarResponse, tags=["ia"],
              summary="Responde perguntas sobre acessibilidade citando a norma ou lei (RAG)")
    def endpoint_consultar(request: Request, req: ConsultarRequest):
        resp = consultar(_ia(request), _indice(request) if req.modo == "rag" else None, cfg, req)
        log.info("consultar modo=%s latencia_ms=%d fontes=%d", req.modo, resp.latenciaMs, len(resp.fontes))
        return resp

    @app.post("/classificar", response_model=ClassificarResponse, tags=["ia"],
              summary="Classifica o relato e fundamenta na norma (RAG)")
    def endpoint_classificar(request: Request, req: ClassificarRequest):
        resp = classificar(_ia(request), _indice(request) if req.modo == "rag" else None, cfg, req)
        log.info("classificar modo=%s latencia_ms=%d sem_norma=%s", req.modo, resp.latenciaMs,
                 resp.semNormaAplicavel)
        return resp

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = criar_app()
