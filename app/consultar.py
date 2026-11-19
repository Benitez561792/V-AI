"""Consulta sobre acessibilidade pelo terminal, sem servidor e sem navegador.

    python consultar.py                                          # conversa: pergunta até sair
    python consultar.py "Qual a largura mínima da faixa livre?"   # uma pergunta só
    python consultar.py "Qual a largura mínima da faixa livre?" --comparar   # com e sem RAG
    python consultar.py "Como sinalizar um orelhão?" --trechos    # mostra o texto da norma

Na primeira vez, prepara sozinho as leis e o índice do RAG.

Usa o mesmo código do POST /consultar, com o provedor e o índice do .env.
"""
from __future__ import annotations

import argparse
import re
import sys
import textwrap

from app.config import carregar_config
from app.provedores import ErroIA, criar_provedor
from app.rag.indice import IndiceIndisponivel, carregar_compativel
from app.schemas import ConsultarRequest, ConsultarResponse
from app.services.consulta import consultar

LARGURA = 90


def _bloco(texto: str, recuo: str = "   ") -> str:
    linhas = []
    for paragrafo in texto.splitlines() or [""]:
        linhas.append(textwrap.fill(paragrafo, LARGURA, initial_indent=recuo, subsequent_indent=recuo + "  ")
                      if paragrafo.strip() else "")
    return "\n".join(linhas)


def _numerar_citacoes(r: ConsultarResponse) -> str:
    """Troca "[Lei 13.146/2015 art. 46]" por "[1]", na ordem da lista de fontes."""
    numeros = {f.referencia: n for n, f in enumerate(r.fontes, start=1)}
    texto = re.sub(r"\[([^\[\]]+)\]", lambda m: f"[{numeros[m.group(1)]}]" if m.group(1) in numeros
                   else m.group(0), r.resposta)
    return re.sub(r"\](\s+)\[", "][", texto)


def mostrar(r: ConsultarResponse, detalhes: bool = False, cabecalho: bool = False) -> None:
    if cabecalho:
        titulo = "COM RAG" if r.modo == "rag" else "SEM RAG (memória do modelo)"
        print(f"\n--- {titulo} · {r.latenciaMs} ms ---")
    print()
    if r.modo == "rag":
        print(_bloco(_numerar_citacoes(r)))
        if r.fontes:
            print("\n   Fontes:")
            for n, f in enumerate(r.fontes, start=1):
                print(f"   [{n}] {f.referencia}")
                if detalhes:
                    print(_bloco(f.trecho.replace("\n", " ")[:600] + "...", "       "))
    else:
        print(_bloco(r.resposta))
        if r.referenciasCitadas:
            print("\n   Referências citadas de memória (não conferidas): " + "; ".join(r.referenciasCitadas))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pergunta", nargs="*")
    parser.add_argument("--comparar", action="store_true", help="mostra a resposta com e sem RAG")
    parser.add_argument("--trechos", action="store_true", help="mostra o texto dos trechos usados")
    parser.add_argument("--sem-preparar", action="store_true", help="não confere leis e índice antes")
    args = parser.parse_args(argv)

    if not args.sem_preparar:
        from app.preparar import preparar

        if not preparar():
            return 1

    cfg = carregar_config()
    try:
        ia = criar_provedor(cfg)
        indice = carregar_compativel(cfg.dir_indice, ia.id_embedding)
    except (ErroIA, IndiceIndisponivel) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    if ia.nome_modelo == "falso":
        print("Atenção: IA_PROVEDOR=falso no .env. As respostas são fixas, sem a OpenAI.")

    def responder(pergunta: str) -> bool:
        try:
            for modo in (("rag", "sem_rag") if args.comparar else ("rag",)):
                mostrar(consultar(ia, indice, cfg, ConsultarRequest(pergunta=pergunta, modo=modo)),
                        args.trechos, cabecalho=args.comparar)
            return True
        except (ErroIA, IndiceIndisponivel) as e:
            print(f"\nErro: {e}", file=sys.stderr)
            return False

    if args.pergunta:
        return 0 if responder(" ".join(args.pergunta)) else 1

    print("\nBem-vindo ao Vê AI")
    while True:
        try:
            pergunta = input("\nPergunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pergunta:
            break
        if len(pergunta) < 3:
            print("Escreva uma pergunta um pouco maior.")
            continue
        responder(pergunta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
