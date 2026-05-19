from glob import glob
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    computed_field,
    field_validator,
    model_validator,
)

from models import (
    DimensionalFund,
    FREDIndex,
    FundCompany,
    FundsmithFund,
    GMOFund,
    GreatLinkFund,
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


class MsciSecurity(BaseModel):
    source: Literal["MSCI"] = "MSCI"
    msci_base_index: MSCIRegionalIndex | MSCICountryIndex
    msci_size: MSCISize
    msci_style: MSCIStyle
    msci_tax_treatment: TaxTreatment

    @computed_field
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


class FredTreasurySecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.US_T] = FREDIndex.US_T
    us_treasury_duration: USTreasuryDuration

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.us_treasury_duration.label} {self.fred_index.label}"


class FredFfrSecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.FFR] = FREDIndex.FFR

    @computed_field
    @property
    def label(self) -> str:
        return self.fred_index.label


FredSecurity = Annotated[
    FredTreasurySecurity | FredFfrSecurity,
    Field(discriminator="fred_index"),
]


class MasSgsSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SGS] = MASIndex.SGS
    sgs_duration: SGSDuration

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.sgs_duration.label} {self.mas_index.label}"


class MasSoraSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SORA] = MASIndex.SORA

    @computed_field
    @property
    def label(self) -> str:
        return self.mas_index.label


MasSecurity = Annotated[
    MasSgsSecurity | MasSoraSecurity,
    Field(discriminator="mas_index"),
]


class SpxSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SPX] = OthersIndex.SPX
    others_tax_treatment: TaxTreatment

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.others_index.label} {self.others_tax_treatment.label}"


class ShillerSpxSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SHILLER_SPX] = OthersIndex.SHILLER_SPX
    others_tax_treatment: TaxTreatment

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.others_index.label} {self.others_tax_treatment.label}"


class SreitSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SREIT] = OthersIndex.SREIT
    others_tax_treatment: TaxTreatment = TaxTreatment.GROSS

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.others_index.label} {self.others_tax_treatment.label}"

    @field_validator("others_tax_treatment", mode="after")
    @classmethod
    def is_gross(cls, _):
        return TaxTreatment.GROSS


OthersSecurity = Annotated[
    SpxSecurity | ShillerSpxSecurity | SreitSecurity,
    Field(discriminator="others_index"),
]


class YfSecurity(BaseModel):
    source: Literal["YF"] = "YF"
    ticker: str
    currency: str
    tax_treatment: TaxTreatment

    @computed_field
    @property
    def label(self) -> str:
        return f"yfinance: {self.ticker} {self.tax_treatment.label}"


class FtSecurity(BaseModel):
    source: Literal["FT"] = "FT"
    ticker: str
    currency: str
    dividends: bool

    @computed_field
    @property
    def label(self) -> str:
        return f"FT: {self.ticker} {('(With Dividends)') * self.dividends}"


class GreatlinkSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GREATLINK] = FundCompany.GREATLINK
    fund: GreatLinkFund
    currency: Literal["SGD"] = "SGD"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"


class GMOSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GMO] = FundCompany.GMO
    fund: GMOFund
    currency: Literal["USD"] = "USD"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"


class FundsmithSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.FUNDSMITH] = FundCompany.FUNDSMITH
    fund: FundsmithFund
    currency: Literal["EUR"] = "EUR"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"


class DimensionalSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.DIMENSIONAL] = FundCompany.DIMENSIONAL
    fund: DimensionalFund
    currency: Literal["GBP"] = "GBP"

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.fund_company.label} {self.fund.label}"


FundSecurity = Annotated[
    GreatlinkSecurity | GMOSecurity | FundsmithSecurity | DimensionalSecurity,
    Field(discriminator="fund_company"),
]


IndexSecurity = Annotated[
    MsciSecurity | FredSecurity | MasSecurity | OthersSecurity,
    Field(discriminator="source"),
]


Security = Annotated[
    MsciSecurity
    | FredSecurity
    | MasSecurity
    | OthersSecurity
    | YfSecurity
    | FtSecurity
    | FundSecurity,
    Field(discriminator="source"),
]

parse_security = TypeAdapter(Security).validate_json
