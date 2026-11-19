"""Vê AI · Avaliação com e sem RAG: perguntas de consulta e classificação de relatos.

    python avaliar.py              # roda as duas e gera os relatórios em avaliacao/resultados/
    python avaliar.py perguntas    # só a consulta
"""
import sys

from app.preparar import preparar
from avaliacao import perguntas, relatos


def main(argv: list[str]) -> int:
    if not preparar():
        return 1
    qual = argv[0] if argv else "todas"
    if qual in ("todas", "perguntas"):
        print("\n=== Consulta: perguntas com e sem RAG ===\n")
        if perguntas.main(["rodar"]) != 0:
            return 1
    if qual in ("todas", "relatos"):
        print("\n=== Classificação de relatos com e sem RAG ===\n")
        if relatos.main(["rodar"]) != 0:
            return 1
    print("\nRelatórios em avaliacao/resultados/ (relatorio_perguntas.md e relatorio_relatos.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
