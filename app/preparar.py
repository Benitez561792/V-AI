"""Deixa tudo pronto antes da consulta: .env, leis e índice do RAG.

Chamado automaticamente por `python consultar.py` e `python avaliar.py`. Na primeira vez baixa
as leis e gera o índice; depois só confere e segue (o índice só é refeito quando um documento
de data/fontes/ ou o provedor de IA muda). Por padrão trabalha em silêncio: só avisa quando
vai demorar e mostra o detalhe se algo der errado.
"""
from __future__ import annotations

import contextlib
import io
import shutil
import sys

from app.config import RAIZ, carregar_config

MARCA_LEIS = ".leis_tentadas"  # evita tentar baixar as leis toda vez se o site estiver fora


def preparar(silencioso: bool = True) -> bool:
    env = RAIZ / ".env"
    if not env.exists() and (RAIZ / ".env.example").exists():
        shutil.copy(RAIZ / ".env.example", env)
        print("Arquivo .env criado. Coloque a OPENAI_API_KEY nele para usar o ChatGPT.")

    from app.provedores import ErroIA, criar_provedor
    from app.rag import baixar_leis, ingestao

    cfg = carregar_config()
    marca = cfg.dir_fontes / MARCA_LEIS
    baixar = not any(cfg.dir_fontes.glob("lei*.txt")) and not marca.exists()
    try:
        id_embedding = criar_provedor(cfg).id_embedding
    except ErroIA as e:
        print(f"Erro: {e}", file=sys.stderr)
        return False
    indexar = baixar or not ingestao.indice_em_dia(
        cfg.dir_indice, id_embedding, ingestao.assinatura_fontes(cfg.dir_fontes, cfg.chunk_max_caracteres))
    if not indexar:
        return True

    print("Preparando a base de consulta (só na primeira vez)...")
    registro = io.StringIO()
    saida = registro if silencioso else sys.stdout
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        if baixar:
            if baixar_leis.main() != 0:
                print("Não foi possível baixar as leis agora; a consulta usa só as normas.")
            cfg.dir_fontes.mkdir(parents=True, exist_ok=True)
            marca.write_text("ok\n", encoding="utf-8")
        ok = ingestao.main(["--se-preciso", "--silencioso"]) == 0
    if not ok:
        print(registro.getvalue(), file=sys.stderr)
    return ok
