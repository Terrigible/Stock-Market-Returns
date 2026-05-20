from glob import glob
from io import StringIO
from typing import Annotated, Generic, Literal, TypeVar

import pandas as pd
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    field_validator,
    model_validator,
)

from funcs.loaders import (
    fast_bday_downsample,
    fast_bday_upsample,
    load_fed_funds_returns,
    load_sgd_interest_rates_returns,
    load_sgs_returns,
    load_us_treasury_returns,
    read_ft_data,
    read_greatlink_data,
    read_msci_data,
    read_shiller_sp500_data,
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


def resample_bme(series: pd.Series):
    df = (
        series.rename("price")
        .to_frame()
        .assign(date=series.index)
        .resample("BME")
        .last()
    )
    new_index = df.index[:-1].union([df["date"].iloc[-1]])
    return df["price"].set_axis(new_index)


class MsciSecurity(BaseModel):
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
            f"{self.source}/"
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


class FredTreasurySecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.US_T] = FREDIndex.US_T
    us_treasury_duration: USTreasuryDuration
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return f"{self.us_treasury_duration.label} {self.fred_index.label}"

    def load_data(self, interval: Interval):
        series = (
            load_us_treasury_returns()[self.us_treasury_duration]
            .dropna()
            .pipe(fast_bday_downsample)
        )
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class FredFfrSecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.FFR] = FREDIndex.FFR
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return self.fred_index.label

    def load_data(self, interval: Interval):
        fed_funds_returns = load_fed_funds_returns()
        series = fed_funds_returns.pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


FredSecurity = Annotated[
    FredTreasurySecurity | FredFfrSecurity,
    Field(discriminator="fred_index"),
]


class MasSgsSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SGS] = MASIndex.SGS
    sgs_duration: SGSDuration
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return f"{self.sgs_duration.label} {self.mas_index.label}"

    def load_data(self, interval: Interval):
        series = (
            load_sgs_returns()[self.sgs_duration].dropna().pipe(fast_bday_downsample)
        )
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class MasSoraSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SORA] = MASIndex.SORA
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return self.mas_index.label

    def load_data(self, interval: Interval):
        sgd_interest_rates_returns = load_sgd_interest_rates_returns()
        series = sgd_interest_rates_returns.pipe(fast_bday_downsample)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


MasSecurity = Annotated[
    MasSgsSecurity | MasSoraSecurity,
    Field(discriminator="mas_index"),
]


OthersIndexT = TypeVar("OthersIndexT", bound=OthersIndex)


class BaseOthersIndexSecurity(BaseModel, Generic[OthersIndexT]):
    source: Literal["Others"] = "Others"
    others_index: OthersIndexT
    others_tax_treatment: TaxTreatment

    @property
    def label(self) -> str:
        return f"{self.others_index.label} {self.others_tax_treatment.label}"


class SpxSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SPX]]):
    currency: Literal["USD"] = "USD"

    def load_data(self, interval: Interval):
        series = read_ft_data(f"S&P 500 USD {self.others_tax_treatment}")
        if interval == Interval.DAILY:
            series = series.pipe(fast_bday_upsample)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class ShillerSpxSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SHILLER_SPX]]):
    currency: Literal["USD"] = "USD"

    def load_data(self, interval: Interval):
        series = read_shiller_sp500_data(self.others_tax_treatment)
        if interval == Interval.DAILY:
            series = series.pipe(fast_bday_upsample)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class SreitSecurity(BaseOthersIndexSecurity[Literal[OthersIndex.SREIT]]):
    currency: Literal["USD"] = "USD"

    @field_validator("others_tax_treatment", mode="after")
    @classmethod
    def is_gross(cls, _):
        return TaxTreatment.GROSS

    def load_data(self, interval: Interval):
        series = read_ft_data("iEdge S-REIT Leaders USD Gross")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


OthersIndexSecurity = Annotated[
    SpxSecurity | ShillerSpxSecurity | SreitSecurity,
    Field(discriminator="others_index"),
]


class YfSecurity(BaseModel):
    source: Literal["YF"] = "YF"
    ticker: str
    currency: str
    tax_treatment: TaxTreatment

    @property
    def label(self) -> str:
        return f"yfinance: {self.ticker} {self.tax_treatment.label}"

    def load_data(self, interval: Interval, cached_security: str | None):
        series = pd.read_json(StringIO(cached_security), orient="index", typ="series")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class FtSecurity(BaseModel):
    source: Literal["FT"] = "FT"
    ticker: str
    currency: str
    dividends: bool

    @property
    def label(self) -> str:
        return f"FT: {self.ticker} {('(With Dividends)') * self.dividends}"

    def load_data(self, interval: Interval, cached_security: str | None):
        series = pd.read_json(StringIO(cached_security), orient="index", typ="series")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class GreatlinkSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GREATLINK] = FundCompany.GREATLINK
    fund: GreatLinkFund
    currency: Literal["SGD"] = "SGD"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        series = read_greatlink_data(self.fund)
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class GMOSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GMO] = FundCompany.GMO
    fund: GMOFund
    currency: Literal["USD"] = "USD"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        series = read_ft_data("GMO Quality Investment Fund")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class FundsmithSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.FUNDSMITH] = FundCompany.FUNDSMITH
    fund: FundsmithFund
    currency: Literal["EUR"] = "EUR"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        series = read_ft_data(f"Fundsmith {self.fund.replace('Class ', '')} EUR Acc")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


class DimensionalSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.DIMENSIONAL] = FundCompany.DIMENSIONAL
    fund: DimensionalFund
    currency: Literal["GBP"] = "GBP"

    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"

    def load_data(self, interval: Interval):
        series = read_ft_data(f"Dimensional {self.fund} GBP Accumulation")
        if interval == Interval.MONTHLY:
            series = series.pipe(resample_bme)
        return series


FundSecurity = Annotated[
    GreatlinkSecurity | GMOSecurity | FundsmithSecurity | DimensionalSecurity,
    Field(discriminator="fund_company"),
]


IndexSecurity = Annotated[
    MsciSecurity | FredSecurity | MasSecurity | OthersIndexSecurity,
    Field(discriminator="source"),
]


Security = Annotated[
    IndexSecurity | YfSecurity | FtSecurity | FundSecurity,
    Field(discriminator="source"),
]

parse_security = TypeAdapter(Security).validate_json


class Allocation(BaseModel):
    security: Security
    weight: float = Field(gt=0, le=100)

    @property
    def label(self) -> str:
        return f"{self.weight}% {self.security.label}"


class Portfolio(RootModel):
    model_config = ConfigDict(validate_assignment=True)

    root: list[Allocation]

    @property
    def label(self) -> str:
        return ",\n".join(allocation.label for allocation in self.root)

    def add_allocation(self, new_allocation: Allocation):
        for allocation in self.root:
            if new_allocation.security == allocation.security:
                allocation.weight = new_allocation.weight
                break
        else:
            self.root.append(new_allocation)

    def to_plotly_options(self) -> dict[str, str]:
        return {
            allocation.model_dump_json(exclude_none=True): allocation.label
            for allocation in self.root
        }


def convert_percent_to_decimal(v: float) -> float:
    return v / 100


class AccumulationStrategy(BaseModel):
    strategy_portfolio: Portfolio
    currency: Currency
    investment_amount: float = Field(default=0, ge=0)
    monthly_investment: float = Field(default=0, ge=0)
    adjust_monthly_investment_for_inflation: bool = False
    investment_horizon: int = Field(gt=0)
    dca_length: int = Field(gt=0)
    dca_interval: int = Field(default=1, ge=1)
    adjust_portfolio_value_for_inflation: bool = False
    variable_transaction_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)
    fixed_transaction_fees: float = Field(default=0, ge=0)
    annualised_holding_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_dca_length_le_horizon(self):
        if self.dca_length > self.investment_horizon:
            raise ValueError("DCA length must not exceed investment horizon")
        return self

    @model_validator(mode="after")
    def check_nonzero_investment(self):
        if self.investment_amount == 0 and self.monthly_investment == 0:
            raise ValueError(
                "At least one of investment amount or monthly investment must be greater than 0"
            )
        return self

    @property
    def label(self) -> str:
        return (
            f"{self.strategy_portfolio.label} {self.currency}\n"
            f"${self.investment_amount:,.0f} initial capital\n"
            f"${self.monthly_investment:,.0f} invested monthly"
            f"{', inflation adjusted' if self.adjust_monthly_investment_for_inflation else ''}\n"
            f"for {self.dca_length} months every {self.dca_interval} months\n"
            f"held for {self.investment_horizon} months\n"
            f"{self.variable_transaction_fees:.2%} + ${self.fixed_transaction_fees} Fee\n"
            f"{self.annualised_holding_fees:.2%} p.a. Holding Fees\n"
            f"Portfolio value {'' if self.adjust_portfolio_value_for_inflation else 'not '}adjusted for inflation"
        )


class AccumulationBootstrapStrategy(AccumulationStrategy):
    num_bootstrap_samples: int = Field(default=1000, gt=0)
    avg_block_length: float = Field(default=120, gt=0)

    @property
    def label(self) -> str:
        return (
            f"{super().label}\n"
            f"{self.num_bootstrap_samples} samples, {self.avg_block_length:.0f}mo avg block"
        )


class WithdrawalStrategy(BaseModel):
    strategy_portfolio: Portfolio
    currency: Currency
    initial_capital: float = Field(gt=0)
    monthly_withdrawal: float = Field(gt=0)
    adjust_for_inflation: bool = False
    withdrawal_horizon: int = Field(gt=0)
    withdrawal_interval: int = Field(default=1, ge=1)
    variable_transaction_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)
    fixed_transaction_fees: float = Field(default=0, ge=0)
    annualised_holding_fees: Annotated[
        float, AfterValidator(convert_percent_to_decimal)
    ] = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_withdrawal_sustainable(self):
        if self.initial_capital <= self.monthly_withdrawal * self.withdrawal_interval:
            raise ValueError("Initial capital must exceed initial withdrawal amount")
        return self

    @property
    def label(self) -> str:
        return (
            f"{self.strategy_portfolio.label} {self.currency}\n"
            f"${self.initial_capital:,.0f} initial capital\n"
            f"${self.monthly_withdrawal:,.0f} withdrawn monthly"
            f"{', inflation adjusted' if self.adjust_for_inflation else ''}\n"
            f"every {self.withdrawal_interval} months for {self.withdrawal_horizon} months\n"
            f"{self.variable_transaction_fees:.2%} + ${self.fixed_transaction_fees} Fee\n"
            f"{self.annualised_holding_fees:.2%} p.a. Holding Fees"
        )


class WithdrawalBootstrapStrategy(WithdrawalStrategy):
    num_bootstrap_samples: int = Field(default=1000, gt=0)
    avg_block_length: float = Field(default=120, gt=0)

    @property
    def label(self) -> str:
        return (
            f"{super().label}\n"
            f"{self.num_bootstrap_samples} samples, {self.avg_block_length:.0f}mo avg block"
        )
