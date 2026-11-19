# Vê AI · Serviço de IA

**IA de consulta sobre acessibilidade para pessoas com deficiência visual**, parte do projeto **Vê AI**. Responde perguntas sobre o que as normas e leis exigem (calçadas, piso tátil, rampas, travessias, estabelecimentos) e classifica relatos de barreiras, sempre citando a seção da norma ou o artigo da lei de onde tirou a informação. Funciona sozinha, pelo terminal; a integração com a API Java do projeto é opcional.

Disciplina: **Disruptive Architectures: IoT, IoB & Generative IA** · FIAP 2TDS · Global Solution 2026/2

## Integrantes

| RM | Nome |
|---|---|
| 561413 | Lucas Grillo Alcântara |
| 562027 | Lucca Ramos Mussumecci |
| 561469 | Pietro Ferreira Gomes Abrahamian |
| 561792 | Pedro Peres Benitez |

## Funcionalidade de IA

O acervo de consulta reúne a ABNT NBR 9050:2020 (acessibilidade em edificações e espaço urbano), a ABNT NBR 16537:2024 (sinalização tátil no piso) e as leis de acessibilidade (Lei 13.146/2015, Lei 10.098/2000 e Decreto 5.296/2004). Tudo funciona pelo terminal. A IA generativa é a da OpenAI (ChatGPT), e o aprofundamento é **RAG**: o modelo só responde com os trechos recuperados desse acervo.

1. **Consulta (função principal, `python consultar.py`).** A pessoa pergunta, por exemplo, "Qual a largura mínima da faixa livre?" ou "Tenho uma loja com um degrau na entrada; o que preciso adequar para clientes cegos?". O serviço busca os trechos mais relevantes, o modelo responde só com eles e cita cada informação pelo número do trecho, e o sistema troca esse número pela referência real (`ABNT NBR 9050:2020 6.12.3`). Se o acervo não trata do assunto, a resposta diz isso em vez de inventar. Público: gestores de ONGs e CRAS, técnicos da prefeitura, donos de estabelecimentos e as próprias pessoas com deficiência visual.
2. **Classificação de relato (`python -m app.classificar` ou `POST /classificar`).** Recebe a descrição de uma barreira ("o orelhão está na calçada sem nada no piso para avisar") e devolve tipo, gravidade, a norma descumprida e uma justificativa para o encaminhamento. É o que a API Java do Vê AI chama quando um relato é criado (classe `RagClassificador`), mas também funciona sozinha.
3. **Descrição de foto (`POST /descrever`, complementar).** JSON estruturado com perigos, resumo, objetos, texto lido e barreira, com regras de segurança aplicadas em código (perigos primeiro, nunca afirmar "caminho livre", aviso para foto escura). No produto, quem descreve as fotos é a API Java.

Nas três, nenhuma referência é escrita pelo modelo: ela sempre sai dos metadados do trecho recuperado.

## Arquitetura

```mermaid
flowchart LR
    Pessoa["Pessoa no terminal<br/>python consultar.py"] --> IA
    App["App React Native<br/>(Pietro)"] -->|foto / relato| API["API Java Spring Boot<br/>(Lucas)"]
    API -->|"descrição da foto<br/>Spring AI"| OpenAI[(OpenAI)]
    API -->|"RagClassificador: POST /classificar<br/>assíncrono, após o commit, timeout 3 s"| IA["Serviço de IA<br/>FastAPI (este repo)"]
    IA -->|"embedding da consulta<br/>+ classificação"| OpenAI
    IA --> Indice[("Índice vetorial (numpy)<br/>trechos + metadados")]
    Fontes["NBR 9050<br/>guias municipais"] -->|"ingestão: chunking por seção<br/>+ embeddings"| Indice
    API -->|"grava normaReferencia<br/>(VARCHAR2 200)"| BD[(Oracle)]
```

Fluxo da consulta:

```mermaid
sequenceDiagram
    participant P as Pessoa (terminal)
    participant C as consultar.py
    participant O as OpenAI
    participant I as Índice vetorial
    P->>C: pergunta
    C->>O: embedding da pergunta
    C->>I: top-k trechos por cosseno
    I-->>C: trechos + similaridade
    Note over C: descarta trechos abaixo de RAG_LIMIAR
    C->>O: pergunta + trechos numerados (saída estruturada)
    O-->>C: resposta com citações [1], [2] e trechos usados
    Note over C: troca cada [n] pela referência real do trecho<br/>número inválido é removido
    C-->>P: resposta + fontes (ou "o acervo não trata disso")
```

