import os
import pandas as pd
import gspread
import gspread_dataframe as gd
import time
import awswrangler as wr
import boto3

from tqdm.auto import tqdm
from datetime import datetime
from prophet import Prophet #as novas versoes utlizam apenas from prophet import Prophet
from dotenv import load_dotenv

load_dotenv()

## Configurando credenciais google sheets
print('code_sheet:', os.environ.get('CODE_SHEET'))

gc = gspread.service_account(filename = 'key.json')
sh = gc.open_by_key(os.environ.get('CODE_SHEET'))

def query_data_lake(query):
    my_session = boto3.session.Session(
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name='us-east-1'
    )

    df = wr.athena.read_sql_query(query, database="dw_bs", ctas_approach=False, boto3_session=my_session)

    return df

def gerar_dados_completos():
    print('Generating data...')
    inicio = time.time()
    dados = query_data_lake(
    """
        select 
            date,
            business_model,
            sum(gmv) as gmv,
            sum(tickets) as ticket
        from ft_results
        where year(date) >= 2017
        group by 1, 2
        order by 1
    """
    )
    dados['gmv'] = dados['gmv'].astype('float')
    dados['ano'] = pd.DatetimeIndex(dados['date']).year
    dados['mes'] = pd.DatetimeIndex(dados['date']).month
    
    gd.set_with_dataframe(worksheet=sh.worksheet('Dados'), dataframe=dados, include_index=False, \
                          include_column_header=True, resize=True)
    
    total = dados.groupby('date', as_index=False)[['gmv', 'ticket']].sum()
    total.columns = ['date', 'gmv_total', 'ticket_total']

    pivot = pd.pivot_table(data=dados, index='date', columns=['business_model'], values=['gmv', 'ticket'])
    pivot = pivot.reset_index().dropna(axis=1)
    pivot.columns = ['date', 'gmv_ota', 'gmv_outras_otas', 'gmv_parc', 'gmv_wl', 'ticket_ota', 'ticket_outras_otas','ticket_parc', 'ticket_wl']
    pivot = pivot.drop(columns=['gmv_outras_otas','ticket_outras_otas'])
    
    join = pd.merge(pivot, total, on='date')
    join.to_csv('data/gmv_full.csv', sep=',', index=False)
    fim = time.time()
    
    print(f'Data generated! Time: {fim - inicio} s')

def high_season(ds):
    date = pd.to_datetime(ds)
    return date.month == 12 or date.month == 7

def modelo(dados, metrica, data_corte, holidays):
    dados['ds'] = pd.to_datetime(dados['ds'])
    
    # Removendo dos dados o período da queda de vendas na pandemia
    dados.loc[(dados['ds'] > '2020-03-14') & (dados['ds'] < '2020-07-01'), 'y'] = None
    dados['high_season'] = dados['ds'].apply(high_season)

    modelo = Prophet(holidays                = holidays,
                     daily_seasonality       = False, 
                     weekly_seasonality      = True, 
                     yearly_seasonality      = True,
                     interval_width          = 0.8,
                     n_changepoints          = 25,
                     changepoint_range       = 0.85,
                     changepoint_prior_scale = 0.05,
                     holidays_prior_scale    = 10.0,
                     seasonality_prior_scale = 5.0, 
                     seasonality_mode        = 'multiplicative')
    modelo.add_regressor('high_season')
    modelo.fit(dados[dados['ds'] <= data_corte])
    
    return modelo

def previsao(modelo, data_corte, data_previsao):
    # Definindo o período para previsão
    data_corte = datetime.strptime(data_corte, "%Y-%m-%d")
    data_previsao = datetime.strptime(data_previsao, "%Y-%m-%d")
    period = data_previsao - data_corte
    
    data_futuro = modelo.make_future_dataframe(periods=period.days)
    data_futuro['high_season'] = data_futuro['ds'].apply(high_season)
    previsao = modelo.predict(data_futuro)
    
#     previsao['yhat'] = previsao['yhat'] * 1.05 #apply(lambda x: x*1.05) 
    
    return previsao

if __name__ == '__main__':
    # Variaveis a serem modificadas #
    data_inicio_previsao = '2024-02-01'
    data_fim_previsao = '2024-03-30'
    gerar_dados = 1 # caso o dataset esteja desatualizado ou não exista, 1 para gerar ou atualizar e 0 caso contrário

    metricas = ['gmv_total', 'gmv_ota', 'gmv_parc', 'gmv_wl', 'ticket_total', 'ticket_ota', 'ticket_parc', 'ticket_wl']

    calendar = pd.read_table('data/calendar.tsv')
    holidays = calendar[(calendar['ds'] >= '2017-01-01') & (calendar['ds'] <= '2023-12-31')]

    if gerar_dados:
        gerar_dados_completos()

    dataset = pd.read_csv('data/gmv_full.csv')
    dt_cal = dataset['date'].iloc[-1]    # data até onde tem dados reais; ou pode ser definida uma outra data especifica

    for metrica in tqdm(metricas):
        dados = dataset[['date', metrica]].copy()
        dados.columns = ['ds', 'y']
        
        model = modelo(dados, metrica, dt_cal, holidays) 
        forecast = previsao(model, dt_cal, data_fim_previsao)
        
        forecast = forecast[['ds', 'yhat_lower', 'yhat_upper', 'yhat']]
        forecast = forecast[forecast['ds'] >= data_inicio_previsao]
        
        dados['ds'] = pd.to_datetime(dados['ds']) # necessario para fazer o merge
        dados = dados[['ds', 'y']]
        
        forecast = pd.merge(forecast, dados, how='left', on='ds')
        
        gd.set_with_dataframe(worksheet=sh.worksheet(metrica), dataframe=forecast, include_index=False, \
                            include_column_header=True, resize=True)
        
    #     forecast.to_csv('previsoes/'+metrica+'.csv', sep=',', index=False)