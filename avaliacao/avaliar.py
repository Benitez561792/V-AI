"""Avaliação do serviço de IA em duas etapas.

1) rodar: chama a descrição em cada foto anotada e, quando há barreira, a classificação
   com e sem RAG. Grava um CSV de execução com tudo que é medido automaticamente e
   colunas vazias para a revisão manual (alucinacao, notas_revisor).

       python -m avaliacao.avaliar rodar

2) resumir: depois de preencher a coluna "alucinacao" seguindo avaliacao/rubrica.md,
   calcula as métricas e gera resultados/relatorio.md e resultados/resumo.json.

       python -m avaliacao.avaliar resumir avaliacao/resultados/execucao_AAAAMMDD_HHMM.csv

Métricas: latência p50/p95, recall e precisão de perigos, taxa de alucinação, acurácia do
tipo de barreira (descrição, classificação com RAG e sem RAG), referências normativas
inexistentes e corretas com e sem RAG, e detecção de fotos ruins.
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
from app.services.descricao import descrever
from avaliacao.metricas import fmt, percentil, recall_precisao, referencia_confere, separar, taxa

DIR = Path(__file__).parent
MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
COLUNAS = [
    "arquivo", "origem", "grupo", "modo", "erro",
    "latencia_descricao_ms", "qualidade_adequada", "problema_imagem", "imagem_ruim_esperada",
    "perigos_esperados", "perigos_retornados",
    "barreira_esperada", "barreira_detectada", "tipo_descricao", "confianca_barreira", "sugerir_relato",
    "tipo_rag", "tipo_sem_rag", "norma_rag", "norma_sem_rag", "secao_rag", "secao_sem_rag", "secao_esperada",
    "norma_rag_existe", "norma_sem_rag_existe", "latencia_rag_ms", "latencia_sem_rag_ms",
    "resumo", "perigos_texto", "texto_lido", "avisos", "justificativa_rag",
    "alucinacao", "notas_revisor",
]


# ------------------------------------------------------------------ rodar

def _chamar_com_retentativa(funcao, tentativas: int = 2, espera: float = 10.0):
    for i in range(tentativas):
        try:
            return funcao()
        except ErroIA:
            if i == tentativas - 1:
                raise
            time.sleep(espera)


def rodar(args) -> int:
    cfg = carregar_config()
    ia = criar_provedor(cfg)
    if ia.nome_modelo == "falso":
        print("Atenção: IA_PROVEDOR=falso. Os resultados não valem para a avaliação.", file=sys.stderr)
    try:
        indice = carregar_compativel(cfg.dir_indice, ia.id_embedding)
    except IndiceIndisponivel as e:
        if not args.sem_classificacao:
            print(e, file=sys.stderr)
            return 1
        indice = None

    with open(args.anotacoes, encoding="utf-8") as f:
        anotacoes = list(csv.DictReader(f))
    if args.limite:
        anotacoes = anotacoes[: args.limite]

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    arquivo_saida = saida / f"execucao_{datetime.now():%Y%m%d_%H%M}.csv"

    linhas = []
    for n, a in enumerate(anotacoes, start=1):
        caminho = Path(args.fotos) / a["arquivo"]
        linha = {c: "" for c in COLUNAS}
        linha.update({k: a.get(k, "") for k in ("arquivo", "origem", "grupo", "perigos_esperados",
                                                 "barreira_esperada", "secao_esperada", "imagem_ruim_esperada")})
        modo = a.get("modo") or "ambiente"
        linha["modo"] = modo
        print(f"[{n}/{len(anotacoes)}] {a['arquivo']}", flush=True)
        try:
            imagem = caminho.read_bytes()
            r = _chamar_com_retentativa(
                lambda: descrever(ia, cfg, imagem, MIMES.get(caminho.suffix.lower(), "image/jpeg"), modo))
            d = r.descricao
            linha.update({
                "latencia_descricao_ms": r.latenciaMs,
                "qualidade_adequada": d.qualidadeImagem.adequada,
                "problema_imagem": d.qualidadeImagem.problema.value,
                "perigos_retornados": "; ".join(sorted({p.categoria.value for p in d.perigos})),
                "barreira_detectada": d.barreira.detectada,
                "tipo_descricao": d.barreira.tipo.value if d.barreira.tipo else "",
                "confianca_barreira": d.barreira.confianca,
                "sugerir_relato": r.sugerirRelato,
                "resumo": d.resumo,
                "perigos_texto": " | ".join(f"{p.urgencia.value}: {p.descricao}" for p in d.perigos),
                "texto_lido": d.textoLido or "",
                "avisos": " | ".join(d.avisos),
            })

            classificar_esta = indice is not None and not args.sem_classificacao and (
                a.get("barreira_esperada") or d.barreira.detectada)
            if classificar_esta:
                texto = d.barreira.descricao or d.resumo
                tipo_sugerido = d.barreira.tipo if args.com_tipo_sugerido else None
                objetos = d.objetos
                for modo_c in ("rag", "sem_rag"):
                    time.sleep(args.intervalo)
                    req = ClassificarRequest(texto=texto, tipoSugerido=tipo_sugerido, objetos=objetos, modo=modo_c)
                    c = _chamar_com_retentativa(lambda: classificar(ia, indice, cfg, req))
                    linha[f"tipo_{modo_c}"] = c.tipo.value
                    linha[f"norma_{modo_c}"] = c.normaReferencia or ""
                    linha[f"secao_{modo_c}"] = c.secao or ""
                    linha[f"norma_{modo_c}_existe"] = ("" if c.secao is None
                                                       else indice.referencia_existe(c.normaReferencia, c.secao))
                    linha[f"latencia_{modo_c}_ms"] = c.latenciaMs
                    if modo_c == "rag":
                        linha["justificativa_rag"] = c.justificativa
        except Exception as e:  # registra e segue: a falha também é resultado
            linha["erro"] = f"{type(e).__name__}: {e}"
            print(f"   erro: {linha['erro']}", file=sys.stderr)
        linhas.append(linha)
        time.sleep(args.intervalo)

    with arquivo_saida.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    print(f"\nExecução salva em {arquivo_saida}")
    print("Próximo passo: preencha a coluna 'alucinacao' (0, 1 ou 2) seguindo avaliacao/rubrica.md e rode:")
    print(f"  python -m avaliacao.avaliar resumir {arquivo_saida}")
    return 0


# ------------------------------------------------------------------ resumir

def _bool(v) -> bool | None:
    s = str(v).strip().lower()
    if s in ("true", "sim", "1", "s"):
        return True
    if s in ("false", "nao", "não", "0", "n"):
        return False
    return None


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def calcular(linhas: list[dict]) -> dict:
    ok = [l for l in linhas if not l.get("erro")]
    perigos = recall_precisao([separar(l["perigos_esperados"]) for l in ok],
                              [separar(l["perigos_retornados"]) for l in ok])

    anotadas = [int(l["alucinacao"]) for l in ok if str(l.get("alucinacao", "")).strip() in ("0", "1", "2")]

    com_barreira = [l for l in ok if l.get("barreira_esperada")]
    sem_barreira = [l for l in ok if not l.get("barreira_esperada")]

    def acuracia(coluna: str) -> float | None:
        avaliadas = [l for l in com_barreira if l.get(coluna)]
        return taxa([l[coluna] == l["barreira_esperada"] for l in avaliadas])

    def refs(modo: str) -> dict:
        com_ref = [l for l in com_barreira if l.get(f"norma_{modo}")]
        existe = [_bool(l[f"norma_{modo}_existe"]) for l in com_ref if _bool(l[f"norma_{modo}_existe"]) is not None]
        com_esperada = [l for l in com_barreira if l.get("secao_esperada") and l.get(f"tipo_{modo}")]
        return {
            "classificadas": len([l for l in com_barreira if l.get(f"tipo_{modo}")]),
            "comReferencia": len(com_ref),
            "taxaReferenciaInexistente": taxa([not e for e in existe]),
            "acertoSecao": taxa([referencia_confere(l.get(f"norma_{modo}"), l.get(f"secao_{modo}"), l["secao_esperada"]) for l in com_esperada]),
            "latenciaP50": percentil([_num(l[f"latencia_{modo}_ms"]) for l in ok if _num(l[f"latencia_{modo}_ms"])], 50),
            "latenciaP95": percentil([_num(l[f"latencia_{modo}_ms"]) for l in ok if _num(l[f"latencia_{modo}_ms"])], 95),
        }

    ruins = [l for l in ok if _bool(l.get("imagem_ruim_esperada"))]
    boas = [l for l in ok if _bool(l.get("imagem_ruim_esperada")) is False]
    lat = [_num(l["latencia_descricao_ms"]) for l in ok if _num(l["latencia_descricao_ms"])]

    por_grupo = {}
    for g in sorted({l["grupo"] for l in ok}):
        gl = [l for l in ok if l["grupo"] == g]
        rp = recall_precisao([separar(l["perigos_esperados"]) for l in gl], [separar(l["perigos_retornados"]) for l in gl])
        al = [int(l["alucinacao"]) for l in gl if str(l.get("alucinacao", "")).strip() in ("0", "1", "2")]
        por_grupo[g] = {"fotos": len(gl), "recallPerigos": rp["recall"], "precisaoPerigos": rp["precisao"],
                        "taxaAlucinacao": taxa([a >= 1 for a in al]),
                        "latenciaP50": percentil([_num(l["latencia_descricao_ms"]) for l in gl], 50)}

    return {
        "fotos": len(linhas),
        "fotosComErro": len(linhas) - len(ok),
        "descricao": {
            "latenciaP50": percentil(lat, 50),
            "latenciaP95": percentil(lat, 95),
            "recallPerigos": perigos["recall"],
            "precisaoPerigos": perigos["precisao"],
            "perigosEsperados": perigos["esperados"],
            "fotosAnotadasAlucinacao": len(anotadas),
            "taxaAlucinacao": taxa([a >= 1 for a in anotadas]),
            "taxaAlucinacaoGrave": taxa([a == 2 for a in anotadas]),
            "deteccaoFotoRuim": taxa([_bool(l["qualidade_adequada"]) is False for l in ruins]),
            "falsoAlarmeFotoRuim": taxa([_bool(l["qualidade_adequada"]) is False for l in boas]),
            "barreiraDetectadaQuandoExiste": taxa([_bool(l["barreira_detectada"]) is True for l in com_barreira]),
            "barreiraFalsaQuandoNaoExiste": taxa([_bool(l["barreira_detectada"]) is True for l in sem_barreira]),
        },
        "tipoBarreira": {
            "fotosComBarreira": len(com_barreira),
            "acuraciaDescricao": acuracia("tipo_descricao"),
            "acuraciaComRag": acuracia("tipo_rag"),
            "acuraciaSemRag": acuracia("tipo_sem_rag"),
        },
        "referencias": {"rag": refs("rag"), "semRag": refs("sem_rag")},
        "porGrupo": por_grupo,
    }


def relatorio_md(m: dict, linhas: list[dict], origem: str) -> str:
    d, t, r = m["descricao"], m["tipoBarreira"], m["referencias"]
    p = lambda v: fmt(v, pct=True)  # noqa: E731
    ms = lambda v: fmt(v) + " ms" if v is not None else "n/d"  # noqa: E731
    out = [
        "# Relatório de avaliação · Vê AI (serviço de IA)",
        "",
        f"Execução: `{origem}` · Gerado em {datetime.now():%d/%m/%Y %H:%M}",
        f"Fotos: {m['fotos']} ({m['fotosComErro']} com erro de execução)",
        "",
        "## Descrição",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Latência p50 / p95 | {ms(d['latenciaP50'])} / {ms(d['latenciaP95'])} |",
        f"| Recall de perigos | {p(d['recallPerigos'])} ({d['perigosEsperados']} perigos anotados) |",
        f"| Precisão de perigos | {p(d['precisaoPerigos'])} |",
        f"| Taxa de alucinação (nível ≥ 1) | {p(d['taxaAlucinacao'])} ({d['fotosAnotadasAlucinacao']} fotos revisadas) |",
        f"| Taxa de alucinação grave (nível 2) | {p(d['taxaAlucinacaoGrave'])} |",
        f"| Foto ruim detectada | {p(d['deteccaoFotoRuim'])} |",
        f"| Foto boa marcada como ruim | {p(d['falsoAlarmeFotoRuim'])} |",
        f"| Barreira detectada quando existe | {p(d['barreiraDetectadaQuandoExiste'])} |",
        f"| Barreira apontada quando não existe | {p(d['barreiraFalsaQuandoNaoExiste'])} |",
        "",
        "## Tipo de barreira e referência normativa: com e sem RAG",
        "",
        f"Fotos com barreira anotada: {t['fotosComBarreira']}",
        "",
        "| Métrica | Só descrição | Classificação sem RAG | Classificação com RAG |",
        "|---|---|---|---|",
        f"| Acurácia do tipo | {p(t['acuraciaDescricao'])} | {p(t['acuraciaSemRag'])} | {p(t['acuraciaComRag'])} |",
        f"| Relatos com referência | n/a | {r['semRag']['comReferencia']} | {r['rag']['comReferencia']} |",
        f"| Referência inexistente na base | n/a | {p(r['semRag']['taxaReferenciaInexistente'])} | {p(r['rag']['taxaReferenciaInexistente'])} |",
        f"| Seção correta (vs. anotação) | n/a | {p(r['semRag']['acertoSecao'])} | {p(r['rag']['acertoSecao'])} |",
        f"| Latência p50 / p95 | n/a | {ms(r['semRag']['latenciaP50'])} / {ms(r['semRag']['latenciaP95'])} | {ms(r['rag']['latenciaP50'])} / {ms(r['rag']['latenciaP95'])} |",
        "",
        "## Por grupo",
        "",
        "| Grupo | Fotos | Recall perigos | Precisão perigos | Alucinação | Latência p50 |",
        "|---|---|---|---|---|---|",
    ]
    for g, v in m["porGrupo"].items():
        out.append(f"| {g} | {v['fotos']} | {p(v['recallPerigos'])} | {p(v['precisaoPerigos'])} | "
                   f"{p(v['taxaAlucinacao'])} | {ms(v['latenciaP50'])} |")

    erros_tipo = [l for l in linhas if l.get("barreira_esperada") and l.get("tipo_rag")
                  and l["tipo_rag"] != l["barreira_esperada"]]
    perigos_perdidos = [l for l in linhas if separar(l.get("perigos_esperados")) - separar(l.get("perigos_retornados"))]
    out += ["", "## Casos para interpretar", "", "### Perigos não detectados", ""]
    out += [f"- `{l['arquivo']}` ({l['grupo']}): faltou "
            f"{', '.join(sorted(separar(l['perigos_esperados']) - separar(l['perigos_retornados'])))}"
            for l in perigos_perdidos] or ["- Nenhum."]
    out += ["", "### Tipo de barreira errado (com RAG)", ""]
    out += [f"- `{l['arquivo']}`: esperado {l['barreira_esperada']}, retornado {l['tipo_rag']}"
            for l in erros_tipo] or ["- Nenhum."]
    falhas = [l for l in linhas if l.get("erro")]
    if falhas:
        out += ["", "### Erros de execução", ""] + [f"- `{l['arquivo']}`: {l['erro']}" for l in falhas]
    out += ["", "## Interpretação", "",
            "_Escreva aqui a análise do grupo: o que os números mostram, onde o sistema falha, "
            "por que, e o que isso muda no produto (ver README, seção Avaliação)._", ""]
    return "\n".join(out)


def resumir(args) -> int:
    with open(args.execucao, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    metricas = calcular(linhas)
    saida = Path(args.execucao).parent
    (saida / "resumo.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    (saida / "relatorio.md").write_text(relatorio_md(metricas, linhas, Path(args.execucao).name), encoding="utf-8")
    print(f"Gerados {saida / 'resumo.json'} e {saida / 'relatorio.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    r = sub.add_parser("rodar", help="executa o modelo nas fotos anotadas")
    r.add_argument("--anotacoes", default=str(DIR / "anotacoes.csv"))
    r.add_argument("--fotos", default=str(DIR / "fotos"))
    r.add_argument("--saida", default=str(DIR / "resultados"))
    r.add_argument("--intervalo", type=float, default=4.0, help="segundos entre chamadas (cota gratuita)")
    r.add_argument("--limite", type=int, default=0, help="avaliar só as N primeiras fotos")
    r.add_argument("--sem-classificacao", action="store_true", help="avaliar só a descrição")
    r.add_argument("--com-tipo-sugerido", action="store_true",
                   help="enviar o tipo da descrição ao classificador (como no app); por padrão não envia, "
                        "para medir o classificador isoladamente")
    r.set_defaults(func=rodar)

    s = sub.add_parser("resumir", help="calcula as métricas a partir do CSV revisado")
    s.add_argument("execucao")
    s.set_defaults(func=resumir)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
