import asyncio
import datetime
import os
from glob import glob
from itertools import chain

import httpx
import pandas as pd
import polars as pl


def read_msci_data(filename_pattern: str):
    return pl.read_csv(
        filename_pattern,
        try_parse_dates=True,
        new_columns=["date", "price"],
    ).with_columns(pl.col("date").cast(pl.Date))


def read_ft_data(filename: str):
    df = pl.read_csv("data/{filename}.csv", try_parse_dates=True).select(
        pl.col("date"), pl.col("close").alias("price")
    )
    if filename == "S&P 500 USD Gross":
        df = df.with_columns(
            pl.when(pl.col("date") <= pl.date(1987, 12, 31))
            .then(
                pl.col("price")
                .truediv(
                    pl.col("price").filter(pl.col("date") == pl.date(1987, 12, 31))
                )
                .mul(pl.col("price").filter(pl.col("date") == pl.date(1988, 1, 4)))
            )
            .otherwise(pl.col("price"))
            .alias("price"),
        )
    return df


def get_fred_series(series_id: str):
    res = httpx.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": os.environ["FRED_API_KEY"],
            "file_type": "json",
        },
    )
    df = (
        pl.read_json(res.content)["observations"]
        .explode()
        .struct.unnest()
        .select(
            pl.col("date").str.to_date(),
            pl.col("value").replace(".", None).cast(pl.Float64),
        )
    )
    return df


def download_fed_funds_rate():
    fed_funds_rate = get_fred_series("DFF").rename({"value": "ffr"})
    fed_funds_rate.write_csv("data/fed_funds_rate.csv")
    return fed_funds_rate


