from app.rag.chunking import _dividir_texto, carregar_trechos, dividir_por_secoes
from app.rag.indice import extrair_secao
from tests.conftest import FONTES


def test_secoes_viram_metadados_e_sumario_e_ignorado():
    trechos = carregar_trechos(FONTES)
    assert [t.secao for t in trechos] == ["1", "2.1", "2.2", "3.1", "3.2"]
    assert all(t.fonte == "Norma Fictícia de Teste" for t in trechos)


def test_linha_de_corpo_com_numero_nao_vira_secao():
    trechos = carregar_trechos(FONTES)
    objetivo = next(t for t in trechos if t.secao == "1")
    assert "1 m de largura" in objetivo.texto


def test_secao_longa_e_dividida_mantendo_o_numero():
    corpo = "\n\n".join(f"Parágrafo {i} " + "x" * 300 for i in range(6))
    trechos = dividir_por_secoes(f"4.2 Seção longa\n{corpo}", "Fonte", maximo=700)
    assert len(trechos) > 1
    assert {t.secao for t in trechos} == {"4.2"}
    assert len({t.id for t in trechos}) == len(trechos)


def test_documento_sem_numeracao_vira_partes():
    trechos = dividir_por_secoes("Guia de calçadas.\n\nMantenha a faixa livre.", "Guia", maximo=30)
    assert [t.secao for t in trechos] == ["parte 1", "parte 2"]


def test_dividir_texto_respeita_maximo():
    assert all(len(p) <= 50 for p in _dividir_texto("a" * 180, 50))


def test_extrair_secao_ignora_numero_da_norma():
    assert extrair_secao("NBR 9050 6.12.1") == "6.12.1"
    assert extrair_secao("ABNT NBR 9050:2020, item 5.4") == "5.4"
    assert extrair_secao(None) is None


def test_lei_e_dividida_por_artigo():
    lei = ("LEI FICTÍCIA DE TESTE\nCAPÍTULO I\nArt. 1º Esta lei de teste trata de acessibilidade.\n"
           "Art. 2º Os estabelecimentos devem garantir rota acessível.\nParágrafo único. Inclui piso tátil.\n"
           "Art. 10. O descumprimento gera sanção.\n")
    trechos = dividir_por_secoes(lei, "Lei de Teste")
    assert [t.secao for t in trechos] == ["art. 1", "art. 2", "art. 10"]
    assert "Parágrafo único" in trechos[1].texto
    assert trechos[1].texto.startswith("Os estabelecimentos")


def test_limpeza_de_pdf_de_norma():
    from app.rag.chunking import limpar_texto
    paginas = []
    assuntos = ["calçadas", "rampas", "piso tátil", "travessias"]
    for n, romano in [(1, "iii"), (2, "iv"), (3, "v"), (4, "vi")]:
        paginas += ["ABNT NBR 0000:2020", f"6.{n} Seção {n} .............. {n}",
                    f"Requisitos sobre {assuntos[n - 1]}.", "0,75 0,90 0,90", "42 mm", "°",
                    f"© ABNT 2020 - Todos os direitos reservados {romano}"]
    texto = limpar_texto("\n".join(paginas + ["6.6.2.1"]))
    assert "Todos os direitos" not in texto and "ABNT NBR 0000" not in texto
    assert "....." not in texto and "0,75" not in texto and "42 mm" not in texto
    assert "Requisitos sobre piso tátil." in texto and texto.endswith("6.6.2.1")


def test_numero_sozinho_e_legenda_de_figura():
    texto = ("Sumário\n1 Escopo\n2 Referências\n"
             "1 Escopo\nEsta norma trata de calçadas.\n"
             "2 Requisitos\n2.1 Rampas\nAs rampas devem ser suaves.\n"
             "1 Piso tátil de alerta\n5 Guia\n"
             "2.1.1\nAs rampas devem ter patamares.\n")
    trechos = dividir_por_secoes(texto, "Norma")
    assert [t.secao for t in trechos] == ["1", "2.1", "2.1.1"]
    assert "5 Guia" in trechos[1].texto  # legenda fica no corpo, não vira capítulo
    assert trechos[1].texto.startswith("Rampas")  # o título também fica no corpo


def test_miniyaml_le_os_arquivos_do_projeto():
    import pytest
    from app import miniyaml
    dados = miniyaml.loads('# comentário\nsecao:\n  A: "texto: com dois pontos"  # fim\n  B: sem aspas\nnome.pdf: \'X\'\n')
    assert dados == {"secao": {"A": "texto: com dois pontos", "B": "sem aspas"}, "nome.pdf": "X"}
    assert miniyaml.loads(miniyaml.dumps({"a.txt": 'Lei "1"'})) == {"a.txt": 'Lei "1"'}
    with pytest.raises(ValueError):
        miniyaml.loads("  solto: x\n")
