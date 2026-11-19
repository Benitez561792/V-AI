"""Mede a latência do POST /classificar contra o timeout da API Java (3 s).

Usa o mesmo JSON que o RagClassificador envia e só a biblioteca padrão, então roda contra
o serviço local ou publicado:

    python -m avaliacao.latencia --url http://localhost:8000 --n 20
    python -m avaliacao.latencia --url https://<seu-servico>.azurecontainerapps.io --n 20

A primeira chamada é reportada à parte, porque inclui partida a frio do servidor.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from avaliacao.metricas import percentil

RELATOS = Path(__file__).parent / "relatos.exemplo.csv"


def chamar(url: str, corpo: dict, timeout: float) -> tuple[float, str]:
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(f"{url.rstrip('/')}/classificar", data=dados,
                                    headers={"Content-Type": "application/json"}, method="POST")
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resp:
            resp.read()
            status = str(resp.status)
    except urllib.error.HTTPError as e:
        status = str(e.code)
    except (urllib.error.URLError, TimeoutError) as e:
        status = f"falha: {getattr(e, 'reason', e)}"
    return (time.perf_counter() - inicio) * 1000, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--timeout-java", type=float, default=3.0, help="segundos (veai.rag.timeout)")
    parser.add_argument("--intervalo", type=float, default=2.0)
    args = parser.parse_args(argv)

    with RELATOS.open(encoding="utf-8") as f:
        relatos = [r for r in csv.DictReader(f)]

    tempos, falhas = [], 0
    for i in range(args.n + 1):
        r = relatos[i % len(relatos)]
        corpo = {"texto": r["texto"], "tipoSugerido": r["tipo_relato"], "gravidadeSugerida": r["gravidade_esperada"]}
        ms, status = chamar(args.url, corpo, timeout=30)
        rotulo = "aquecimento" if i == 0 else f"{i}/{args.n}"
        print(f"[{rotulo}] {ms:7.0f} ms  status {status}")
        if i > 0:
            if status == "200":
                tempos.append(ms)
            else:
                falhas += 1
        time.sleep(args.intervalo)

    limite = args.timeout_java * 1000
    acima = sum(t > limite for t in tempos)
    print("\nResumo (sem a chamada de aquecimento)")
    print(f"  sucesso: {len(tempos)}  falhas: {falhas}")
    if tempos:
        print(f"  p50: {percentil(tempos, 50):.0f} ms   p95: {percentil(tempos, 95):.0f} ms   máx: {max(tempos):.0f} ms")
        print(f"  acima de {args.timeout_java:g} s (timeout da API Java): {acima} de {len(tempos)}")
        if acima:
            print("  -> Nessas chamadas o relato ficaria sem norma. Considerem subir veai.rag.timeout na API Java;"
                  " a chamada é assíncrona e não atrasa o app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
