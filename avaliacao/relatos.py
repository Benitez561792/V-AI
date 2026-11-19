"""Avaliação do RAG com relatos em texto (critério 03), sem depender de fotos.

Cada relato é classificado duas vezes, com e sem RAG, com o mesmo texto. Assim a diferença
entre as duas colunas mede só a contribuição do RAG.

    cp avaliacao/relatos.exemplo.csv avaliacao/relatos.csv   # revisem e preencham secao_esperada
    python -m avaliacao.relatos rodar
    # opcional: preencham "justificativa_fiel" (sim/nao) nas linhas modo=rag
    python -m avaliacao.relatos resumir avaliacao/resultados/relatos_AAAAMMDD_HHMM.csv

Colunas do CSV de entrada:
- tipo_relato: tipo que o cidadão escolheu no app (é o que a API Java envia como tipoSugerido)
- tipo_esperado, gravidade_esperada: anotação do grupo
- secao_esperada: seções aceitas, com o número da norma, separadas por ";" (ex.: "9050 6.12.3; 16537 6.8");
  "nenhuma" quando nenhuma norma se aplica; vazio quando ainda não foi conferida (fica fora da métrica)
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
from app.rag.indice import IndiceIndisponivel, carregar_compativel
from app.schemas import ClassificarRequest
from app.services.classificacao import classificar
from avaliacao.metricas import fmt, percentil, referencia_confere, taxa

DIR = Path(__file__).parent
TIMEOUT_JAVA_MS = 3000
COLUNAS = [
    "id", "modo", "texto", "tipo_relato", "tipo_esperado", "gravidade_esperada", "secao_esperada",
    "erro", "tipo", "gravidade", "normaReferencia", "secao", "secao_existe", "semNormaAplicavel",
    "similaridade_max", "latencia_ms", "justificativa", "trecho", "justificativa_fiel", "notas_revisor",
]


def rodar(args) -> int:
    cfg = carregar_config()
    ia = criar_provedor(cfg)
    if ia.nome_modelo == "falso":
        print("Atenção: IA_PROVEDOR=falso. Os resultados não valem para a avaliação.", file=sys.stderr)
    indice = carregar_compativel(cfg.dir_indice, ia.id_embedding)

    if not args.relatos:
        proprio = DIR / "relatos.csv"
        args.relatos = str(proprio if proprio.exists() else DIR / "relatos.exemplo.csv")
    print(f"Relatos: {args.relatos}")
    with open(args.relatos, encoding="utf-8") as f:
        relatos = list(csv.DictReader(f))
    if args.limite:
        relatos = relatos[: args.limite]

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    arquivo = saida / f"relatos_{datetime.now():%Y%m%d_%H%M}.csv"
    linhas = []
    for n, r in enumerate(relatos, start=1):
        print(f"[{n}/{len(relatos)}] {r['id']}", flush=True)
        for modo in ("rag", "sem_rag"):
            linha = {c: "" for c in COLUNAS}
            linha.update({k: r.get(k, "") for k in ("id", "texto", "tipo_relato", "tipo_esperado",
                                                     "gravidade_esperada", "secao_esperada")})
            linha["modo"] = modo
            req = ClassificarRequest(
                texto=r["texto"],
                tipoSugerido=(r.get("tipo_relato") or None) if not args.sem_tipo_sugerido else None,
                modo=modo,
            )
            for tentativa in range(2):
                try:
                    c = classificar(ia, indice, cfg, req)
                    linha.update({
                        "tipo": c.tipo.value, "gravidade": c.gravidade.value,
                        "normaReferencia": c.normaReferencia or "", "secao": c.secao or "",
                        "secao_existe": "" if not c.secao else indice.referencia_existe(c.normaReferencia, c.secao),
                        "semNormaAplicavel": c.semNormaAplicavel,
                        "similaridade_max": max((x.similaridade for x in c.referenciasConsultadas), default=""),
                        "latencia_ms": c.latenciaMs, "justificativa": c.justificativa, "trecho": c.trecho or "",
                    })
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
    print("Se preencherem a coluna justificativa_fiel no CSV, gerem o relatório de novo com:\n"
          f"  python -m avaliacao.relatos resumir {arquivo}")
    return 0


def _sim(v) -> bool | None:
    s = str(v).strip().lower()
    return True if s in ("sim", "s", "true", "1") else False if s in ("nao", "não", "n", "false", "0") else None


def calcular(linhas: list[dict]) -> dict:
    resultado = {}
    for modo in ("rag", "sem_rag"):
        ls = [l for l in linhas if l["modo"] == modo and not l.get("erro")]
        com_secao = [l for l in ls if l.get("secao_esperada") and l["secao_esperada"] != "nenhuma"]
        sem_norma_esperada = [l for l in ls if l.get("secao_esperada") == "nenhuma"]
        com_ref = [l for l in ls if l.get("secao")]
        existe = [_sim(l["secao_existe"]) for l in com_ref if _sim(l["secao_existe"]) is not None]
        latencias = [float(l["latencia_ms"]) for l in ls if l.get("latencia_ms")]
        fiel = [_sim(l.get("justificativa_fiel")) for l in ls if _sim(l.get("justificativa_fiel")) is not None]
        resultado[modo] = {
            "relatos": len(ls),
            "erros": len([l for l in linhas if l["modo"] == modo and l.get("erro")]),
            "acuraciaTipo": taxa([l["tipo"] == l["tipo_esperado"] for l in ls if l.get("tipo_esperado")]),
            "acuraciaGravidade": taxa([l["gravidade"] == l["gravidade_esperada"]
                                       for l in ls if l.get("gravidade_esperada")]),
            "comReferencia": taxa([bool(l.get("secao")) for l in ls]),
            "referenciaInexistente": taxa([not e for e in existe]),
            "secaoCorreta": taxa([referencia_confere(l.get("normaReferencia"), l.get("secao"), l["secao_esperada"])
                                  for l in com_secao]),
            "relatosComSecaoAnotada": len(com_secao),
            "semNormaQuandoNaoSeAplica": taxa([not l.get("secao") for l in sem_norma_esperada]),
            "justificativaFiel": taxa(fiel),
            "justificativasRevisadas": len(fiel),
            "latenciaP50": percentil(latencias, 50),
            "latenciaP95": percentil(latencias, 95),
            "acimaTimeoutJava": taxa([x > TIMEOUT_JAVA_MS for x in latencias]),
        }
    return resultado


def relatorio(m: dict, linhas: list[dict], origem: str) -> str:
    p = lambda v: fmt(v, pct=True)  # noqa: E731
    ms = lambda v: "n/d" if v is None else f"{v:.0f} ms"  # noqa: E731
    r, s = m["rag"], m["sem_rag"]
    out = [
        "# Relatório · RAG com relatos em texto", "",
        f"Execução: `{origem}` · Gerado em {datetime.now():%d/%m/%Y %H:%M}", "",
        "| Métrica | Sem RAG | Com RAG |", "|---|---|---|",
        f"| Relatos classificados | {s['relatos']} | {r['relatos']} |",
        f"| Acurácia do tipo | {p(s['acuraciaTipo'])} | {p(r['acuraciaTipo'])} |",
        f"| Acurácia da gravidade | {p(s['acuraciaGravidade'])} | {p(r['acuraciaGravidade'])} |",
        f"| Relatos com referência normativa | {p(s['comReferencia'])} | {p(r['comReferencia'])} |",
        f"| Referência inexistente na base | {p(s['referenciaInexistente'])} | {p(r['referenciaInexistente'])} |",
        f"| Seção correta ({r['relatosComSecaoAnotada']} relatos anotados) | {p(s['secaoCorreta'])} | {p(r['secaoCorreta'])} |",
        f"| Sem norma quando nenhuma se aplica | {p(s['semNormaQuandoNaoSeAplica'])} | {p(r['semNormaQuandoNaoSeAplica'])} |",
        f"| Justificativa fiel ao trecho | n/a | {p(r['justificativaFiel'])} ({r['justificativasRevisadas']} revisadas) |",
        f"| Latência p50 / p95 | {ms(s['latenciaP50'])} / {ms(s['latenciaP95'])} | {ms(r['latenciaP50'])} / {ms(r['latenciaP95'])} |",
        f"| Acima do timeout da API Java (3 s) | {p(s['acimaTimeoutJava'])} | {p(r['acimaTimeoutJava'])} |",
        "", "## Divergências com RAG", "",
    ]
    rag = [l for l in linhas if l["modo"] == "rag" and not l.get("erro")]
    div = [l for l in rag if l.get("tipo_esperado") and l["tipo"] != l["tipo_esperado"]]
    out += [f"- `{l['id']}` tipo: esperado {l['tipo_esperado']}, retornado {l['tipo']} · {l['texto']}"
            for l in div] or ["- Nenhuma divergência de tipo."]
    errado = [l for l in rag if l.get("secao_esperada") and l["secao_esperada"] != "nenhuma"
              and not referencia_confere(l.get("normaReferencia"), l.get("secao"), l["secao_esperada"])]
    out += [f"- `{l['id']}` referência: esperada {l['secao_esperada']}, retornada {l.get('normaReferencia') or 'nenhuma'}"
            for l in errado]
    indevida = [l for l in rag if l.get("secao_esperada") == "nenhuma" and l.get("secao")]
    out += [f"- `{l['id']}` citou {l['secao']} num relato fora do escopo" for l in indevida]
    out += ["", "## Interpretação", "", "_Escrever a análise do grupo._", ""]
    return "\n".join(out)


def resumir(args) -> int:
    with open(args.execucao, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    m = calcular(linhas)
    pasta = Path(args.execucao).parent
    (pasta / "resumo_relatos.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "relatorio_relatos.md").write_text(relatorio(m, linhas, Path(args.execucao).name), encoding="utf-8")
    print(f"Gerados {pasta / 'resumo_relatos.json'} e {pasta / 'relatorio_relatos.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("rodar")
    r.add_argument("--relatos", default="", help="padrão: relatos.csv, ou relatos.exemplo.csv se não existir")
    r.add_argument("--saida", default=str(DIR / "resultados"))
    r.add_argument("--intervalo", type=float, default=4.0, help="segundos entre chamadas (cota gratuita)")
    r.add_argument("--limite", type=int, default=0)
    r.add_argument("--sem-tipo-sugerido", action="store_true",
                   help="não enviar o tipo escolhido pelo cidadão (mede o classificador isolado)")
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
