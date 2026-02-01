import numpy as np
import pandas as pd
from scipy.signal import correlate2d


def calculate_return_vector(price: pd.Series, dca_length: int, investment_horizon: int):
    if investment_horizon < dca_length:
        raise ValueError(
            "Investment horizon must be greater than or equal to DCA length"
        )
    return (
        price.shift()
        .shift(investment_horizon - dca_length)
        .rdiv(1 / dca_length)
        .rolling(dca_length)
        .sum()
        .mul(price)
        .sub(1)
    )


def calculate_dca_portfolio_value_with_fees_and_interest_vector(
    series: pd.Series,
    *,
    dca_length: int,
    dca_interval: int = 1,
    investment_horizon: None | int = None,
    monthly_amount: float,
    variable_transaction_fees: float = 0,
    fixed_transaction_fees: float = 0,
    annualised_holding_fees: float = 0,
    interest_rates: None | pd.Series = None,
):
    if dca_length < 1:
        print(
            "DCA length must be greater than 0. For lump sum calculations, use dca_length=1"
        )
        dca_length = 1
    if dca_interval < 1:
        print("DCA interval must be greater than 0.")
        dca_interval = 1
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError(
            "Investment horizon must be greater than or equal to DCA length"
        )
    if interest_rates is None:
        interest_rates = pd.Series(0, index=series.index)
    else:
        interest_rates = interest_rates.reindex(series.index, fill_value=0)
    series = (
        series.pct_change()
        .add(1)
        .pow(12)
        .sub(annualised_holding_fees)
        .pow(1 / 12)
        .cumprod()
        .fillna(1)
    )
    cash_index = interest_rates.div(100).add(1).pow(1 / 12).cumprod().fillna(1)

    dca_weights = (
        pd.RangeIndex(dca_length)
        .to_series()
        .mod(dca_interval)
        .eq(dca_interval - 1)
        .mul(dca_interval)
    )
    dca_weights[dca_length - 1] = dca_length % dca_interval or dca_interval

    return_on_cash = pd.DataFrame(
        {
            dca_length: cash_index.rdiv(1 / dca_length)
            .rolling(dca_length)
            .sum()
            .mul(cash_index)
            for dca_length in dca_weights.unique()
        }
    )

    return_on_cash_selection_mask = pd.DataFrame(
        {dca_weight: dca_weights.eq(dca_weight) for dca_weight in dca_weights.unique()}
    )

    dca_share_count_multiplier = dca_weights.mul(
        1 - fixed_transaction_fees / monthly_amount / dca_weights
    )

    dca_share_multiplier_plus_interest = return_on_cash_selection_mask.mul(
        dca_share_count_multiplier, axis=0
    ).fillna(0)

    shares_per_investment = (
        series.shift().shift(investment_horizon - dca_length).rdiv(monthly_amount)
    )

    shares_obtained = np.pad(
        correlate2d(
            return_on_cash.shift().mul(shares_per_investment, axis=0).to_numpy(),
            dca_share_multiplier_plus_interest.to_numpy(),
            mode="valid",
        ).flatten(),
        (dca_length - 1, 0),
        constant_values=np.nan,
    )

    return (
        pd.Series(shares_obtained, index=series.index)
        .mul(1 - variable_transaction_fees)
        .mul(series)
    )
