# Roteiro da apresentação · Disruptive Architectures

A apresentação vale 30% e tem quatro critérios: funcionamento, arquitetura/fluxo/limitações, adaptação a uma mudança de requisito e participação. Cada parte abaixo indica quem fala; ajustem como preferirem, mas todos precisam falar.

## Antes de começar (checklist)

- [ ] `python consultar.py` responde sem o aviso de provedor falso
- [ ] API Java com `VEAI_RAG_URL` apontando para o serviço
- [ ] Postman da API Java aberto, com login feito
- [ ] Terminal aberto na pasta do serviço, com o ambiente ativado e `python consultar.py` já rodado uma vez
- [ ] Relatórios de avaliação abertos (`avaliacao/resultados/`)
- [ ] Editor aberto em `app/taxonomia.yaml` e `.env`, para a mudança de requisito
- [ ] Plano B: serviço rodando também localmente, caso a rede falhe

## 1. Problema e solução (1 min) · qualquer integrante

A cidade não foi feita para quem não enxerga, e quem precisa adequar um espaço (prefeitura, ONG, dono de loja) raramente sabe o que as normas exigem. A IA deste repositório é uma consulta especializada: responde com base na NBR 9050, na NBR 16537 e nas leis de acessibilidade, sempre citando de onde tirou a informação.

## 2. Funcionamento (3 min) · Pedro

Tudo no terminal, com `python consultar.py`:

1. **Pergunta técnica:** "Qual a largura mínima da faixa livre?" Mostrar a resposta e a fonte (`ABNT NBR 9050:2020 6.12.3`).
2. **Conformidade de um estabelecimento:** "Tenho uma loja com um degrau na entrada e sem rampa. O que preciso adequar para clientes cegos?" A resposta vem item por item, cada um com a sua norma.
3. **Com e sem RAG lado a lado:** `python consultar.py "Como sinalizar um orelhão na calçada?" --comparar`. Sem RAG, o modelo cita de memória e as referências não são conferidas; com RAG, cada informação aponta para o trecho real.
4. **Fora do escopo:** "Qual o horário do metrô?" O sistema diz que o acervo não trata disso, em vez de inventar.
5. **Classificação de relato (bônus):** `python -m app.classificar "O orelhão está na calçada sem nada no piso para avisar"`: tipo, gravidade e norma descumprida, prontos para encaminhar.

## 3. Arquitetura, fluxo e limitações (3 min) · Pedro e Lucas

- Diagramas do README: pergunta → busca no acervo (índice vetorial) → OpenAI responde só com os trechos → o sistema troca as citações pela referência real.
- Por que a referência não pode ser inventada: o modelo só cita números de trecho, e o sistema troca cada número pela seção real tirada dos metadados.
- Integração opcional: a API Java do Vê AI chama a classificação quando um relato é criado; se o serviço cair, o relato existe do mesmo jeito, só sem norma.
- **Resultados:** a tabela com e sem RAG do `relatorio_perguntas.md` (referência inexistente, referência correta, recusa fora do escopo) e o principal achado da interpretação.
- **Limitações** (dizer antes que perguntem):
  - a referência só é tão boa quanto a base indexada;
  - relatos curtos e ambíguos ("buraco perto da rampa") confundem o tipo;
  - o texto do relato e as fotos vão para a OpenAI, o que precisa estar no consentimento;
  - no produto, a descrição com latência de segundos não serve para avisar sobre carros em movimento: o Vê AI complementa a bengala e o cão-guia, não os substitui.

## 4. Mudança de requisito (preparada, 2 a 4 min) · Pedro

O professor vai pedir uma mudança na hora. As prováveis, com o passo a passo:

| Pedido | O que fazer | Como mostrar |
|---|---|---|
| Classificar um novo tipo de barreira (ex.: "bueiro aberto") | Novo valor em `app/taxonomia.yaml`, reiniciar | `python -m app.classificar` com um relato do novo tipo. Explicar que, no produto, o enum `TipoRelato` e a constraint do Oracle mudam junto |
| Incluir um novo documento na base (ex.: lei municipal) | Copiar para `data/fontes/` | `python consultar.py` com uma pergunta sobre o novo documento (o índice é refeito sozinho) |
| Ser mais rigoroso ao citar norma | Subir `RAG_LIMIAR` no `.env`, reiniciar | O mesmo relato limítrofe passa a vir com `semNormaAplicavel` |
| Trocar de modelo | `OPENAI_MODEL` no `.env`, reiniciar | `python consultar.py` com a mesma pergunta, comparando as respostas |
| Resposta mais curta, mais formal ou em outro idioma | Editar `app/prompts/consulta_rag.md` | Mesma pergunta no `python consultar.py`, nova resposta |
| Responder também sobre outro tema (ex.: acessibilidade para cadeirantes) | Novos documentos em `data/fontes/` e ajuste do público no `consulta_rag.md` | Pergunta sobre o tema novo |
| Devolver um campo novo (ex.: prazo sugerido) | Campo em `RespostaClassificacaoRag` e `ClassificarResponse` (`app/schemas.py`), repassar em `classificacao.py` | `python -m app.classificar` mostra o campo |
| Funcionar sem a OpenAI | Já previsto: o serviço responde 502 (OpenAI fora) ou 503 (sem chave) e a API Java segue sem norma | Parar o serviço e criar um relato no Postman: o relato é criado com `normaReferencia` nula |

Ensaiem pelo menos as três primeiras no dia 18/11, cronometrando.

## 5. Encerramento (30 s) · qualquer integrante

O que o grupo aprendeu e o próximo passo do produto.

## Perguntas prováveis

- **Por que RAG e não fine-tuning?** A norma muda e a base precisa de fonte rastreável; o RAG mostra o trecho exato e se atualiza só reindexando.
- **Como sabem que funciona?** Avaliação com e sem RAG nos mesmos relatos, métricas no repositório.
- **E se o modelo escolher um trecho errado?** A justificativa é revisada na avaliação (coluna `justificativa_fiel`), e o gestor sempre vê o trecho, não só o número.
- **Por que não um banco vetorial?** Cerca de mil trechos: busca exata em memória com numpy, sem servidor e reproduzível com três arquivos.
- **Por que a descrição usa outro provedor?** Responder com a decisão real do grupo.
