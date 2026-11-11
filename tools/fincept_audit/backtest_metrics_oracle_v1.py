"""Independent performance-metric oracle for a backtest equity curve.

Standard library only. Ratios that are rational (total return, drawdown, win
rate, profit factor, per-trade averages) are exact `Fraction`s. Roots and
powers (annualised return, volatility, Sharpe, Sortino, Calmar) are evaluated
with 60-digit `Decimal` arithmetic from those exact inputs.

The definitions follow what the ORIGINAL Fincept provider states in its
`assumptions.annualization` text and metric docstrings; they are conventions,
several of them not the textbook ones, so they are spelled out here:

  * years = bars / periods_per_year (bars, not bars-1);
    annualised return (CAGR) = (final / initial) ** (1 / years) - 1.
  * per-bar return r_i = equity_i / equity_{i-1} - 1.
  * volatility = sample standard deviation of r (n-1 divisor) * sqrt(ppy).
  * Sharpe = (CAGR - rf) / volatility.  NOT mean(r)*ppy / volatility.
  * Sortino = (CAGR - rf) / downside, downside = sqrt(mean(min(r - rf/ppy, 0)^2))
    over ALL bars * sqrt(ppy).
  * max drawdown = largest (peak - equity) / peak, peak being the running
    maximum of equity itself (the initial capital is not an extra peak).
  * Calmar = CAGR / max drawdown.
  * a trade with P&L <= 0 is a losing trade; average / largest win and loss and
    expectancy are P&L divided by the INITIAL capital, not per-trade returns.
  * profit factor = sum(winning P&L) / sum(|losing P&L|); infinite (None here)
    when there are winners and no losing P&L.

`conventional_sharpe` (arithmetic mean based) is returned next to the stated
one only so the gap between the two conventions is visible. Synthetic input
only; no number here is evidence about any market.
"""
from __future__ import annotations

from decimal import Decimal, getcontext, localcontext
from fractions import Fraction

PRECISION = 60


class MetricsRefused(ValueError):
    pass


def _dec(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def metrics(equity, trades, initial_capital, periods_per_year: int, risk_free_rate=Fraction(0)) -> dict:
    """`equity`: list of Fractions per bar. `trades`: dicts with a Fraction `pnl`."""
    if isinstance(periods_per_year, bool) or not isinstance(periods_per_year, int) or periods_per_year <= 0:
        raise MetricsRefused("INVALID_PERIODS_PER_YEAR")
    initial = Fraction(initial_capital)
    rf = Fraction(risk_free_rate)
    if len(equity) < 3 or initial <= 0 or any(not isinstance(x, Fraction) or x <= 0 for x in equity):
        raise MetricsRefused("INVALID_EQUITY")
    if not 0 <= rf < 1:
        raise MetricsRefused("INVALID_RISK_FREE_RATE")
    bars = len(equity)
    ppy = Fraction(periods_per_year)
    returns = [equity[i] / equity[i - 1] - 1 for i in range(1, bars)]
    mean = sum(returns, Fraction(0)) / len(returns)
    variance = sum(((r - mean) ** 2 for r in returns), Fraction(0)) / (len(returns) - 1)
    per_bar_rf = rf / ppy
    downside_sq = sum((min(r - per_bar_rf, Fraction(0)) ** 2 for r in returns), Fraction(0)) / len(returns)

    peak, max_drawdown = equity[0], Fraction(0)
    for value in equity:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak)

    pnl = [Fraction(t["pnl"]) for t in trades]
    winners = [x for x in pnl if x > 0]
    losers = [x for x in pnl if x <= 0]
    gross_loss = sum((-x for x in losers), Fraction(0))
    if gross_loss > 0:
        profit_factor = sum(winners, Fraction(0)) / gross_loss
    else:
        profit_factor = None if winners else Fraction(0)

    with localcontext() as context:
        context.prec = PRECISION
        growth = _dec(equity[-1] / initial)
        exponent = _dec(ppy / bars)
        cagr = (growth.ln() * exponent).exp() - 1
        volatility = (_dec(variance) * _dec(ppy)).sqrt()
        downside = (_dec(downside_sq) * _dec(ppy)).sqrt()
        excess = cagr - _dec(rf)
        sharpe = excess / volatility if volatility > Decimal("1e-10") else Decimal(0)
        sortino = excess / downside if downside > Decimal("1e-10") else Decimal(0)
        calmar = cagr / _dec(max_drawdown) if max_drawdown > 0 else Decimal(0)
        conventional = ((_dec(mean) * _dec(ppy) - _dec(rf)) / volatility
                        if volatility > Decimal("1e-10") else Decimal(0))

    return {
        "total_return": equity[-1] / initial - 1,
        "max_drawdown": max_drawdown,
        "total_trades": len(pnl),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": Fraction(len(winners), len(pnl)) if pnl else Fraction(0),
        "profit_factor": profit_factor,
        "average_win": sum(winners, Fraction(0)) / len(winners) / initial if winners else Fraction(0),
        "average_loss": sum(losers, Fraction(0)) / len(losers) / initial if losers else Fraction(0),
        "largest_win": max(winners) / initial if winners else Fraction(0),
        "largest_loss": min(losers) / initial if losers else Fraction(0),
        "expectancy": sum(pnl, Fraction(0)) / len(pnl) / initial if pnl else Fraction(0),
        "winning_bars": sum(1 for r in returns if r > 0),
        "losing_bars": sum(1 for r in returns if r < 0),
        "average_bar_return": mean,
        "best_bar": max(returns),
        "worst_bar": min(returns),
        "annualized_return": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "conventional_sharpe": conventional,
        "periods_per_year": periods_per_year,
    }
