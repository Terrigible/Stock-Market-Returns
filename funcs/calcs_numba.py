from numba import float64, guvectorize, int64, njit

import numpy as np
import pandas as pd


@njit
def calculate_return(ending_index: int, dca_length: int, monthly_returns: pd.Series | np.ndarray, investment_horizon=None):
    if investment_horizon is None:
        investment_horizon = dca_length
    elif investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    if ending_index < dca_length:
        return np.nan
    share_value = 0
    cash = 1
    for i in range(ending_index - investment_horizon, ending_index - investment_horizon + dca_length):
        cash -= 1/dca_length
        share_value += 1/dca_length
        share_value *= 1 + monthly_returns[i+1]
    for i in range(ending_index - investment_horizon + dca_length, ending_index):
        share_value *= 1 + monthly_returns[i+1]
    return share_value - 1


@guvectorize([(int64, float64[:], int64, float64[:])], '(),(n),()->(n)', target='cpu', nopython=True)
def calculate_return_vector(dca_length: int, monthly_returns: pd.Series | np.ndarray, investment_horizon: int, res=np.array([])):
    if investment_horizon < dca_length:
        raise ValueError('Investment horizon must be greater than or equal to DCA length')
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
            continue
        share_value = 0
        cash = 1
        for j in range(i - investment_horizon, i - investment_horizon + dca_length):
            cash -= 1/dca_length
            share_value += 1/dca_length
            share_value *= 1 + monthly_returns[j+1]
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= 1 + monthly_returns[j+1]
        res[i] = share_value - 1


@guvectorize([(float64, float64, float64, float64, int64, int64, int64, float64[:], float64[:], float64[:])], '(),(),(),(),(),(),(),(n),(n)->(n)', target='cpu', nopython=True)
def calculate_lumpsum_return_with_fees_and_interest_vector(variable_transaction_fees: float, fixed_transaction_fees: float, annualised_holding_fees: float, total_investment: float, dca_length: int, dca_interval: int, investment_horizon: int, monthly_returns: pd.Series | np.ndarray, interest_rates: pd.Series | np.ndarray, res=np.array([])):
    if investment_horizon < dca_length:
        raise ValueError(f'Investment horizon ({investment_horizon}) must be greater than or equal to DCA length ({dca_length})')
    if fixed_transaction_fees >= total_investment / dca_length * dca_interval:
        raise ValueError(f'Fixed fees ({fixed_transaction_fees}) must be less than the amount invested in each DCA ({total_investment / dca_length * dca_interval})')
    if dca_interval > dca_length:
        raise ValueError(f'DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})')
    if dca_interval >= investment_horizon/2:
        print(f'Warning: DCA interval ({dca_interval}) is large relative to investment horizon ({investment_horizon}). Figures might not be representative of market returns')
    for i in range(len(monthly_returns)):
        if i < investment_horizon:
            res[i] = np.nan
            continue
        share_value = 0
        dca_amount = total_investment / np.ceil(dca_length/dca_interval)
        cash = total_investment
        capital = total_investment
        for index, j in enumerate(range(i - investment_horizon, i - investment_horizon + dca_length)):
            if index % dca_interval == 0:
                share_value += (dca_amount + cash - capital) * (1 - variable_transaction_fees) - fixed_transaction_fees
                capital -= dca_amount
                cash = capital
            share_value *= ((1 + monthly_returns[j+1]) ** 12 - annualised_holding_fees) ** (1/12)
            cash *= (1 + interest_rates[j+1] / 100) ** (1/12)
        cash = 0
        for j in range(i - investment_horizon + dca_length, i):
            share_value *= 1 + monthly_returns[j+1]
        res[i] = (share_value - total_investment) / total_investment


@guvectorize([(float64, float64, float64, float64, int64, int64, float64[:], float64[:], float64[:])], '(),(),(),(),(),(),(n),(n)->(n)', target='cpu', nopython=True)
def calculate_dca_return_with_fees_and_interest_vector(variable_transaction_fees: float, fixed_transaction_fees: float, annualised_holding_fees: float, monthly_amount: float, dca_length: int, dca_interval: int, monthly_returns: pd.Series | np.ndarray, interest_rates: pd.Series | np.ndarray, res=np.array([])):
    total_investment = monthly_amount * dca_length
    dca_amount = monthly_amount * dca_interval
    if fixed_transaction_fees >= dca_amount:
        raise ValueError('Fixed fees must be less than the amount invested in each DCA')
    if dca_interval > dca_length:
        raise ValueError(f'DCA interval ({dca_interval}) must be less than or equal to DCA length ({dca_length})')
    for i in range(len(monthly_returns)):
        if i < dca_length:
            res[i] = np.nan
            continue
        share_value = 0
        funds_to_invest = 0
        for index, j in enumerate(range(i - dca_length, i)):
            funds_to_invest += monthly_amount
            if ((index + 1) % dca_interval == 0) or (index == dca_length - 1):
                share_value += funds_to_invest * (1 - variable_transaction_fees) - fixed_transaction_fees
                funds_to_invest = 0
            share_value *= ((1 + monthly_returns[j+1]) ** 12 - annualised_holding_fees) ** (1/12)
            funds_to_invest *= (1 + interest_rates[j+1] / 100) ** (1/12)
        res[i] = (share_value + funds_to_invest - total_investment) / total_investment
