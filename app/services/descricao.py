"""Descrição da imagem: chamada ao modelo + regras de segurança aplicadas em código.

As regras estão no prompt, mas o modelo pode descumprir. Por isso também são garantidas
aqui, de forma determinística. A API Java deve reproduzir `aplicar_regras_de_seguranca` e
`montar_fala` se chamar o modelo diretamente.

A imagem existe só em memória durante a chamada. Nada é gravado em disco nem em log.
"""
from __future__ import annotations

import re
import time

from app.config import Config
from app.provedores import ModeloIA
from app.prompts import renderizar
from app.schemas import Descricao, DescreverResponse, Posicao, ProblemaImagem, Urgencia

AVISO_SEM_PERIGOS = "Não identifiquei perigos nesta foto. Isso não garante que o caminho esteja livre."
AVISOS_QUALIDADE = {
    ProblemaImagem.escura: "A foto está escura. A descrição pode estar incompleta. Tente de novo com mais luz.",
    ProblemaImagem.tremida: "A foto ficou tremida. A descrição pode estar incompleta. Tente segurar o celular parado.",
    ProblemaImagem.obstruida: "Algo está cobrindo a câmera. Verifique a lente e tente de novo.",
    ProblemaImagem.sem_conteudo_util: "Não consegui entender a foto. Tente apontar a câmera para frente.",
}
_FRASES_PROIBIDAS = re.compile(
    r"(o\s+)?caminho\s+(est[aá]\s+)?(livre|seguro|desobstru[ií]do)|"
    r"(est[aá]\s+)?livre\s+de\s+obst[aá]culos|sem\s+(nenhum\s+)?obst[aá]culos?",
    re.IGNORECASE,
)
_ORDEM_URGENCIA = {Urgencia.imediata: 0, Urgencia.atencao: 1, Urgencia.informativa: 2}
_POSICAO_FALA = {
    Posicao.frente: "à frente",
    Posicao.esquerda: "à esquerda",
    Posicao.direita: "à direita",
    Posicao.indefinida: "",
}


def aplicar_regras_de_seguranca(d: Descricao) -> Descricao:
    d = d.model_copy(deep=True)

    # Perigos mais urgentes primeiro.
    d.perigos.sort(key=lambda p: _ORDEM_URGENCIA[p.urgencia])

    # Nunca afirmar "caminho livre".
    d.resumo = _FRASES_PROIBIDAS.sub("nenhum obstáculo identificado nesta foto", d.resumo).strip()
    if not d.perigos and AVISO_SEM_PERIGOS not in d.avisos:
        d.avisos.append(AVISO_SEM_PERIGOS)

    # Qualidade da imagem: coerência entre o booleano e o problema, e aviso garantido.
    q = d.qualidadeImagem
    if q.problema != ProblemaImagem.nenhum:
        q.adequada = False
    if not q.adequada:
        aviso = AVISOS_QUALIDADE.get(q.problema, AVISOS_QUALIDADE[ProblemaImagem.sem_conteudo_util])
        if aviso not in d.avisos:
            d.avisos.insert(0, aviso)

    # Barreira: confiança dentro de [0, 1] e campos coerentes.
    b = d.barreira
    b.confianca = min(max(float(b.confianca), 0.0), 1.0)
    if not b.detectada:
        b.tipo, b.descricao, b.confianca = None, None, 0.0
    elif b.tipo is None:
        b.detectada, b.descricao, b.confianca = False, None, 0.0

    return d


def _frase(texto: str) -> str:
    texto = texto.strip()
    return texto if not texto or texto[-1] in ".!?" else texto + "."


def montar_fala(d: Descricao) -> tuple[str, str]:
    """Retorna (fala só com perigos, fala completa). Perigos sempre primeiro."""
    perigos = []
    for p in d.perigos:
        posicao = _POSICAO_FALA[p.posicao]
        perigos.append(f"{p.descricao.rstrip('.')}{', ' + posicao if posicao else ''}")
    fala_perigos = ("Atenção: " + "; ".join(perigos) + ".") if perigos else ""

    partes, ja_falados = [], set()
    if not d.qualidadeImagem.adequada and d.avisos:
        partes.append(_frase(d.avisos[0]))  # aviso de qualidade vem antes de tudo
        ja_falados.add(d.avisos[0])
    if fala_perigos:
        partes.append(fala_perigos)
    partes.append(_frase(d.resumo))
    if d.textoLido:
        partes.append(f"Texto: {_frase(d.textoLido)}")
    partes.extend(_frase(a) for a in d.avisos if a not in ja_falados)
    return fala_perigos, " ".join(p for p in partes if p)


def descrever(ia: ModeloIA, cfg: Config, imagem: bytes, mime: str, modo: str) -> DescreverResponse:
    inicio = time.perf_counter()
    bruta = ia.gerar_json(
        sistema=renderizar("descricao"),
        texto=f"Modo: {modo}. Descreva a imagem seguindo as regras.",
        schema=Descricao,
        imagem=imagem,
        mime=mime,
    )
    d = aplicar_regras_de_seguranca(bruta)
    fala_perigos, fala_completa = montar_fala(d)
    sugerir = (
        d.barreira.detectada
        and d.barreira.confianca >= cfg.limiar_sugerir_relato
        and d.qualidadeImagem.adequada
    )
    return DescreverResponse(
        descricao=d,
        falaPerigos=fala_perigos,
        falaCompleta=fala_completa,
        sugerirRelato=sugerir,
        modelo=ia.nome_modelo,
        latenciaMs=round((time.perf_counter() - inicio) * 1000),
    )