Fluxo da classificação de relato (usado pela API Java):

```mermaid
sequenceDiagram
    participant API as API Java (RagClassificador)
    participant IA as Serviço de IA
    participant G as OpenAI
    participant F as Índice vetorial
    Note over API: relato salvo, evento CRIADO depois do commit
    API->>IA: POST /classificar {texto, tipoSugerido, gravidadeSugerida}
    IA->>G: embedding da consulta
    IA->>F: top-k por cosseno
    F-->>IA: trechos + similaridade
    Note over IA: descarta trechos abaixo de RAG_LIMIAR
    IA->>G: relato + trechos numerados (saída estruturada)
    G-->>IA: tipo, gravidade, trechoEscolhido, justificativa
    Note over IA: normaReferencia = metadados do trecho escolhido<br/>índice inválido ou nenhum trecho → null
    IA-->>API: {tipo, gravidade, normaReferencia, trecho, justificativa, ...}
    Note over API: grava só normaReferencia no relato
```

**Integração sem dependência.** O `RagClassificador` só é ativado quando `VEAI_RAG_URL` está preenchida na API Java. Ele roda de forma assíncrona depois do commit, com timeout de 3 s. Se este serviço estiver fora do ar, demorar ou devolver erro, o relato continua válido com `normaReferencia = null`. O relato nunca depende da IA para existir, e a classificação do RAG não altera o tipo nem a gravidade escolhidos pelo cidadão.

**Contrato com a API Java.** Os valores de tipo e gravidade em `app/taxonomia.yaml` são os mesmos dos enums `TipoRelato` e `Gravidade` da API Java e das constraints `ck_relato_tipo` e `ck_relato_gravidade` do Oracle. Se um deles mudar, os três precisam mudar juntos. O teste `test_contrato_do_rag_classificador_java` envia exatamente o JSON do record `ClassificarRequest` da API Java e confere se a resposta tem os campos e valores que o record `ClassificarResposta` espera.

Para ligar a integração, na API Java:

```bash
VEAI_RAG_URL=http://localhost:8000   # ou a URL pública deste serviço
```

## Dados e preparação

| Fonte | Versão | Trechos | Acesso | No GitHub |
|---|---|---|---|---|
| ABNT NBR 9050 (acessibilidade em edificações e espaço urbano) | 2020, 4ª edição | 549 | Publicada pela Prefeitura de São Paulo em drive.prefeitura.sp.gov.br/cidade/secretarias/upload/NBR9050_20.pdf | Não (direitos da ABNT) |
| ABNT NBR 16537 (sinalização tátil no piso) | 2024, 2ª edição | 110 | ABNT (abntcatalogo.com.br) | Não (direitos da ABNT) |
| Lei 13.146/2015, Lei 10.098/2000, Decreto 5.296/2004 | texto vigente | por artigo | planalto.gov.br, baixadas por `python -m app.rag.baixar_leis` | Sim |

Preparação (feita sozinha pelo `consultar.py` quando os documentos mudam; detalhes em `data/fontes/README.md`):

1. **Extração:** texto dos PDFs com pdfplumber; leis do HTML do Planalto, sem os trechos revogados.
2. **Limpeza:** saem sumário, cabeçalhos e rodapés repetidos e restos de figuras (cotas como `0,75 0,90`).
3. **Divisão:** um trecho por seção da norma (`6.12.3`) ou artigo da lei (`art. 46`), com o número como metadado; seções longas viram partes com o mesmo número.
4. **Embeddings:** cada trecho vira um vetor (`text-embedding-3-small`), salvo em `data/indice/` com o modelo usado e a assinatura das fontes.

Nenhum dado pessoal é usado: o acervo são normas e leis, e os casos de avaliação são perguntas e relatos escritos pelo grupo.

## Como executar

Requisito: Python 3.11 ou mais novo. (Se a instalação falhar em alguma biblioteca, instale o Python 3.13 em python.org e use `py -3.13` no lugar de `python` no primeiro comando.)

