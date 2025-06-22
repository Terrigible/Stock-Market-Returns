import asyncio
import json
import os
import re
from glob import glob
from itertools import chain

import httpx
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pandas.tseries.offsets import BMonthEnd
from requests.exceptions import JSONDecodeError


def read_msci_data(filename_pattern: str):
    return (
        pd.read_csv(glob(filename_pattern)[0], index_col="Date", parse_dates=["Date"])
        .rename_axis("date")
        .set_axis(["price"], axis=1)
    )


def read_ft_data(filename):
    df = pd.read_csv(
        f"data/{filename}.csv",
        parse_dates=["date"],
        index_col="date",
    )[["close"]].set_axis(["price"], axis=1)

    if filename == "S&P 500 USD Gross":
        df.update(
            df.loc[:"1987-12-31"].div(df.loc["1987-12-31"]).mul(df.loc["1988-01-04"])
        )

    return df


def get_fred_series(series_id: str) -> pd.Series:
    res = httpx.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": os.environ["FRED_API_KEY"],
            "file_type": "json",
        },
    )
    return (
        pd.DataFrame(res.json()["observations"])
        .assign(date=lambda df: pd.to_datetime(df["date"]))
        .set_index("date")
        .loc[:, "value"]
        .replace(".", np.nan)
        .astype(float)
        .rename(series_id)
    )


def download_fed_funds_rate():
    fed_funds_rate = get_fred_series("DFF").rename("ffr")
    fed_funds_rate.to_csv("data/fed_funds_rate.csv")
    return fed_funds_rate


def load_fed_funds_rate():
    try:
        fed_funds_rate = pd.read_csv(
            "data/fed_funds_rate.csv", parse_dates=["date"], index_col="date"
        )
        if fed_funds_rate.index[-1] < pd.to_datetime("today") + BMonthEnd(
            -1, True
        ) and os.environ.get("FRED_API_KEY", None):
            raise FileNotFoundError
        fed_funds_rate = fed_funds_rate["ffr"]

    except FileNotFoundError:
        fed_funds_rate = download_fed_funds_rate()

    fed_funds_rate_1m = (
        fed_funds_rate.div(36000).add(1).resample("BME").prod().pow(12).sub(1).mul(100)
    )

    return fed_funds_rate, fed_funds_rate_1m


async def download_us_treasury_rates_async():
    durations = ["1MO", "3MO", "6MO", "1", "2", "3", "5", "7", "10", "20", "30"]
    async with httpx.AsyncClient() as client:
        tasks = (
            client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": f"DGS{duration}",
                    "api_key": os.environ["FRED_API_KEY"],
                    "file_type": "json",
                },
            )
            for duration in durations
        )
        responses = await asyncio.gather(*tasks)
    treasury_rates = pd.DataFrame(
        {
            duration: pd.DataFrame(response.json()["observations"])
            .assign(date=lambda df: pd.to_datetime(df["date"]))
            .set_index("date")
            .loc[:, "value"]
            .rename(duration)
            for duration, response in zip(durations, responses)
        }
    )
    treasury_rates = treasury_rates.replace(".", np.nan).astype(float)
    return treasury_rates


async def load_us_treasury_rates_async():
    try:
        treasury_rates = pd.read_csv(
            "data/us_treasury.csv", parse_dates=["date"], index_col="date"
        )
        if treasury_rates.index[-1] < pd.to_datetime("today") + BMonthEnd(
            -1, True
        ) and os.environ.get("FRED_API_KEY", None):
            raise FileNotFoundError

    except FileNotFoundError:
        treasury_rates = await download_us_treasury_rates_async()
        treasury_rates.to_csv("data/us_treasury.csv")

    treasury_rates["20"] = treasury_rates["20"].fillna(
        treasury_rates["10"].add(treasury_rates["30"]).div(2)
    )

    treasury_rates = treasury_rates.resample("D").last().interpolate()
    return treasury_rates


def load_us_treasury_rates():
    return asyncio.run(load_us_treasury_rates_async())


