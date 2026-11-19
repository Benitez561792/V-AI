from app.schemas import RespostaConsultaRag


def test_consulta_troca_citacoes_pela_referencia_real(cliente):
    r = cliente.post("/consultar", json={"pergunta": "Onde o piso tátil de alerta é exigido?"})
    assert r.status_code == 200
    corpo = r.json()
    # [1] vira a referência do trecho; [9] não existe e some; "[X][X]" vira um só
    assert corpo["resposta"] == ("O piso tátil de alerta é exigido antes de rampas [Norma Fictícia de Teste 2.1]. "
                                 "Também não pode estar danificado [Norma Fictícia de Teste 2.1].")
    assert corpo["referenciasCitadas"] == ["Norma Fictícia de Teste 2.1"]
    assert corpo["fontes"][0]["trecho"].startswith("Piso tátil de alerta")
    assert corpo["respondidaPelaBase"] is True


def test_consulta_fora_da_base(cliente, ia):
    ia.resposta_consulta = RespostaConsultaRag(resposta="A base não trata disso.", trechosUsados=[],
                                               respondidaPelaBase=False)
    corpo = cliente.post("/consultar", json={"pergunta": "Zzzz qqqq wwww"}).json()
    assert corpo["fontes"] == [] and corpo["respondidaPelaBase"] is False
    assert "nenhum trecho relevante" in ia.chamadas[-1]["texto"]


def test_consulta_nao_aceita_trecho_inexistente(cliente, ia):
    ia.resposta_consulta = RespostaConsultaRag(resposta="Resposta [7].", trechosUsados=[7], respondidaPelaBase=True)
    corpo = cliente.post("/consultar", json={"pergunta": "Piso tátil de alerta"}).json()
    assert corpo["resposta"] == "Resposta." and corpo["fontes"] == [] and corpo["respondidaPelaBase"] is False


def test_consulta_sem_rag(cliente):
    corpo = cliente.post("/consultar", json={"pergunta": "Piso tátil", "modo": "sem_rag"}).json()
    assert corpo["modo"] == "sem_rag" and corpo["referenciasCitadas"] == ["NBR 9050 9.9.9"] and corpo["fontes"] == []


def test_consultar_no_terminal(tmp_path, monkeypatch, capsys):
    from app import consultar
    from app.provedores import ProvedorFalso
    from app.rag.chunking import carregar_trechos
    from app.rag.ingestao import construir_indice
    from tests.conftest import FONTES
    ia = ProvedorFalso()
    construir_indice(carregar_trechos(FONTES), ia).salvar(tmp_path / "idx", ia.id_embedding)
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "idx"))
    monkeypatch.setenv("RAG_LIMIAR", "0.2")

    assert consultar.main(["Onde usar piso tátil de alerta?", "--comparar", "--sem-preparar"]) == 0
    saida = capsys.readouterr().out
    assert "--- COM RAG" in saida and "--- SEM RAG" in saida and "[1] Norma Fictícia de Teste" in saida

    respostas = iter(["Onde usar piso tátil de alerta?", ""])  # uma pergunta e depois sai
    monkeypatch.setattr("builtins.input", lambda _: next(respostas))
    assert consultar.main(["--sem-preparar"]) == 0
    saida = capsys.readouterr().out
    assert "Bem-vindo ao Vê AI" in saida and "Fontes:" in saida
    assert "--- COM RAG" not in saida  # conversa normal sem cabeçalho técnico
    assert "trecho encontrado [1]." in saida  # citação curta, ligada à lista de fontes


def test_avaliacao_das_perguntas(tmp_path, monkeypatch, indice):
    import csv
    from avaliacao import perguntas
    from tests.conftest import IAFalsa
    indice.salvar(tmp_path / "idx", "teste:hash")
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "idx"))
    monkeypatch.setenv("RAG_LIMIAR", "0.1")
    monkeypatch.setattr(perguntas, "criar_provedor", lambda cfg: IAFalsa())
    entrada = tmp_path / "perguntas.csv"
    entrada.write_text("id,pergunta,secao_esperada,observacao\n"
                       "p1,Onde usar piso tátil de alerta?,Fictícia 2.1,\n"
                       "p2,Qual o horário do metrô?,nenhuma,\n", encoding="utf-8")
    saida = tmp_path / "res"
    assert perguntas.main(["rodar", "--perguntas", str(entrada), "--saida", str(saida), "--intervalo", "0"]) == 0
    linhas = list(csv.DictReader(next(saida.glob("perguntas_*.csv")).open(encoding="utf-8")))
    m = perguntas.calcular(linhas)
    assert m["rag"]["referenciaInexistente"] == 0 and m["rag"]["referenciaCorreta"] == 1
    assert m["sem_rag"]["referenciaInexistente"] == 1  # o modelo falso cita "NBR 9050 9.9.9" de memória
    assert "Consulta com e sem RAG" in (saida / "relatorio_perguntas.md").read_text(encoding="utf-8")


def test_preparar_baixa_leis_uma_vez_e_gera_indice(tmp_path, monkeypatch):
    import shutil
    from app import preparar
    from app.rag import baixar_leis
    from tests.conftest import FONTES
    fontes = tmp_path / "fontes"
    shutil.copytree(FONTES, fontes)
    monkeypatch.setenv("DIR_FONTES", str(fontes))
    monkeypatch.setenv("DIR_INDICE", str(tmp_path / "idx"))
    chamadas = []
    monkeypatch.setattr(baixar_leis, "main", lambda argv=None: chamadas.append(1) or 1)  # site fora do ar

    assert preparar.preparar() is True
    assert (tmp_path / "idx" / "vetores.npy").exists() and chamadas == [1]
    assert preparar.preparar() is True
    assert chamadas == [1]  # não tenta baixar de novo a cada execução



def test_citacoes_viram_numeros_ligados_as_fontes():
    from app.consultar import _numerar_citacoes
    from app.schemas import ConsultarResponse, FonteConsulta
    fontes = [FonteConsulta(referencia=r, fonte="x", secao=None, trecho="t", similaridade=0.5)
              for r in ("Lei 13.146/2015 art. 121", "Decreto 5.296/2004 art. 1")]
    r = ConsultarResponse(pergunta="p", resposta="As leis são A e B [Lei 13.146/2015 art. 121] [Decreto 5.296/2004 art. 1]. "
                          "Veja também [Lei 13.146/2015 art. 121].", fontes=fontes, referenciasCitadas=[],
                          respondidaPelaBase=True, modo="rag", referenciasConsultadas=[], modelo="m", latenciaMs=1)
    assert _numerar_citacoes(r) == "As leis são A e B [1][2]. Veja também [1]."
