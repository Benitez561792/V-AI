"""Schemas da API e das saídas estruturadas do modelo.

Os modelos usados como saída estruturada (Descricao, RespostaClassificacaoRag,
RespostaClassificacaoSemRag) seguem as regras do modo estrito da OpenAI: todos os campos
obrigatórios (os opcionais são "X | None"), sem valores padrão e sem restrições numéricas.
Valores fora da faixa são corrigidos no pós-processamento (app/services/descricao.py).
O teste test_schemas_aceitos_no_modo_estrito garante isso.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.taxonomia import CategoriaPerigo, Gravidade, TipoBarreira


# ---------- Descrição (saída estruturada do modelo) ----------

class Posicao(str, Enum):
    frente = "frente"
    esquerda = "esquerda"
    direita = "direita"
    indefinida = "indefinida"


class Urgencia(str, Enum):
    imediata = "imediata"
    atencao = "atencao"
    informativa = "informativa"


class ProblemaImagem(str, Enum):
    nenhum = "nenhum"
    escura = "escura"
    tremida = "tremida"
    obstruida = "obstruida"
    sem_conteudo_util = "sem_conteudo_util"


class Perigo(BaseModel):
    categoria: CategoriaPerigo
    descricao: str
    posicao: Posicao
    urgencia: Urgencia


class Barreira(BaseModel):
    detectada: bool
    tipo: TipoBarreira | None
    descricao: str | None
    confianca: float


class QualidadeImagem(BaseModel):
    adequada: bool
    problema: ProblemaImagem


class Descricao(BaseModel):
    qualidadeImagem: QualidadeImagem
    perigos: list[Perigo]
    resumo: str
    objetos: list[str]
    textoLido: str | None
    barreira: Barreira
    avisos: list[str]


class DescreverResponse(BaseModel):
    descricao: Descricao
    falaPerigos: str = Field(description="Só os perigos, para o modo trajeto.")
    falaCompleta: str = Field(description="Perigos primeiro, depois cena, texto e avisos.")
    sugerirRelato: bool = Field(description="True quando o app deve perguntar se a pessoa quer avisar a rede de apoio.")
    modelo: str
    latenciaMs: int


# ---------- Classificação do relato ----------

class RespostaClassificacaoRag(BaseModel):
    tipo: TipoBarreira
    gravidade: Gravidade
    trechoEscolhido: int | None
    justificativa: str


class RespostaClassificacaoSemRag(BaseModel):
    tipo: TipoBarreira
    gravidade: Gravidade
    normaReferencia: str | None
    justificativa: str


class ClassificarRequest(BaseModel):
    """Os três primeiros campos são os que o RagClassificador da API Java envia."""
    texto: str = Field(min_length=3, max_length=2000, description="Texto do relato (Relato.texto na API Java).")
    tipoSugerido: TipoBarreira | None = Field(default=None, description="Tipo escolhido no relato (TipoRelato).")
    gravidadeSugerida: Gravidade | None = Field(default=None, description="Gravidade escolhida no relato.")
    objetos: list[str] = Field(default_factory=list, max_length=30)
    modo: Literal["rag", "sem_rag"] = "rag"
    relatoId: str | None = Field(default=None, max_length=100, description="Ecoado na resposta, para a API de domínio.")


class ReferenciaConsultada(BaseModel):
    fonte: str
    secao: str | None
    titulo: str | None
    similaridade: float


class ClassificarResponse(BaseModel):
    """tipo, gravidade, normaReferencia, trecho e justificativa são os campos lidos pela API Java;
    os demais são extras (o Jackson do Spring Boot ignora campos desconhecidos)."""
    relatoId: str | None
    tipo: TipoBarreira
    gravidade: Gravidade
    normaReferencia: str | None = Field(description="Até 200 caracteres (coluna RELATO.norma_referencia).")
    fonte: str | None
    secao: str | None
    trecho: str | None
    justificativa: str
    semNormaAplicavel: bool
    modo: Literal["rag", "sem_rag"]
    referenciasConsultadas: list[ReferenciaConsultada]
    modelo: str
    latenciaMs: int


# ---------- Consulta (perguntas sobre acessibilidade) ----------

class RespostaConsultaRag(BaseModel):
    resposta: str
    trechosUsados: list[int]
    respondidaPelaBase: bool


class RespostaConsultaSemRag(BaseModel):
    resposta: str
    referencias: list[str]


class ConsultarRequest(BaseModel):
    pergunta: str = Field(min_length=3, max_length=2000, description="Pergunta sobre acessibilidade.")
    modo: Literal["rag", "sem_rag"] = "rag"


class FonteConsulta(BaseModel):
    referencia: str = Field(description="Norma ou lei e seção, ex.: ABNT NBR 9050:2020 6.12.3")
    fonte: str
    secao: str | None
    trecho: str
    similaridade: float


class ConsultarResponse(BaseModel):
    pergunta: str
    resposta: str = Field(description="Resposta com as citações já trocadas pela referência real.")
    fontes: list[FonteConsulta] = Field(description="Trechos que fundamentam a resposta (só com RAG).")
    referenciasCitadas: list[str]
    respondidaPelaBase: bool
    modo: Literal["rag", "sem_rag"]
    referenciasConsultadas: list[ReferenciaConsultada]
    modelo: str
    latenciaMs: int
