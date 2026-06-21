import asyncio
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache, reduce
from glob import glob
from typing import Annotated, Generic, Literal, TypeVar

import numpy as np
import polars as pl
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from funcs.calcs_numpy import (
    calculate_dca_portfolio_value_with_fees_and_interest_vector,
    calculate_withdrawal_portfolio_value_with_fees_vector,
    generate_bootstrap_indices,
    simulate_bootstrap_accumulation,
    simulate_bootstrap_withdrawal,
)
from funcs.loaders_pl import (
    fast_bday_downsample,
    fast_bday_upsample,
    load_cpi,
    load_fed_funds_returns,
    load_fred_usd_fx_async,
    load_ft_data,
    load_mas_sgd_fx,
    load_sgd_interest_rates_returns,
    load_sgs_returns,
    load_us_treasury_returns_async,
    load_usdsgd,
    load_yf_data,
    pchip_daily_upsample,
    read_ft_data,
    read_greatlink_data,
    read_msci_data,
    read_shiller_sp500_data,
    resample_bme,
)
from models import (
    Currency,
    DimensionalFund,
    FREDIndex,
    FundCompany,
    FundsmithFund,
    GMOFund,
    GreatLinkFund,
    Interval,
    MASIndex,
    MSCICountryIndex,
    MSCIRegionalIndex,
    MSCISize,
    MSCIStyle,
    OthersIndex,
    SGSDuration,
    TaxTreatment,
    USTreasuryDuration,
)


def convert_price(
    df: pl.DataFrame,
    source_currency: str,
    destination_currency: Currency,
) -> pl.DataFrame:
    if source_currency == destination_currency:
        return df

    usd_sgd = (
        load_usdsgd()
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency == "USD" and destination_currency == Currency.SGD:
        return df.join(usd_sgd, on="date", how="left").select(
            "date", price=pl.col("price") * pl.col("usdsgd")
        )
    if source_currency == "SGD" and destination_currency == Currency.USD:
        return df.join(usd_sgd, on="date", how="left").select(
            "date", price=pl.col("price") / pl.col("usdsgd")
        )

    usd_fx = (
        asyncio.run(load_fred_usd_fx_async())
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency == "GBp":
        df = df.with_columns(pl.col("price") / 100)
        source_currency = "GBP"

    if source_currency in usd_fx.columns:
        usd_series = df.join(
            usd_fx.select("date", source_currency), on="date", how="left"
        ).select("date", price=pl.col("price") * pl.col(source_currency))
        if destination_currency == Currency.USD:
            return usd_series
        if destination_currency == Currency.SGD:
            return usd_series.join(usd_sgd, on="date", how="left").select(
                "date", price=pl.col("price") * pl.col("usdsgd")
            )

    sgd_fx = (
        load_mas_sgd_fx()
        .sort("date")
        .upsample("date", every="1d", maintain_order=True)
        .fill_null(strategy="forward")
    )

    if source_currency in sgd_fx.columns:
        sgd_series = df.join(
            sgd_fx.select("date", source_currency), on="date", how="left"
        ).select("date", price=pl.col("price") * pl.col(source_currency))
        if destination_currency == Currency.SGD:
            return sgd_series
        if destination_currency == Currency.USD:
            return sgd_series.join(usd_sgd, on="date", how="left").select(
                "date", price=pl.col("price") / pl.col("usdsgd")
            )

    return df


@lru_cache
def _cached_load_security(
    security_json: str,
    interval: Interval,
    currency: Currency,
    adjust_for_inflation: bool,
) -> pl.DataFrame:
    security: Security = TypeAdapter(Security).validate_json(security_json)
    df = security.load_data(interval)
    df = convert_price(df, security.currency, currency)
    if adjust_for_inflation:
        cpi = load_cpi(currency)
        cpi = cpi.pipe(pchip_daily_upsample, "cpi").fill_null(strategy="forward")
        df = df.join(cpi, on="date", how="left").select(
            "date", price=pl.col("price") / pl.col("cpi")
        )
    return df.sort("date")


class BaseSecurity(BaseModel):
    holding_type: Literal["Security"] = "Security"

    def load_series(
        self, interval: Interval, currency: Currency, adjust_for_inflation: bool
    ) -> pl.DataFrame:
        return _cached_load_security(
            self.model_dump_json(), interval, currency, adjust_for_inflation
        )


class MsciSecurity(BaseSecurity):
    source: Literal["MSCI"] = "MSCI"
    msci_base_index: MSCIRegionalIndex | MSCICountryIndex
    msci_size: MSCISize
    msci_style: MSCIStyle
    msci_tax_treatment: TaxTreatment
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return " ".join(
            field
            for field in [
                "MSCI",
                self.msci_base_index.label,
                None if self.msci_size == MSCISize.STANDARD else self.msci_size.label,
                "Cap"
                if self.msci_size
                in (MSCISize.SMALL, MSCISize.SMID, MSCISize.MID, MSCISize.LARGE)
                and self.msci_style == MSCIStyle.BLEND
                else None,
                None if self.msci_style == MSCIStyle.BLEND else self.msci_style.label,
                self.msci_tax_treatment.label,
            ]
            if field is not None
        )

    @model_validator(mode="after")
    def check_valid(self):
        if not glob(
            f"data/"
            f"MSCI/"
            f"{self.msci_base_index}/"
            f"{self.msci_size}/"
            f"{self.msci_style}/"
            f"* {self.msci_tax_treatment}*.csv"
        ):
            raise ValueError("The constructed index is not available")
        return self

    def load_data(self, interval: Interval):
        return read_msci_data(
            f"data/"
            f"MSCI/"
            f"{self.msci_base_index}/"
            f"{self.msci_size}/"
            f"{self.msci_style}/"
            f"*{self.msci_tax_treatment} {interval}.csv"
        )


class FredTreasurySecurity(BaseSecurity):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.US_T] = FREDIndex.US_T
    us_treasury_duration: USTreasuryDuration
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return f"{self.us_treasury_duration.label} {self.fred_index.label}"

    def load_data(self, interval: Interval):
        df = (
            asyncio.run(load_us_treasury_returns_async())
            .select("date", pl.col(self.us_treasury_duration).alias("price"))
            .drop_nulls()
            .pipe(fast_bday_downsample)
        )
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class FredFfrSecurity(BaseSecurity):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.FFR] = FREDIndex.FFR
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return self.fred_index.label

    def load_data(self, interval: Interval):
        df = load_fed_funds_returns().pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


