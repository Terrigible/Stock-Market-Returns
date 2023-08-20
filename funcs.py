import os

import numpy as np
import pandas as pd
import requests
from requests.exceptions import JSONDecodeError
from fredapi import Fred
from numba import float64, guvectorize, int64, njit
from pandas.tseries.offsets import BMonthEnd

def group_by_b_month_end(dt):
    end_date = dt + BMonthEnd(0)
    return end_date

def read_msci_data(filename):
    df = pd.read_excel(filename, skiprows=6, skipfooter=19)
    df.columns = ['date', 'price']
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.replace(',','', regex=True)
    df['price'] = df['price'].astype(float)
    return df

def extract_financialtimes_data(filepaths):
    dfs = [pd.read_html(filepath)[2].iloc[::-1] for filepath in filepaths]
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'].apply(lambda x: ''.join(x.rsplit(',', maxsplit=2)[-2:])[1:]))
    df = df[df['Date'].isin(pd.date_range(df['Date'].iloc[0], df['Date'].iloc[-1], freq='BM'))]
    df = df.reset_index(drop=True)
    df = df[['Date', 'Close']]
    df.columns = ['date', 'price']
    df = df.set_index('date')
    return df
    
def download_fed_funds_rate():
    fred = Fred()
    fed_funds_rate = fred.get_series('DFF').rename('ffr').rename_axis('date')
    fed_funds_rate.to_csv('data/fed_funds_rate.csv')
    return fed_funds_rate

