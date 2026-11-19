"""Provedores de IA: OpenAI (ChatGPT) ou falso.

O resto do código depende só do protocolo `ModeloIA`. O provedor é escolhido por
IA_PROVEDOR no .env, como o VEAI_IA_PROVEDOR da API Java:

- openai: modelo da OpenAI com saída estruturada (Responses API) e embeddings da OpenAI.
- falso:  respostas fixas e embeddings por hashing de palavras, sem chave e sem custo.
          Serve para testar ingestão, integração com a API Java e a demonstração antes
          de ter a chave. Os resultados NÃO valem para a avaliação.
"""
from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from typing import Protocol, TypeVar

import numpy as np
from pydantic import BaseModel

from app.config import Config

T = TypeVar("T", bound=BaseModel)


class ErroIA(RuntimeError):
    """Falha ao chamar o modelo, configuração ausente ou resposta fora do schema."""


class ModeloIA(Protocol):
    nome_modelo: str
    id_embedding: str  # gravado no índice: trocar de modelo de embedding exige reindexar

    def gerar_json(self, sistema: str, texto: str, schema: type[T],
                   imagem: bytes | None = None, mime: str | None = None) -> T: ...

    def embeddings(self, textos: list[str], tarefa: str) -> np.ndarray: ...


# --------------------------------------------------------------------------- OpenAI

class ClienteOpenAI:
    def __init__(self, cfg: Config, cliente=None):
        if cliente is None:
            if not cfg.openai_api_key:
                raise ErroIA("OPENAI_API_KEY não configurada. Copie .env.example para .env "
                             "ou use IA_PROVEDOR=falso.")
            from openai import OpenAI

            cliente = OpenAI(api_key=cfg.openai_api_key, timeout=cfg.timeout_s, max_retries=1)
        self._cliente = cliente
        self._cfg = cfg
        self.nome_modelo = cfg.modelo_geracao
        dimensao = cfg.dimensao_embedding or "nativa"
        self.id_embedding = f"openai:{cfg.modelo_embedding}:{dimensao}"

    def gerar_json(self, sistema, texto, schema, imagem=None, mime=None):
        conteudo: list[dict] = [{"type": "input_text", "text": texto}]
        if imagem is not None:
            b64 = base64.b64encode(imagem).decode("ascii")
            conteudo.append({"type": "input_image", "detail": "auto",
                             "image_url": f"data:{mime or 'image/jpeg'};base64,{b64}"})

        opcionais: dict = {}
        if self._cfg.temperatura is not None:  # modelos gpt-5+/gpt-6 só aceitam o padrão
            opcionais["temperature"] = self._cfg.temperatura
        if self._cfg.reasoning_effort:  # modelos sem raciocínio (gpt-4o/gpt-4.1) não aceitam
            opcionais["reasoning"] = {"effort": self._cfg.reasoning_effort}

        try:
            resp = self._cliente.responses.parse(
                model=self._cfg.modelo_geracao,
                instructions=sistema,
                input=[{"role": "user", "content": conteudo}],
                text_format=schema,
                store=False,  # a OpenAI não guarda a resposta para recuperação posterior
                **opcionais,
            )
        except Exception as e:  # rede, cota, timeout, parâmetro não suportado pelo modelo
            raise ErroIA(f"Falha ao chamar a OpenAI: {e}") from e

        resultado = getattr(resp, "output_parsed", None)
        if isinstance(resultado, schema):
            return resultado
        try:
            return schema.model_validate_json(getattr(resp, "output_text", "") or "")
        except Exception as e:
            raise ErroIA(f"Resposta da OpenAI fora do schema (pode ser recusa do modelo): {e}") from e

    def embeddings(self, textos, tarefa):
        # A OpenAI usa o mesmo embedding para documento e consulta: "tarefa" é ignorada.
        opcionais = {"dimensions": self._cfg.dimensao_embedding} if self._cfg.dimensao_embedding else {}
        vetores: list[list[float]] = []
        try:
            for i in range(0, len(textos), 100):
                resp = self._cliente.embeddings.create(
                    model=self._cfg.modelo_embedding, input=textos[i:i + 100], **opcionais)
                vetores.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        except Exception as e:
            raise ErroIA(f"Falha ao gerar embeddings na OpenAI: {e}") from e
        return np.asarray(vetores, dtype="float32")


