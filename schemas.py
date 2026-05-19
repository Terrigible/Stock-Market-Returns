from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

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


class FredTreasurySecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.US_T] = FREDIndex.US_T
    us_treasury_duration: USTreasuryDuration


class FredFfrSecurity(BaseModel):
    source: Literal["FRED"] = "FRED"
    fred_index: Literal[FREDIndex.FFR] = FREDIndex.FFR


FredSecurity = Annotated[
    FredTreasurySecurity | FredFfrSecurity,
    Field(discriminator="fred_index"),
]


class MasSgsSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SGS] = MASIndex.SGS
    sgs_duration: SGSDuration


class MasSoraSecurity(BaseModel):
    source: Literal["MAS"] = "MAS"
    mas_index: Literal[MASIndex.SORA] = MASIndex.SORA


MasSecurity = Annotated[
    MasSgsSecurity | MasSoraSecurity,
    Field(discriminator="mas_index"),
]


class SpxSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SPX] = OthersIndex.SPX
    others_tax_treatment: TaxTreatment


class ShillerSpxSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SHILLER_SPX] = OthersIndex.SHILLER_SPX
    others_tax_treatment: TaxTreatment


class SreitSecurity(BaseModel):
    source: Literal["Others"] = "Others"
    others_index: Literal[OthersIndex.SREIT] = OthersIndex.SREIT
    others_tax_treatment: TaxTreatment = TaxTreatment.GROSS

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


class FtSecurity(BaseModel):
    source: Literal["FT"] = "FT"
    ticker: str
    currency: str
    dividends: bool


class GreatlinkSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GREATLINK] = FundCompany.GREATLINK
    fund: GreatLinkFund
    currency: Literal["SGD"] = "SGD"


class GMOSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.GMO] = FundCompany.GMO
    fund: GMOFund
    currency: Literal["USD"] = "USD"


class FundsmithSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.FUNDSMITH] = FundCompany.FUNDSMITH
    fund: FundsmithFund
    currency: Literal["EUR"] = "EUR"


class DimensionalSecurity(BaseModel):
    source: Literal["Fund"] = "Fund"
    fund_company: Literal[FundCompany.DIMENSIONAL] = FundCompany.DIMENSIONAL
    fund: DimensionalFund
    currency: Literal["GBP"] = "GBP"


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
