# Rubrica de anotação

## Antes de rodar: o que anotar em `anotacoes.csv`

Copie `anotacoes.exemplo.csv` para `anotacoes.csv` e preencha uma linha por foto **antes** de ver a resposta do modelo, para não enviesar a anotação.

| Coluna | Como preencher |
|---|---|
| `arquivo` | Nome do arquivo em `avaliacao/fotos/` |
| `origem` | `propria` ou `vizwiz` |
| `grupo` | `barreira`, `sem_barreira`, `perigo`, `texto` ou `falha` |
| `modo` | `ambiente` ou `texto` |
| `perigos_esperados` | Categorias de perigo visíveis, separadas por `;`, usando as chaves de `app/taxonomia.yaml`. Anote só o que uma pessoa andando ali precisaria saber. |
| `barreira_esperada` | Chave do tipo de barreira estrutural, ou vazio se não houver |
| `secao_esperada` | Seção da norma que trata da barreira (ex.: `6.12.1`), conferida por alguém do grupo na norma. Vazio se não souberem. |
| `imagem_ruim_esperada` | `sim` se a foto está escura, tremida, obstruída ou sem conteúdo útil |
| `observacao` | Contexto livre |

Composição sugerida para 30 a 50 fotos: cerca de 40% `barreira`, 15% `sem_barreira`, 15% `perigo`, 10% `texto` e 20% `falha`. As fotos de calçada precisam ser próprias, porque o VizWiz quase não tem cenas urbanas; ele é ótimo para os casos de falha.

## Depois de rodar: coluna `alucinacao`

Leia `resumo`, `perigos_texto`, `texto_lido` e `justificativa_rag` olhando a foto e dê uma nota:

| Nota | Significado | Exemplos |
|---|---|---|
| 0 | Nada inventado | Descrição incompleta, mas tudo que foi dito está na foto |
| 1 | Alucinação leve | Cor errada, objeto irrelevante que não existe, texto de placa com uma palavra errada |
| 2 | Alucinação grave | Perigo inexistente que faria a pessoa desviar, perigo descrito no lugar errado, barreira inventada, "caminho livre" com obstáculo visível, justificativa que cita exigência que o trecho não tem |

Omissões (perigo que existe e não foi citado) **não** contam como alucinação: elas já aparecem no recall de perigos.

Se possível, duas pessoas anotam as mesmas 10 fotos de forma independente e registram em `notas_revisor` quantas notas coincidiram. Isso mostra se a rubrica é objetiva.

## Cuidados com dados pessoais

Não commite fotos com rostos ou placas de carro legíveis. Desfoque antes ou mantenha as fotos fora do repositório (a pasta `avaliacao/fotos/` está no `.gitignore`) e commite só os CSVs e o relatório.
