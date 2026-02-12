import numpy as np
from numba import bool_, float64, int64, njit, optional


@njit(float64(int64, int64, float64[:], optional(int64)))
def calculate_return(
    ending_index: int,
    dca_length: int,
    monthly_returns: np.ndarray,
    investment_horizon=None,
):
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError(
            "Investment horizon must be greater than or equal to DCA length"
        )
    if ending_index < dca_length:
        return np.nan
    monthly_returns = 1 + monthly_returns
    share_value = 0
    cash = 1
    for i in range(
        ending_index - investment_horizon,
        ending_index - investment_horizon + dca_length,
    ):
        cash -= 1 / dca_length
        share_value += 1 / dca_length
        share_value *= monthly_returns[i + 1]
    for i in range(ending_index - investment_horizon + dca_length, ending_index):
        share_value *= monthly_returns[i + 1]
    return share_value - 1


@njit(float64[:](float64[:], int64, int64))
def calculate_return_vector(
    monthly_returns: np.ndarray, dca_length: int, investment_horizon: int
):
    if investment_horizon < dca_length:
        raise ValueError(
            "Investment horizon must be greater than or equal to DCA length"
        )
    res = np.full_like(monthly_returns, np.nan)
    monthly_returns = 1 + monthly_returns
    for i in range(investment_horizon, len(monthly_returns)):
        share_value = 0
        cash = 1
        for j in range(i - investment_horizon, i - investment_horizon + dca_length):
            cash -= 1 / dca_length
            share_value += 1 / dca_length
            share_value *= monthly_returns[j + 1]
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= monthly_returns[j + 1]
        res[i] = share_value - 1
    return res


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
    dca_amount = initial_monthly_amount * dca_interval
    if fixed_transaction_fees >= dca_amount:
        raise ValueError("Fixed fees must be less than the amount invested in each DCA")
    if dca_interval > dca_length:
        raise ValueError(
            f"DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})"
        )
    res = np.full((monthly_returns.shape[0], investment_horizon), np.nan)
    monthly_returns_with_fees = (
        (1 + monthly_returns) ** 12 - annualised_holding_fees
    ) ** (1 / 12)
    for i in range(investment_horizon, len(monthly_returns)):
        share_value = initial_portfolio_value
        funds_to_invest = 0

        if not adjust_monthly_investment_for_inflation:
            monthly_amounts = np.full(dca_length, initial_monthly_amount)
        else:
            monthly_amounts = (
                cpi[
                    i - investment_horizon + 1 : i - investment_horizon + dca_length + 1
                ]
                / cpi[i - investment_horizon + 1]
                * initial_monthly_amount
            )
        for index, j in enumerate(
            range(i - investment_horizon, i - investment_horizon + dca_length)
        ):
            share_value *= monthly_returns_with_fees[j + 1]
            funds_to_invest += monthly_amounts[index]
            if ((index + 1) % dca_interval == 0) or (index + 1 == dca_length):
                share_value += (
                    funds_to_invest * (1 - variable_transaction_fees)
                    - fixed_transaction_fees
                )
                funds_to_invest = 0
            else:
                funds_to_invest *= 1 + cash_returns[j + 1]
            res[i, index] = share_value
        for index, j in enumerate(range(i - investment_horizon + dca_length, i)):
            share_value *= monthly_returns_with_fees[j + 1]
            res[i, dca_length + index] = share_value
        if adjust_portfolio_value_for_inflation:
            res[i] /= (
                cpi[i - investment_horizon + 1 : i + 1] / cpi[i - investment_horizon]
            )
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
    monthly_returns_with_fees = (
        (1 + monthly_returns) ** 12 - annualised_holding_fees
    ) ** (1 / 12)
    res = np.full((monthly_returns.shape[0], withdrawal_horizon), np.nan)
    for i in range(withdrawal_horizon, len(monthly_returns)):
        share_value = initial_portfolio_value
        withdrawal_amounts = (
            cpi[i - withdrawal_horizon : i]
            / cpi[i - withdrawal_horizon]
            * initial_withdrawal_amount
            * (1 + variable_transaction_fees)
            + fixed_transaction_fees
        )
        for index, j in enumerate(range(i - withdrawal_horizon, i)):
            if index % withdrawal_interval == 0:
                share_value -= withdrawal_amounts[index]
                if share_value <= 0:
                    res[i, index:] = 0
                    break
            share_value *= monthly_returns_with_fees[j + 1]
            res[i, index] = share_value
    return res