type FredSecurity = Annotated[
    FredTreasurySecurity | FredFfrSecurity,
    Field(discriminator="fred_index"),
]


class MasSgsSecurity(BaseSecurity):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SGS] = MASIndex.SGS
    sgs_duration: SGSDuration
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return f"{self.sgs_duration.label} {self.mas_index.label}"

    def load_data(self, interval: Interval):
        df = (
            load_sgs_returns()
            .select("date", pl.col(self.sgs_duration).alias("price"))
            .drop_nulls()
            .pipe(fast_bday_downsample)
        )
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class MasSoraSecurity(BaseSecurity):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SORA] = MASIndex.SORA
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return self.mas_index.label

    def load_data(self, interval: Interval):
        df = load_sgd_interest_rates_returns().pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


type MasSecurity = Annotated[
    MasSgsSecurity | MasSoraSecurity,
    Field(discriminator="mas_index"),
]


OthersIndexT = TypeVar("OthersIndexT", bound=OthersIndex)


class BaseOthersIndexSecurity(BaseSecurity, Generic[OthersIndexT]):
    source: Literal["Others"] = "Others"
    others_index: OthersIndexT
    others_tax_treatment: TaxTreatment

    @property
    def label(self) -> str:
        return f"{self.others_index.label} {self.others_tax_treatment.label}"


class SpxSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SPX]]):
    currency: Literal["USD"] = "USD"

    def load_data(self, interval: Interval):
        df = read_ft_data(f"S&P 500 USD {self.others_tax_treatment}")
        if interval == Interval.DAILY:
            df = df.pipe(fast_bday_upsample)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class ShillerSpxSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SHILLER_SPX]]):
    currency: Literal["USD"] = "USD"

    def load_data(self, interval: Interval):
        df = read_shiller_sp500_data(self.others_tax_treatment)
        if interval == Interval.DAILY:
            df = df.pipe(fast_bday_upsample)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class SreitSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SREIT]]):
    currency: Literal["USD"] = "USD"

    @field_validator("others_tax_treatment", mode="after")
    @classmethod
    def force_gross_tax(cls, _):
        return TaxTreatment.GROSS

    def load_data(self, interval: Interval):
        df = read_ft_data("iEdge S-REIT Leaders USD Gross")
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


type OthersIndexSecurity = Annotated[
    SpxSecurity | ShillerSpxSecurity | SreitSecurity,
    Field(discriminator="others_index"),
]


class YfSecurity(BaseSecurity):
    source: Literal["YF"] = "YF"
    ticker: str
    currency: str
    tax_treatment: TaxTreatment

    @property
    def label(self) -> str:
        return f"yfinance: {self.ticker} {self.tax_treatment.label}"

    def load_data(self, interval: Interval):
        df = load_yf_data(self.ticker, self.tax_treatment)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class FtSecurity(BaseSecurity):
    source: Literal["FT"] = "FT"
    ticker: str
    currency: str
    issue_type: str
    inception_date: str
    dividends: bool

    @property
    def label(self) -> str:
        return f"FT: {self.ticker} {('(With Dividends)') * self.dividends}"

    def load_data(self, interval: Interval):
        df = load_ft_data(
            self.ticker, self.issue_type, self.inception_date, self.dividends
        )
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class GreatlinkSecurity(BaseSecurity):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GREATLINK] = FundCompany.GREATLINK
    fund: GreatLinkFund
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        df = read_greatlink_data(self.fund)
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class GMOSecurity(BaseSecurity):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GMO] = FundCompany.GMO
    fund: GMOFund
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        df = read_ft_data("GMO Quality Investment Fund")
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class FundsmithSecurity(BaseSecurity):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.FUNDSMITH] = FundCompany.FUNDSMITH
    fund: FundsmithFund
    currency: Literal["EUR"] = "EUR"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        df = read_ft_data(f"Fundsmith {self.fund.replace('Class ', '')} EUR Acc")
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


class DimensionalSecurity(BaseSecurity):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.DIMENSIONAL] = FundCompany.DIMENSIONAL
    fund: DimensionalFund
    currency: Literal["GBP"] = "GBP"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        df = read_ft_data(f"Dimensional {self.fund} GBP Accumulation")
        if interval == Interval.MONTHLY:
            df = df.pipe(resample_bme)
        return df


type FundSecurity = Annotated[
    GreatlinkSecurity | GMOSecurity | FundsmithSecurity | DimensionalSecurity,
    Field(discriminator="fund_company"),
]


type IndexSecurity = Annotated[
    MsciSecurity | FredSecurity | MasSecurity | OthersIndexSecurity,
    Field(discriminator="source"),
]


type Security = Annotated[
    IndexSecurity | YfSecurity | FtSecurity | FundSecurity,
    Field(discriminator="source"),
]