def load_fed_funds_rate():
    try:
        fed_funds_rate = pd.read_csv('data/fed_funds_rate.csv', parse_dates=['date'])
        if pd.to_datetime(fed_funds_rate['date']).iloc[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
        fed_funds_rate = fed_funds_rate.set_index('date')['ffr']
    
    except FileNotFoundError:
        fed_funds_rate = download_fed_funds_rate()
    
    fed_funds_rate_1m = fed_funds_rate.div(36000).add(1).groupby(group_by_b_month_end).prod().pow(12).sub(1).mul(100)
    
    return fed_funds_rate, fed_funds_rate_1m

def read_shiller_sp500_data(net=False):
    df = pd.read_excel('data/ie_data.xls', 'Data', skiprows=range(7), skipfooter=1).drop(['Unnamed: 13','Unnamed: 15'], axis=1)
    df.index = pd.to_datetime(df['Date'].astype(str).str.split('.').apply(lambda x: '-'.join(x)).str.ljust(7, '0')) + BMonthEnd(0)
    shiller_sp500 = df['P'].add(df['D'].ffill().div(12).mul(0.7 if net else 1)).div(df['P'].shift(1)).fillna(1).cumprod()
    shiller_sp500 = shiller_sp500.rename('shiller_sp500')
    return shiller_sp500

def download_usdsgd_monthly():
    usd_sgd_response = requests.get('https://eservices.mas.gov.sg/api/action/datastore/search.json',
                   params={'resource_id': '10eafb90-11a2-4fbd-b7a7-ac15a42d60b6',
                           'between[end_of_month]': f'1969-12,{pd.to_datetime("today").strftime("%Y-%m")}',
                           'fields': 'end_of_month,usd_sgd'
                           }
                   ).json()
    usdsgd = pd.DataFrame(usd_sgd_response['result']['records'])[['end_of_month', 'usd_sgd']]
    usdsgd['end_of_month'] = pd.to_datetime(usdsgd['end_of_month']) + BMonthEnd()
    return usdsgd

def download_usdsgd_daily():
    usd_sgd_response = usdsgd_daily_response = requests.get('https://eservices.mas.gov.sg/api/action/datastore/search.json',
             params={'resource_id': '95932927-c8bc-4e7a-b484-68a66a24edfe',
                     'between[end_of_day]': f'1988-01-01,{pd.to_datetime("today").strftime("%Y-%m-%d")}',
                     'fields': 'end_of_day,usd_sgd'
                     }).json()
    usdsgd = pd.DataFrame(usdsgd_daily_response['result']['records'])
    usdsgd['end_of_day'] = usdsgd['end_of_day'].apply(pd.to_datetime)
    usdsgd['usd_sgd'] = usdsgd['usd_sgd'].astype(float)
    
    return usdsgd

def read_mas_swap_points():
    df = pd.concat([pd.read_excel('data/SwapPoint_202308.xlsx', None, skiprows=3, skipfooter=6, index_col=0, header=[0,1])[key].unstack().reset_index().rename({'level_0': 'month', 'level_1': 'tenor', 'level_2': 'day', 0: 'swap_points'}, axis=1).dropna() for key in reversed(pd.read_excel('data/SwapPoint_202308.xlsx', None).keys())])
    df['end_of_day'] = pd.to_datetime(df['month'].dt.year.astype('str')+df['month'].dt.month.astype('str').str.pad(2, 'left', '0')+df['day'].astype('str').str.pad(2, 'left', '0'))
    swap_points = df.set_index('end_of_day').drop(columns=['month', 'day'])
    swap_points = swap_points.pivot_table(columns='tenor', index='end_of_day').droplevel(0, axis=1)
    return swap_points

def download_sgd_interest_rates():
    offset = 0
    dfs = []
    with requests.Session() as session:
        while True:
            sgd_interest_rates_response = session.get('https://eservices.mas.gov.sg/api/action/datastore/search.json',
                        params={'resource_id': '9a0bf149-308c-4bd2-832d-76c8e6cb47ed',
                                'between[end_of_day]': f'1987-07-01,{pd.to_datetime("today").strftime("%Y-%m-%d")}',
                                'offset': f'{offset}',
                                'fields': 'end_of_day,interbank_overnight,sora'
                                }
                        ).json()
            df = pd.DataFrame(sgd_interest_rates_response['result']['records'])[['end_of_day', 'interbank_overnight', 'sora']]
            offset += 100
            dfs.append(df)
            if len(df) < 100:
                break
    sgd_interest_rates = pd.concat(dfs)
    sgd_interest_rates['interbank_overnight'] = sgd_interest_rates['interbank_overnight'].astype(float)
    sgd_interest_rates['end_of_day'] = pd.to_datetime(sgd_interest_rates['end_of_day'])
    sgd_interest_rates = sgd_interest_rates.dropna(how='all', subset=['interbank_overnight', 'sora'])
    sgd_interest_rates = sgd_interest_rates.drop_duplicates().drop_duplicates(subset=['end_of_day', 'interbank_overnight']).drop_duplicates(subset=['end_of_day', 'sora'])
    sgd_interest_rates = sgd_interest_rates.reset_index(drop=True)
    sgd_interest_rates = sgd_interest_rates.set_index('end_of_day')
    return sgd_interest_rates

def load_sgd_interest_rates():
    try:
        sgd_interest_rates = pd.read_csv('data/sgd_interest_rates.csv', parse_dates=['end_of_day'])
        if pd.to_datetime(sgd_interest_rates['end_of_day']).iloc[-1] < pd.to_datetime('today') + BMonthEnd(-1):
            raise FileNotFoundError
        sgd_interest_rates = sgd_interest_rates.set_index('end_of_day')
        
    except FileNotFoundError:
        sgd_interest_rates = download_sgd_interest_rates()
        sgd_interest_rates.to_csv('data/sgd_interest_rates.csv')
        
    sgd_interest_rates_1m = sgd_interest_rates.resample('D').ffill().div(36500).add(1).groupby(group_by_b_month_end).prod().pow(12).sub(1).mul(100).replace(0, np.nan)
    sgd_interest_rates_1m.loc['2014-01-31', 'interbank_overnight'] = np.nan
    sgd_interest_rates_1m['sgd_ir_1m'] = sgd_interest_rates_1m['interbank_overnight'].fillna(sgd_interest_rates['sora'])
    return sgd_interest_rates, sgd_interest_rates_1m

def download_sg_cpi():
    try:
        sg_cpi_response = requests.get('https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212882')
        sg_cpi = pd.DataFrame(sg_cpi_response.json()['Data']['row'][0]['columns'])
        sg_cpi.columns = ['date', 'sg_cpi']
        sg_cpi['date'] = pd.to_datetime(sg_cpi['date']) + BMonthEnd()
        sg_cpi = sg_cpi.set_index('date')
    except JSONDecodeError:
        sg_cpi = pd.read_csv('data/sg_cpi.csv', index_col='date')
    return sg_cpi
def load_sg_cpi():
    try:
        sg_cpi = pd.read_csv('data/sg_cpi.csv', parse_dates=['date'])
        if pd.to_datetime(sg_cpi['date']).iloc[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
        sg_cpi = sg_cpi.set_index('date')
        return sg_cpi
    except FileNotFoundError:
        sg_cpi = download_sg_cpi()
        sg_cpi.to_csv('data/sg_cpi.csv')
        return sg_cpi

def download_us_cpi():
    with requests.Session() as session:
        dfs = [
            pd.DataFrame(
                session.post(
                    'https://api.bls.gov/publicAPI/v2/timeseries/data/',
                    json={'seriesid': ['CUSR0000SA0'],
                        'startyear': f'{year}',
                        'endyear': f'{year+9}',
                        'catalog': 'true',
                        'registrationkey': os.environ['BLS_API_KEY']
                        },
                    headers={'Content-Type': 'application/json'}
                ).json()['Results']['series'][0]['data']
            ).iloc[::-1]
        for year in range(1947, 2023, 10)
        ]
    us_cpi = pd.concat(dfs).reset_index(drop=True)
    us_cpi['month'] = us_cpi['period'].str[-2:]
    us_cpi['date'] = pd.to_datetime(us_cpi['year'] + '-' + us_cpi['month']) + BMonthEnd()
    us_cpi['value'] = us_cpi['value'].astype(float)
    us_cpi = us_cpi[['date', 'value']]
    us_cpi.columns = ['date', 'us_cpi']
    us_cpi = us_cpi.set_index('date')
    return us_cpi

def load_us_cpi():
    try:
        us_cpi = pd.read_csv('data/us_cpi.csv', parse_dates=['date'])
        if pd.to_datetime(us_cpi['date']).iloc[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
        us_cpi = us_cpi.set_index('date')
        return us_cpi
    except FileNotFoundError:
        us_cpi = download_us_cpi()
        us_cpi.to_csv('data/us_cpi.csv')
        return us_cpi

@njit
def calculate_return(ending_index, dca_length, monthly_returns, investment_horizon=None):
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    if ending_index < dca_length:
        return np.nan
    share_value = 0
    cash = 1
    for i in range(ending_index - investment_horizon, ending_index - investment_horizon + dca_length):
        cash -= 1/dca_length
        share_value += 1/dca_length
        share_value *= 1 + monthly_returns[i+1]
    for i in range(ending_index - investment_horizon + dca_length, ending_index):
        share_value *= 1 + monthly_returns[i+1]
    return share_value - 1

@guvectorize([(int64, float64[:], int64, float64[:])], '(),(n),()->(n)', target='parallel', nopython=True)
def calculate_return_vector(dca_length, monthly_returns, investment_horizon, res=np.array([])):
    if investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
        share_value = 0
        cash = 1
        for j in range(i - investment_horizon, i - investment_horizon + dca_length):
            cash -= 1/dca_length
            share_value += 1/dca_length
            share_value *= 1 + monthly_returns[j+1]
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= 1 + monthly_returns[j+1]
        res[i] = share_value - 1

@guvectorize([(float64, float64, float64, float64, int64, int64, int64, float64[:], float64[:], float64[:])], '(),(),(),(),(),(),(),(n),(n)->(n)', target='parallel', nopython=True)
def calculate_lumpsum_return_with_fees_and_interest_vector(variable_transaction_fees, fixed_transaction_fees, annualised_holding_fees, total_investment, dca_length, dca_interval, investment_horizon, monthly_returns, interest_rates, res=np.array([])):
    if investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    if fixed_transaction_fees >= total_investment / dca_length * dca_interval:
        raise ValueError('Fixed fees must be less than the amount invested in each DCA')
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
        share_value = 0
        cash = total_investment
        monthly_amount = total_investment / dca_length
        for index, j in enumerate(range(i - investment_horizon, i - investment_horizon + dca_length)):
            if index % dca_interval == 0:
                dca_amount = cash - (dca_length - index - 1) * monthly_amount
                share_value += dca_amount * (1 - variable_transaction_fees) - fixed_transaction_fees
                cash = (dca_length - index - 1) * monthly_amount
            share_value *= ((1 + monthly_returns[j+1]) ** 12 - annualised_holding_fees) ** (1/12)
            cash *= (1 + interest_rates[j+1] / 100) ** (1/12)
        share_value += cash
        cash = 0
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= 1 + monthly_returns[j+1]
        res[i] = (share_value - total_investment) / total_investment

@guvectorize([(float64, float64, float64, float64, int64, int64, float64[:], float64[:], float64[:])], '(),(),(),(),(),(),(n),(n)->(n)', target='parallel', nopython=True)
def calculate_dca_return_with_fees_and_interest_vector(variable_transaction_fees, fixed_transaction_fees, annualised_holding_fees, monthly_amount, dca_length, dca_interval, monthly_returns, interest_rates, res=np.array([])):
    total_investment = monthly_amount * dca_length
    dca_amount = monthly_amount * dca_interval
    if fixed_transaction_fees >= dca_amount:
        raise ValueError('Fixed fees must be less than the amount invested in each DCA')
    for i in range(len(monthly_returns)):
        if i < dca_length:
            res[i] = np.nan
        share_value = 0
        funds_to_invest = 0
        for index, j in enumerate(range(i - dca_length, i)):
            funds_to_invest += monthly_amount
            if (index + 1) % dca_interval == 0:
                share_value += funds_to_invest * (1 - variable_transaction_fees) - fixed_transaction_fees
                funds_to_invest = 0
            share_value *= ((1 + monthly_returns[j+1]) ** 12 - annualised_holding_fees) ** (1/12)
            funds_to_invest *= (1 + interest_rates[j+1] / 100) ** (1/12)
        res[i] = (share_value + funds_to_invest - total_investment) / total_investment
        
def add_return_columns(df, periods, durations):
    for period, duration in zip(periods, durations):
        df[f'{period}_cumulative'] = df['price'].pct_change(periods=duration)
    for period, duration in zip(periods, durations):
        df[f'{period}_annualized'] = (1 + df[f'{period}_cumulative'])**(12/duration) - 1
    for period, duration in zip(periods, durations):
        df[f'{period}_dca_cumulative'] = calculate_return_vector(duration, df['1m_cumulative'].values, duration)
    for period, duration in zip(periods, durations):
        df[f'{period}_dca_annualized'] = (1 + df[f'{period}_dca_cumulative'])**(12/duration) - 1
    for period, duration in zip(periods, durations):
        df[f'{period}_cumulative_difference'] = df[f'{period}_cumulative'] - df[f'{period}_dca_cumulative']
    for period, duration in zip(periods, durations):
        df[f'{period}_difference_in_annualized'] = df[f'{period}_annualized'] - df[f'{period}_dca_annualized']
        
__all__ = [
    'group_by_b_month_end',
    'read_msci_data',
    'extract_financialtimes_data',
    'load_fed_funds_rate',
    'read_shiller_sp500_data',
    'download_usdsgd_monthly',
    'download_usdsgd_daily',
    'read_mas_swap_points',
    'load_sgd_interest_rates',
    'load_sg_cpi',
    'load_us_cpi',
    'calculate_return',
    'calculate_return_vector',
    'calculate_lumpsum_return_with_fees_and_interest_vector',
    'calculate_dca_return_with_fees_and_interest_vector',
    'add_return_columns'
    ]