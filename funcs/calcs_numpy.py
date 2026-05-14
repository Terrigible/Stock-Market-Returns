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


@njit(int64[:, :](int64, int64, int64, float64))
def generate_bootstrap_indices(
    num_samples: int,
    sample_length: int,
    n_data: int,
    avg_block_length: float,
):
    res = np.empty((num_samples, sample_length), dtype=np.int64)
    p = 1.0 / avg_block_length
    log_1_minus_p = np.log(1.0 - p)
    tiny = np.finfo(np.float64).tiny
    for s in range(num_samples):
        pos = 0
        while pos < sample_length:
            i = np.random.randint(0, n_data)
            u = max(np.random.random(), tiny)
            block_len = min(
                int(np.ceil(np.log(u) / log_1_minus_p)), sample_length - pos
            )
            for j in range(block_len):
                res[s, pos + j] = (i + j) % n_data
            pos += block_len
    return res


@njit(
    float64[:, :](
        float64[:],
        float64[:],
        float64[:],
        int64[:, :],
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
    )
)
def simulate_bootstrap_accumulation(
    monthly_returns: np.ndarray,
    cpi: np.ndarray,
    cash_returns: np.ndarray,
    bootstrap_indices: np.ndarray,
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
) -> np.ndarray:
    num_samples = bootstrap_indices.shape[0]
    res = np.zeros((num_samples, investment_horizon + 1))
    annual_fee_factor = (1.0 - annualised_holding_fees) ** (1.0 / 12.0)
    dca_len = dca_length if dca_length <= investment_horizon else investment_horizon
    for s in range(num_samples):
        idx = bootstrap_indices[s]
        boot_ret_fees = (1.0 + monthly_returns[idx]) * annual_fee_factor
        boot_cpi = cpi[idx]
        boot_cash = cash_returns[idx]
        cum_cpi = np.empty(investment_horizon + 1)
        cum_cpi[0] = 1.0
        for t in range(investment_horizon):
            cum_cpi[t + 1] = cum_cpi[t] * (1.0 + boot_cpi[t])
        res[s, 0] = initial_portfolio_value
        share_value = initial_portfolio_value
        funds_to_invest = 0.0
        monthly_amounts = np.full(dca_len + 1, initial_monthly_amount)
        if adjust_monthly_investment_for_inflation:
            monthly_amounts *= cum_cpi[: dca_len + 1] / cum_cpi[1]
        for t in range(1, dca_len + 1):
            share_value *= boot_ret_fees[t]
            funds_to_invest += monthly_amounts[t]
            if (t % dca_interval == 0) or (t == dca_len):
                share_value += (
                    funds_to_invest * (1.0 - variable_transaction_fees)
                    - fixed_transaction_fees
                )
                funds_to_invest = 0.0
            else:
                funds_to_invest *= 1.0 + boot_cash[t]
            res[s, t] = share_value + funds_to_invest
        for t in range(dca_len + 1, investment_horizon + 1):
            share_value *= boot_ret_fees[t]
            res[s, t] = share_value
        if adjust_portfolio_value_for_inflation:
            res[s] /= cum_cpi
    return res


@njit(
    float64[:, :](
        float64[:],
        float64[:],
        int64[:, :],
        int64,
        int64,
        float64,
        float64,
        float64,
        float64,
        float64,
    )
)
def simulate_bootstrap_withdrawal(
    monthly_returns: np.ndarray,
    cpi: np.ndarray,
    bootstrap_indices: np.ndarray,
    withdrawal_horizon: int,
    withdrawal_interval: int,
    initial_portfolio_value: float,
    initial_monthly_withdrawal: float,
    variable_transaction_fees: float,
    fixed_transaction_fees: float,
    annualised_holding_fees: float,
) -> np.ndarray:
    num_samples = bootstrap_indices.shape[0]
    res = np.zeros((num_samples, withdrawal_horizon + 1))
    annual_fee_factor = (1.0 - annualised_holding_fees) ** (1.0 / 12.0)
    initial_withdrawal_amount = initial_monthly_withdrawal * withdrawal_interval
    for s in range(num_samples):
        idx = bootstrap_indices[s]
        boot_ret_fees = (1.0 + monthly_returns[idx]) * annual_fee_factor
        boot_cpi = cpi[idx]
        cum_cpi = np.empty(withdrawal_horizon)
        cum_cpi[0] = 1.0
        for t in range(withdrawal_horizon - 1):
            cum_cpi[t + 1] = cum_cpi[t] * (1.0 + boot_cpi[t])
        withdrawal_amounts = np.zeros(withdrawal_horizon + 1)
        for t in range(withdrawal_horizon):
            withdrawal_amounts[t + 1] = (
                cum_cpi[t]
                * initial_withdrawal_amount
                * (1.0 + variable_transaction_fees)
                + fixed_transaction_fees
            )
        res[s, 0] = initial_portfolio_value
        share_value = initial_portfolio_value
        for t in range(1, withdrawal_horizon + 1):
            if (t - 1) % withdrawal_interval == 0:
                share_value -= withdrawal_amounts[t]
                if share_value <= 0.0:
                    res[s, t:] = 0.0
                    break
            share_value *= boot_ret_fees[t]
            res[s, t] = share_value
    return res


@njit(float64[:, :](float64[:, :]))
def compute_bootstrap_max_drawdown(portfolio_values: np.ndarray) -> np.ndarray:
    num_samples = portfolio_values.shape[0]
    num_months = portfolio_values.shape[1]
    res = np.zeros((num_samples, num_months))
    for s in range(num_samples):
        running_max = portfolio_values[s, 0]
        max_dd = 0.0
        res[s, 0] = 0.0
        for t in range(1, num_months):
            if portfolio_values[s, t] > running_max:
                running_max = portfolio_values[s, t]
            dd = running_max - portfolio_values[s, t]
            if dd > max_dd:
                max_dd = dd
            res[s, t] = max_dd
    return res
