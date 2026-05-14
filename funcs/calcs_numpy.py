import numpy as np
from numba import bool_, float64, int64, njit


@njit(
    float64[:, :](
        float64[:],
        int64,
        int64,
        int64,
        float64,
        float64,
        bool_,
        float64,
        float64,
        float64,
        bool_,
        float64[:],
        float64[:],
    )
)
def calculate_dca_portfolio_value_with_fees_and_interest_vector(
    monthly_returns: np.ndarray,
    dca_length: int,
    dca_interval: int,
    investment_horizon: int,
    initial_portfolio_value: float,
    initial_monthly_amount: float,
    adjust_monthly_investment_for_inflation: bool,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
    adjust_portfolio_value_for_inflation: bool,
    cpi: np.ndarray,
    cash_returns: np.ndarray,
):
    res = np.full((monthly_returns.shape[0], investment_horizon + 1), np.nan)
    res[investment_horizon:, 0] = initial_portfolio_value
    monthly_returns_with_fees = (1 + monthly_returns) * (
        1 - annualised_holding_fees
    ) ** (1 / 12)
    for i in range(investment_horizon, len(monthly_returns)):
        sample_slice = slice(i - investment_horizon, i + 1)
        sample_monthly_returns = monthly_returns_with_fees[sample_slice]
        sample_cash_returns = cash_returns[sample_slice]
        sample_cpi = cpi[sample_slice]
        share_value = initial_portfolio_value
        funds_to_invest = 0

        monthly_amounts = np.full(dca_length + 1, initial_monthly_amount)
        if adjust_monthly_investment_for_inflation:
            monthly_amounts *= sample_cpi[: dca_length + 1] / sample_cpi[1]

        for j in range(1, dca_length + 1):
            share_value *= sample_monthly_returns[j]
            funds_to_invest += monthly_amounts[j]
            if (j % dca_interval == 0) or (j == dca_length):
                share_value += (
                    funds_to_invest * (1 - variable_transaction_fees)
                    - fixed_transaction_fees
                )
                funds_to_invest = 0
            else:
                funds_to_invest *= 1 + sample_cash_returns[j]
            res[i, j] = share_value + funds_to_invest
        for j in range(dca_length + 1, investment_horizon + 1):
            share_value *= sample_monthly_returns[j]
            res[i, j] = share_value
        if adjust_portfolio_value_for_inflation:
            res[i] /= sample_cpi / sample_cpi[0]
    return res


@njit(
    float64[:, :](
        float64[:],
        int64,
        int64,
        float64,
        float64,
        float64[:],
        float64,
        float64,
        float64,
    )
)
def calculate_withdrawal_portfolio_value_with_fees_vector(
    monthly_returns: np.ndarray,
    withdrawal_horizon: int,
    withdrawal_interval: int,
    initial_portfolio_value: float,
    initial_monthly_withdrawal: float,
    cpi: np.ndarray,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
):
    initial_withdrawal_amount = initial_monthly_withdrawal * withdrawal_interval
    monthly_returns_with_fees = (1 + monthly_returns) * (
        1 - annualised_holding_fees
    ) ** (1 / 12)
    res = np.full((monthly_returns.shape[0], withdrawal_horizon + 1), np.nan)
    res[withdrawal_horizon:, 0] = initial_portfolio_value
    for i in range(withdrawal_horizon, len(monthly_returns)):
        sample_slice = slice(i - withdrawal_horizon, i + 1)
        sample_monthly_returns = monthly_returns_with_fees[sample_slice]
        sample_cpi = cpi[sample_slice]
        share_value = initial_portfolio_value
        withdrawal_amounts = (
            sample_cpi
            / sample_cpi[1]
            * initial_withdrawal_amount
            * (1 + variable_transaction_fees)
            + fixed_transaction_fees
        )
        for j in range(1, withdrawal_horizon + 1):
            if (j - 1) % withdrawal_interval == 0:
                share_value -= withdrawal_amounts[j]
                if share_value <= 0:
                    res[i, j:] = 0
                    break
            share_value *= sample_monthly_returns[j]
            res[i, j] = share_value
    return res
