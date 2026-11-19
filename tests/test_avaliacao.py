import csv

from avaliacao import avaliar
from avaliacao.metricas import percentil, recall_precisao, secao_confere, separar
from tests.conftest import IAFalsa, png_minimo


def test_percentil_igual_ao_numpy():
    assert percentil([100, 200, 300, 400], 50) == 250
    assert percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 9.55
    assert percentil([], 50) is None


def test_recall_e_precisao_micro():
    r = recall_precisao([{"veiculo", "pessoa"}, {"buraco_ou_desnivel"}], [{"veiculo"}, {"buraco_ou_desnivel", "obra"}])
    assert r["recall"] == 2 / 3 and r["precisao"] == 2 / 3


def test_secao_confere_aceita_subsecao():
    assert secao_confere("6.12.1", "6.12") and not secao_confere("6.1", "6.12")
    assert separar("veiculo; pessoa ;") == {"veiculo", "pessoa"}


def test_fluxo_completo_rodar_e_resumir(tmp_path, monkeypatch, indice):
    indice.salvar(tmp_path / "indice", "teste:hash")
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "indice"))
    monkeypatch.setenv("RAG_LIMIAR", "0.1")
    monkeypatch.setattr(avaliar, "criar_provedor", lambda cfg: IAFalsa())

    fotos = tmp_path / "fotos"
    fotos.mkdir()
    for nome in ("a.png", "b.png"):
        (fotos / nome).write_bytes(png_minimo())
    anotacoes = tmp_path / "anotacoes.csv"
    anotacoes.write_text(
        "arquivo,origem,grupo,modo,perigos_esperados,barreira_esperada,secao_esperada,imagem_ruim_esperada,observacao\n"
        "a.png,propria,barreira,ambiente,buraco_ou_desnivel; veiculo,CALCADA_DANIFICADA,3.1,nao,\n"
        "b.png,vizwiz,falha,ambiente,,,,sim,\n", encoding="utf-8")

    saida = tmp_path / "resultados"
    assert avaliar.main(["rodar", "--anotacoes", str(anotacoes), "--fotos", str(fotos),
                         "--saida", str(saida), "--intervalo", "0"]) == 0
    execucao = next(saida.glob("execucao_*.csv"))
    linhas = list(csv.DictReader(execucao.open(encoding="utf-8")))
    assert linhas[0]["norma_rag_existe"] == "True"
    assert linhas[0]["norma_sem_rag_existe"] == "False"  # 9.9.9 não existe na base

    for l in linhas:
        l["alucinacao"] = "0"
    with execucao.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=avaliar.COLUNAS)
        w.writeheader()
        w.writerows(linhas)

    assert avaliar.main(["resumir", str(execucao)]) == 0
    m = avaliar.calcular(linhas)
    assert m["descricao"]["recallPerigos"] == 0.5
    assert m["referencias"]["rag"]["taxaReferenciaInexistente"] == 0
    assert m["referencias"]["semRag"]["taxaReferenciaInexistente"] == 1
    assert m["referencias"]["rag"]["acertoSecao"] == 1
    assert "Casos para interpretar" in (saida / "relatorio.md").read_text(encoding="utf-8")


def test_referencia_confere_com_numero_da_norma():
    from avaliacao.metricas import referencia_confere
    esperada = "9050 6.12.3; 16537 6.8"
    assert referencia_confere("ABNT NBR 9050:2020 6.12.3", "6.12.3", esperada)
    assert referencia_confere("ABNT NBR 16537:2024 6.8", "6.8", esperada)
    assert not referencia_confere("ABNT NBR 16537:2024 6.12.3", "6.12.3", esperada)  # norma errada
    assert referencia_confere("Norma X 3.1.2", "3.1.2", "3.1")  # anotação sem norma


def test_referencia_existe_por_norma():
    from app.rag.chunking import Trecho
    from app.rag.indice import IndiceVetorial
    import numpy as np
    idx = IndiceVetorial(np.eye(2, dtype="float32"),
                         [Trecho("a", "ABNT NBR 9050:2020", "6.3", None, "x"),
                          Trecho("b", "ABNT NBR 16537:2024", "6.8", None, "y")])
    assert idx.referencia_existe("NBR 16537 6.8", "6.8") is True
    assert idx.referencia_existe("NBR 9050 6.8", "6.8") is False
    assert idx.referencia_existe(None, None) is None


def test_secao_mae_sem_texto_proprio_existe():
    from app.rag.chunking import Trecho
    from app.rag.indice import IndiceVetorial
    import numpy as np
    idx = IndiceVetorial(np.eye(2, dtype="float32"),
                         [Trecho("a", "ABNT NBR 9050:2020", "6.3.4.1", None, "x"),
                          Trecho("b", "Lei 13.146/2015", "art. 55", None, "y")])
    assert idx.referencia_existe("NBR 9050 6.3.4", "6.3.4") is True      # "6.3.4 Desníveis" só tem subseções
    assert idx.referencia_existe("NBR 9050 6.3.5", "6.3.5") is False
    assert idx.referencia_existe("Lei 13.146/2015 art. 5", "art. 5") is False  # art. 5 não é "pai" do art. 55
