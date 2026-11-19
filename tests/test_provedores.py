from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai.lib._pydantic import to_strict_json_schema

from app.config import carregar_config
from app.main import criar_app
from app.provedores import ClienteOpenAI, ErroIA, ProvedorFalso, criar_provedor
from app.rag.chunking import carregar_trechos
from app.rag.ingestao import construir_indice
from app.schemas import (Descricao, RespostaClassificacaoRag, RespostaClassificacaoSemRag,
                         RespostaConsultaRag, RespostaConsultaSemRag)
from tests.conftest import FONTES, png_minimo


# ---------------------------------------------------------------- schemas

@pytest.mark.parametrize("schema", [Descricao, RespostaClassificacaoRag, RespostaClassificacaoSemRag,
                                    RespostaConsultaRag, RespostaConsultaSemRag])
def test_schemas_aceitos_no_modo_estrito(schema):
    s = to_strict_json_schema(schema)
    assert s["additionalProperties"] is False
    assert set(s["required"]) == set(s["properties"])


# ---------------------------------------------------------------- OpenAI com cliente simulado

class ClienteSimulado:
    """Imita openai.OpenAI: guarda os argumentos e devolve respostas prontas."""

    def __init__(self, parsed=None, texto="", erro=None):
        self.chamadas = []
        self.embeds = []
        self._parsed, self._texto, self._erro = parsed, texto, erro
        self.responses = SimpleNamespace(parse=self._parse)
        self.embeddings = SimpleNamespace(create=self._embed)

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        return SimpleNamespace(output_parsed=self._parsed, output_text=self._texto)

    def _embed(self, model, input, **kwargs):
        self.embeds.append({"model": model, "n": len(input), **kwargs})
        dados = [SimpleNamespace(index=i, embedding=[float(i), 1.0]) for i in range(len(input))]
        return SimpleNamespace(data=list(reversed(dados)))  # fora de ordem de propósito


def _cfg(**mudancas):
    return replace(carregar_config(), provedor="openai", openai_api_key="teste", **mudancas)


def test_openai_monta_pedido_com_imagem_schema_e_sem_guardar():
    resposta = RespostaClassificacaoRag(tipo="RAMPA", gravidade="ALTA", trechoEscolhido=1, justificativa="ok")
    sim = ClienteSimulado(parsed=resposta)
    ia = ClienteOpenAI(_cfg(modelo_geracao="gpt-teste", reasoning_effort="none", temperatura=None), cliente=sim)
    assert ia.gerar_json("sistema", "texto", RespostaClassificacaoRag, imagem=b"abc", mime="image/png") is resposta

    pedido = sim.chamadas[0]
    assert pedido["model"] == "gpt-teste" and pedido["instructions"] == "sistema"
    assert pedido["text_format"] is RespostaClassificacaoRag and pedido["store"] is False
    assert pedido["reasoning"] == {"effort": "none"} and "temperature" not in pedido
    conteudo = pedido["input"][0]["content"]
    assert conteudo[0] == {"type": "input_text", "text": "texto"}
    assert conteudo[1]["image_url"] == "data:image/png;base64,YWJj"


def test_openai_omite_reasoning_e_envia_temperatura_quando_configurado():
    sim = ClienteSimulado(parsed=RespostaClassificacaoSemRag(tipo="OUTRO", gravidade="BAIXA",
                                                             normaReferencia=None, justificativa="ok"))
    ClienteOpenAI(_cfg(reasoning_effort=None, temperatura=0.2), cliente=sim).gerar_json(
        "s", "t", RespostaClassificacaoSemRag)
    assert "reasoning" not in sim.chamadas[0] and sim.chamadas[0]["temperature"] == 0.2


def test_openai_converte_erros_em_erro_ia():
    with pytest.raises(ErroIA, match="Falha ao chamar a OpenAI"):
        ClienteOpenAI(_cfg(), cliente=ClienteSimulado(erro=TimeoutError("lento"))).gerar_json(
            "s", "t", RespostaClassificacaoRag)
    with pytest.raises(ErroIA, match="fora do schema"):  # recusa: sem output_parsed e texto inválido
        ClienteOpenAI(_cfg(), cliente=ClienteSimulado(texto="Não posso ajudar.")).gerar_json(
            "s", "t", RespostaClassificacaoRag)


