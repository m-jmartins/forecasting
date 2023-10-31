# Forecasting
Modelo de forecasting utilizando a biblioteca prophet para geração de metas.

Para executar é necessário criar uma pasta 'data' na raiz do projeto. Após isso, gerar um arquivo .env com as seguintes credencias:
``` 
DW_USER=""
DW_PASSWORD=""
DW_HOST=dw.clickbus.com.br
DW_PORT=3306
DW_NAME=dw
```
Altere a variável 'config' com o caminho para esse .env.

Para regular o período que deseja-se ter o output da previsão, altere os valores das variáveis 'data_inicio_previsao' e 'data_fim_previsao'. Se a variável 'gerar_dados' for igual a 1, então o código gerará um arquivo na pasta 'data' com a base de dados atualizada (D-1) necessária para executar o modelo, se 0 então não gerará dados. É necessário que a VPN-CLICK esteja ativada se for gerar novos dados. 

Selecione todas as células (Ctrl + a) e execute o código (Ctrl + enter). 

Os dados são impressos nessa [planilha](https://docs.google.com/spreadsheets/d/1ljGKmk6-vJcmJPYO0LkBEsbwaqSjHAMv-Oc9OTHRSyo/edit#gid=655679508), em que eles são analisados para gerar as metas.