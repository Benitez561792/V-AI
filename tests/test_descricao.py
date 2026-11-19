from app.schemas import Perigo, QualidadeImagem
from app.services.descricao import AVISO_SEM_PERIGOS, aplicar_regras_de_seguranca, montar_fala
from tests.conftest import descricao_exemplo


def test_perigos_imediatos_vem_primeiro():
    d = aplicar_regras_de_seguranca(descricao_exemplo())
    assert d.perigos[0].urgencia.value == "imediata"
    fala_perigos, fala = montar_fala(d)
    assert fala.startswith("Atenção: Buraco grande, à frente")
    assert fala.index("Buraco") < fala.index("Calçada estreita")


def test_nunca_afirma_caminho_livre():
    d = aplicar_regras_de_seguranca(descricao_exemplo(perigos=[], resumo="O caminho está livre. Há uma praça."))
    assert "livre" not in d.resumo.lower()
    assert AVISO_SEM_PERIGOS in d.avisos
    assert montar_fala(d)[0] == ""


def test_foto_escura_gera_aviso_antes_de_tudo():
    d = aplicar_regras_de_seguranca(descricao_exemplo(
        qualidadeImagem=QualidadeImagem(adequada=True, problema="escura")))
    assert d.qualidadeImagem.adequada is False
    assert montar_fala(d)[1].startswith("A foto está escura")


def test_barreira_incoerente_e_corrigida():
    d = descricao_exemplo()
    d.barreira.confianca = 1.7
    assert aplicar_regras_de_seguranca(d).barreira.confianca == 1.0
    d.barreira.detectada, d.barreira.confianca = False, 0.8
    corrigida = aplicar_regras_de_seguranca(d).barreira
    assert corrigida.tipo is None and corrigida.confianca == 0.0