def test_openai_embeddings_em_lotes_na_ordem_certa():
    sim = ClienteSimulado()
    ia = ClienteOpenAI(_cfg(modelo_embedding="emb-teste", dimensao_embedding=None), cliente=sim)
    vetores = ia.embeddings([f"t{i}" for i in range(150)], "RETRIEVAL_QUERY")
    assert vetores.shape == (150, 2) and vetores[1, 0] == 1.0
    assert [e["n"] for e in sim.embeds] == [100, 50] and "dimensions" not in sim.embeds[0]
    assert ia.id_embedding == "openai:emb-teste:nativa"

    sim2 = ClienteSimulado()
    ClienteOpenAI(_cfg(dimensao_embedding=512), cliente=sim2).embeddings(["a"], "x")
    assert sim2.embeds[0]["dimensions"] == 512


def test_openai_sem_chave_explica_o_que_fazer():
    with pytest.raises(ErroIA, match="OPENAI_API_KEY"):
        ClienteOpenAI(replace(carregar_config(), provedor="openai", openai_api_key=""))


# ---------------------------------------------------------------- configuração

def test_config_padroes_e_opcionais(monkeypatch):
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("IA_PROVEDOR", raising=False)
    monkeypatch.setenv("OPENAI_TEMPERATURE", "")
    cfg = carregar_config()
    assert cfg.reasoning_effort == "none" and cfg.temperatura is None and cfg.provedor == "falso"
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "")
    assert carregar_config().reasoning_effort is None
    with pytest.raises(ErroIA, match="IA_PROVEDOR"):
        criar_provedor(replace(cfg, provedor="gemini"))


# ---------------------------------------------------------------- provedor falso ponta a ponta

@pytest.fixture
def app_falso(tmp_path):
    cfg = replace(carregar_config(), provedor="falso", dir_fontes=FONTES, dir_indice=tmp_path / "idx",
                  rag_limiar=0.2)
    ia = ProvedorFalso()
    construir_indice(carregar_trechos(FONTES), ia).salvar(cfg.dir_indice, ia.id_embedding)
    with TestClient(criar_app(cfg=cfg)) as c:
        yield c, cfg


def test_provedor_falso_atende_contrato_da_api_java(app_falso):
    cliente, _ = app_falso
    saude = cliente.get("/health").json()
    assert saude["provedor"] == "falso" and saude["indiceCarregado"] and saude["status"] == "ok"
    corpo = cliente.post("/classificar", json={"texto": "Piso tátil interrompido e danificado",
                                               "tipoSugerido": "PISO_TATIL", "gravidadeSugerida": "MEDIA"}).json()
    assert corpo["tipo"] == "PISO_TATIL" and corpo["gravidade"] == "MEDIA"
    assert corpo["normaReferencia"] == "Norma Fictícia de Teste 2.1"
    r = cliente.post("/descrever", files={"imagem": ("f.png", png_minimo(), "image/png")})
    assert r.status_code == 200 and r.json()["sugerirRelato"] is True


def test_indice_de_outro_embedding_e_recusado(tmp_path):
    cfg = replace(carregar_config(), provedor="falso", dir_indice=tmp_path / "idx")
    construir_indice(carregar_trechos(FONTES), ProvedorFalso()).salvar(cfg.dir_indice, "openai:outro:nativa")
    with TestClient(criar_app(cfg=cfg)) as c:
        saude = c.get("/health").json()
        assert saude["indiceCarregado"] is False and "Rode de novo" in saude["erroIndice"]
        assert c.post("/classificar", json={"texto": "buraco grande"}).status_code == 503
        sem_rag = c.post("/classificar", json={"texto": "buraco grande", "modo": "sem_rag"})
        assert sem_rag.status_code == 200


def test_testar_no_terminal(tmp_path, monkeypatch, capsys):
    from app import classificar as testar
    ia = ProvedorFalso()
    construir_indice(carregar_trechos(FONTES), ia).salvar(tmp_path / "idx", ia.id_embedding)
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "idx"))
    monkeypatch.setenv("RAG_LIMIAR", "0.2")
    assert testar.main(["Piso tátil interrompido e danificado", "--tipo", "PISO_TATIL", "--comparar"]) == 0
    saida = capsys.readouterr().out
    assert "--- COM RAG" in saida and "--- SEM RAG" in saida
    assert "Norma Fictícia de Teste 2.1" in saida and "Tipo:        PISO_TATIL" in saida


def test_testar_sem_indice_explica_o_erro(tmp_path, monkeypatch, capsys):
    from app import classificar as testar
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "vazio"))
    assert testar.main(["Buraco grande"]) == 1
    assert "ingestao" in capsys.readouterr().err