async def load_us_treasury_returns_async():
    treasury_rates = await load_us_treasury_rates_async()
    treasury_returns = pd.DataFrame()
    # Formula taken from https://portfoliooptimizer.io/blog/the-mathematics-of-bonds-simulating-the-returns-of-constant-maturity-government-bond-etfs/
    for duration in treasury_rates.columns:
        rates = treasury_rates[duration]
        rates = rates.div(100)
        prev_rates = rates.shift(1)
        price = (
            prev_rates.div(365.25)
            .add(
                prev_rates.div(rates).mul(
                    rates.div(2)
                    .add(1)
                    .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
                    .rsub(1)
                )
            )
            .add(
                rates.div(2)
                .add(1)
                .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
            )
            .cumprod()
        )
        price.iloc[price.index.get_indexer([price.first_valid_index()])[0] - 1] = 1
        treasury_returns[duration] = price

    return treasury_returns


def load_us_treasury_returns():
    return asyncio.run(load_us_treasury_returns_async())


def read_shiller_sp500_data(tax_treatment: str):
    df = pd.read_excel(
        "data/ie_data.xls",
        "Data",
        engine="calamine",
        skiprows=range(7),
        skipfooter=1,
        dtype={"Date": str},
    ).drop(["Unnamed: 13", "Unnamed: 15"], axis=1)
    df["Date"] = pd.to_datetime(
        df["Date"].str.pad(7, "right", "0"), format="%Y.%m"
    ).add(BMonthEnd(0))
    df = df.set_index("Date")
    shiller_sp500 = (
        df["P"]
        .add(df["D"].ffill().div(12).mul(0.7 if tax_treatment == "Net" else 1))
        .div(df["P"].shift(1))
        .fillna(1)
        .cumprod()
    )
    shiller_sp500 = pd.DataFrame(shiller_sp500.rename_axis("date").rename("price"))
    return shiller_sp500


def download_mas_sgd_fx():
    sgd_fx_response = requests.get(
        "https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610ora/exchange_rates_end_of_period_daily/views/exchange_rates_end_of_period_daily",
        headers={"keyid": os.environ["MAS_EXCHANGE_RATE_API_KEY"]},
        timeout=20,
    )
    sgd_fx = (
        pd.DataFrame(sgd_fx_response.json()["elements"])
        .drop(columns=["preliminary"])
        .assign(
            end_of_day=lambda df: pd.to_datetime(df["end_of_day"]),
        )
        .set_index("end_of_day")
        .astype(float)
        .rename_axis("date")
    )
    sgd_fx.update(sgd_fx.filter(like="100").div(100))
    sgd_fx.columns = (
        sgd_fx.columns.str.replace("_100", "").str.replace("_sgd", "").str.upper()
    )
    return sgd_fx


def load_mas_sgd_fx():
    try:
        sgd_fx = pd.read_csv("data/sgd_fx.csv", parse_dates=["date"], index_col="date")
        if sgd_fx.index[-1] < pd.to_datetime("today") + BMonthEnd(
            -1, True
        ) and os.environ.get("MAS_EXCHANGE_RATE_API_KEY", None):
            raise FileNotFoundError
    except FileNotFoundError:
        sgd_fx = download_mas_sgd_fx()
        sgd_fx.to_csv("data/sgd_fx.csv")
    return sgd_fx


async def download_fred_usd_fx_async():
    series = {
        "1_MXN": "DEXMXUS",
        "1_INR": "DEXINUS",
        "1_BRL": "DEXBZUS",
        "AUD": "DEXUSAL",
        "1_THB": "DEXTHUS",
        "1_CHF": "DEXSZUS",
        "1_MYR": "DEXMAUS",
        "1_LKR": "DEXSLUS",
        "1_TWD": "DEXTAUS",
        "1_ZAR": "DEXSFUS",
        "1_HKD": "DEXHKUS",
        "1_SGD": "DEXSIUS",
        "EUR": "DEXUSEU",
        "1_NOK": "DEXNOUS",
        "1_NZD": "DEXUSNZ",
        "1_SEK": "DEXSDUS",
        "1_DKK": "DEXDNUS",
        "1_JPY": "DEXJPUS",
        "1_CNY": "DEXCHUS",
        "1_KRW": "DEXKOUS",
        "GBP": "DEXUSUK",
        "1_CAD": "DEXCAUS",
    }
    async with httpx.AsyncClient() as client:
        tasks = (
            client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series,
                    "api_key": os.environ["FRED_API_KEY"],
                    "file_type": "json",
                },
            )
            for series in series.values()
        )
        responses = await asyncio.gather(*tasks)
    usd_fx = pd.DataFrame(
        {
            currency: pd.DataFrame(response.json()["observations"])
            .assign(date=lambda df: pd.to_datetime(df["date"]))
            .set_index("date")
            .loc[:, "value"]
            .rename(currency)
            for currency, response in zip(series.keys(), responses)
        }
    )
    usd_fx = usd_fx.replace(".", np.nan).astype(float)
    usd_fx.update(usd_fx.filter(like="1_").rdiv(1))
    usd_fx.columns = usd_fx.columns.str.replace("1_", "")
    return usd_fx


