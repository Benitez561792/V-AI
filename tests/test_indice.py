from app.rag.indice import IndiceVetorial


def test_busca_recupera_secao_certa(ia, indice):
    vetor = ia.embeddings(["piso tátil interrompido e danificado"], "RETRIEVAL_QUERY")
    melhor = indice.buscar(vetor, 3)[0]
    assert melhor.trecho.secao == "2.1"


def test_salvar_e_carregar_preserva_resultados(ia, indice, tmp_path):
    indice.salvar(tmp_path, "modelo-falso")
    carregado = IndiceVetorial.carregar(tmp_path)
    vetor = ia.embeddings(["lixeira bloqueando a faixa livre"], "RETRIEVAL_QUERY")
    assert [r.trecho.id for r in carregado.buscar(vetor, 3)] == [r.trecho.id for r in indice.buscar(vetor, 3)]
    assert carregado.meta["modeloEmbedding"] == "modelo-falso"
    assert carregado.secoes_conhecidas() == {"1", "2.1", "2.2", "3.1", "3.2"}


def test_ingestao_so_refaz_quando_precisa(tmp_path, monkeypatch, capsys):
    import shutil
    from app.rag import ingestao
    from tests.conftest import FONTES
    fontes = tmp_path / "fontes"
    shutil.copytree(FONTES, fontes)
    monkeypatch.setenv("DIR_FONTES", str(fontes))
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "idx"))

    assert ingestao.main(["--se-preciso"]) == 0
    assert "Gerando embeddings" in capsys.readouterr().out
    assert ingestao.main(["--se-preciso"]) == 0
    assert "Índice em dia" in capsys.readouterr().out

    (fontes / "nova.txt").write_text("1 Objetivo\nTexto novo sobre rampas.\n", encoding="utf-8")
    assert ingestao.main(["--se-preciso"]) == 0
    assert "Gerando embeddings" in capsys.readouterr().out
