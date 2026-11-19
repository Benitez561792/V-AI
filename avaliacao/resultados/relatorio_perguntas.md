# Relatório · Consulta com e sem RAG

Execução: `perguntas_20261119_0126.csv` · Gerado em 19/11/2026 01:28

| Métrica | Sem RAG | Com RAG |
|---|---|---|
| Perguntas respondidas | 18 | 18 |
| Referências citadas | 22 | 25 |
| Referência inexistente na base | 4.5% | 0.0% |
| Referência correta (perguntas no escopo) | 50.0% | 87.5% |
| Sem referência quando a pergunta está fora do escopo | 100.0% | 100.0% |
| Resposta correta (revisão manual) | n/d (0) | n/d (0) |
| Latência p50 / p95 | 2286 ms / 3521 ms | 2016 ms / 2780 ms |

## Respostas com RAG

**p01. Qual a largura mínima da faixa livre da calçada?** ✓

> A faixa livre da calçada deve ter no mínimo 1,20 m de largura. [ABNT NBR 9050:2020 6.12.3] [ABNT NBR 16537:2024 3.13]

Esperado: 9050 6.12.3 · Citado: ABNT NBR 9050:2020 6.12.3 | ABNT NBR 16537:2024 3.13

**p02. Qual a altura livre mínima que a faixa livre da calçada deve ter?** ✓

> A faixa livre da calçada deve ter altura livre mínima de 2,10 m. [ABNT NBR 9050:2020 6.12.3] [ABNT NBR 16537:2024 3.13]

Esperado: 9050 6.12.3 · Citado: ABNT NBR 9050:2020 6.12.3 | ABNT NBR 16537:2024 3.13

**p03. Qual a inclinação transversal máxima permitida na faixa livre da calçada?** ✓

> A inclinação transversal máxima permitida na faixa livre da calçada é de 3 % [ABNT NBR 9050:2020 6.12.1].

Esperado: 9050 6.12.1; 9050 6.12.3 · Citado: ABNT NBR 9050:2020 6.12.1

**p04. Qual a inclinação máxima do rebaixamento de calçada na travessia de pedestres?** ✓

> A inclinação deve ser preferencialmente menor que 5%, mas admite-se até 8,33% (1:12) no sentido longitudinal da rampa central e nas abas laterais [ABNT NBR 9050:2020 6.12.7.3].

Esperado: 9050 6.12.7 · Citado: ABNT NBR 9050:2020 6.12.7.3

**p05. Qual desnível no piso dispensa tratamento especial em uma rota acessível?** ✓

> Desníveis no piso de até 5 mm dispensam tratamento especial. [ABNT NBR 9050:2020 6.3.4.1]

Esperado: 9050 6.3.4 · Citado: ABNT NBR 9050:2020 6.3.4.1

**p06. Qual o tamanho máximo dos vãos de uma grelha que fica na rota de pedestres?** ✓

> Os vãos podem ter no máximo 15 mm. Quando a grelha estiver em rota acessível, ela deve ficar fora do fluxo principal; se isso não for tecnicamente possível, os vãos devem ter no máximo 15 mm e ser instalados perpendicularmente ao fluxo ou ter formato quadriculado ou circular quando houver circulação em mais de um sentido. [ABNT NBR 9050:2020 6.3.5]

Esperado: 9050 6.3.5 · Citado: ABNT NBR 9050:2020 6.3.5

**p07. Como deve ser tratada uma obra sobre o passeio para não prejudicar a circulação?** ✓

> A obra sobre o passeio deve ser sinalizada e isolada, mantendo uma faixa livre com largura mínima de 1,20 m para circulação e garantindo acesso e segurança de pedestres e pessoas com mobilidade reduzida [ABNT NBR 9050:2020 6.12.5].

Esperado: 9050 6.12.5 · Citado: ABNT NBR 9050:2020 6.12.5

**p08. Os semáforos para pedestres precisam ter sinal sonoro?** ✓

> Sim. Os semáforos para pedestres devem ter sinais visuais e sonoros ou vibratórios, sincronizados com os sinais visuais, para favorecer a autonomia de pessoas com deficiência visual [ABNT NBR 9050:2020 5.6.4.3] [ABNT NBR 9050:2020 8.2.2.3].

Esperado: 9050 5.6.4.3; 9050 8.2.2.3 · Citado: ABNT NBR 9050:2020 5.6.4.3 | ABNT NBR 9050:2020 8.2.2.3

**p09. Como deve ser a sinalização tátil no piso em uma travessia de pedestres?** ✗

> A sinalização tátil direcional deve ser implantada transversalmente à calçada, marcando a área de travessia [ABNT NBR 16537:2024 7.8.5]. Quando houver foco semafórico acionável por pedestre, deve ficar alinhada ao dispositivo de acionamento [ABNT NBR 16537:2024 7.8.5]. Se não houver foco semafórico, ou se ele não puder ser acionado pelo pedestre, deve ser direcionada ao eixo do rebaixamento da calçada ou da faixa de travessia elevada [ABNT NBR 16537:2024 7.8.5]. Nas faixas de travessia, ela pode orientar o deslocamento entre uma calçada e outra [ABNT NBR 16537:2024 7.8.8].

Esperado: 16537 6.6 · Citado: ABNT NBR 16537:2024 7.8.5 | ABNT NBR 16537:2024 7.8.8