async def load_fred_usd_fx_async():
    try:
        usd_fx = pd.read_csv("data/usd_fx.csv", parse_dates=["date"], index_col="date")
        if usd_fx.index[-1] < pd.to_datetime("today") + BMonthEnd(
            -1, True
        ) and os.environ.get("FRED_API_KEY", None):
            raise FileNotFoundError
    except FileNotFoundError:
        usd_fx = await download_fred_usd_fx_async()
        usd_fx.to_csv("data/usd_fx.csv")
    return usd_fx


def load_fred_usd_fx():
    return asyncio.run(load_fred_usd_fx_async())


def load_fred_usdsgd():
    usdsgd = get_fred_series("DEXSIUS").rename("usdsgd")
    return usdsgd


def read_worldbank_usdsgd():
    series = (
        pd.read_csv("data/World Bank USDSGD.csv")
        .T.iloc[4:]
        .rename_axis("date")
        .rename({0: "usd_sgd"}, axis=1)["usd_sgd"]
        .astype(float)
    )
    series.index = pd.to_datetime(series.index.str[:4])
    return series


def load_worldbank_usdsgd():
    series = read_worldbank_usdsgd()
    series = series.set_axis(series.index + pd.DateOffset(months=6))
    return (
        pd.concat(
            [
                series.loc[: load_fred_usdsgd().index[0]],
                load_fred_usdsgd().iloc[0:1],
            ],
        )
        .resample("D")
        .interpolate("pchip")
        .iloc[:-1]
    )


def load_usdsgd():
    try:
        usdsgd = pd.read_csv("data/usdsgd.csv", parse_dates=["date"], index_col="date")
        if (
            usdsgd.index[-1] < pd.to_datetime("today") + BMonthEnd(-1, True)
            and os.environ.get("FRED_API_KEY", None)
            and os.environ.get("MAS_EXCHANGE_RATE_API_KEY", None)
        ):
            raise FileNotFoundError
        usdsgd = usdsgd["usdsgd"]
    except FileNotFoundError:
        df = pd.merge(
            pd.merge(
                load_mas_sgd_fx()["USD"].rename("mas_usdsgd"),
                load_fred_usdsgd().rename("fred_usdsgd"),
                how="outer",
                left_index=True,
                right_index=True,
            ),
            load_worldbank_usdsgd().rename("worldbank_usdsgd"),
            how="outer",
            left_index=True,
            right_index=True,
        )
        usdsgd = (
            df["mas_usdsgd"]
            .fillna(df["fred_usdsgd"])
            .fillna(df["worldbank_usdsgd"])
            .rename("usdsgd")
            .rename_axis("date")
        )
        usdsgd.to_csv("data/usdsgd.csv")
    return usdsgd


def load_mas_swap_points():
    df = pd.read_csv(
        "data/sgd_swap_points.csv",
        parse_dates=["date"],
        index_col="date",
    )
    if df.index[-1] < pd.Timestamp.now() - BMonthEnd(1, True):
        try:
            res = httpx.get(
                "https://www.mas.gov.sg/api/v1/MAS/chart/swappoint",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"
                },
            )
            res.raise_for_status()
            df = (
                pd.DataFrame(res.json()["elements"])
                .loc[::-1, ["dy", "month1", "month3", "month6"]]
                .assign(dy=lambda x: pd.to_datetime(x["dy"]))
                .set_index("dy")
                .rename_axis("date")
            )
            df.to_csv("data/sgd_swap_points.csv")
        except httpx.HTTPError as e:
            print(f"Error fetching new swap points data: {e}")
    return df


