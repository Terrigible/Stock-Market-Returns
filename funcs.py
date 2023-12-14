import os
from glob import glob
from typing import Literal

import numpy as np
import pandas as pd
import requests
from fredapi import Fred
from numba import float64, guvectorize, int64, njit
from pandas.tseries.offsets import BMonthEnd
from requests.exceptions import JSONDecodeError


def read_msci_source(filename):
    df = pd.read_excel(filename, skiprows=6, skipfooter=19, parse_dates=['Date'], date_format='%b %d, %Y')
    df = df.set_axis(['date', 'price'], axis=1)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.replace(',', '', regex=True)
    df['price'] = df['price'].astype(float)
    return df


def read_msci_data(filename_pattern):
    return pd.concat(map(read_msci_source, glob(filename_pattern)))


def read_sti_data():
    return pd.read_csv('data/Straits Times Index USD Gross.csv', parse_dates=['Date'], index_col='Date').rename_axis('date')[['Close']].set_axis(['price'], axis=1)


def read_spx_data():
    return pd.read_csv('data/S&P 500 USD Gross.csv', parse_dates=['Date'], index_col='Date').rename_axis('date')[['Close']].set_axis(['price'], axis=1)


def download_fed_funds_rate():
    fred = Fred()
    fed_funds_rate = fred.get_series('DFF').rename('ffr').rename_axis('date')
    fed_funds_rate.to_csv('data/fed_funds_rate.csv')
    return fed_funds_rate


def load_fed_funds_rate():
    try:
        fed_funds_rate = pd.read_csv('data/fed_funds_rate.csv', parse_dates=['date'], index_col='date')
        if fed_funds_rate.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
        fed_funds_rate = fed_funds_rate['ffr']

    except FileNotFoundError:
        fed_funds_rate = download_fed_funds_rate()

    fed_funds_rate_1m = fed_funds_rate.div(36000).add(1).resample('BM').prod().pow(12).sub(1).mul(100)

    return fed_funds_rate, fed_funds_rate_1m