Na pasta do projeto, só na primeira vez:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
source .venv/bin/activate        # Mac/Linux
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e coloque a sua `OPENAI_API_KEY`. Depois, para consultar:

```bash
python consultar.py
```

Na primeira execução, ele baixa as leis do Planalto e monta o índice do RAG com a chave do `.env` (alguns segundos e centavos de crédito), mostrando só "Preparando a base de consulta". Nas seguintes, abre direto a conversa:

```
Bem-vindo ao Vê AI

Pergunta: Qual a largura mínima da faixa livre da calçada?

   A faixa livre da calçada deve ter no mínimo 1,20 m de largura [1].

   Fontes:
   [1] ABNT NBR 9050:2020 6.12.3

Pergunta:
```

Cada citação `[n]` aponta para a fonte de mesmo número. Para sair, aperte Enter sem escrever nada.

Outras formas:

```bash
python consultar.py "Qual a largura mínima da faixa livre?"                 # uma pergunta só
python consultar.py "Como sinalizar um orelhão na calçada?" --comparar      # com e sem RAG
python consultar.py "Como sinalizar um orelhão na calçada?" --trechos       # mostra o texto da norma
python -m app.classificar "O orelhão está na calçada sem nada no piso"      # classifica um relato
python avaliar.py perguntas                                               # avaliação com e sem RAG
pytest                                                                    # testes (pip install -r requirements-dev.txt)
```

Nas próximas vezes, basta ativar o ambiente (`.venv\Scripts\activate`) e rodar `python consultar.py`.

### Provedor de IA

O `.env.example` vem com `IA_PROVEDOR=falso`; para usar o ChatGPT, troque para `openai` e preencha a chave. Os dois provedores:

| `IA_PROVEDOR` | Para quê |
|---|---|
| `openai` | ChatGPT pela API da OpenAI, com saída estruturada e embeddings da OpenAI. |
| `falso` | Respostas fixas e embeddings por hashing, sem chave e sem custo. Só para testar o fluxo; os resultados **não** valem para a avaliação. |

O índice guarda qual embedding foi usado. Ao trocar de provedor ou de modelo de embedding, ele é refeito sozinho na próxima execução do `consultar.py`.

### Integração com a API Java (opcional)

O serviço também pode ficar no ar para a API Java do Vê AI classificar relatos: `uvicorn app.main:app`. Na API Java, colocar `VEAI_RAG_URL=http://localhost:8000` no `.env`, criar um relato pela coleção Postman e consultar o relato depois de alguns segundos: `normaReferencia` deve vir preenchida.

## Contrato da API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Status, modelos e quantos trechos há no índice |
| POST | `/consultar` | JSON: `pergunta` e `modo` (`rag` ou `sem_rag`). Devolve a resposta com as citações já trocadas pela referência, as `fontes` (referência, trecho e similaridade) e `respondidaPelaBase` |
| POST | `/descrever` | `multipart/form-data`: `imagem` (JPEG/PNG/WEBP, até 5 MB) e `modo` (`ambiente` ou `texto`) |
| POST | `/classificar` | JSON: `texto`, `tipoSugerido?`, `gravidadeSugerida?` (enviados pela API Java) e os opcionais `objetos`, `modo` (`rag` ou `sem_rag`) e `relatoId` |
| GET | `/taxonomia`, `/schema/descricao`, `/prompts/{nome}` | Contrato compartilhado |

Respostas de erro: `415` tipo de arquivo inválido, `413` imagem grande demais, `422` entrada inválida, `502` falha na OpenAI, `503` chave não configurada ou índice ausente ou incompatível.

## Modelos

| Uso | Modelo (configurável no `.env`) | Configuração |
|---|---|---|
| Consulta, classificação e descrição | `OPENAI_MODEL` (padrão `gpt-6-luna`, o mesmo da API Java) | Responses API com saída estruturada estrita (`text_format`), `reasoning.effort=none`, `store=false` |
| Embeddings | `OPENAI_EMBEDDING_MODEL` (padrão `text-embedding-3-small`) | Dimensão nativa, ou `OPENAI_EMBEDDING_DIMENSOES` |
| Vector store | numpy (busca exata) | Vetores normalizados e similaridade de cosseno por produto de matrizes |

Modelos sem raciocínio (gpt-4o, gpt-4.1) não aceitam `reasoning`: deixe `OPENAI_REASONING_EFFORT` vazio para eles.

