import asyncio
import os
from glob import glob
from io import BytesIO
from itertools import chain
from typing import Literal
from zipfile import ZipFile

import httpx
import numpy as np
import pandas as pd
import requests
from fredapi import Fred
from pandas.tseries.offsets import BMonthEnd, MonthEnd
from requests.exceptions import JSONDecodeError


def read_msci_source(filename):
    df = pd.read_excel(filename, engine='calamine', skiprows=6, skipfooter=19, parse_dates=['Date'], date_format='%b %d, %Y', thousands=',')
    df = df.set_axis(['date', 'price'], axis=1)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    return df


def read_msci_data(filename_pattern):
    return pd.concat(map(read_msci_source, glob(filename_pattern)))


def read_sti_data():
    df = pd.read_csv('data/Straits Times Index USD Gross.csv', parse_dates=['Date'], index_col='Date').rename_axis('date')[['Close']].set_axis(['price'], axis=1)
    df.loc['2022-10-07'] = 5467.64
    return df


def read_spx_data(tax_treatment: str):
    df = pd.read_csv(f'data/S&P 500 USD {tax_treatment}.csv', parse_dates=['Date'], index_col='Date').rename_axis('date')[['Close']].set_axis(['price'], axis=1)
    if tax_treatment == 'Gross':
        df.update(df.loc[:'1987-12-31'].div(df.loc['1987-12-31']).mul(df.loc['1988-01-04']))
    return df


def read_gmo_data():
    df = pd.read_csv('data/GMO Quality Investment Fund.csv', parse_dates=['Date'], index_col='Date').rename_axis('date')[['Close']].set_axis(['price'], axis=1)
    return df


def download_fed_funds_rate():
    fred = Fred()
    fed_funds_rate = fred.get_series('DFF').rename('ffr').rename_axis('date')
    fed_funds_rate.to_csv('data/fed_funds_rate.csv')
    return fed_funds_rate


def load_fed_funds_rate():
    try:
        fed_funds_rate = pd.read_csv('data/fed_funds_rate.csv', parse_dates=['date'], index_col='date')
        if fed_funds_rate.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D') and os.environ.get('FRED_API_KEY', None):
            raise FileNotFoundError
        fed_funds_rate = fed_funds_rate['ffr']

    except FileNotFoundError:
        fed_funds_rate = download_fed_funds_rate()

    fed_funds_rate_1m = fed_funds_rate.div(36000).add(1).resample('BME').prod().pow(12).sub(1).mul(100)

    return fed_funds_rate, fed_funds_rate_1m