# --------------------------------------------------------------------------- falso

class ProvedorFalso:
    """Respostas fixas e coerentes com o pedido. Nunca use os resultados na avaliação."""

    nome_modelo = "falso"
    id_embedding = "falso:hash-1024"
    _DIM = 1024

    @staticmethod
    def _palavras(texto: str) -> list[str]:
        sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
        return re.findall(r"[a-z]{3,}", sem_acento)

    def embeddings(self, textos, tarefa):
        matriz = np.zeros((len(textos), self._DIM), dtype="float32")
        for i, texto in enumerate(textos):
            for p in self._palavras(texto):
                matriz[i, int(hashlib.md5(p.encode()).hexdigest(), 16) % self._DIM] += 1.0
        return matriz

    def gerar_json(self, sistema, texto, schema, imagem=None, mime=None):
        from app.schemas import (Descricao, RespostaClassificacaoRag, RespostaClassificacaoSemRag,
                                 RespostaConsultaRag, RespostaConsultaSemRag)
        from app.taxonomia import TAXONOMIA

        if schema is Descricao:
            return Descricao.model_validate({
                "qualidadeImagem": {"adequada": True, "problema": "nenhum"},
                "perigos": [{"categoria": "buraco_ou_desnivel", "descricao": "Buraco na calçada",
                             "posicao": "frente", "urgencia": "imediata"}],
                "resumo": "Resposta do provedor falso: calçada com um buraco à frente.",
                "objetos": ["poste", "lixeira"],
                "textoLido": None,
                "barreira": {"detectada": True, "tipo": "CALCADA_DANIFICADA",
                             "descricao": "Buraco na calçada", "confianca": 0.9},
                "avisos": ["Descrição gerada pelo provedor falso, sem análise da foto."],
            })

        if schema is RespostaConsultaRag:
            tem_trecho = "\n[1] " in texto
            return RespostaConsultaRag(
                resposta=("Resposta do provedor falso, sem análise. Primeiro trecho encontrado [1]."
                          if tem_trecho else "Resposta do provedor falso: nenhum trecho encontrado na base."),
                trechosUsados=[1] if tem_trecho else [], respondidaPelaBase=tem_trecho)
        if schema is RespostaConsultaSemRag:
            return RespostaConsultaSemRag(resposta="Resposta do provedor falso, sem análise.", referencias=[])

        def campo(rotulo: str, validos, padrao: str) -> str:
            m = re.search(rf"{rotulo}: (\w+)", texto)
            return m.group(1) if m and m.group(1) in validos else padrao

        tipo = campo("Tipo escolhido no relato", TAXONOMIA["barreiras"], "OUTRO")
        gravidade = campo("Gravidade escolhida no relato", TAXONOMIA["gravidades"], "MEDIA")
        justificativa = "Resposta do provedor falso: classificação repetida do relato, sem análise."
        if schema is RespostaClassificacaoRag:
            escolhido = 1 if "\n[1] " in texto else None
            return RespostaClassificacaoRag(tipo=tipo, gravidade=gravidade,
                                            trechoEscolhido=escolhido, justificativa=justificativa)
        if schema is RespostaClassificacaoSemRag:
            return RespostaClassificacaoSemRag(tipo=tipo, gravidade=gravidade,
                                               normaReferencia=None, justificativa=justificativa)
        raise ErroIA(f"Provedor falso não conhece o schema {schema.__name__}.")


def criar_provedor(cfg: Config) -> ModeloIA:
    if cfg.provedor == "openai":
        return ClienteOpenAI(cfg)
    if cfg.provedor == "falso":
        return ProvedorFalso()
    raise ErroIA(f"IA_PROVEDOR inválido: {cfg.provedor!r}. Use openai ou falso.")
