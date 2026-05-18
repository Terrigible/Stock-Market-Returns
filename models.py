from enum import StrEnum


class Option(StrEnum):
    label: str

    def __new__(cls, value: str, label: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        return obj

    @classmethod
    def to_dict(cls):
        return {option.value: option.label for option in cls}


class SecurityType(Option):
    INDEX = ("Index", "Index")
    PRESET_FUND = ("Preset Fund", "Preset Fund")
    YAHOO_FINANCE = ("Yahoo Finance", "Yahoo Finance")
    FINANCIAL_TIMES = ("Financial Times", "Financial Times")


class IndexProvider(Option):
    MSCI = ("MSCI", "MSCI")
    FRED = ("FRED", "FRED")
    MAS = ("MAS", "MAS")
    OTHERS = ("Others", "Others")


class MSCIIndexType(Option):
    REGIONAL = ("Regional", "Regional")
    COUNTRY = ("Country", "Country")


class MSCIRegionalIndex(Option):
    WORLD = ("WORLD", "World")
    ACWI = ("ACWI", "ACWI")
    EMERGING_MARKETS = ("EM (EMERGING MARKETS)", "Emerging Markets")
    WORLD_EX_USA = ("WORLD ex USA", "World ex USA")
    KOKUSAI_INDEX = ("KOKUSAI INDEX (WORLD ex JP)", "World ex Japan")
    EUROPE = ("EUROPE", "Europe")


class MSCICountryIndex(Option):
    AUSTRALIA = ("AUSTRALIA", "Australia")
    AUSTRIA = ("AUSTRIA", "Austria")
    BELGIUM = ("BELGIUM", "Belgium")
    CANADA = ("CANADA", "Canada")
    DENMARK = ("DENMARK", "Denmark")
    FINLAND = ("FINLAND", "Finland")
    FRANCE = ("FRANCE", "France")
    GERMANY = ("GERMANY", "Germany")
    HONG_KONG = ("HONG KONG", "Hong Kong")
    IRELAND = ("IRELAND", "Ireland")
    ISRAEL = ("ISRAEL", "Israel")
    ITALY = ("ITALY", "Italy")
    JAPAN = ("JAPAN", "Japan")
    NIHONKABU = ("NIHONKABU", "Nihonkabu (Japan ex REITs)")
    NETHERLANDS = ("NETHERLANDS", "Netherlands")
    NEW_ZEALAND = ("NEW ZEALAND", "New Zealand")
    NORWAY = ("NORWAY", "Norway")
    PORTUGAL = ("PORTUGAL", "Portugal")
    SINGAPORE = ("SINGAPORE", "Singapore")
    SPAIN = ("SPAIN", "Spain")
    SWEDEN = ("SWEDEN", "Sweden")
    SWITZERLAND = ("SWITZERLAND", "Switzerland")
    UNITED_KINGDOM = ("UNITED KINGDOM", "United Kingdom")
    USA = ("USA", "USA")


class MSCISize(Option):
    STANDARD = ("STANDARD", "Standard")
    SMALL = ("SMALL", "Small")
    SMID = ("SMID", "SMID")
    MID = ("MID", "Mid")
    LARGE = ("LARGE", "Large")
    IMI = ("IMI", "IMI")


class MSCIStyle(Option):
    BLEND = ("BLEND", "None")
    GROWTH = ("GROWTH", "Growth")
    VALUE = ("VALUE", "Value")


class TaxTreatment(Option):
    GROSS = ("Gross", "Gross")
    NET = ("Net", "Net")


class FREDIndex(Option):
    US_T = ("US-T", "US Treasuries")
    FFR = ("FFR", "Fed Funds Rate")


class USTreasuryDuration(Option):
    DURATION_1MO = ("1MO", "1 Month")
    DURATION_3MO = ("3MO", "3 Months")
    DURATION_6MO = ("6MO", "6 Months")
    DURATION_1Y = ("1", "1 Year")
    DURATION_2Y = ("2", "2 Years")
    DURATION_3Y = ("3", "3 Years")
    DURATION_5Y = ("5", "5 Years")
    DURATION_7Y = ("7", "7 Years")
    DURATION_10Y = ("10", "10 Years")
    DURATION_20Y = ("20", "20 Years")
    DURATION_30Y = ("30", "30 Years")


class MASIndex(Option):
    SGS = ("SGS", "SGS")
    SORA = ("SORA", "SORA")


class SGSDuration(Option):
    DURATION_1Y = ("1", "1 Year")
    DURATION_2Y = ("2", "2 Years")
    DURATION_5Y = ("5", "5 Years")
    DURATION_10Y = ("10", "10 Years")
    DURATION_15Y = ("15", "15 Years")
    DURATION_20Y = ("20", "20 Years")
    DURATION_30Y = ("30", "30 Years")
    DURATION_50Y = ("50", "50 Years")


class OthersIndex(Option):
    SPX = ("SPX", "S&P 500")
    SHILLER_SPX = ("SHILLER_SPX", "Shiller S&P 500")
    SREIT = ("SREIT", "iEdge S-REIT Leaders")


class FundCompany(Option):
    GREATLINK = ("GreatLink", "GreatLink")
    GMO = ("GMO", "GMO")
    FUNDSMITH = ("Fundsmith", "Fundsmith")
    DIMENSIONAL = ("Dimensional", "Dimensional")


class GreatLinkFund(Option):
    ASEAN_GROWTH_FUND = ("ASEAN Growth Fund", "ASEAN Growth Fund")
    ASIA_DIVIDEND_ADVANTAGE_FUND = (
        "Asia Dividend Advantage Fund",
        "Asia Dividend Advantage Fund",
    )
    ASIA_HIGH_DIVIDEND_EQUITY_FUND = (
        "Asia High Dividend Equity Fund",
        "Asia High Dividend Equity Fund",
    )
    ASIA_PACIFIC_EQUITY_FUND = ("Asia Pacific Equity Fund", "Asia Pacific Equity Fund")
    CASH_FUND = ("Cash Fund", "Cash Fund")
    CHINA_GROWTH_FUND = ("China Growth Fund", "China Growth Fund")
    DIVERSIFIED_GROWTH_PORTFOLIO = (
        "Diversified Growth Portfolio",
        "Diversified Growth Portfolio",
    )
    DYNAMIC_BALANCED_PORTFOLIO = (
        "Dynamic Balanced Portfolio",
        "Dynamic Balanced Portfolio",
    )
    DYNAMIC_GROWTH_PORTFOLIO = ("Dynamic Growth Portfolio", "Dynamic Growth Portfolio")
    DYNAMIC_SECURE_PORTFOLIO = ("Dynamic Secure Portfolio", "Dynamic Secure Portfolio")
    EUROPEAN_SUSTAINABLE_EQUITY_FUND = (
        "European Sustainable Equity Fund",
        "European Sustainable Equity Fund",
    )
    FAR_EAST_EX_JAPAN_EQUITIES_FUND = (
        "Far East Ex Japan Equities Fund",
        "Far East Ex Japan Equities Fund",
    )
    GLOBAL_BOND_FUND = ("Global Bond Fund", "Global Bond Fund")
    GLOBAL_DISRUPTIVE_INNOVATION_FUND = (
        "Global Disruptive Innovation Fund",
        "Global Disruptive Innovation Fund",
    )
    GLOBAL_EMERGING_MARKETS_EQUITY_FUND = (
        "Global Emerging Markets Equity Fund",
        "Global Emerging Markets Equity Fund",
    )
    GLOBAL_EQUITY_ALPHA_FUND = ("Global Equity Alpha Fund", "Global Equity Alpha Fund")
    GLOBAL_EQUITY_FUND = ("Global Equity Fund", "Global Equity Fund")
    GLOBAL_PERSPECTIVE_FUND = ("Global Perspective Fund", "Global Perspective Fund")
    GLOBAL_REAL_ESTATE_SECURITIES_FUND = (
        "Global Real Estate Securities Fund",
        "Global Real Estate Securities Fund",
    )
    GLOBAL_SUPREME_FUND = ("Global Supreme Fund", "Global Supreme Fund")
    GLOBAL_TECHNOLOGY_FUND = ("Global Technology Fund", "Global Technology Fund")
    INCOME_BOND_FUND = ("Income Bond Fund", "Income Bond Fund")
    INCOME_FOCUS_FUND = ("Income Focus Fund", "Income Focus Fund")
    INTERNATIONAL_HEALTH_CARE_FUND = (
        "International Health Care Fund",
        "International Health Care Fund",
    )
    LIFESTYLE_BALANCED_PORTFOLIO = (
        "Lifestyle Balanced Portfolio",
        "Lifestyle Balanced Portfolio",
    )
    LIFESTYLE_DYNAMIC_PORTFOLIO = (
        "Lifestyle Dynamic Portfolio",
        "Lifestyle Dynamic Portfolio",
    )
    LIFESTYLE_PROGRESSIVE_PORTFOLIO = (
        "Lifestyle Progressive Portfolio",
        "Lifestyle Progressive Portfolio",
    )
    LIFESTYLE_SECURE_PORTFOLIO = (
        "Lifestyle Secure Portfolio",
        "Lifestyle Secure Portfolio",
    )
    LIFESTYLE_STEADY_PORTFOLIO = (
        "Lifestyle Steady Portfolio",
        "Lifestyle Steady Portfolio",
    )
    LION_ASIAN_BALANCED_FUND = ("Lion Asian Balanced Fund", "Lion Asian Balanced Fund")
    LION_INDIA_FUND = ("Lion India Fund", "Lion India Fund")
    LION_JAPAN_GROWTH_FUND = ("Lion Japan Growth Fund", "Lion Japan Growth Fund")
    LION_VIETNAM_FUND = ("Lion Vietnam Fund", "Lion Vietnam Fund")
    MULTI_SECTOR_INCOME_FUND = ("Multi-Sector Income Fund", "Multi-Sector Income Fund")
    MULTI_THEME_EQUITY_FUND = ("Multi-Theme Equity Fund", "Multi-Theme Equity Fund")
    SHORT_DURATION_BOND_FUND = ("Short Duration Bond Fund", "Short Duration Bond Fund")
    SINGAPORE_EQUITIES_FUND = ("Singapore Equities Fund", "Singapore Equities Fund")
    SINGAPORE_PHYSICAL_GOLD_FUND = (
        "Singapore Physical Gold Fund",
        "Singapore Physical Gold Fund",
    )
    SUSTAINABLE_GLOBAL_THEMATIC_FUND = (
        "Sustainable Global Thematic Fund",
        "Sustainable Global Thematic Fund",
    )
    US_INCOME_AND_GROWTH_FUND_DIS = (
        "US Income and Growth Fund (Dis)",
        "US Income and Growth Fund (Dis)",
    )


class GMOFund(Option):
    QUALITY_INVESTMENT_FUND = ("Quality Investment Fund", "Quality Investment Fund")


class FundsmithFund(Option):
    EQUITY_FUND_CLASS_T = ("Equity Fund Class T", "Equity Fund Class T")
    EQUITY_FUND_CLASS_R = ("Equity Fund Class R", "Equity Fund Class R")


class DimensionalFund(Option):
    WORLD_EQUITY_FUND = ("World Equity Fund", "World Equity Fund")


class Interval(Option):
    MONTHLY = ("Monthly", "Monthly")
    DAILY = ("Daily", "Daily")


class Currency(Option):
    SGD = ("SGD", "SGD")
    USD = ("USD", "USD")


class YVar(Option):
    PRICE = ("price", "Price")
    DRAWDOWN = ("drawdown", "Drawdown")
    ROLLING_RETURNS = ("rolling_returns", "Rolling Returns")
    CALENDAR_RETURNS = ("calendar_returns", "Calendar Returns")


class ReturnInterval(Option):
    MONTHLY = ("1mo", "Monthly")
    QUARTERLY = ("3mo", "Quarterly")
    ANNUAL = ("1y", "Annual")


class ReturnDuration(Option):
    DURATION_1MO = ("1mo", "1 Month")
    DURATION_3MO = ("3mo", "3 Months")
    DURATION_6MO = ("6mo", "6 Months")
    DURATION_1Y = ("1y", "1 Year")
    DURATION_2Y = ("2y", "2 Years")
    DURATION_3Y = ("3y", "3 Years")
    DURATION_5Y = ("5y", "5 Years")
    DURATION_10Y = ("10y", "10 Years")
    DURATION_15Y = ("15y", "15 Years")
    DURATION_20Y = ("20y", "20 Years")
    DURATION_25Y = ("25y", "25 Years")
    DURATION_30Y = ("30y", "30 Years")


class ReturnAnnualisation(Option):
    CUMULATIVE = ("cumulative", "Cumulative")
    ANNUALISED = ("annualised", "Annualised")


class RollingReturnsPresentation(Option):
    TIMESERIES = ("timeseries", "Time Series")
    DISTRIBUTION = ("dist", "Distribution")


class DistributionChartType(Option):
    HISTOGRAM = ("hist", "Histogram")
    BOX_PLOT = ("box", "Box Plot")


class BacktestYVar(Option):
    ENDING_VALUES = ("ending_values", "Ending Values")
    MAX_DRAWDOWN = ("max_drawdown", "Max Drawdown")


class DrawdownType(Option):
    PERCENT = ("percent", "Percent Drawdown")
    DOLLAR = ("dollar", "Dollar Drawdown")


class BootstrapYVar(Option):
    PORTFOLIO_VALUES = ("portfolio_values", "Portfolio Value Quantiles")
    MAX_DRAWDOWN = ("max_drawdown", "Max Dollar Drawdown Quantiles")
