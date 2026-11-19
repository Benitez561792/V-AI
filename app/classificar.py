"""Testa a classificação pelo terminal, sem servidor e sem navegador.

    python -m app.classificar "O orelhão está na calçada sem nada no piso para avisar"
    python -m app.classificar "Buraco grande na calçada" --tipo CALCADA_DANIFICADA --gravidade ALTA
    python -m app.classificar "Buraco grande na calçada" --comparar    # com e sem RAG, lado a lado
    python -m app.classificar                                          # pergunta o texto

Usa o mesmo código do POST /classificar, com o provedor e o índice do .env.
"""
from __future__ import annotations

import argparse
import sys
import textwrap

from app.config import carregar_config
from app.provedores import ErroIA, criar_provedor
from app.rag.indice import IndiceIndisponivel, carregar_compativel
from app.schemas import ClassificarRequest, ClassificarResponse
from app.services.classificacao import classificar
from app.taxonomia import TAXONOMIA


def _mostrar(r: ClassificarResponse) -> None:
    titulo = "COM RAG" if r.modo == "rag" else "SEM RAG"
    print(f"\n--- {titulo} ({r.latenciaMs} ms, modelo {r.modelo}) ---")
    print(f"Tipo:        {r.tipo.value}")
    print(f"Gravidade:   {r.gravidade.value}")
    print(f"Norma:       {r.normaReferencia or 'nenhuma norma aplicável encontrada'}")
    if r.trecho:
        print("Trecho:")
        print(textwrap.indent(textwrap.fill(r.trecho.replace("\n", " "), 90), "   "))
    print("Justificativa:")
    print(textwrap.indent(textwrap.fill(r.justificativa, 90), "   "))
    if r.referenciasConsultadas:
        print("Trechos consultados (similaridade):")
        for ref in r.referenciasConsultadas:
            print(f"   {ref.similaridade:.2f}  {ref.fonte} {ref.secao or ''}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("texto", nargs="*", help="texto do relato")
    parser.add_argument("--tipo", choices=list(TAXONOMIA["barreiras"]), help="tipo escolhido no relato")
    parser.add_argument("--gravidade", choices=list(TAXONOMIA["gravidades"]), help="gravidade escolhida no relato")
    parser.add_argument("--comparar", action="store_true", help="mostra o resultado com e sem RAG")
    args = parser.parse_args(argv)

    texto = " ".join(args.texto).strip() or input("Descreva a barreira: ").strip()
    if len(texto) < 3:
        print("Escreva pelo menos uma frase curta.", file=sys.stderr)
        return 1

    cfg = carregar_config()
    try:
        ia = criar_provedor(cfg)
        indice = carregar_compativel(cfg.dir_indice, ia.id_embedding)
        if ia.nome_modelo == "falso":
            print("Atenção: IA_PROVEDOR=falso no .env. As respostas são fixas, sem a OpenAI.")
        for modo in (("rag", "sem_rag") if args.comparar else ("rag",)):
            req = ClassificarRequest(texto=texto, tipoSugerido=args.tipo, gravidadeSugerida=args.gravidade, modo=modo)
            _mostrar(classificar(ia, indice, cfg, req))
    except (ErroIA, IndiceIndisponivel) as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
