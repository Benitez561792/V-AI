from tests.conftest import descricao_exemplo, png_minimo


def test_health(cliente):
    corpo = cliente.get("/health").json()
    assert corpo["status"] == "ok" and corpo["indiceCarregado"] and corpo["trechosNoIndice"] == 5


def test_contrato_publicado(cliente):
    assert "barreira" in cliente.get("/schema/descricao").json()["properties"]
    assert "PISO_TATIL" in cliente.get("/prompts/descricao").text
    assert "$tipos_barreira" not in cliente.get("/prompts/classificacao_rag").text


def test_descrever(cliente, ia):
    r = cliente.post("/descrever", files={"imagem": ("f.png", png_minimo(), "image/png")}, data={"modo": "ambiente"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["sugerirRelato"] is True
    assert corpo["falaPerigos"].startswith("Atenção: Buraco grande")
    assert ia.chamadas[-1]["tem_imagem"]


def test_descrever_nao_sugere_relato_com_foto_ruim(cliente, ia):
    from app.schemas import QualidadeImagem
    ia.descricao = descricao_exemplo(qualidadeImagem=QualidadeImagem(adequada=False, problema="tremida"))
    corpo = cliente.post("/descrever", files={"imagem": ("f.png", png_minimo(), "image/png")}).json()
    assert corpo["sugerirRelato"] is False


def test_descrever_rejeita_arquivo_que_nao_e_imagem(cliente):
    r = cliente.post("/descrever", files={"imagem": ("a.txt", b"oi", "text/plain")})
    assert r.status_code == 415


def test_classificar_com_rag_tira_norma_dos_metadados(cliente):
    r = cliente.post("/classificar", json={"texto": "Piso tátil interrompido e danificado na esquina",
                                            "relatoId": "r-1"})
    corpo = r.json()
    assert r.status_code == 200
    assert corpo["normaReferencia"] == "Norma Fictícia de Teste 2.1"
    assert "piso tátil de alerta" in corpo["trecho"]
    assert corpo["relatoId"] == "r-1" and corpo["semNormaAplicavel"] is False


def test_classificar_indice_fora_da_faixa_vira_sem_norma(cliente, ia):
    ia.trecho_escolhido = 99
    corpo = cliente.post("/classificar", json={"texto": "Piso tátil interrompido"}).json()
    assert corpo["normaReferencia"] is None and corpo["semNormaAplicavel"] is True


def test_classificar_sem_trecho_relevante(cliente, ia):
    corpo = cliente.post("/classificar", json={"texto": "Zzzz qqqq wwww"}).json()
    assert corpo["semNormaAplicavel"] is True
    assert "nenhum trecho relevante" in ia.chamadas[-1]["texto"]


def test_classificar_sem_rag(cliente):
    corpo = cliente.post("/classificar", json={"texto": "Piso tátil interrompido", "modo": "sem_rag"}).json()
    assert corpo["modo"] == "sem_rag" and corpo["normaReferencia"] == "NBR 9050 9.9.9"


def test_classificar_valida_entrada(cliente):
    assert cliente.post("/classificar", json={"texto": "x"}).status_code == 422
    assert cliente.post("/classificar", json={"texto": "abc", "tipoSugerido": "inexistente"}).status_code == 422


def test_contrato_do_rag_classificador_java(cliente):
    """Mesmo JSON que o record ClassificarRequest do RagClassificador.java envia."""
    pedido = {"texto": "Piso tátil interrompido e danificado na esquina",
              "tipoSugerido": "PISO_TATIL", "gravidadeSugerida": "MEDIA"}
    r = cliente.post("/classificar", json=pedido)
    assert r.status_code == 200
    corpo = r.json()
    # Campos lidos pelo record ClassificarResposta, com valores dos enums TipoRelato e Gravidade
    assert corpo["tipo"] in {"CALCADA_DANIFICADA", "OBSTRUCAO_PERMANENTE", "PISO_TATIL", "RAMPA",
                             "SEMAFORO_SEM_SOM", "OBRA_SEM_SINALIZACAO", "OUTRO"}
    assert corpo["gravidade"] in {"BAIXA", "MEDIA", "ALTA"}
    assert corpo["normaReferencia"] and len(corpo["normaReferencia"]) <= 200
    assert {"trecho", "justificativa"} <= corpo.keys()


def test_gravidade_fora_do_enum_java_e_rejeitada(cliente):
    r = cliente.post("/classificar", json={"texto": "buraco", "gravidadeSugerida": "CRITICA"})
    assert r.status_code == 422
