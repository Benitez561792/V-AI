"""Monta o índice do RAG: fontes -> trechos por seção -> embeddings -> índice vetorial.

Uso:
    python -m app.rag.ingestao              # lê DIR_FONTES e grava em DIR_INDICE
    python -m app.rag.ingestao --listar     # só mostra os trechos, sem chamar a API
    python -m app.rag.ingestao --se-preciso # só refaz se as fontes ou o provedor mudaram
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import carregar_config
from app.provedores import ErroIA, ModeloIA, criar_provedor
from app.rag.chunking import EXTENSOES, Trecho, carregar_trechos
from app.rag.indice import IndiceVetorial


def construir_indice(trechos: list[Trecho], ia: ModeloIA) -> IndiceVetorial:
    vetores = ia.embeddings([t.texto_para_embedding() for t in trechos], "RETRIEVAL_DOCUMENT")
    return IndiceVetorial(vetores, trechos)


def assinatura_fontes(diretorio: Path, chunk_max: int) -> list:
    """Nome, tamanho e data de cada fonte: muda quando um documento entra, sai ou é editado."""
    arquivos = [a for a in sorted(diretorio.glob("*"))
                if a.suffix.lower() in EXTENSOES | {".yaml"} and a.name.lower() != "readme.md"]
    return [chunk_max] + [[a.name, a.stat().st_size, int(a.stat().st_mtime)] for a in arquivos]


def indice_em_dia(dir_indice: Path, id_embedding: str, assinatura: list) -> bool:
    try:
        meta = json.loads((dir_indice / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return ((dir_indice / "vetores.npy").exists() and meta.get("modeloEmbedding") == id_embedding
            and meta.get("assinaturaFontes") == assinatura)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listar", action="store_true", help="mostra os trechos e sai")
    parser.add_argument("--se-preciso", action="store_true",
                        help="não refaz o índice se as fontes e o provedor não mudaram")
    parser.add_argument("--silencioso", action="store_true", help="não avisa quando o índice já está em dia")
    args = parser.parse_args(argv)

    cfg = carregar_config()
    assinatura = assinatura_fontes(cfg.dir_fontes, cfg.chunk_max_caracteres)
    if args.se_preciso and not args.listar:
        try:  # confere antes de ler os PDFs, que é a parte demorada
            if indice_em_dia(cfg.dir_indice, criar_provedor(cfg).id_embedding, assinatura):
                if not args.silencioso:
                    print("Índice em dia, nada a refazer.")
                return 0
        except ErroIA as e:
            print(e, file=sys.stderr)
            return 1

    trechos = carregar_trechos(cfg.dir_fontes, cfg.chunk_max_caracteres)
    if not trechos:
        print(f"Nenhuma fonte em {cfg.dir_fontes}. Veja data/fontes/README.md.", file=sys.stderr)
        return 1

    if args.se_preciso:
        print("Montando o índice do RAG (só quando os documentos mudam)...")
    por_fonte: dict[str, int] = {}
    for t in trechos:
        por_fonte[t.fonte] = por_fonte.get(t.fonte, 0) + 1
    for fonte, n in por_fonte.items():
        print(f"{fonte}: {n} trechos")

    if args.listar:
        for t in trechos:
            print(f"\n[{t.id}] {t.titulo or ''} ({len(t.texto)} caracteres)\n{t.texto[:200]}...")
        return 0

    try:
        ia = criar_provedor(cfg)
        print("Gerando embeddings...")
        indice = construir_indice(trechos, ia)
    except ErroIA as e:
        print(e, file=sys.stderr)
        return 1
    indice.salvar(cfg.dir_indice, ia.id_embedding, {"assinaturaFontes": assinatura})
    print(f"Índice salvo em {cfg.dir_indice} com {indice.tamanho} trechos (embedding: {ia.id_embedding}).")
    if ia.id_embedding.startswith("falso"):
        print("Atenção: índice do provedor falso. Com IA_PROVEDOR=openai, ele é refeito na próxima execução.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