def load_fed_funds_rate():
    fed_funds_rate = pl.read_csv("data/fed_funds_rate.csv", try_parse_dates=True)

    if (
        fed_funds_rate.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(2, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "FRED_API_KEY" in os.environ
    ):
        fed_funds_rate = download_fed_funds_rate()
        fed_funds_rate.write_csv("data/fed_funds_rate.csv")

    fed_funds_rate_1m = (
        fed_funds_rate.with_columns(
            pl.col("date")
            .dt.add_business_days(0, roll="forward")
            .dt.month_end()
            .dt.add_business_days(0, roll="backward"),
        )
        .set_sorted("date")
        .group_by("date")
        .agg(pl.col("ffr").truediv(36000).add(1).product().pow(12).sub(1).mul(100))
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
    treasury_rates = pl.concat(
        [
            pl.DataFrame(response.json()["observations"]).select(
                pl.col("date").str.to_date(),
                pl.col("value").replace(".", None).cast(pl.Float64).alias(duration),
            )
            for duration, response in zip(durations, responses)
        ],
        how="align",
    )
    return treasury_rates


async def load_us_treasury_rates_async():
    treasury_rates = pl.read_csv("data/us_treasury.csv", use_pyarrow=True)

    if (
        treasury_rates.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(2, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "FRED_API_KEY" in os.environ
    ):
        treasury_rates = await download_us_treasury_rates_async()
        treasury_rates.write_csv("data/us_treasury.csv")

    treasury_rates = treasury_rates.with_columns(
        pl.col("20").fill_null(pl.col("10").add(pl.col("30")).truediv(2)),
    )

    treasury_rates = (
        treasury_rates.set_sorted("date").upsample("date", every="1d").interpolate()
    )
    return treasury_rates


async def load_us_treasury_returns_async():
    treasury_rates = await load_us_treasury_rates_async()
    treasury_returns = pl.DataFrame().with_columns(treasury_rates["date"])
    # Formula taken from https://portfoliooptimizer.io/blog/the-mathematics-of-bonds-simulating-the-returns-of-constant-maturity-government-bond-etfs/
    for duration in treasury_rates.drop("date").columns:
        rates = treasury_rates.select(duration).with_columns(
            pl.col(duration).truediv(100)
        )
        price = rates.with_columns(
            pl.col(duration)
            .shift(1)
            .truediv(365.25)
            .add(
                pl.col(duration)
                .shift(1)
                .truediv(pl.col(duration))
                .mul(
                    pl.lit(1).sub(
                        pl.col(duration)
                        .truediv(2)
                        .add(1)
                        .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
                    )
                )
            )
            .add(
                pl.col(duration)
                .truediv(2)
                .add(1)
                .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
            )
            .fill_nan(1)
            .cum_prod()
        )
        treasury_returns = treasury_returns.with_columns(price[duration])

    return treasury_returns


def read_shiller_sp500_data(tax_treatment: str):
    return pl.read_excel(
        "data/ie_data.xls",
        sheet_name="Data",
        read_options=dict(header_row=7),
        schema_overrides={"Date": pl.String},
    ).select(
        pl.col("Date")
        .str.pad_end(7, "0")
        .str.to_date("%Y.%m")
        .dt.offset_by("2w")
        .alias("date"),
        pl.col("P")
        .add(
            pl.col("D")
            .forward_fill()
            .truediv(12)
            .mul(0.7 if tax_treatment == "Net" else 1)
        )
        .truediv(pl.col("P").shift(1))
        .fill_null(1)
        .cum_prod()
        .alias("price"),
    )


def download_mas_sgd_fx():
    sgd_fx_response = httpx.get(
        "https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610ora/exchange_rates_end_of_period_daily/views/exchange_rates_end_of_period_daily",
        headers={"keyid": os.environ["MAS_EXCHANGE_RATE_API_KEY"]},
        timeout=20,
    )

    return (
        pl.read_json(sgd_fx_response.content)["elements"]
        .explode()
        .struct.unnest()
        .with_columns(
            pl.col("end_of_day").str.to_date(),
            pl.col(
                [
                    "eur_sgd",
                    "gbp_sgd",
                    "usd_sgd",
                    "aud_sgd",
                    "cad_sgd",
                    "chf_sgd",
                    "nzd_sgd",
                ]
            ).cast(pl.Decimal(5, 4)),
            pl.col(
                [
                    "inr_sgd_100",
                    "jpy_sgd_100",
                    "krw_sgd_100",
                    "twd_sgd_100",
                    "php_sgd_100",
                    "thb_sgd_100",
                ]
            )
            .cast(pl.Decimal(7, 5))
            .truediv(100)
            .cast(pl.Decimal(7, 6)),
            pl.col(
                [
                    "cny_sgd_100",
                    "hkd_sgd_100",
                    "myr_sgd_100",
                    "qar_sgd_100",
                    "sar_sgd_100",
                    "aed_sgd_100",
                ]
            )
            .cast(pl.Decimal(4, 2))
            .truediv(100)
            .cast(pl.Decimal(5, 4)),
            pl.col("idr_sgd_100", "vnd_sgd_100")
            .cast(pl.Decimal(9, 7))
            .truediv(100)
            .cast(pl.Decimal(9, 8)),
        )
        .select(
            pl.col("end_of_day").alias("date"),
            pl.all()
            .exclude("end_of_day", "preliminary")
            .name.map(lambda s: s.removesuffix("_100").removesuffix("_sgd").upper()),
        )
    )


def load_mas_sgd_fx():
    sgd_fx = pl.read_csv("data/sgd_fx.csv", use_pyarrow=True)

    if (
        sgd_fx.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(0, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "FRED_API_KEY" in os.environ
    ):
        sgd_fx = download_mas_sgd_fx()
        sgd_fx.write_csv("data/sgd_fx.csv")
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
    usd_fx = (
        pl.concat(
            [
                pl.read_json(response.content)["observations"]
                .explode()
                .struct.unnest()
                .select(
                    pl.col("date").str.to_date(),
                    pl.col("value").replace(".", None).cast(pl.Float64).alias(currency),
                )
                for currency, response in zip(series.keys(), responses)
            ],
            how="align",
        )
        .with_columns(pl.col("^1_.*$").pow(-1).name.map(lambda s: s.lstrip("1_")))
        .select(pl.all().exclude("^1_.*$"))
    )
    return usd_fx


async def load_fred_usd_fx_async():
    usd_fx = pl.read_csv("data/usd_fx.csv", use_pyarrow=True)
    if (
        usd_fx.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(2, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "FRED_API_KEY" in os.environ
    ):
        usd_fx = await download_fred_usd_fx_async()
        usd_fx.write_csv("data/usd_fx.csv")
    return usd_fx


def load_fred_usdsgd():
    usdsgd = get_fred_series("DEXSIUS").select(
        pl.col("date"), pl.col("value").alias("usd_sgd")
    )
    return usdsgd


def read_worldbank_usdsgd() -> pl.DataFrame:
    return (
        pl.read_csv("data/World Bank USDSGD.csv")
        .transpose(include_header=True)
        .slice(4)
        .rename({"column": "date", "column_0": "usd_sgd"})
        .with_columns(
            pl.col("date").str.slice(0, 4).str.to_date("%Y"),
            pl.col("usd_sgd").cast(pl.Float64),
        )
    )


def load_worldbank_usdsgd():
    fred_usdsgd = load_fred_usdsgd()
    return pl.from_pandas(
        pl.concat(
            [
                read_worldbank_usdsgd()
                .with_columns(
                    pl.col("date").dt.offset_by("6mo"),
                )
                .filter(pl.col("date").lt(fred_usdsgd.get_column("date").first())),
                fred_usdsgd[0],
            ]
        )
        .to_pandas()
        .set_index("date")
        .resample("D")
        .interpolate("pchip")
        .iloc[:-1]
        .reset_index(),
        schema_overrides={"date": pl.Date},
    )


def load_usdsgd():
    usdsgd = pl.read_csv("data/usdsgd.csv", use_pyarrow=True)
    if (
        usdsgd.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(0, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "FRED_API_KEY" in os.environ
        and "MAS_EXCHANGE_RATE_API_KEY" in os.environ
    ):
        world_bank_usdsgd = load_worldbank_usdsgd().rename({"usd_sgd": "usd_sgd_wb"})
        fred_usdsgd = load_fred_usdsgd().rename({"usd_sgd": "usd_sgd_fred"})
        mas_usdsgd = (
            load_mas_sgd_fx().select(["date", "USD"]).rename({"USD": "usd_sgd_mas"})
        )
        usdsgd = pl.concat(
            [mas_usdsgd, fred_usdsgd, world_bank_usdsgd], how="align"
        ).select(
            pl.col("date"),
            pl.col("usd_sgd_mas")
            .fill_null(pl.col("usd_sgd_fred"))
            .fill_null(pl.col("usd_sgd_wb"))
            .alias("usdsgd"),
        )
        usdsgd.write_csv("data/usdsgd.csv")
    return usdsgd


def load_mas_swap_points():
    df = pl.read_csv("data/sgd_swap_points.csv", try_parse_dates=True)
    if (
        df.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(0, roll="backward")
        .lt(datetime.date.today())
        .last()
    ):
        try:
            res = httpx.get(
                "https://www.mas.gov.sg/api/v1/MAS/chart/swappoint",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"
                },
            )
            res.raise_for_status()
            df = (
                pl.DataFrame(
                    res.json()["elements"],
                    ["dy", "month1", "month3", "month6"],
                )
                .select(
                    pl.col("dy").cast(pl.Date).alias("date"),
                    pl.all().exclude("dy"),
                )
                .reverse()
            )
            df.write_csv("data/sgd_swap_points.csv")
        except httpx.HTTPError as e:
            print(f"Failed to fetch data: {e}")
    return df


def load_sgd_neer():
    df = pl.read_csv("data/sgd_neer.csv", try_parse_dates=True)
    if (
        df.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(0, roll="backward")
        .lt(datetime.date.today())
        .last()
    ):
        try:
            res = httpx.get(
                "https://www.mas.gov.sg/api/v1/MAS/chart/sneer",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"
                },
            )
            res.raise_for_status()
            df = (
                pl.DataFrame(
                    res.json()["elements"],
                    ["date", "value"],
                )
                .select(
                    pl.col("date").cast(pl.Date),
                    pl.col("value").cast(pl.Float64).alias("sgd_neer"),
                )
                .reverse()
            )
            df.write_csv("data/sgd_neer.csv")
        except httpx.HTTPError as e:
            print(f"Failed to fetch data: {e}")
    return df


def download_sgd_interest_rates():
    sgd_interest_rates_response = httpx.get(
        "https://eservices.mas.gov.sg/apimg-gw/server/monthly_statistical_bulletin_non610mssql/domestic_interest_rates_daily/views/domestic_interest_rates_daily",
        headers={"keyid": os.environ["MAS_INTEREST_RATE_API_KEY"]},
        timeout=20,
    )

    return (
        pl.read_json(sgd_interest_rates_response.content)["elements"]
        .explode()
        .struct.unnest()
        .select(
            pl.col("end_of_day").str.to_date().alias("date"),
            pl.col("interbank_overnight").cast(pl.Float64),
            pl.col("sora").cast(pl.Float64),
        )
        .unique(keep="first", maintain_order=True)
        .sort("date")
    )


def load_sgd_interest_rates():
    sgd_interest_rates = pl.read_csv("data/sgd_interest_rates.csv", use_pyarrow=True)

    if (
        sgd_interest_rates.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.add_business_days(0, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "MAS_INTEREST_RATE_API_KEY" in os.environ
    ):
        sgd_interest_rates = download_sgd_interest_rates()
        sgd_interest_rates.write_csv("data/sgd_interest_rates.csv")

    sgd_interest_rates_1m = (
        sgd_interest_rates.upsample("date", every="1d")
        .with_columns(
            pl.all().exclude("date").forward_fill(),
        )
        .with_columns(
            pl.when(pl.col("date").dt.year() < 2014)
            .then(pl.col("interbank_overnight"))
            .alias("interbank_overnight"),
        )
        .with_columns(
            pl.col("date")
            .dt.add_business_days(0, roll="forward")
            .dt.month_end()
            .dt.add_business_days(0, roll="backward"),
        )
        .set_sorted("date")
        .group_by("date")
        .agg(pl.all().truediv(36500).add(1).product().pow(12).sub(1).mul(100))
        .with_columns(
            pl.all().exclude("date").replace(0, None),
        )
        .with_columns(
            sgd_ir_1m=pl.col("sora").fill_null(pl.col("interbank_overnight")),
        )
    )

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
    sgs = pl.DataFrame(data, ["Year", "Month", "Day", *columns[3:]], orient="row")
    return (
        sgs.with_columns(
            pl.col(["Year", "Month", "Day"]).replace("", None).forward_fill(),
        )
        .insert_column(
            0,
            pl.col("Year")
            .add(pl.col("Month"))
            .add(pl.col("Day"))
            .str.to_date("%Y%b%d")
            .alias("date"),
        )
        .select(
            pl.col("date"),
            pl.all()
            .exclude("date", "Year", "Month", "Day")
            .replace("", None)
            .cast(pl.Float64)
            .name.map(
                lambda s: s.removeprefix(
                    "Average Buying Rates of Govt Securities Dealers "
                )
            ),
        )
    )


def load_sgs_rates():
    sgs = read_sgs_data()
    sgs = (
        sgs.select(
            pl.all()
            .exclude("^.*Price.*$")
            .name.map(
                lambda s: s.removesuffix(" Yield")
                .removesuffix(" T-Bill")
                .removesuffix(" Bond")
                .removesuffix("-Year")
            )
        )
        .upsample("date", every="1d")
        .fill_null(strategy="forward")
    )
    return sgs


def load_sgs_returns():
    sgs_rates = load_sgs_rates()
    sgs_returns = pl.DataFrame().with_columns(sgs_rates["date"])
    # Formula taken from https://portfoliooptimizer.io/blog/the-mathematics-of-bonds-simulating-the-returns-of-constant-maturity-government-bond-etfs/
    for duration in sgs_rates.drop("date").columns:
        rates = sgs_rates.select(duration).with_columns(pl.col(duration).truediv(100))
        price = rates.with_columns(
            pl.col(duration)
            .shift(1)
            .truediv(365.25)
            .add(
                pl.col(duration)
                .shift(1)
                .truediv(pl.col(duration))
                .mul(
                    pl.lit(1).sub(
                        pl.col(duration)
                        .truediv(2)
                        .add(1)
                        .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
                    )
                )
            )
            .add(
                pl.col(duration)
                .truediv(2)
                .add(1)
                .pow(-2 * (eval(duration.replace("MO", "/12")) - 1 / 365.25))
            )
            .fill_nan(1)
            .cum_prod()
        )
        sgs_returns = sgs_returns.with_columns(price[duration])
    return sgs_returns


def download_sg_cpi():
    sg_cpi_response = httpx.get(
        "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212882",
        params={"seriesNoORrowNo": 1},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=20,
    )
    sg_cpi = (
        pl.read_json(sg_cpi_response.content)["Data"]
        .struct.unnest()["row"]
        .explode()
        .struct.unnest()["columns"]
        .explode()
        .struct.unnest()
        .select(
            pl.col("key")
            .str.to_date("%Y %b")
            .dt.month_end()
            .dt.add_business_days(0, roll="backward")
            .alias("date"),
            pl.col("value").cast(pl.Float64).alias("sg_cpi"),
        )
    )

    return sg_cpi


def load_sg_cpi():
    sg_cpi = pl.read_csv("data/sg_cpi.csv", use_pyarrow=True)
    if (
        sg_cpi.get_column("date")
        .dt.add_business_days(1, roll="forward")
        .dt.month_end()
        .dt.offset_by("25d")
        .lt(datetime.date.today())
        .last()
    ):
        sg_cpi = download_sg_cpi()
        sg_cpi.write_csv("data/sg_cpi.csv")
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
    us_cpi = (
        pl.DataFrame(
            chain.from_iterable(
                [
                    response.json()["Results"]["series"][0]["data"]
                    for response in responses
                ]
            )
        )
        .select(
            pl.col("year")
            .add(pl.col("period").str.slice(-2))
            .str.to_date("%Y%m")
            .dt.month_end()
            .dt.add_business_days(0, roll="backward")
            .alias("date"),
            pl.col("value").cast(pl.Float64).alias("us_cpi"),
        )
        .sort("date")
    )
    return us_cpi


async def load_us_cpi_async():
    us_cpi = pl.read_csv("data/us_cpi.csv", try_parse_dates=True)
    if (
        us_cpi.get_column("date")
        .dt.month_end()
        .dt.add_business_days(15, roll="backward")
        .lt(datetime.date.today())
        .last()
        and "BLS_API_KEY" in os.environ
    ):
        us_cpi = await download_us_cpi_async()
        us_cpi.write_csv("data/us_cpi.csv")
        return us_cpi


def read_greatlink_data(fund_name: str):
    price = (
        pl.read_excel(
            f"data/GreatLink/{fund_name}.xlsx",
            engine="calamine",
            columns=["Price Date", "Price"],
        )
        .select(
            pl.col("Price Date").str.to_date().alias("date"),
            pl.col("Price").replace(".", None).cast(pl.Float64).alias("price"),
        )
        .sort("date")
    )
    if glob(f"data/GreatLink/{fund_name}_Dividends.xlsx"):
        dividends = (
            pl.read_excel(
                f"data/GreatLink/{fund_name}_Dividends.xlsx",
                engine="calamine",
                columns=["XD Date", "Gross Dividend"],
            )
            .select(
                pl.col("XD Date").str.to_date().alias("date"),
                pl.col("Gross Dividend")
                .replace(".", None)
                .cast(pl.Float64)
                .alias("dividend"),
            )
            .sort("date")
        )
        price = price.join(dividends, "date", "full").select(
            pl.col("date"),
            pl.col("price")
            .add(pl.col("dividend").fill_null(0))
            .truediv(pl.col("price").shift(1))
            .cum_prod()
            .fill_null(1),
        )
    return price