class Allocation(BaseModel):
    security: Security
    weight: Decimal = Field(ge=Decimal("0.01"), le=Decimal("100"))

    @field_validator("weight", mode="after")
    @classmethod
    def parse_weight(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @field_serializer("weight")
    def serialize_weight(self, v: Decimal) -> float:
        return float(v)

    @property
    def label(self) -> str:
        return f"{self.weight}% {self.security.label}"


class Portfolio(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    holding_type: Literal["Portfolio"] = "Portfolio"
    allocations: list[Allocation]

    @property
    def label(self) -> str:
        return ",\n".join(allocation.label for allocation in self.allocations)

    def add_allocation(self, new_allocation: Allocation):
        for allocation in self.allocations:
            if new_allocation.security == allocation.security:
                allocation.weight = new_allocation.weight
                break
        else:
            self.allocations.append(new_allocation)

    def to_plotly_options(self) -> dict[str, str]:
        return {
            allocation.model_dump_json(exclude_none=True): allocation.label
            for allocation in self.allocations
        }

    def load_series(
        self, interval: Interval, currency: Currency, adjust_for_inflation: bool
    ) -> pl.DataFrame:
        dfs = [
            allocation.security.load_series(
                Interval.MONTHLY, currency, adjust_for_inflation
            ).rename({"price": allocation.security.model_dump_json()})
            for allocation in self.allocations
        ]
        portfolio_df = reduce(
            lambda left, right: left.join(right, on="date", how="full", coalesce=True),
            dfs,
        )
        portfolio_series = (
            portfolio_df.with_columns(
                pl.col(allocation.security.model_dump_json())
                .pct_change()
                .mul(allocation.weight)
                .truediv(100)
                for allocation in self.allocations
            )
            .select(
                "date",
                price=pl.sum_horizontal(pl.all().exclude("date"), ignore_nulls=False)
                .add(1)
                .cum_prod(),
            )
            .select(
                "date",
                price=pl.when(
                    pl.int_range(pl.len())
                    == pl.arg_where(pl.col("price").is_not_null()).first().sub(1)
                )
                .then(1)
                .otherwise(pl.col("price")),
            )
            .drop_nulls()
        )
        return portfolio_series


class NoneHolding(BaseModel):
    holding_type: Literal["None"] = "None"

    @property
    def label(self) -> str:
        return "None"

    def load_series(
        self, interval: Interval, currency: Currency, adjust_for_inflation: bool
    ) -> pl.DataFrame:
        raise ValueError("Cannot load series for NoneHolding")


type Holding = Annotated[
    Security | Portfolio | NoneHolding, Field(discriminator="holding_type")
]


def convert_percent_to_decimal(v: float) -> float:
    return v / 100


class BaseAccumulationStrategy(BaseModel):
    strategy_phase: Literal["Accumulation"] = "Accumulation"
    strategy_portfolio: Portfolio
    currency: Currency
    investment_amount: float = Field(default=0, ge=0)
    monthly_investment: float = Field(default=0, ge=0)
    adjust_monthly_investment_for_inflation: bool = False
    coast_duration: int = Field(ge=0)
    dca_duration: int = Field(ge=0)
    dca_interval: int = Field(default=1, ge=1)
    adjust_portfolio_value_for_inflation: bool = False
    variable_transaction_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)
    fixed_transaction_fees: float = Field(default=0, ge=0)
    annualised_holding_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)

    @computed_field
    @property
    def strategy_horizon(self) -> int:
        return self.dca_duration + self.coast_duration

    @property
    def label(self) -> str:
        return (
            f"{self.strategy_portfolio.label} {self.currency}\n"
            f"${self.investment_amount:,.2f} initial capital\n"
            f"${self.monthly_investment:,.2f} invested monthly"
            f"{', inflation adjusted' if self.adjust_monthly_investment_for_inflation else ''}\n"
            f"for {self.dca_duration} months every {self.dca_interval} months\n"
            f"coast for {self.coast_duration} months\n"
            f"{self.variable_transaction_fees:.2%} + ${self.fixed_transaction_fees:,.2f} Fee\n"
            f"{self.annualised_holding_fees:.2%} p.a. Holding Fees\n"
            f"Portfolio value {'' if self.adjust_portfolio_value_for_inflation else 'not '}adjusted for inflation"
        )