## Justificativas

**Por que RAG na consulta.** Quem precisa adequar um espaço (técnico da prefeitura, gestor de ONG, dono de loja) quer uma resposta curta e verificável, não uma norma de 160 páginas. Um modelo generativo sozinho responde bem em linguagem simples, mas cita itens e medidas de memória e erra números de seção e valores. Com RAG, o modelo responde só com trechos recuperados do acervo e cita cada informação pelo número do trecho; o sistema troca esse número pela referência real. A avaliação compara as duas abordagens nas mesmas perguntas.

**Por que RAG e não fine-tuning, ML ou visão computacional.** O problema é de conhecimento normativo, que muda (a NBR 16537 teve edição nova em 2024) e precisa ser rastreável até o texto original. RAG se atualiza só trocando os documentos e mostra a fonte de cada resposta; fine-tuning exigiria dados de treino que não existem e não mostraria a fonte; ML ou visão computacional não respondem perguntas sobre normas.

**Por que citação por número do trecho.** Se o modelo escrevesse a referência, poderia inventar uma seção plausível. Ele só escreve `[n]`, e o código monta a referência a partir dos metadados; números que não correspondem a um trecho recuperado são removidos.

**Por que a API da OpenAI e não um modelo local.** É o mesmo provedor da API Java do Vê AI, tem saída estruturada estrita (o JSON sempre segue o schema) e embeddings de boa qualidade em português, sem exigir GPU dos integrantes. O custo do índice e das consultas é de centavos.

**Por que chunking por seção.** O número da seção vira metadado do trecho. Assim, a referência é montada a partir do metadado e não pode ser inventada. Seções longas viram várias partes com o mesmo número.

**Por que limiar de similaridade.** Se nenhum trecho passa de `RAG_LIMIAR`, a resposta diz que o acervo não trata do assunto em vez de forçar uma norma parecida. Errar dizendo "não há norma aplicável" é melhor do que fundamentar uma orientação em um trecho que não trata do problema. O valor padrão (0,40) é um ponto de partida para os embeddings da OpenAI e pode ser calibrado com a avaliação.

**Por que desligar o raciocínio do modelo.** Com `reasoning.effort=none`, o modelo responde sem a etapa de raciocínio, que é a parte mais lenta. A tarefa é responder com poucos trechos já recuperados, então o raciocínio estendido traz pouco ganho; a avaliação mostra respostas em torno de 2 a 3 s.

**Por que numpy e não um banco vetorial.** A base tem cerca de mil trechos, não milhões. Multiplicar a consulta pela matriz de vetores dá a busca exata em menos de um milissegundo, sem servidor, sem biblioteca nativa (funciona em qualquer versão do Python) e com o índice em três arquivos, o que facilita reproduzir.

## Avaliação

A avaliação principal é a da consulta (`python avaliar.py perguntas`). Os resultados são gravados em `avaliacao/resultados/`.

As mesmas 18 perguntas (`avaliacao/perguntas.exemplo.csv`) são respondidas com RAG e pela memória do modelo: 16 sobre calçadas, rampas, piso tátil, travessias e estabelecimentos, e 2 fora do escopo. As seções esperadas foram conferidas no texto da NBR 9050:2020 e da NBR 16537:2024.

| Métrica | O que mostra |
|---|---|
| Referência correta | Pelo menos uma referência citada confere com a anotação (a seção anotada ou uma subseção dela) |
| Referência inexistente na base | Referências citadas que não existem na norma ou lei indexada |
| Sem referência fora do escopo | Perguntas que o acervo não cobre e ficaram sem referência, em vez de uma inventada |
| Latência p50/p95 | Tempo de resposta |

### Situações de falha testadas

Além das perguntas fora do escopo na avaliação, os testes automáticos (`pytest`, 66 testes, sem chamar a OpenAI) cobrem as falhas do fluxo:

| Situação | Comportamento esperado | Teste |
|---|---|---|
| Nenhum trecho acima do limiar | Responde que o acervo não trata do assunto, sem fontes | `test_consulta_fora_da_base` |
| Modelo cita um trecho que não existe | Citação removida, sem fonte inventada | `test_consulta_nao_aceita_trecho_inexistente` |
| OpenAI fora do ar, timeout ou recusa | Erro claro em vez de resposta falsa | `test_openai_converte_erros_em_erro_ia` |
| Sem chave da OpenAI | Mensagem dizendo o que configurar | `test_openai_sem_chave_explica_o_que_fazer` |
| Índice gerado com outro modelo | Índice recusado e refeito | `test_indice_de_outro_embedding_e_recusado` |
| Site das leis fora do ar | Segue só com as normas e não tenta de novo a cada execução | `test_preparar_baixa_leis_uma_vez_e_gera_indice` |
| PDF com sumário, rodapés e legendas | Removidos antes da divisão | `test_limpeza_de_pdf_de_norma` |

### Resultados

**Configuração:** modelo `gpt-6-luna` (`reasoning.effort=none`), embedding `text-embedding-3-small`, `CONSULTA_TOP_K=6`, `RAG_LIMIAR=0.40`, 5 fontes indexadas (NBR 9050:2020, NBR 16537:2024, Lei 13.146/2015, Lei 10.098/2000 e Decreto 5.296/2004; 936 trechos), execução de 19/11/2026.

Evidências: `avaliacao/resultados/perguntas_20261119_0126.csv` (todas as respostas, com e sem RAG) e `avaliacao/resultados/relatorio_perguntas.md` (tabela e respostas com RAG comentadas).

**Consulta com e sem RAG** (18 perguntas: 16 no escopo e 2 fora):

| Métrica | Sem RAG | Com RAG |
|---|---|---|
| Referência correta (perguntas no escopo) | 50,0% (8 de 16) | **87,5% (14 de 16)** |
| Referência inexistente na base | 4,5% (1 de 22) | **0,0% (0 de 25)** |
| Sem referência quando a pergunta está fora do escopo | 100% (2 de 2) | 100% (2 de 2) |
| Latência p50 / p95 | 2.286 / 3.521 ms | 2.016 / 2.780 ms |

A conferência de "referência inexistente" considera existente uma seção-mãe sem texto próprio quando ela tem subseções (por exemplo, "6.3.4 Desníveis" existe porque há 6.3.4.1).

**Interpretação**

- **O RAG quase dobra a precisão das referências.** Sem RAG, o modelo conhece a estrutura das normas, mas cita seções genéricas, como "NBR 16537 7.3" para a largura do piso direcional, quando o item certo é 7.3.7. Com RAG, cita o item exato e a resposta vem com o texto da norma para conferência. Para quem vai encaminhar uma adequação à prefeitura, essa diferença decide se a referência é útil.
- **Sem RAG, o modelo cita norma desatualizada.** Na pergunta do orelhão (p10), citou a seção 5.4.6.3 da NBR 9050, que não existe na edição de 2020: nela, a 5.4.6 só remete à NBR 16537. É o tipo de erro que o RAG elimina, porque a referência só pode vir de um trecho do acervo atual.
- **Fora do escopo, os dois modos recusam.** Nas perguntas sobre o horário do metrô e o custo do piso tátil, nenhum citou norma; com RAG, a resposta diz explicitamente que o acervo não trata do assunto.
- **Pergunta de conformidade (p15, loja com degrau):** a resposta combinou a NBR 9050 (substituir parte do degrau por rampa, barra de apoio) e a NBR 16537 (piso de alerta no início e no fim da rampa), que é a orientação prática que o público precisa.
- **Latência:** com RAG ficou um pouco mais rápida, mesmo com a busca adicional, provavelmente porque as respostas baseadas em trechos são mais curtas e diretas. Os dois modos ficam em torno de 2 a 3,5 s.

**Onde falhou e por quê**

| Pergunta | O que aconteceu | Causa provável |
|---|---|---|
| p09, sinalização tátil na travessia | Respondeu só sobre o piso direcional (16537 7.8.5) e não trouxe o piso de alerta da travessia (16537 6.6) | A busca recuperou os trechos sobre travessia do capítulo de sinalização direcional, mais parecidos com a pergunta |
| p10, orelhão na calçada | Não encontrou a regra de elementos suspensos (16537 6.8) e disse que os trechos não especificam | A norma não usa a palavra "orelhão". A falha foi segura: não inventou a resposta |
| p15, loja com degrau | Usou um trecho sobre rampa de acesso a piscina (9050 10.12.2.3) como regra para a rampa da loja | A busca vetorial não distingue o ambiente a que o trecho se aplica; a referência existe, mas o contexto está errado |