def download_us_treasury_rate(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    fred = Fred()
    treasury = fred.get_series(f'DGS{duration}').rename_axis('date').rename('rate')

    return treasury


def load_us_treasury_rate(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    try:
        treasury_rate = pd.read_csv(f'data/us_treasury_{duration.lower()}.csv', parse_dates=['date'], index_col='date')
        if treasury_rate.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
        treasury_rate = treasury_rate['rate']

    except FileNotFoundError:
        treasury_rate = download_us_treasury_rate(duration)
        treasury_rate.to_csv(f'data/us_treasury_{duration.lower()}.csv')

    if duration == '20':
        treasury_rate = treasury_rate.fillna(load_us_treasury_rate('10')['rate'].add(load_us_treasury_rate('30')['rate']).div(2))

    treasury_rate = treasury_rate.resample('D').last().interpolate().reset_index().set_index('date')

    return treasury_rate


def load_us_treasury_returns(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    treasury = load_us_treasury_rate(duration)
    treasury['old_issue_start_price'] = treasury['rate'].div(100).add(1).pow(-eval(duration.replace('MO', '/12'))).shift()
    treasury['old_issue_end_price'] = treasury['rate'].div(100).add(1).pow(1 / 365 - eval(duration.replace('MO', '/12')))
    treasury['change'] = treasury['old_issue_end_price'].div(treasury['old_issue_start_price'])
    treasury['price'] = np.exp(np.log(treasury['change']).cumsum()).fillna(1)

    return treasury


def read_shiller_sp500_data(net=False):
    df = pd.read_excel('data/ie_data.xls', 'Data', skiprows=range(7), skipfooter=1).drop(['Unnamed: 13', 'Unnamed: 15'], axis=1)
    df['Date'] = df['Date'].apply(lambda x: pd.to_datetime(f'{x:.2f}', format='%Y.%m'))
    df = df.set_index('Date')
    shiller_sp500 = df['P'].add(df['D'].ffill().div(12).mul(0.7 if net else 1)).div(df['P'].shift(1)).fillna(1).cumprod()
    shiller_sp500 = pd.DataFrame(shiller_sp500.rename_axis('date').rename('price'))
    return shiller_sp500


def download_usdsgd():
    usdsgd_response = requests.get(
        'https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610ora/exchange_rates_end_of_period_daily/views/exchange_rates_end_of_period_daily',
        headers={
            'keyid': os.environ['MAS_EXCHANGE_RATE_API_KEY']
        }
    )
    usdsgd = (
        pd.DataFrame(usdsgd_response.json()['elements'])
        .loc[:, ['end_of_day', 'usd_sgd']]
        .assign(
            end_of_day=lambda df: pd.to_datetime(df['end_of_day']),
            usd_sgd=lambda df: pd.to_numeric(df['usd_sgd']),
        )
        .set_index('end_of_day')
        .rename_axis('date')
    )
    return usdsgd


def load_usdsgd():
    try:
        usdsgd = pd.read_csv('data/usdsgd.csv', parse_dates=['date'], index_col='date')
        if usdsgd.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D'):
            raise FileNotFoundError
    except FileNotFoundError:
        usdsgd = download_usdsgd()
        usdsgd.to_csv('data/usdsgd.csv')
    return usdsgd


def download_mas_swap_points():
    swap_points_response = requests.get(
        f'https://www.mas.gov.sg/-/media/mas-media-library/statistics/exchange-rates/swap-points/SwapPoint_{pd.Timestamp("today").strftime("%Y%m")}.xlsx',
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    if swap_points_response.status_code == 200:
        with open('data/SwapPoint.xlsx', 'wb') as f:
            f.write(swap_points_response.content)
    else:
        raise Exception(f'Error downloading MAS swap points: {swap_points_response.status_code} {swap_points_response.reason}')


def read_mas_swap_points():
    df = pd.concat(pd.read_excel('data/SwapPoint.xlsx', None, skiprows=3, skipfooter=6, index_col=0,
                   header=[0, 1]).values(), axis=1).unstack().dropna().reset_index().rename({'level_0': 'month', 'level_1': 'tenor', 'level_2': 'day', 0: 'swap_points'}, axis=1)
    df['date'] = df['month'].dt.to_period('M').dt.to_timestamp() + pd.TimedeltaIndex(df['day'].sub(1), unit='D')
    swap_points = df.set_index('date').drop(columns=['month', 'day'])
    swap_points = swap_points.pivot_table(columns='tenor', index='date').droplevel(0, axis=1)
    return swap_points


def load_mas_swap_points():
    try:
        swap_points = read_mas_swap_points()
    except FileNotFoundError:
        download_mas_swap_points()
        swap_points = read_mas_swap_points()
    if (
        pd.Timestamp('today').tz_localize('Asia/Singapore')
        > (swap_points.index[-1] + pd.offsets.MonthBegin(2) + pd.offsets.Week(weekday=0) + pd.offsets.Hour(12)).tz_localize('Asia/Singapore')
    ):
        download_mas_swap_points()
    swap_points = read_mas_swap_points()
    return swap_points


def download_sgd_neer():
    sgd_neer_response = requests.get(
        f'https://www.mas.gov.sg/-/media/mas-media-library/statistics/exchange-rates/s$neer/S$NEER_{pd.Timestamp("today").strftime("%Y%m")}.xlsx',
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    if sgd_neer_response.status_code == 200:
        with open('data/S$NEER.xlsx', 'wb') as f:
            f.write(sgd_neer_response.content)
    else:
        raise Exception(f'Error downloading MAS swap points: {sgd_neer_response.status_code} {sgd_neer_response.reason}')


def read_sgd_neer():
    sgd_neer = pd.concat(pd.read_excel('data/S$NEER.xlsx', None, names=['date', 'neer'], dtype={'date': str, 'neer': float}, skiprows=6).values()).dropna().reset_index(drop=True)
    sgd_neer['date'] = pd.to_datetime(pd.DataFrame(sgd_neer['date'].str.split().apply(lambda x: ([np.nan] * (3-len(x)) + x)).to_list()).ffill().sum(axis=1), format='%Y%b%d')
    return sgd_neer.set_index('date')


def load_sgd_neer():
    try:
        sgd_neer = read_sgd_neer()
    except FileNotFoundError:
        download_sgd_neer()
        sgd_neer = read_sgd_neer()
    if (
        pd.Timestamp('today').tz_localize('Asia/Singapore')
        > (sgd_neer.index[-1] + pd.offsets.MonthBegin(2) + pd.offsets.Week(weekday=0) + pd.offsets.Hour(12)).tz_localize('Asia/Singapore')
    ):
        download_sgd_neer()
    return sgd_neer


def download_sgd_interest_rates():
    sgd_interest_rates_response = requests.get(
        'https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610mssql/domestic_interest_rates_daily/views/domestic_interest_rates_daily',
        headers={
            'keyid': os.environ['MAS_INTEREST_RATE_API_KEY']
        }
    )

    sgd_interest_rates = (
        pd.DataFrame(sgd_interest_rates_response.json()['elements'])
        .loc[:, ['end_of_day', 'interbank_overnight', 'sora']]
        .assign(
            end_of_day=lambda df: pd.to_datetime(df['end_of_day']),
            interbank_overnight=lambda df: pd.to_numeric(df['interbank_overnight']),
            sora=lambda df: pd.to_numeric(df['sora']),
        )
        .drop_duplicates(subset='end_of_day')
        .set_index('end_of_day')
        .rename_axis('date')
    )
    return sgd_interest_rates


def load_sgd_interest_rates():
    try:
        sgd_interest_rates = pd.read_csv('data/sgd_interest_rates.csv', parse_dates=['date'], index_col='date')
        if sgd_interest_rates.index[-1] < pd.to_datetime('today') + BMonthEnd(-1):
            raise FileNotFoundError

    except FileNotFoundError:
        sgd_interest_rates = download_sgd_interest_rates()
        sgd_interest_rates.to_csv('data/sgd_interest_rates.csv')

    sgd_interest_rates_1m = sgd_interest_rates.resample('D').ffill().div(36500).add(1).resample('BM').prod().pow(12).sub(1).mul(100).replace(0, np.nan)
    sgd_interest_rates_1m.loc['2014-01-31', 'interbank_overnight'] = np.nan
    sgd_interest_rates_1m['sgd_ir_1m'] = sgd_interest_rates_1m['interbank_overnight'].fillna(sgd_interest_rates['sora'])
    return sgd_interest_rates, sgd_interest_rates_1m


def download_sg_cpi():
    try:
        sg_cpi_response = requests.get('https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212882')
        sg_cpi = pd.DataFrame(sg_cpi_response.json()['Data']['row'][0]['columns'])
        sg_cpi = sg_cpi.set_axis(['date', 'sg_cpi'], axis=1)
        sg_cpi['date'] = pd.to_datetime(sg_cpi['date'], format='%Y %b')
        sg_cpi = sg_cpi.set_index('date').resample('BM').last()
    except JSONDecodeError:
        sg_cpi = pd.read_csv('data/sg_cpi.csv', index_col='date')
    return sg_cpi


def load_sg_cpi():
    try:
        sg_cpi = pd.read_csv('data/sg_cpi.csv', parse_dates=['date'], index_col='date')
        if sg_cpi.index[-1] + pd.DateOffset(days=55) < pd.to_datetime('today'):
            raise FileNotFoundError
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
    us_cpi = us_cpi.set_axis(['date', 'us_cpi'], axis=1)
    us_cpi = us_cpi.set_index('date')
    return us_cpi


def load_us_cpi():
    try:
        us_cpi = pd.read_csv('data/us_cpi.csv', parse_dates=['date'], index_col='date')
        if us_cpi.index[-1] + pd.DateOffset(days=45) < pd.to_datetime('today'):
            raise FileNotFoundError
        return us_cpi
    except FileNotFoundError:
        us_cpi = download_us_cpi()
        us_cpi.to_csv('data/us_cpi.csv')
        return us_cpi


@njit
def calculate_return(ending_index: int, dca_length: int, monthly_returns: pd.Series | np.ndarray, investment_horizon=None):
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
def calculate_return_vector(dca_length: int, monthly_returns: pd.Series | np.ndarray, investment_horizon: int, res=np.array([])):
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
def calculate_lumpsum_return_with_fees_and_interest_vector(variable_transaction_fees: float, fixed_transaction_fees: float, annualised_holding_fees: float, total_investment: float, dca_length: int, dca_interval: int, investment_horizon: int, monthly_returns: pd.Series | np.ndarray, interest_rates: pd.Series | np.ndarray, res=np.array([])):
    if investment_horizon < dca_length:
        raise ValueError(f'Investment horizon ({investment_horizon}) must be greater than or equal to DCA length ({dca_length})')
    if fixed_transaction_fees >= total_investment / dca_length * dca_interval:
        raise ValueError(f'Fixed fees ({fixed_transaction_fees}) must be less than the amount invested in each DCA ({total_investment / dca_length * dca_interval})')
    if dca_interval > dca_length:
        raise ValueError(f'DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})')
    if dca_interval >= investment_horizon/2:
        print(f'Warning: DCA interval ({dca_interval}) is large relative to investment horizon ({investment_horizon}). Figures might not be representative of market returns')
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
def calculate_dca_return_with_fees_and_interest_vector(variable_transaction_fees: float, fixed_transaction_fees: float, annualised_holding_fees: float, monthly_amount: float, dca_length: int, dca_interval: int, monthly_returns: pd.Series | np.ndarray, interest_rates: pd.Series | np.ndarray, res=np.array([])):
    total_investment = monthly_amount * dca_length
    dca_amount = monthly_amount * dca_interval
    if fixed_transaction_fees >= dca_amount:
        raise ValueError('Fixed fees must be less than the amount invested in each DCA')
    if dca_interval > dca_length:
        raise ValueError(f'DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})')
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


def add_return_columns(df: pd.DataFrame, periods: list[str], durations: list[int]):
    for period, duration in zip(periods, durations):
        df[f'{period}_cumulative'] = df['price'].pct_change(periods=duration)
    for period, duration in zip(periods, durations):
        df[f'{period}_annualized'] = (1 + df[f'{period}_cumulative'])**(12/duration) - 1


__all__ = [
    'read_msci_data',
    'read_sti_data',
    'read_spx_data',
    'load_fed_funds_rate',
    'load_us_treasury_rate',
    'load_us_treasury_returns',
    'read_shiller_sp500_data',
    'load_usdsgd',
    'load_mas_swap_points',
    'load_sgd_neer',
    'load_sgd_interest_rates',
    'load_sg_cpi',
    'load_us_cpi',
    'calculate_return',
    'calculate_return_vector',
    'calculate_lumpsum_return_with_fees_and_interest_vector',
    'calculate_dca_return_with_fees_and_interest_vector',
    'add_return_columns'
]