**p10. Como sinalizar no piso um orelhão ou outro elemento suspenso na calçada?** ✗

> A sinalização suspensa deve ficar acima de 2,10 m do piso; em aplicações essenciais, deve ser complementada por sinalização tátil e ou sonora [ABNT NBR 9050:2020 5.2.8.2.3]. Os trechos não especificam como sinalizar no piso um orelhão ou outro elemento suspenso na calçada.

Esperado: 16537 6.8 · Citado: ABNT NBR 9050:2020 5.2.8.2.3

**p11. Qual deve ser a largura da sinalização tátil direcional?** ✓

> A sinalização tátil direcional no piso deve ter largura entre 0,25 m e 0,40 m, ou pelo menos três elementos de sinalização tátil. [ABNT NBR 16537:2024 7.3.7]

Esperado: 16537 7.3.7 · Citado: ABNT NBR 16537:2024 7.3.7

**p12. Qual a distância mínima entre o piso tátil direcional e paredes ou obstáculos?** ✓

> Deve haver pelo menos 0,60 m entre o piso tátil direcional e paredes, pilares ou outros obstáculos, medidos a partir da borda da sinalização. A distância recomendada é de, no mínimo, 1,00 m. [ABNT NBR 16537:2024 7.7.1]

Esperado: 16537 7.7.1 · Citado: ABNT NBR 16537:2024 7.7.1

**p13. O piso tátil direcional precisa ser contínuo ao longo da calçada?** ✓

> Sim. A sinalização tátil direcional deve manter continuidade e linearidade ao longo de toda a faixa livre da calçada, pelo menos em uma frente de quadra ou entre locais de travessia de pedestres. Devem ser evitados desvios desnecessários. [ABNT NBR 16537:2024 7.8.1]

Esperado: 16537 7.8.1 · Citado: ABNT NBR 16537:2024 7.8.1

**p14. Quando é preciso colocar piso tátil de alerta no início e no fim de uma escada?** ✓

> O piso tátil de alerta deve ser instalado no início e no término de escadas fixas, com ou sem grelhas, e de degraus isolados [ABNT NBR 16537:2024 6.4]. Em escadas com patamares, também deve haver sinalização de alerta no início e no fim de cada trecho quando houver interrupção de pelo menos um corrimão, patamar com comprimento superior a 2,10 m ou patamar com circulação adjacente [ABNT NBR 16537:2024 6.5.2].

Esperado: 16537 6.4; 16537 6.5 · Citado: ABNT NBR 16537:2024 6.4 | ABNT NBR 16537:2024 6.5.2

**p15. Tenho uma loja com um degrau na entrada e sem rampa. O que preciso adequar para clientes cegos?** ✓

> - O degrau na entrada precisa ser parcialmente substituído por uma rampa com largura mínima de 0,90 m, dimensionada conforme o desnível e os parâmetros aplicáveis. O restante pode permanecer como degrau somente se houver, em pelo menos um lado, barra de apoio horizontal ou vertical com comprimento mínimo de 0,30 m e eixo a 0,75 m do piso, sem avançar sobre a área de circulação pública. [ABNT NBR 9050:2020 6.3.4.4]
- A rampa deve ter inclinação máxima de 8,33 %, piso conforme as especificações aplicáveis e corrimão nos dois lados, a 0,70 m do piso. [ABNT NBR 9050:2020 10.12.2.3]
- Para orientação e segurança de clientes cegos, deve haver sinalização tátil de alerta para informar sobre o desnível e indicar o início e o término da rampa. Se a rampa tiver inclinação igual ou superior a 5 %, a sinalização deve ser instalada no início e no término. [ABNT NBR 16537:2024 6.3] [ABNT NBR 16537:2024 6.4]

Esperado: 9050 6.3.4; 9050 6.6; 16537 6.4 · Citado: ABNT NBR 9050:2020 6.3.4.4 | ABNT NBR 9050:2020 10.12.2.3 | ABNT NBR 16537:2024 6.3 | ABNT NBR 16537:2024 6.4

**p16. Qual a inclinação máxima de uma rampa de acesso?** ✓

> A inclinação máxima usual é 8,33 % (1:12), respeitando também os limites de desnível e quantidade de segmentos da rampa [ABNT NBR 9050:2020 6.6.2.1]. Em reformas, quando não houver solução que atenda integralmente a esses limites, podem ser admitidas inclinações superiores, de até 12,5 % (1:8), conforme condições específicas [ABNT NBR 9050:2020 6.6.2.2].

Esperado: 9050 6.6.2 · Citado: ABNT NBR 9050:2020 6.6.2.1 | ABNT NBR 9050:2020 6.6.2.2

**p17. Qual o horário de funcionamento do metrô de São Paulo?** ✓

> Os trechos fornecidos não informam o horário de funcionamento do metrô de São Paulo.

Esperado: nenhuma · Citado: nenhuma

**p18. Quanto custa em média instalar piso tátil por metro quadrado?** ✓

> Os trechos não informam o custo médio para instalar piso tátil por metro quadrado.

Esperado: nenhuma · Citado: nenhuma

## Referências inexistentes sem RAG

- `p10`: NBR 9050 5.4.6.3 | NBR 16537 7.8

## Interpretação

_Escrever a análise do grupo._
