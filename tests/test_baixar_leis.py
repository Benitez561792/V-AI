from app import miniyaml as yaml_mini

from app.rag import baixar_leis
from app.rag.chunking import carregar_trechos

HTML_PLANALTO = """<html><head><title>L13146</title><style>p{}</style></head><body>
<p align=center><b>LEI DE TESTE</b></p>
<p>Art. 1º&nbsp; Esta lei de teste institui regras de acessibilidade.</p>
<p><strike>Art. 2º Texto revogado que não deve aparecer.</strike></p>
<p>Art. 2º A calçada deve ter piso tátil.</p>
<p>Parágrafo único. Inclusive na travessia.</p>
<p>Art. 3o Os semáforos devem ter sinal sonoro.</p>
</body></html>"""


def test_html_para_texto_descarta_revogado_e_estilo():
    texto = baixar_leis.html_para_texto(HTML_PLANALTO)
    assert "revogado" not in texto and "p{}" not in texto
    assert "Art. 1º Esta lei" in texto and "Parágrafo único. Inclusive na travessia." in texto


def test_decodifica_windows_1252():
    assert baixar_leis._decodificar("Calçada".encode("windows-1252"), None) == "Calçada"


def test_main_salva_textos_nomes_e_chunking_por_artigo(tmp_path, monkeypatch):
    monkeypatch.setenv("DIR_FONTES", str(tmp_path))
    (tmp_path / "fontes.yaml").write_text("nbr9050.pdf: ABNT NBR 9050\n", encoding="utf-8")
    monkeypatch.setattr(baixar_leis, "baixar", lambda url: HTML_PLANALTO)
    assert baixar_leis.main() == 0

    nomes = yaml_mini.loads((tmp_path / "fontes.yaml").read_text(encoding="utf-8"))
    assert nomes["nbr9050.pdf"] == "ABNT NBR 9050" and nomes["lei13146.txt"] == "Lei 13.146/2015"
    trechos = [t for t in carregar_trechos(tmp_path) if t.fonte == "Lei 13.146/2015"]
    assert [t.secao for t in trechos] == ["art. 1", "art. 2", "art. 3"]


def test_main_explica_quando_nao_consegue_baixar(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DIR_FONTES", str(tmp_path))

    def falha(url):
        raise OSError("sem rede")
    monkeypatch.setattr(baixar_leis, "baixar", falha)
    assert baixar_leis.main() == 1
    assert "Baixe manualmente" in capsys.readouterr().err
