from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base
from datetime import datetime


class Analyst(Base):
    __tablename__ = "analysts"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    strategy = Column(String(100), nullable=False)
    strategy_description = Column(Text)
    initial_capital = Column(Float, default=10000.0)
    current_balance = Column(Float, default=10000.0)
    avatar_color = Column(String(20), default="#6366F1")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Risk management fields
    paused_until = Column(DateTime, nullable=True)
    pause_reason = Column(String(200), nullable=True)
    consecutive_losses = Column(Integer, default=0)
    peak_balance = Column(Float, nullable=True)
    force_trade_until = Column(DateTime, nullable=True)

    trades = relationship("Trade", back_populates="analyst")
    balance_history = relationship("BalanceSnapshot", back_populates="analyst")
    messages = relationship("GroupMessage", back_populates="analyst")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    analyst_id = Column(Integer, ForeignKey("analysts.id"))
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # long / short
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)  # position size in USDT
    leverage = Column(Integer, default=1)
    realized_pnl = Column(Float, default=0.0)
    status = Column(String(10), default="open")  # open / closed
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    mode = Column(String(10), default="paper")  # paper | live | shadow

    analyst = relationship("Analyst", back_populates="trades")


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"

    id = Column(Integer, primary_key=True)
    analyst_id = Column(Integer, ForeignKey("analysts.id"))
    balance = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    analyst = relationship("Analyst", back_populates="balance_history")


class GroupMessage(Base):
    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True)
    analyst_id = Column(Integer, ForeignKey("analysts.id"))
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="analysis")  # analysis / signal / alert
    timestamp = Column(DateTime, default=datetime.utcnow)

    analyst = relationship("Analyst", back_populates="messages")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True)
    analyst_id = Column(Integer, ForeignKey("analysts.id"), nullable=True)
    strategy = Column(String(100))
    primary_symbol = Column(String(20))
    period_days = Column(Integer, default=540)
    interval = Column(String(10), default="1h")
    status = Column(String(20), default="pending")  # pending running completed failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    # Metrics
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    avg_win_usdt = Column(Float, default=0.0)
    avg_loss_usdt = Column(Float, default=0.0)
    initial_capital = Column(Float, default=10000.0)
    final_capital = Column(Float, default=0.0)
    equity_curve_json = Column(Text, nullable=True)  # [[iso_ts, balance], ...]
    error_msg = Column(Text, nullable=True)


class WalkForwardRun(Base):
    """One walk-forward validation run covers all windows for one strategy."""

    __tablename__ = "walk_forward_runs"

    id = Column(Integer, primary_key=True)
    strategy = Column(String(100), nullable=False)
    primary_symbol = Column(String(20))
    total_days = Column(Integer, default=365)
    train_days = Column(Integer, default=120)
    test_days = Column(Integer, default=60)
    status = Column(String(20), default="pending")  # pending running completed failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    n_windows = Column(Integer, default=0)
    avg_consistency = Column(Float, default=0.0)   # avg(test_return / train_return)
    results_json = Column(Text, nullable=True)      # JSON array of window dicts
    error_msg = Column(Text, nullable=True)


class RiskState(Base):
    """Single-row table tracking portfolio-level risk state."""

    __tablename__ = "risk_state"

    id = Column(Integer, primary_key=True, default=1)
    portfolio_peak = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)