class AccumulationBacktestStrategy(BaseAccumulationStrategy):
    def simulate(self) -> pl.DataFrame:
        strategy_series = self.strategy_portfolio.load_series(
            Interval.MONTHLY,
            self.currency,
            False,
        )
        cash_returns = (
            load_fed_funds_returns()
            if self.currency == Currency.USD
            else load_sgd_interest_rates_returns()
        ).pipe(resample_bme)
        cpi = load_cpi(self.currency)

        df = (
            strategy_series.rename({"price": "strategy"})
            .join(
                cash_returns.rename({"price": "cash"}),
                on="date",
                coalesce=True,
                maintain_order="left",
            )
            .join(cpi, on="date", coalesce=True, maintain_order="left")
        )

        portfolio_values = (
            pl.from_numpy(
                calculate_dca_portfolio_value_with_fees_and_interest_vector(
                    df.get_column("strategy").pct_change().to_numpy(),
                    self.dca_duration,
                    self.dca_interval,
                    self.strategy_horizon,
                    self.investment_amount,
                    self.monthly_investment,
                    self.adjust_monthly_investment_for_inflation,
                    self.variable_transaction_fees,
                    self.fixed_transaction_fees,
                    self.annualised_holding_fees,
                    self.adjust_portfolio_value_for_inflation,
                    df.get_column("cpi").to_numpy(),
                    df.get_column("cash").to_numpy(writable=True),
                ),
                schema=[str(i) for i in range(self.strategy_horizon + 1)],
            )
            .fill_nan(None)
            .insert_column(0, df.get_column("date"))
        )
        return portfolio_values


class AccumulationBootstrapStrategy(BaseAccumulationStrategy):
    num_bootstrap_samples: int = Field(default=1000, ge=100)
    avg_block_length: float = Field(default=120, ge=2)

    @property
    def label(self) -> str:
        return (
            f"{super().label}\n"
            f"{self.num_bootstrap_samples} samples, {self.avg_block_length:.0f}mo avg block"
        )

    def simulate(self) -> np.ndarray:
        strategy_series = self.strategy_portfolio.load_series(
            Interval.MONTHLY,
            self.currency,
            False,
        )
        cash_returns = (
            load_fed_funds_returns()
            if self.currency == Currency.USD
            else load_sgd_interest_rates_returns()
        ).pipe(resample_bme)
        cpi = load_cpi(self.currency)

        df = (
            strategy_series.rename({"price": "strategy"})
            .join(
                cash_returns.rename({"price": "cash"}),
                on="date",
                coalesce=True,
                maintain_order="left",
            )
            .join(cpi, on="date", coalesce=True, maintain_order="left")
            .with_columns(pl.all().exclude("date").pct_change())
            .drop_nulls()
        )

        strategy_series = df.get_column("strategy").to_numpy()
        cpi = df.get_column("cpi").to_numpy()
        cash_returns = df.get_column("cash").to_numpy()

        n_data = len(strategy_series)
        sample_length = self.strategy_horizon + 1
        indices = generate_bootstrap_indices(
            self.num_bootstrap_samples, sample_length, n_data, self.avg_block_length
        )
        portfolio_values = simulate_bootstrap_accumulation(
            strategy_series,
            cpi,
            cash_returns,
            indices,
            self.dca_duration,
            self.dca_interval,
            self.strategy_horizon,
            self.investment_amount,
            self.monthly_investment,
            self.adjust_monthly_investment_for_inflation,
            self.variable_transaction_fees,
            self.fixed_transaction_fees,
            self.annualised_holding_fees,
            self.adjust_portfolio_value_for_inflation,
        )
        return portfolio_values


class BaseWithdrawalStrategy(BaseModel):
    strategy_phase: Literal["Withdrawal"] = "Withdrawal"
    strategy_portfolio: Portfolio
    currency: Currency
    initial_capital: float = Field(ge=0)
    coast_duration: int = Field(ge=0)
    monthly_withdrawal: float = Field(ge=0)
    adjust_withdrawals_for_inflation: bool = False
    adjust_portfolio_value_for_inflation: bool = False
    withdrawal_duration: int = Field(ge=0)
    withdrawal_interval: int = Field(default=1, ge=1)
    variable_transaction_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)
    fixed_transaction_fees: float = Field(default=0, ge=0)
    annualised_holding_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)

    @computed_field
    @property
    def strategy_horizon(self) -> int:
        return self.coast_duration + self.withdrawal_duration

    @property
    def label(self) -> str:
        return (
            f"{self.strategy_portfolio.label} {self.currency}\n"
            f"${self.initial_capital:,.2f} initial capital\n"
            f"coast for {self.coast_duration} months\n"
            f"${self.monthly_withdrawal:,.2f} withdrawn monthly"
            f"{', inflation adjusted' if self.adjust_withdrawals_for_inflation else ''}\n"
            f"every {self.withdrawal_interval} months for {self.withdrawal_duration} months\n"
            f"{self.variable_transaction_fees:.2%} + ${self.fixed_transaction_fees:,.2f} Fee\n"
            f"{self.annualised_holding_fees:.2%} p.a. Holding Fees\n"
            f"Portfolio value {'' if self.adjust_portfolio_value_for_inflation else 'not '}adjusted for inflation"
        )


