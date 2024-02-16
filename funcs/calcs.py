from functools import cache

import numpy as np
import pandas as pd


def calculate_return_vector(price: pd.Series, dca_length: int, investment_horizon: int):
    if investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    return price.shift().shift(investment_horizon-dca_length).rdiv(1/dca_length).rolling(dca_length).sum().mul(price).sub(1)


def adjust_dca_amount_with_interest(
    series: pd.Series,
    dca_length: int,
    dca_interval: int,
    cash_return: pd.Series
):
    return (
        cash_return
        .reindex(series.iloc[::dca_interval].index)
        .pow(
            pd.Series([0, *range(dca_length-dca_interval, 0-dca_interval, -dca_interval)[:-1]], index=series.iloc[::dca_interval].index)
            .div(dca_length)
        )
        .mul(series.iloc[::dca_interval])
        .sum()
    )


def calculate_lumpsum_return_with_fees_and_interest_vector(
    series: pd.Series, *,
    dca_length: int,
    dca_interval: int = 1,
    investment_horizon: None | int = None,
    investment_amount: float,
    variable_transaction_fees: float = 0,
    fixed_transaction_fees: float = 0,
    annualised_holding_fees: float = 0,
    interest_rates: None | pd.Series = None
):
    if dca_length < 1:
        print('DCA length must be greater than 0. For lump sum calculations, use dca_length=1')
        dca_length = 1
    if dca_interval < 1:
        print('DCA interval must be greater than 0.')
        dca_interval = 1
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    if interest_rates is None:
        interest_rates = pd.Series(0, index=series.index)
    else:
        interest_rates = interest_rates.reindex(series.index, fill_value=0)
    series = series.pct_change().add(1).pow(12).sub(annualised_holding_fees).pow(1/12).cumprod().fillna(1)
    cash_return = interest_rates.div(100).add(1).pow(1/12).rolling(dca_interval).apply(np.prod, raw=True)

    return (
        series
        .shift()
        .shift(investment_horizon-dca_length)
        .rdiv((investment_amount * (1 - variable_transaction_fees) - fixed_transaction_fees) / np.ceil(dca_length/dca_interval))
        .rolling(dca_length).apply(adjust_dca_amount_with_interest, args=(dca_length, dca_interval, cash_return))
        .mul(series)
        .div(investment_amount)
        .sub(1)
    )


def calculate_dca_return_with_fees_and_interest_vector(
    series: pd.Series, *,
    dca_length: int,
    dca_interval: int = 1,
    investment_horizon: None | int = None,
    monthly_amount: float,
    variable_transaction_fees: float = 0,
    fixed_transaction_fees: float = 0,
    annualised_holding_fees: float = 0,
    interest_rates: None | pd.Series = None
):
    if dca_length < 1:
        print('DCA length must be greater than 0. For lump sum calculations, use dca_length=1')
        dca_length = 1
    if dca_interval < 1:
        print('DCA interval must be greater than 0.')
        dca_interval = 1
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    investment_amount = monthly_amount * dca_length
    if interest_rates is None:
        interest_rates = pd.Series(0, index=series.index)
    else:
        interest_rates = interest_rates.reindex(series.index, fill_value=0)
    series = series.pct_change().add(1).pow(12).sub(annualised_holding_fees).pow(1/12).cumprod().fillna(1)
    cash_index = interest_rates.div(100).add(1).pow(1/12).cumprod().fillna(1)

    dca_weights = pd.RangeIndex(dca_length).to_series().mod(dca_interval).eq(dca_interval-1).mul(dca_interval)
    dca_weights[dca_length-1] = dca_length % dca_interval or dca_interval

    return_on_cash = pd.DataFrame(
        {
            dca_length:
                cash_index
                .rdiv(1/dca_length)
                .rolling(dca_length)
                .sum()
                .mul(cash_index)
            for dca_length in dca_weights.unique()
        }
    )

    return_on_cash_selection_mask = pd.DataFrame(
        {
            dca_weight:
                dca_weights.eq(dca_weight)
            for dca_weight in dca_weights.unique()
        }
    )

    fixed_transaction_fee_adjustment = dca_weights.replace(0, np.inf).rdiv(fixed_transaction_fees / monthly_amount).rsub(1)

    return (
        series
        .shift()
        .shift(investment_horizon-dca_length)
        .rdiv(monthly_amount)
        .rolling(dca_length).apply(
            lambda series:
                series
                .mul(
                    dca_weights
                    .set_axis(series.index, axis=0)
                )
                .mul(
                    return_on_cash_selection_mask
                    .set_axis(series.index, axis=0)
                    .mul(
                        return_on_cash
                        .reindex(series.index)
                    )
                    .sum(axis=1)
                )
                .mul(
                    fixed_transaction_fee_adjustment
                    .set_axis(series.index, axis=0)
                )
                .sum()
        )
        .mul(1 - variable_transaction_fees)
        .mul(series)
        .div(investment_amount)
        .sub(1)
    )