def download_us_treasury_rate(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    fred = Fred()
    treasury = fred.get_series(f'DGS{duration}').rename_axis('date').rename('rate')

    return treasury


def load_us_treasury_rate(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    try:
        treasury_rate = pd.read_csv(f'data/us_treasury_{duration.lower()}.csv', parse_dates=['date'], index_col='date')
        if treasury_rate.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D') and os.environ.get('FRED_API_KEY', None):
            raise FileNotFoundError
        treasury_rate = treasury_rate['rate']

    except FileNotFoundError:
        treasury_rate = download_us_treasury_rate(duration)
        treasury_rate.to_csv(f'data/us_treasury_{duration.lower()}.csv')

    if duration == '20':
        treasury_rate = treasury_rate.fillna(load_us_treasury_rate('10').add(load_us_treasury_rate('30')).div(2))

    treasury_rate = treasury_rate.resample('D').last().interpolate()

    return treasury_rate


def load_us_treasury_returns(duration: Literal['1MO', '3MO', '6MO', '1', '2', '3', '5', '7', '10', '20', '30']):
    rates = load_us_treasury_rate(duration)
    # Formula taken from https://portfoliooptimizer.io/blog/the-mathematics-of-bonds-simulating-the-returns-of-constant-maturity-government-bond-etfs/
    rates = rates.div(100)
    prev_rates = rates.shift(1)
    price = (
        prev_rates.div(365.25)
        .add(
            prev_rates.div(rates)
            .mul(
                rates.div(2).add(1).pow(-2*(eval(duration.replace('MO', '/12')) - 1 / 365.25))
                .rsub(1)
            )
        )
        .add(
            rates.div(2).add(1).pow(-2*(eval(duration.replace('MO', '/12')) - 1 / 365.25))
        )
        .cumprod()
    )

    return price


def read_shiller_sp500_data(tax_treatment: str):
    df = pd.read_excel('data/ie_data.xls', 'Data', engine='calamine', skiprows=range(7), skipfooter=1, dtype={'Date': str}).drop(['Unnamed: 13', 'Unnamed: 15'], axis=1)
    df['Date'] = pd.to_datetime(df['Date'].str.pad(7, 'right', '0'), format='%Y.%m').add(BMonthEnd(0))
    df = df.set_index('Date')
    shiller_sp500 = df['P'].add(df['D'].ffill().div(12).mul(0.7 if tax_treatment == 'Net' else 1)).div(df['P'].shift(1)).fillna(1).cumprod()
    shiller_sp500 = pd.DataFrame(shiller_sp500.rename_axis('date').rename('price'))
    return shiller_sp500


def download_mas_usdsgd():
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


def download_mas_sgd_fx():
    sgd_fx_response = requests.get(
        'https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610ora/exchange_rates_end_of_period_daily/views/exchange_rates_end_of_period_daily',
        headers={
            'keyid': os.environ['MAS_EXCHANGE_RATE_API_KEY']
        }
    )
    sgd_fx = (
        pd.DataFrame(sgd_fx_response.json()['elements'])
        .drop(columns=['preliminary'])
        .assign(
            end_of_day=lambda df: pd.to_datetime(df['end_of_day']),
        )
        .set_index('end_of_day')
        .astype(float)
        .rename_axis('date')
    )
    sgd_fx.update(sgd_fx.filter(like='100').div(100))
    sgd_fx.columns = (
        sgd_fx.columns
        .str.replace('_100', '')
        .str.replace('_sgd', '')
        .str.upper()
    )
    return sgd_fx


def load_mas_sgd_fx():
    try:
        sgd_fx = pd.read_csv('data/sgd_fx.csv', parse_dates=['date'], index_col='date')
        if sgd_fx.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D') and os.environ.get('MAS_EXCHANGE_RATE_API_KEY', None):
            raise FileNotFoundError
    except FileNotFoundError:
        sgd_fx = download_mas_sgd_fx()
        sgd_fx.to_csv('data/sgd_fx.csv')
    return sgd_fx


async def download_fred_usd_fx_async():
    series = {
        '1_MXN': 'DEXMXUS',
        '1_INR': 'DEXINUS',
        '1_BRL': 'DEXBZUS',
        'AUD':   'DEXUSAL',
        '1_THB': 'DEXTHUS',
        '1_CHF': 'DEXSZUS',
        '1_MYR': 'DEXMAUS',
        '1_LKR': 'DEXSLUS',
        '1_TWD': 'DEXTAUS',
        '1_ZAR': 'DEXSFUS',
        '1_HKD': 'DEXHKUS',
        '1_SGD': 'DEXSIUS',
        'EUR':   'DEXUSEU',
        '1_NOK': 'DEXNOUS',
        '1_NZD': 'DEXUSNZ',
        '1_SEK': 'DEXSDUS',
        '1_DKK': 'DEXDNUS',
        '1_JPY': 'DEXJPUS',
        '1_CNY': 'DEXCHUS',
        '1_KRW': 'DEXKOUS',
        'GBP':   'DEXUSUK',
        '1_CAD': 'DEXCAUS',
    }
    async with httpx.AsyncClient() as client:
        tasks = (
            client.get(
                f'https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={os.environ["FRED_API_KEY"]}&file_type=json'
            )
            for series in series.values()
        )
        responses = await asyncio.gather(*tasks)
    usd_fx = pd.DataFrame(
        {
            currency: pd.DataFrame(response.json()['observations']).assign(date=lambda df: pd.to_datetime(df['date'])).set_index('date').loc[:, 'value'].rename(currency)
            for currency, response in zip(series.keys(), responses)
        }
    )
    usd_fx = usd_fx.replace('.', np.nan).astype(float)
    usd_fx.update(usd_fx.filter(like='1_').rdiv(1))
    usd_fx.columns = (
        usd_fx.columns
        .str.replace('1_', '')
    )
    return usd_fx


async def load_fred_usd_fx_async():
    try:
        usd_fx = pd.read_csv('data/usd_fx.csv', parse_dates=['date'], index_col='date')
        if usd_fx.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D') and os.environ.get('FRED_API_KEY', None):
            raise FileNotFoundError
    except FileNotFoundError:
        usd_fx = await download_fred_usd_fx_async()
        usd_fx.to_csv('data/usd_fx.csv')
    return usd_fx


def load_fred_usd_fx():
    return asyncio.run(load_fred_usd_fx_async())


def load_fred_usdsgd():
    fred = Fred()
    usdsgd = fred.get_series('DEXSIUS').rename('usdsgd').rename_axis('date')
    return usdsgd


def download_worldbank_exchange_rates():
    res = requests.get('https://api.worldbank.org/v2/en/indicator/PA.NUS.FCRF?downloadformat=csv')
    res.raise_for_status()
    with ZipFile(BytesIO(res.content)) as zf:
        for filename in zf.namelist():
            if not filename.startswith('API'):
                continue
            with zf.open(filename) as f:
                df = pd.read_csv(f, skiprows=4)
            break
        else:
            raise FileNotFoundError('No file found in zip file')
    series = df.loc[208].loc['1960':'2022'].astype(float)
    return series


def load_worldbank_usdsgd():
    series = download_worldbank_exchange_rates()
    return (
        pd.concat(
            [
                series.set_axis(pd.to_datetime(series.index, format='%Y') + pd.DateOffset(months=6)).loc[:load_fred_usdsgd().index[0]],
                load_fred_usdsgd().iloc[[0]]
            ],
        )
        .resample('D')
        .interpolate('polynomial', order=3)
        .iloc[:-1]
    )


def load_usdsgd():
    try:
        usdsgd = pd.read_csv('data/usdsgd.csv', parse_dates=['date'], index_col='date')
        if usdsgd.index[-1] < pd.to_datetime('today') + BMonthEnd(-1, 'D') and os.environ.get('FRED_API_KEY', None) and os.environ.get('MAS_EXCHANGE_RATE_API_KEY', None):
            raise FileNotFoundError
        usdsgd = usdsgd['usdsgd']
    except FileNotFoundError:
        df = pd.merge(
            pd.merge(
                download_mas_usdsgd().iloc[:, 0].rename('mas_usdsgd'), load_fred_usdsgd().rename('fred_usdsgd'),
                how='outer', left_index=True, right_index=True
            ),
            load_worldbank_usdsgd().rename('worldbank_usdsgd'),
            how='outer', left_index=True, right_index=True
        )
        usdsgd = df['mas_usdsgd'].fillna(df['fred_usdsgd']).fillna(df['worldbank_usdsgd']).rename('usdsgd').rename_axis('date')
        usdsgd.to_csv('data/usdsgd.csv')
    return usdsgd


def download_mas_swap_points():
    swap_points_response = requests.get(
        f'https://www.mas.gov.sg/-/media/mas-media-library/statistics/exchange-rates/swap-points/swappoint_{pd.Timestamp("today").strftime("%Y%m")}.xlsx',
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    if swap_points_response.status_code == 200:
        with open('data/SwapPoint.xlsx', 'wb') as f:
            f.write(swap_points_response.content)
    else:
        raise Exception(f'Error downloading MAS swap points: {swap_points_response.status_code} {swap_points_response.reason}')


def read_mas_swap_points():
    df = pd.concat(pd.read_excel('data/SwapPoint.xlsx', None, engine='calamine', skiprows=3, skipfooter=6, index_col=0,
                   header=[0, 1]).values(), axis=1).unstack().dropna().reset_index().rename({'level_0': 'month', 'level_1': 'tenor', 'level_2': 'day', 0: 'swap_points'}, axis=1)
    df['date'] = df['month'] - MonthEnd() + pd.to_timedelta(df['day'], unit='D')
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
        f'https://www.mas.gov.sg/-/media/mas-media-library/statistics/exchange-rates/s$neer/s$neer_{pd.Timestamp("today").strftime("%Y%m")}.xlsx',
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    if sgd_neer_response.status_code == 200:
        with open('data/S$NEER.xlsx', 'wb') as f:
            f.write(sgd_neer_response.content)
    else:
        raise Exception(f'Error downloading MAS swap points: {sgd_neer_response.status_code} {sgd_neer_response.reason}')


def read_sgd_neer():
    sgd_neer = pd.concat(pd.read_excel('data/S$NEER.xlsx', None, engine='calamine', names=['date', 'neer'], dtype={'date': str, 'neer': float}, skiprows=6).values()).dropna().reset_index(drop=True)
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
        if sgd_interest_rates.index[-1] < pd.to_datetime('today') + BMonthEnd(-1) and os.environ.get('MAS_INTEREST_RATE_API_KEY', None):
            raise FileNotFoundError

    except FileNotFoundError:
        sgd_interest_rates = download_sgd_interest_rates()
        sgd_interest_rates.to_csv('data/sgd_interest_rates.csv')

    sgd_interest_rates_1m = sgd_interest_rates.resample('D').ffill().div(36500).add(1).resample('BME').prod().pow(12).sub(1).mul(100).replace(0, np.nan)
    sgd_interest_rates_1m.loc['2014-01-31', 'interbank_overnight'] = np.nan
    sgd_interest_rates_1m['sgd_ir_1m'] = sgd_interest_rates_1m['interbank_overnight'].fillna(sgd_interest_rates['sora'])
    return sgd_interest_rates, sgd_interest_rates_1m


def download_sg_cpi():
    try:
        sg_cpi_response = requests.get(
            'https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212882',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }
        )
        sg_cpi = pd.DataFrame(sg_cpi_response.json()['Data']['row'][0]['columns'])
        sg_cpi = sg_cpi.set_axis(['date', 'sg_cpi'], axis=1)
        sg_cpi['date'] = pd.to_datetime(sg_cpi['date'], format='%Y %b')
        sg_cpi = sg_cpi.set_index('date').resample('BME').last()
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


async def download_us_cpi_async():
    async with httpx.AsyncClient() as client:
        tasks = (
            client.post(
                'https://api.bls.gov/publicAPI/v2/timeseries/data/',
                json={'seriesid': ['CUSR0000SA0'],
                      'startyear': f'{year}',
                      'endyear': f'{year+9}',
                      'catalog': 'true',
                      'registrationkey': os.environ['BLS_API_KEY']
                      },
                headers={'Content-Type': 'application/json'}
            )
            for year in range(1947, pd.to_datetime('today').year, 10)
        )
        responses = await asyncio.gather(*tasks)
    responses = responses[::-1]
    us_cpi = pd.DataFrame(chain.from_iterable([response.json()['Results']['series'][0]['data'] for response in responses])).iloc[::-1]
    us_cpi['month'] = us_cpi['period'].str[-2:]
    us_cpi['date'] = pd.to_datetime(us_cpi['year'] + '-' + us_cpi['month']) + BMonthEnd()
    us_cpi['value'] = us_cpi['value'].astype(float)
    us_cpi = us_cpi[['date', 'value']]
    us_cpi = us_cpi.set_axis(['date', 'us_cpi'], axis=1)
    us_cpi = us_cpi.set_index('date')
    return us_cpi


async def load_us_cpi_async():
    try:
        us_cpi = pd.read_csv('data/us_cpi.csv', parse_dates=['date'], index_col='date')
        if us_cpi.index[-1] + pd.DateOffset(days=45) < pd.to_datetime('today') and os.environ.get('BLS_API_KEY', None):
            raise FileNotFoundError
        return us_cpi
    except FileNotFoundError:
        us_cpi = await download_us_cpi_async()
        us_cpi.to_csv('data/us_cpi.csv')
        return us_cpi


def load_us_cpi():
    return asyncio.run(load_us_cpi_async())


def add_return_columns(df: pd.DataFrame, periods: list[str], durations: list[int]):
    for period, duration in zip(periods, durations):
        df[f'{period}_cumulative'] = df['price'].pct_change(periods=duration)
    for period, duration in zip(periods, durations):
        df[f'{period}_annualized'] = (1 + df[f'{period}_cumulative'])**(12/duration) - 1


def read_greatlink_data(fund_name):
    df = (
        pd.read_excel(
            f'data/GreatLink/{fund_name}.xlsx',
            engine='calamine',
            index_col='Price Date',
            usecols=['Price Date', 'Price'],
            parse_dates=['Price Date'],
            date_format='%d/%m/%Y',
        )
        .sort_index()
        .rename_axis('date')
        .rename(columns={'Price': 'price'})
    )
    if glob(f'data/GreatLink/{fund_name}_Dividends.xlsx'):
        dividends = (
            pd.read_excel(
                f'data/GreatLink/{fund_name}_Dividends.xlsx',
                engine='calamine',
                index_col='XD Date',
                usecols=['XD Date', 'Gross Dividend'],
                parse_dates=['XD Date'],
                date_format='%d/%m/%Y',
            )
            .sort_index()
            .rename_axis('date')
            .rename(columns={'Gross Dividend': 'dividend'})
        )
        df = df.join(dividends)
        df = df['price'].add(df['dividend'].fillna(0)).div(df['price'].shift(1)).fillna(1).cumprod()
    return df


__all__ = [
    'read_msci_data',
    'read_sti_data',
    'read_spx_data',
    'load_fed_funds_rate',
    'load_us_treasury_rate',
    'load_us_treasury_returns',
    'read_shiller_sp500_data',
    'load_usdsgd',
    'load_mas_sgd_fx',
    'load_fred_usd_fx_async',
    'load_fred_usd_fx',
    'load_mas_swap_points',
    'load_sgd_neer',
    'load_sgd_interest_rates',
    'load_sg_cpi',
    'load_us_cpi_async',
    'load_us_cpi',
    'add_return_columns',
    'read_greatlink_data',
]