class WithdrawalBacktestStrategy(BaseWithdrawalStrategy):
    def simulate(self) -> pl.DataFrame:
        strategy_series = self.strategy_portfolio.load_series(
            Interval.MONTHLY,
            self.currency,
            False,
        )
        cpi = load_cpi(self.currency)

        df = strategy_series.rename({"price": "strategy"}).join(
            cpi, on="date", coalesce=True, maintain_order="left"
        )

        portfolio_values = (
            pl.from_numpy(
                calculate_withdrawal_portfolio_value_with_fees_vector(
                    df.get_column("strategy").pct_change().to_numpy(),
                    self.coast_duration,
                    self.strategy_horizon,
                    self.withdrawal_interval,
                    self.initial_capital,
                    self.monthly_withdrawal,
                    df.get_column("cpi").to_numpy(),
                    self.variable_transaction_fees,
                    self.fixed_transaction_fees,
                    self.annualised_holding_fees,
                    self.adjust_withdrawals_for_inflation,
                    self.adjust_portfolio_value_for_inflation,
                ),
                schema=[str(i) for i in range(self.strategy_horizon + 1)],
            )
            .fill_nan(None)
            .insert_column(0, df.get_column("date"))
        )
        return portfolio_values


class WithdrawalBootstrapStrategy(BaseWithdrawalStrategy):
    num_bootstrap_samples: int = Field(default=1000, ge=100)
    avg_block_length: float = Field(default=120, ge=2)

    @property
    def label(self) -> str:
        return (
            f"{super().label}\n"
            f"{self.num_bootstrap_samples} samples, {self.avg_block_length:.0f}mo avg block"
        )

    def simulate(self) -> np.ndarray:
        strategy_series = self.strategy_portfolio.load_series(
            Interval.MONTHLY,
            self.currency,
            False,
        )
        cpi = load_cpi(self.currency)

        df = strategy_series.rename({"price": "strategy"}).join(
            cpi, on="date", coalesce=True, maintain_order="left"
        )

        monthly_returns = df.get_column("strategy").pct_change().to_numpy()[1:]
        cpi = df.get_column("cpi").pct_change().to_numpy()[1:]

        n_data = len(monthly_returns)
        sample_length = self.strategy_horizon + 1
        indices = generate_bootstrap_indices(
            self.num_bootstrap_samples,
            sample_length,
            n_data,
            self.avg_block_length,
        )
        portfolio_values = simulate_bootstrap_withdrawal(
            monthly_returns,
            cpi,
            indices,
            self.coast_duration,
            self.strategy_horizon,
            self.withdrawal_interval,
            self.initial_capital,
            self.monthly_withdrawal,
            self.variable_transaction_fees,
            self.fixed_transaction_fees,
            self.annualised_holding_fees,
            self.adjust_withdrawals_for_inflation,
            self.adjust_portfolio_value_for_inflation,
        )
        return portfolio_values


type BacktestStrategy = Annotated[
    AccumulationBacktestStrategy | WithdrawalBacktestStrategy,
    Field(discriminator="strategy_phase"),
]

type BootstrapStrategy = Annotated[
    AccumulationBootstrapStrategy | WithdrawalBootstrapStrategy,
    Field(discriminator="strategy_phase"),
]