def load_sgd_neer():
    df = pd.read_csv(
        "data/sgd_neer.csv",
        parse_dates=["date"],
        index_col="date",
    )
    if df.index[-1] < pd.Timestamp.now() - BMonthEnd(1, True):
        try:
            res = httpx.get(
                "https://www.mas.gov.sg/api/v1/MAS/chart/sneer",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"
                },
            )
            res.raise_for_status()
            df = (
                pd.DataFrame(res.json()["elements"])
                .loc[::-1, ["date", "value"]]
                .assign(
                    date=lambda x: x["date"].astype("datetime64[ns]"),
                    value=lambda x: x["value"].astype(float),
                )
                .set_index("date")
                .rename(columns={"value": "sgd_neer"})
            )
            df.to_csv("data/sgd_neer.csv")
        except httpx.HTTPError as e:
            print(f"Error fetching new NEER data: {e}")
    return df


def download_sgd_interest_rates():
    sgd_interest_rates_response = requests.get(
        "https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610mssql/domestic_interest_rates_daily/views/domestic_interest_rates_daily",
        headers={"keyid": os.environ["MAS_INTEREST_RATE_API_KEY"]},
        timeout=20,
    )

    sgd_interest_rates = (
        pd.DataFrame(sgd_interest_rates_response.json()["elements"])
        .loc[:, ["end_of_day", "interbank_overnight", "sora"]]
        .assign(
            end_of_day=lambda df: pd.to_datetime(df["end_of_day"]),
            interbank_overnight=lambda df: pd.to_numeric(df["interbank_overnight"]),
            sora=lambda df: pd.to_numeric(df["sora"]),
        )
        .drop_duplicates(subset="end_of_day")
        .set_index("end_of_day")
        .rename_axis("date")
    )
    return sgd_interest_rates


def load_sgd_interest_rates():
    try:
        sgd_interest_rates = pd.read_csv(
            "data/sgd_interest_rates.csv", parse_dates=["date"], index_col="date"
        )
        if sgd_interest_rates.index[-1] < pd.to_datetime("today") + BMonthEnd(
            -1
        ) and os.environ.get("MAS_INTEREST_RATE_API_KEY", None):
            raise FileNotFoundError

    except FileNotFoundError:
        sgd_interest_rates = download_sgd_interest_rates()
        sgd_interest_rates.to_csv("data/sgd_interest_rates.csv")

    sgd_interest_rates_1m = (
        sgd_interest_rates.resample("D")
        .ffill()
        .div(36500)
        .add(1)
        .resample("BME")
        .prod()
        .pow(12)
        .sub(1)
        .mul(100)
        .replace(0, np.nan)
    )
    sgd_interest_rates_1m.loc["2014-01-31", "interbank_overnight"] = np.nan
    sgd_interest_rates_1m["sgd_ir_1m"] = sgd_interest_rates_1m[
        "interbank_overnight"
    ].fillna(sgd_interest_rates["sora"])
    return sgd_interest_rates, sgd_interest_rates_1m


def read_sgs_data():
    with open("data/SGS - Historical Prices and Yields - Benchmark Issues.csv") as f:
        file = f.readlines()
        columns = file[4].strip("\n").split(",")
        data = [
            line.strip("\n").split(",")
            for line in file[4:]
            if ('"' not in line) and ("Average" not in line) and (line != "\n")
        ]
    sgs = pd.DataFrame(data, columns=["Year", "Month", "Day", *columns[3:]])
    sgs["Date"] = pd.to_datetime(
        sgs[["Year", "Month", "Day"]].replace("", pd.NA).ffill().sum(axis=1),
        format="%Y%b%d",
    )
    sgs = sgs.set_index("Date").drop(columns=["Year", "Month", "Day"])
    sgs = sgs.set_axis(
        sgs.columns.str.removeprefix(
            "Average Buying Rates of Govt Securities Dealers "
        ),
        axis=1,
    )
    sgs = sgs.replace("", "NaN").astype(float)
    return sgs


def load_sgs_rates():
    sgs = read_sgs_data()
    sgs_yields = sgs.filter(like="Yield")
    sgs_yields = sgs_yields.set_axis(
        sgs_yields.columns.str.removesuffix(" Yield")
        .str.removesuffix(" Bond")
        .str.removesuffix(" T-Bill")
        .str.removesuffix("-Year"),
        axis=1,
    )
    sgs_yields = sgs_yields.resample("D").ffill().ffill()
    return sgs_yields


