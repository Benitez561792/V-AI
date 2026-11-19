import csv

from avaliacao import latencia, relatos
from tests.conftest import IAFalsa


def test_rodar_e_resumir_relatos(tmp_path, monkeypatch, indice):
    indice.salvar(tmp_path / "indice", "teste:hash")
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "indice"))
    monkeypatch.setenv("RAG_LIMIAR", "0.1")
    monkeypatch.setattr(relatos, "criar_provedor", lambda cfg: IAFalsa())
    entrada = tmp_path / "relatos.csv"
    entrada.write_text(
        "id,texto,tipo_relato,tipo_esperado,gravidade_esperada,secao_esperada,observacao\n"
        "r1,Piso tátil interrompido e danificado,PISO_TATIL,PISO_TATIL,ALTA,2.1,\n"
        "r2,O ônibus atrasou,OUTRO,OUTRO,BAIXA,nenhuma,\n", encoding="utf-8")
    saida = tmp_path / "res"
    assert relatos.main(["rodar", "--relatos", str(entrada), "--saida", str(saida), "--intervalo", "0"]) == 0
    arq = next(saida.glob("relatos_*.csv"))
    linhas = list(csv.DictReader(arq.open(encoding="utf-8")))
    assert len(linhas) == 4
    m = relatos.calcular(linhas)
    assert m["rag"]["secaoCorreta"] == 1 and m["rag"]["referenciaInexistente"] == 0
    assert m["sem_rag"]["referenciaInexistente"] == 1  # o modelo falso cita 9.9.9 sem RAG
    assert relatos.main(["resumir", str(arq)]) == 0
    assert (saida / "relatorio_relatos.md").exists()


def test_exemplo_de_relatos_usa_valores_da_api_java():
    from app.taxonomia import TAXONOMIA
    with relatos.DIR.joinpath("relatos.exemplo.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert r["tipo_relato"] in TAXONOMIA["barreiras"]
            assert r["tipo_esperado"] in TAXONOMIA["barreiras"]
            assert r["gravidade_esperada"] in TAXONOMIA["gravidades"]


def test_latencia_contra_servidor_local(cliente, monkeypatch, capsys):
    """Usa o TestClient no lugar da rede para validar o script de ponta a ponta."""
    def chamar(url, corpo, timeout):
        r = cliente.post("/classificar", json=corpo)
        return 10.0, str(r.status_code)
    monkeypatch.setattr(latencia, "chamar", chamar)
    assert latencia.main(["--n", "3", "--intervalo", "0"]) == 0
    assert "sucesso: 3  falhas: 0" in capsys.readouterr().out
