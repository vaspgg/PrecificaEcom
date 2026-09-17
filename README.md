# PrecificaEcom

Precificador local para ecommerce, inicialmente Mercado Livre e Shopee.

## Fluxo inicial
1. Escolha do regime tributário e UF da empresa.
2. Identificação do produto por NCM.
3. Modalidade de venda.
4. Modalidade e custo do frete.
5. Custos, Ads e margem desejada.
6. Cálculo do preço recomendado.

## Windows
O workflow `Build Windows EXE` compila automaticamente `PrecificaEcom.exe` em um runner Windows e publica o executável como artefato `PrecificaEcom-Windows`.

## Estado fiscal da V0.1
A estrutura para regras por regime, UF, NCM e vigência já existe. As alíquotas ainda precisam ser validadas e alimentadas; na ausência de regra o programa sinaliza a pendência e não deve ser usado comercialmente para aquele cálculo.