def load_sgs_returns():
    sgs_rates = load_sgs_rates()
    sgs_returns = pd.DataFrame()
    # Formula taken from https://portfoliooptimizer.io/blog/the-mathematics-of-bonds-simulating-the-returns-of-constant-maturity-government-bond-etfs/
    for duration in sgs_rates.columns:
        rates = sgs_rates[duration]
        rates = rates.div(100)
        prev_rates = rates.shift(1)
        price = (
            prev_rates.div(365.25)
            .add(
                prev_rates.div(rates).mul(
                    rates.div(2).add(1).pow(-2 * (int(duration) - 1 / 365.25)).rsub(1)
                )
            )
            .add(rates.div(2).add(1).pow(-2 * (int(duration) - 1 / 365.25)))
            .cumprod()
        )
        price.iloc[price.index.get_indexer([price.first_valid_index()])[0] - 1] = 1
        sgs_returns[duration] = price

    return sgs_returns


def download_sg_cpi():
    try:
        sg_cpi_response = requests.get(
            "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=20,
        )
        sg_cpi = pd.DataFrame(sg_cpi_response.json()["Data"]["row"][0]["columns"])
        sg_cpi = sg_cpi.set_axis(["date", "sg_cpi"], axis=1)
        sg_cpi["date"] = pd.to_datetime(sg_cpi["date"], format="%Y %b")
        sg_cpi["sg_cpi"] = sg_cpi["sg_cpi"].astype(float)
        sg_cpi = sg_cpi.set_index("date").resample("BME").last()
    except JSONDecodeError:
        sg_cpi = pd.read_csv("data/sg_cpi.csv", index_col="date")
    return sg_cpi


def load_sg_cpi():
    try:
        sg_cpi = pd.read_csv("data/sg_cpi.csv", parse_dates=["date"], index_col="date")
        if sg_cpi.index[-1] + pd.DateOffset(days=55) < pd.to_datetime("today"):
            raise FileNotFoundError
        return sg_cpi
    except FileNotFoundError:
        sg_cpi = download_sg_cpi()
        sg_cpi.to_csv("data/sg_cpi.csv")
        return sg_cpi


async def download_us_cpi_async():
    async with httpx.AsyncClient() as client:
        tasks = (
            client.post(
                "https://api.bls.gov/publicAPI/v2/timeseries/data/",
                json={
                    "seriesid": ["CUSR0000SA0"],
                    "startyear": f"{year}",
                    "endyear": f"{year + 9}",
                    "catalog": "true",
                    "registrationkey": os.environ["BLS_API_KEY"],
                },
                headers={"Content-Type": "application/json"},
            )
            for year in range(1947, pd.to_datetime("today").year, 10)
        )
        responses = await asyncio.gather(*tasks)
    responses = responses[::-1]
    us_cpi = pd.DataFrame(
        chain.from_iterable(
            [response.json()["Results"]["series"][0]["data"] for response in responses]
        )
    ).iloc[::-1]
    us_cpi["month"] = us_cpi["period"].str[-2:]
    us_cpi["date"] = (
        pd.to_datetime(us_cpi["year"] + "-" + us_cpi["month"]) + BMonthEnd()
    )
    us_cpi["value"] = us_cpi["value"].astype(float)
    us_cpi = us_cpi[["date", "value"]]
    us_cpi = us_cpi.set_axis(["date", "us_cpi"], axis=1)
    us_cpi = us_cpi.set_index("date")
    return us_cpi


async def load_us_cpi_async():
    try:
        us_cpi = pd.read_csv("data/us_cpi.csv", parse_dates=["date"], index_col="date")
        if us_cpi.index[-1] + pd.DateOffset(days=45) < pd.to_datetime(
            "today"
        ) and os.environ.get("BLS_API_KEY", None):
            raise FileNotFoundError
        return us_cpi
    except FileNotFoundError:
        us_cpi = await download_us_cpi_async()
        us_cpi.to_csv("data/us_cpi.csv")
        return us_cpi


def load_us_cpi():
    return asyncio.run(load_us_cpi_async())


def add_return_columns(df: pd.DataFrame, periods: list[str], durations: list[int]):
    for period, duration in zip(periods, durations):
        df[f"{period}_cumulative"] = df["price"].pct_change(periods=duration)
    for period, duration in zip(periods, durations):
        df[f"{period}_annualized"] = (1 + df[f"{period}_cumulative"]) ** (
            12 / duration
        ) - 1


