import numpy as np


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


def calculate_return_vector(
    monthly_returns: np.ndarray, dca_length: int, investment_horizon: int
):
    if investment_horizon < dca_length:
        raise ValueError(
            "Investment horizon must be greater than or equal to DCA length"
        )
    res = np.empty_like(monthly_returns)
    res.fill(np.nan)
    monthly_returns = 1 + monthly_returns
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
            continue
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


def calculate_lumpsum_portfolio_value_with_fees_and_interest_vector(
    monthly_returns: np.ndarray,
    dca_length: int,
    dca_interval: int,
    investment_horizon: int,
    total_investment: float,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
    interest_rates: np.ndarray,
):
    if investment_horizon < dca_length:
        raise ValueError(
            f"Investment horizon ({investment_horizon}) "
            f"must be greater than or equal to "
            f"DCA length ({dca_length})"
        )
    if fixed_transaction_fees >= total_investment / dca_length * dca_interval:
        raise ValueError(
            f"Fixed fees ({fixed_transaction_fees}) "
            f"must be less than "
            f"the amount invested in each DCA ({total_investment / dca_length * dca_interval})"
        )
    if dca_interval > dca_length:
        raise ValueError(
            f"DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})"
        )
    if dca_interval >= investment_horizon / 2:
        print(
            f"Warning: DCA interval ({dca_interval}) "
            f"is large relative to investment horizon ({investment_horizon}). "
            f"Figures might not be representative of market returns"
        )
    res = np.empty_like(monthly_returns)
    res.fill(np.nan)
    monthly_returns_with_fees = (
        (1 + monthly_returns) ** 12 - annualised_holding_fees
    ) ** (1 / 12)
    cash_returns = (1 + interest_rates / 100) ** (1 / 12)
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
            continue
        share_value = 0
        dca_amount = total_investment / np.ceil(dca_length / dca_interval)
        cash = total_investment
        capital = total_investment
        for index, j in enumerate(
            range(i - investment_horizon, i - investment_horizon + dca_length)
        ):
            if index % dca_interval == 0:
                share_value += (dca_amount + cash - capital) * (
                    1 - variable_transaction_fees
                ) - fixed_transaction_fees
                capital -= dca_amount
                cash = capital
            share_value *= monthly_returns_with_fees[j + 1]
            cash *= cash_returns[j + 1]
        cash = 0
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= monthly_returns_with_fees[j + 1]
        res[i] = share_value
    return res


def calculate_dca_portfolio_value_with_fees_and_interest_vector(
    monthly_returns: np.ndarray,
    dca_length: int,
    dca_interval: int,
    investment_horizon: int,
    initial_monthly_amount: float,
    cpi: np.ndarray,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
    interest_rates: np.ndarray,
):
    dca_amount = initial_monthly_amount * dca_interval
    if fixed_transaction_fees >= dca_amount:
        raise ValueError("Fixed fees must be less than the amount invested in each DCA")
    if dca_interval > dca_length:
        raise ValueError(
            f"DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})"
        )
    res = np.empty_like(monthly_returns)
    res.fill(np.nan)
    monthly_returns_with_fees = (
        (1 + monthly_returns) ** 12 - annualised_holding_fees
    ) ** (1 / 12)
    cash_returns = (1 + interest_rates / 100) ** (1 / 12)
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
            continue
        share_value = 0
        funds_to_invest = 0
        monthly_amounts = (
            cpi[i - investment_horizon : i - investment_horizon + dca_length]
            / cpi[i - investment_horizon]
            * initial_monthly_amount
        )
        for index, j in enumerate(
            range(i - investment_horizon, i - investment_horizon + dca_length)
        ):
            funds_to_invest += monthly_amounts[index]
            if ((index + 1) % dca_interval == 0) or (index + 1 == dca_length):
                share_value += (
                    funds_to_invest * (1 - variable_transaction_fees)
                    - fixed_transaction_fees
                )
                funds_to_invest = 0
            else:
                funds_to_invest *= cash_returns[j + 1]
            share_value *= monthly_returns_with_fees[j + 1]
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= monthly_returns_with_fees[j + 1]
        res[i] = share_value
    return res


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
    res = np.zeros(len(monthly_returns))
    for i in range(len(monthly_returns)):
        if i < withdrawal_horizon:
            res[i] = np.nan
            continue
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
                    share_value = 0
                    break
            share_value *= monthly_returns_with_fees[j + 1]
        res[i] = share_value
    return res
