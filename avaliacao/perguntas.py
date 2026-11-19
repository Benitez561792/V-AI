"""Avaliação da consulta: perguntas sobre acessibilidade respondidas com e sem RAG.

    python -m avaliacao.perguntas rodar          # gera o CSV e o relatório
    # opcional: preencham "resposta_correta" (sim, parcial ou nao) nas linhas e gerem de novo:
    python -m avaliacao.perguntas resumir avaliacao/resultados/perguntas_AAAAMMDD_HHMM.csv

Usa avaliacao/perguntas.csv se existir, senão perguntas.exemplo.csv. Na coluna secao_esperada,
as seções aceitas vêm com o número da norma ("9050 6.12.3; 16537 6.8"), ou "nenhuma" quando a
pergunta está fora do escopo da base.

Métricas, com e sem RAG:
- referência inexistente: referências citadas que não existem na base (a memória do modelo inventa);
- referência correta: pelo menos uma referência citada confere com a anotação;
- recusa fora do escopo: perguntas sem norma aplicável que ficaram sem referência;
- resposta correta: revisão manual (opcional);
- latência p50/p95.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from app.config import carregar_config
from app.provedores import ErroIA, criar_provedor
from app.rag.indice import IndiceIndisponivel, carregar_compativel, extrair_secao
from app.schemas import ConsultarRequest
from app.services.consulta import consultar
from avaliacao.metricas import fmt, percentil, referencia_confere, taxa

DIR = Path(__file__).parent
COLUNAS = ["id", "modo", "pergunta", "secao_esperada", "erro", "resposta", "referencias",
           "referencias_inexistentes", "referencia_correta", "latencia_ms", "resposta_correta", "notas_revisor"]


def _avaliar_referencias(indice, refs: list[str], secoes: list[str | None], esperada: str) -> tuple[int, bool]:
    inexistentes = sum(1 for r, s in zip(refs, secoes) if indice.referencia_existe(r, s) is False or s is None)
    correta = any(referencia_confere(r, s, esperada) for r, s in zip(refs, secoes))
    return inexistentes, correta


def rodar(args) -> int:
    cfg = carregar_config()
    ia = criar_provedor(cfg)
    if ia.nome_modelo == "falso":
        print("Atenção: IA_PROVEDOR=falso. Os resultados não valem para a avaliação.", file=sys.stderr)
    indice = carregar_compativel(cfg.dir_indice, ia.id_embedding)

    if not args.perguntas:
        proprio = DIR / "perguntas.csv"
        args.perguntas = str(proprio if proprio.exists() else DIR / "perguntas.exemplo.csv")
    print(f"Perguntas: {args.perguntas}")
    with open(args.perguntas, encoding="utf-8") as f:
        perguntas = list(csv.DictReader(f))
    if args.limite:
        perguntas = perguntas[: args.limite]

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    arquivo = saida / f"perguntas_{datetime.now():%Y%m%d_%H%M}.csv"
    linhas = []
    for n, p in enumerate(perguntas, start=1):
        print(f"[{n}/{len(perguntas)}] {p['id']}", flush=True)
        for modo in ("rag", "sem_rag"):
            linha = {c: "" for c in COLUNAS}
            linha.update({"id": p["id"], "modo": modo, "pergunta": p["pergunta"],
                          "secao_esperada": p.get("secao_esperada", "")})
            for tentativa in range(2):
                try:
                    r = consultar(ia, indice, cfg, ConsultarRequest(pergunta=p["pergunta"], modo=modo))
                    if modo == "rag":
                        refs, secoes = [f.referencia for f in r.fontes], [f.secao for f in r.fontes]
                    else:
                        refs = r.referenciasCitadas
                        secoes = [extrair_secao(x) for x in refs]
                    inexistentes, correta = _avaliar_referencias(indice, refs, secoes, linha["secao_esperada"])
                    linha.update({"resposta": r.resposta, "referencias": " | ".join(refs),
                                  "referencias_inexistentes": inexistentes, "referencia_correta": correta,
                                  "latencia_ms": r.latenciaMs, "erro": ""})
                    break
                except ErroIA as e:
                    linha["erro"] = str(e)
                    if tentativa == 0:
                        time.sleep(10)
            linhas.append(linha)
            time.sleep(args.intervalo)

    with arquivo.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    print(f"\nSalvo em {arquivo}")
    resumir(argparse.Namespace(execucao=str(arquivo)))
    print("Se preencherem a coluna resposta_correta no CSV, gerem o relatório de novo com:\n"
          f"  python -m avaliacao.perguntas resumir {arquivo}")
    return 0


def calcular(linhas: list[dict]) -> dict:
    resultado = {}
    for modo in ("rag", "sem_rag"):
        ls = [l for l in linhas if l["modo"] == modo and not l.get("erro")]
        no_escopo = [l for l in ls if l.get("secao_esperada") and l["secao_esperada"] != "nenhuma"]
        fora = [l for l in ls if l.get("secao_esperada") == "nenhuma"]
        total_refs = sum(len([r for r in l["referencias"].split(" | ") if r]) for l in ls)
        inexistentes = sum(int(l["referencias_inexistentes"] or 0) for l in ls)
        manuais = [l["resposta_correta"].strip().lower() for l in ls if l.get("resposta_correta", "").strip()]
        latencias = [float(l["latencia_ms"]) for l in ls if l.get("latencia_ms")]
        resultado[modo] = {
            "perguntas": len(ls),
            "erros": len([l for l in linhas if l["modo"] == modo and l.get("erro")]),
            "referenciasCitadas": total_refs,
            "referenciaInexistente": inexistentes / total_refs if total_refs else None,
            "referenciaCorreta": taxa([str(l["referencia_correta"]) == "True" for l in no_escopo]),
            "recusaForaDoEscopo": taxa([not l["referencias"] for l in fora]),
            "respostaCorreta": taxa([m == "sim" for m in manuais]),
            "respostasRevisadas": len(manuais),
            "latenciaP50": percentil(latencias, 50),
            "latenciaP95": percentil(latencias, 95),
        }
    return resultado


def relatorio(m: dict, linhas: list[dict], origem: str) -> str:
    p = lambda v: fmt(v, pct=True)  # noqa: E731
    ms = lambda v: "n/d" if v is None else f"{v:.0f} ms"  # noqa: E731
    r, s = m["rag"], m["sem_rag"]
    out = [
        "# Relatório · Consulta com e sem RAG", "",
        f"Execução: `{origem}` · Gerado em {datetime.now():%d/%m/%Y %H:%M}", "",
        "| Métrica | Sem RAG | Com RAG |", "|---|---|---|",
        f"| Perguntas respondidas | {s['perguntas']} | {r['perguntas']} |",
        f"| Referências citadas | {s['referenciasCitadas']} | {r['referenciasCitadas']} |",
        f"| Referência inexistente na base | {p(s['referenciaInexistente'])} | {p(r['referenciaInexistente'])} |",
        f"| Referência correta (perguntas no escopo) | {p(s['referenciaCorreta'])} | {p(r['referenciaCorreta'])} |",
        f"| Sem referência quando a pergunta está fora do escopo | {p(s['recusaForaDoEscopo'])} | {p(r['recusaForaDoEscopo'])} |",
        f"| Resposta correta (revisão manual) | {p(s['respostaCorreta'])} ({s['respostasRevisadas']}) | {p(r['respostaCorreta'])} ({r['respostasRevisadas']}) |",
        f"| Latência p50 / p95 | {ms(s['latenciaP50'])} / {ms(s['latenciaP95'])} | {ms(r['latenciaP50'])} / {ms(r['latenciaP95'])} |",
        "", "## Respostas com RAG", "",
    ]
    for l in [l for l in linhas if l["modo"] == "rag"]:
        marca = "" if l.get("erro") else ("✓" if str(l["referencia_correta"]) == "True" else "✗")
        if l.get("secao_esperada") == "nenhuma":
            marca = "✓" if not l["referencias"] else "✗"
        out += [f"**{l['id']}. {l['pergunta']}** {marca}", "",
                f"> {l.get('erro') or l['resposta']}", "",
                f"Esperado: {l['secao_esperada'] or 'não anotado'} · Citado: {l['referencias'] or 'nenhuma'}", ""]
    sem = [l for l in linhas if l["modo"] == "sem_rag" and int(l.get("referencias_inexistentes") or 0) > 0]
    out += ["## Referências inexistentes sem RAG", ""]
    out += [f"- `{l['id']}`: {l['referencias']}" for l in sem] or ["- Nenhuma."]
    out += ["", "## Interpretação", "", "_Escrever a análise do grupo._", ""]
    return "\n".join(out)


def recalcular_referencias(linhas: list[dict], indice) -> None:
    """Refaz a conferência das referências a partir do CSV, sem chamar o modelo de novo."""
    for l in linhas:
        if l.get("erro"):
            continue
        refs = [r for r in l["referencias"].split(" | ") if r]
        inexistentes, correta = _avaliar_referencias(indice, refs, [extrair_secao(r) for r in refs],
                                                     l.get("secao_esperada", ""))
        l["referencias_inexistentes"], l["referencia_correta"] = inexistentes, correta


def resumir(args) -> int:
    with open(args.execucao, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    try:  # recalcula com a versão atual da conferência, se o índice estiver disponível
        cfg = carregar_config()
        recalcular_referencias(linhas, carregar_compativel(cfg.dir_indice, criar_provedor(cfg).id_embedding))
        with open(args.execucao, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUNAS)
            w.writeheader()
            w.writerows(linhas)
    except (ErroIA, IndiceIndisponivel) as e:
        print(f"Aviso: referências não recalculadas ({e})", file=sys.stderr)
    m = calcular(linhas)
    pasta = Path(args.execucao).parent
    (pasta / "resumo_perguntas.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "relatorio_perguntas.md").write_text(relatorio(m, linhas, Path(args.execucao).name), encoding="utf-8")
    print(f"Gerados {pasta / 'resumo_perguntas.json'} e {pasta / 'relatorio_perguntas.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("rodar")
    r.add_argument("--perguntas", default="", help="padrão: perguntas.csv, ou perguntas.exemplo.csv")
    r.add_argument("--saida", default=str(DIR / "resultados"))
    r.add_argument("--intervalo", type=float, default=2.0, help="segundos entre chamadas")
    r.add_argument("--limite", type=int, default=0)
    r.set_defaults(func=rodar)
    s = sub.add_parser("resumir")
    s.add_argument("execucao")
    s.set_defaults(func=resumir)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, IndiceIndisponivel, ErroIA) as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