Os dois primeiros casos se repetiram em duas execuções, o que indica uma limitação da busca, e não variação do modelo. Melhorias possíveis: busca híbrida (vetorial e por palavra-chave), sinônimos para termos populares ("orelhão" para "elemento suspenso") e aumentar `CONSULTA_TOP_K`. A avaliação permite medir cada mudança nas mesmas perguntas.

A classificação de relatos (`python avaliar.py relatos`) e a descrição de fotos têm avaliação pronta no repositório, mas não foram executadas nesta entrega; o foco é a consulta.

## Uso responsável e limitações

- **Não substitui projeto nem vistoria técnica.** A consulta resume o que o acervo diz; adequações de obra devem ser feitas por profissional habilitado, e a prefeitura pode ter regras locais mais exigentes.
- **Só sabe o que está no acervo.** Perguntas sobre temas fora das normas e leis indexadas ficam sem resposta (de propósito). Se uma norma for atualizada, é preciso trocar o PDF; o índice é refeito sozinho.
- **Pode recuperar o trecho errado.** Perguntas vagas ou com termos diferentes dos da norma podem trazer trechos pouco relevantes; a resposta sempre mostra as fontes para conferência, e a avaliação mede a taxa de acerto.
- **As perguntas são enviadas à OpenAI.** Não escreva dados pessoais nas perguntas. O serviço usa `store=false`; pelos termos que conhecemos, os dados enviados pela API não são usados para treinar modelos por padrão, mas podem ser retidos por um período para monitoramento de abuso.
- **Sem credenciais no repositório.** Apenas `.env.example`; o `.env` está no `.gitignore`. Os testes nunca usam a chave real.
- **Direitos autorais.** Os PDFs da NBR 9050 e da NBR 16537 não são versionados; a seção "Dados e preparação" diz onde obtê-los.
- **Descrição de fotos (complementar).** A imagem existe só em memória durante a chamada e não é armazenada. Não substitui bengala, cão-guia nem orientação e mobilidade: a latência de alguns segundos a torna inadequada para avisar sobre objetos em movimento rápido.

## Adaptação a mudanças de requisito

| Mudança | Onde |
|---|---|
| Novo documento no acervo (lei municipal, outra norma) | Colocar em `data/fontes/`; o índice é refeito na próxima execução |
| Resposta mais curta, mais formal ou em outro idioma | `app/prompts/consulta_rag.md` |
| Ser mais rigoroso ao citar norma | Subir `RAG_LIMIAR` no `.env` |
| Trocar modelo ou top-k | `.env` |
| Novo tipo de barreira ou gravidade (classificação) | `app/taxonomia.yaml`, junto com os enums da API Java e as constraints do Oracle |
| Usar outro provedor de IA | Implementar o protocolo `ModeloIA` em `app/provedores.py` e registrar em `criar_provedor` |

## Estrutura

```
consultar.py               ponto de entrada: consulta no terminal
avaliar.py                 ponto de entrada: avaliação com e sem RAG
app/
  consultar.py             conversa no terminal
  preparar.py              baixa as leis e monta o índice quando preciso
  services/consulta.py     consulta com e sem RAG, troca das citações
  services/classificacao.py classificação de relatos com e sem RAG
  services/descricao.py    descrição de fotos + regras de segurança
  provedores.py            OpenAI (ChatGPT) e provedor falso
  prompts/                 prompts versionados (.md)
  rag/chunking.py          leitura das fontes, limpeza e divisão por seção ou artigo
  rag/indice.py            índice vetorial em numpy
  rag/ingestao.py          monta o índice
  rag/baixar_leis.py       baixa as leis de acessibilidade do Planalto
  main.py                  rotas FastAPI (integração com a API Java)
  config.py                configuração via .env
  taxonomia.yaml           tipos de barreira, perigos e gravidades
avaliacao/
  perguntas.py             avaliação da consulta com e sem RAG
  perguntas.exemplo.csv    18 perguntas com as seções esperadas
  resultados/              respostas, relatório e resumo da avaliação
  relatos.py, avaliar.py   avaliações das funções complementares
data/fontes/               acervo do RAG (normas ABNT fora do git)
data/indice/               índice gerado
tests/                     66 testes, sem chamadas à OpenAI
```