def read_greatlink_data(fund_name):
    df = (
        pd.read_excel(
            f"data/GreatLink/{fund_name}.xlsx",
            engine="calamine",
            index_col="Price Date",
            usecols=["Price Date", "Price"],
            na_values=["."],
            parse_dates=["Price Date"],
            date_format="%d/%m/%Y",
        )
        .sort_index()
        .rename_axis("date")
        .rename(columns={"Price": "price"})
    )
    if glob(f"data/GreatLink/{fund_name}_Dividends.xlsx"):
        dividends = (
            pd.read_excel(
                f"data/GreatLink/{fund_name}_Dividends.xlsx",
                engine="calamine",
                index_col="XD Date",
                usecols=["XD Date", "Gross Dividend"],
                na_values=["."],
                parse_dates=["XD Date"],
                date_format="%d/%m/%Y",
            )
            .sort_index()
            .rename_axis("date")
            .rename(columns={"Gross Dividend": "dividend"})
            .ffill()
        )
        df = df.join(dividends)
        df = (
            df["price"]
            .add(df["dividend"].fillna(0))
            .div(df["price"].shift(1))
            .fillna(1)
            .cumprod()
            .to_frame()
        )
    return df


def get_ft_api_key():
    res = httpx.get("https://markets.ft.com/research/webservices/securities/v1/docs")
    source = re.search("source=([0-9a-f]*)", res.content.decode())
    if not source:
        raise ValueError("API key not found in page")
    api_key = source.group(1)
    return api_key


def download_ft_data(symbol: str, api_key: str):
    with httpx.Client() as client:
        details_response = client.get(
            "https://markets.ft.com/research/webservices/securities/v1/details",
            params={
                "source": api_key,
                "symbols": symbol,
            },
        )
        if details_response.is_client_error:
            raise ValueError(details_response.json()["error"]["errors"][0]["message"])
        else:
            details_response.raise_for_status()
        item = details_response.json()["data"]["items"][0]
        ticker = item["basic"]["symbol"]
        currency = item["basic"]["currency"]
        if item["details"]["issueType"] == "IN":
            start_date = pd.Timestamp(item["details"]["inceptionDate"])
        elif item["details"]["issueType"] == "OF":
            historical_tearsheet_response = client.get(
                "https://markets.ft.com/data/funds/tearsheet/historical",
                params={"s": ticker},
                headers={},
            )
            historical_prices_mod = BeautifulSoup(
                historical_tearsheet_response.content, "lxml"
            ).select_one(".mod-tearsheet-historical-prices")

            if historical_prices_mod is None:
                raise ValueError("Unable to retrive inception date")
            data_mod_config = historical_prices_mod.get("data-mod-config")
            start_date = pd.Timestamp(
                json.loads(data_mod_config)["inception"]
            ).tz_convert(None)
        else:
            raise ValueError("Please enter the symbol of a fund or index.")
        response = client.get(
            "https://markets.ft.com/research/webservices/securities/v1/historical-series-quotes",
            params={
                "source": api_key,
                "symbols": symbol,
                "dayCount": (pd.Timestamp.today() - pd.Timestamp(start_date)).days,
            },
        )
        if (
            response.json()["data"]["items"][0]["historicalSeries"].get(
                "historicalQuoteData"
            )
            is None
        ):
            raise ValueError("No data for this fund or index.")
        df = (
            pd.DataFrame(
                response.json()["data"]["items"][0]["historicalSeries"][
                    "historicalQuoteData"
                ]
            )
            .assign(date=lambda df: df["date"].pipe(pd.to_datetime))
            .set_index("date")[::-1]
        )
        df = df[["close"]].set_axis(["price"], axis=1)

        return df, ticker, currency


__all__ = [
    "read_msci_data",
    "load_fed_funds_rate",
    "load_us_treasury_rates_async",
    "load_us_treasury_rates",
    "load_us_treasury_returns_async",
    "load_us_treasury_returns",
    "read_shiller_sp500_data",
    "load_usdsgd",
    "load_mas_sgd_fx",
    "load_fred_usd_fx_async",
    "load_fred_usd_fx",
    "load_mas_swap_points",
    "load_sgd_neer",
    "load_sgd_interest_rates",
    "load_sgs_rates",
    "load_sgs_returns",
    "load_sg_cpi",
    "load_us_cpi_async",
    "load_us_cpi",
    "add_return_columns",
    "read_greatlink_data",
    "read_ft_data",
    "get_ft_api_key",
    "download_ft_data",
]
