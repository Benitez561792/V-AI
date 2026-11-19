# Fontes do RAG

Esta pasta é o acervo que a IA consulta para conferir a conformidade de uma barreira com as normas e leis de acessibilidade. O app funciona sem ela; sem fontes, o relato só fica sem `normaReferencia`.

## Já incluídos

- `nbr9050.pdf`: ABNT NBR 9050:2020 (quarta edição) → 549 trechos
- `nbr16537.pdf`: ABNT NBR 16537:2024 (segunda edição) → 110 trechos

Os dois ficam fora do GitHub pelo `.gitignore` (direitos autorais da ABNT). Falta só rodar `python -m app.rag.baixar_leis` para as leis.

## 1. Documentos sugeridos

| Documento | Para quê | Pode ir para o GitHub? |
|---|---|---|
| ABNT NBR 9050 (acessibilidade em edificações e espaço urbano) | Calçadas, rampas, faixa livre, obstáculos suspensos | Não: direitos autorais da ABNT |
| ABNT NBR 16537 (sinalização tátil no piso) | Piso tátil de alerta e direcional | Não: direitos autorais da ABNT |
| Lei 13.146/2015 (Lei Brasileira de Inclusão) | Obrigações de órgãos públicos e estabelecimentos | Sim: lei pública |
| Lei 10.098/2000 e Decreto 5.296/2004 | Acessibilidade em vias, semáforos sonoros e edificações | Sim: legislação pública |
| Guia ou decreto de calçadas da prefeitura | Regras locais de calçada | Sim, se for publicação oficial |

As leis e decretos da tabela são baixados com um comando, que salva o texto em `.txt`, descarta os trechos revogados e registra os nomes em `fontes.yaml`:

```bash
python -m app.rag.baixar_leis
```

Se o download falhar, o script mostra o link para copiar o texto manualmente. Para as normas ABNT, procurem acesso pela biblioteca da FIAP ou pelo próprio site da ABNT, que já disponibilizou normas de acessibilidade para consulta gratuita; confiram a condição atual. Usem só cópias obtidas legalmente.

## 2. Formatos

`.pdf`, `.txt` ou `.md`. PDF escaneado (imagem) não tem texto: passe por OCR antes ou copie o texto para um `.txt`. Para as leis, o mais simples é abrir a página do Planalto, copiar o texto e salvar como `.txt`.

## 3. Nomes exibidos

Copie `fontes.exemplo.yaml` para `fontes.yaml` e associe cada arquivo ao nome que aparece em `normaReferencia` (no máximo 200 caracteres no total, limite do Oracle):

```yaml
nbr9050.pdf: "ABNT NBR 9050"
nbr16537.pdf: "ABNT NBR 16537"
lei13146.txt: "Lei 13.146/2015"
```

## 4. Conferir e gerar o índice

```bash
python -m app.rag.ingestao --listar   # mostra os trechos; não chama a OpenAI
python -m app.rag.ingestao            # gera os embeddings e salva em data/indice/
```

No `--listar`, confiram se cada documento virou vários trechos com o número da seção (`6.12.1`) ou do artigo (`art. 46`). Se um documento aparecer só como `parte 1`, `parte 2`..., o PDF não preservou a numeração no início das linhas.

Como o texto é lido e dividido:

- **PDF:** o texto é extraído com o pdfplumber, que mantém o número da seção na mesma linha do texto. Antes da divisão, saem as linhas de sumário (pontilhado), os cabeçalhos e rodapés que se repetem em todas as páginas e os restos de figuras (cotas como `0,75 0,90` ou `42 mm`).
- **Início:** tudo antes da seção 1 (capa, sumário, prefácio) é descartado.
- **Capítulos:** só são aceitos em sequência (1, 2, 3...), para que itens numerados de legendas de figura ("5 Guia") não virem capítulos falsos.

- **Normas:** linhas que começam com o número da seção seguido de título com inicial maiúscula (`6.12.1 Calçadas`). Linhas do sumário são descartadas.
- **Leis e decretos:** documentos com pelo menos três linhas `Art. N` são divididos por artigo.
- **Outros:** divididos por parágrafos, como `parte N`.

Seções longas viram várias partes com o mesmo número.

## 5. Calibrar

Faça algumas perguntas com `python consultar.py "pergunta" --trechos` e olhe a similaridade dos trechos consultados. Se trechos certos ficam abaixo de `RAG_LIMIAR`, baixe o limiar; se relatos fora do escopo recebem norma, suba.

## 6. Git

O `.gitignore` ignora tudo nesta pasta, para nenhuma norma ABNT ir para o GitHub por engano. Para versionar uma lei pública, acrescente uma exceção no `.gitignore`, por exemplo `!data/fontes/lei13146.txt`.
