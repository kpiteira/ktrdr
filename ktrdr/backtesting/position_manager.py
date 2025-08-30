"""Position management for backtesting system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import pandas as pd

from .. import get_logger
from ..decision.base import Signal

logger = get_logger(__name__)


class PositionStatus(Enum):
    """Position status enumeration."""

    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Position:
    """Detailed position tracking."""

    status: PositionStatus
    entry_price: float
    entry_time: pd.Timestamp
    quantity: int
    current_price: float
    last_update_time: pd.Timestamp
    unrealized_pnl: float = 0.0
    max_favorable_excursion: float = 0.0  # Best unrealized profit
    max_adverse_excursion: float = 0.0  # Worst unrealized loss

    @property
    def holding_period(self) -> float:
        """Holding period in hours."""
        if self.last_update_time and self.entry_time:
            return (self.last_update_time - self.entry_time).total_seconds() / 3600
        return 0.0

    def update(self, current_price: float, timestamp: pd.Timestamp):
        """Update position with current market price.

        Args:
            current_price: Current market price
            timestamp: Current timestamp
        """
        self.current_price = current_price
        self.last_update_time = timestamp

        # Calculate unrealized P&L
        if self.status == PositionStatus.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.status == PositionStatus.SHORT:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
        else:
            self.unrealized_pnl = 0.0

        # Track excursions
        self.max_favorable_excursion = max(
            self.max_favorable_excursion, self.unrealized_pnl
        )
        self.max_adverse_excursion = min(
            self.max_adverse_excursion, self.unrealized_pnl
        )


@dataclass
class Trade:
    """Completed trade record."""

    trade_id: int
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    entry_time: pd.Timestamp
    exit_price: float
    exit_time: pd.Timestamp
    quantity: int
    gross_pnl: float
    commission: float
    slippage: float
    net_pnl: float
    holding_period_hours: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    decision_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def return_pct(self) -> float:
        """Return percentage."""
        if self.entry_price * self.quantity == 0:
            return 0.0
        return (self.net_pnl / (self.entry_price * self.quantity)) * 100


class PositionManager:
    """Manages positions and trade execution with detailed tracking."""

    def __init__(
        self,
        initial_capital: float,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ):
        """Initialize position manager.

        Args:
            initial_capital: Starting capital
            commission: Commission rate (as fraction, e.g., 0.001 = 0.1%)
            slippage: Slippage rate (as fraction, e.g., 0.0005 = 0.05%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.current_position: Optional[Position] = None
        self.trade_history: list[Trade] = []
        self.next_trade_id = 1

    @property
    def current_position_status(self) -> PositionStatus:
        """Get current position status."""
        return (
            self.current_position.status
            if self.current_position
            else PositionStatus.FLAT
        )

    @property
    def available_capital(self) -> float:
        """Get available capital for trading."""
        if self.current_position:
            # Capital tied up in position
            position_value = (
                self.current_position.entry_price * self.current_position.quantity
            )
            return self.current_capital - position_value
        return self.current_capital

    def get_portfolio_value(self, current_price: float) -> float:
        """Get total portfolio value.

        Args:
            current_price: Current market price

        Returns:
            Total portfolio value including cash and positions
        """
        if self.current_position:
            # Calculate current position market value
            position_market_value = current_price * self.current_position.quantity

            # Update position to track unrealized P&L for reporting
            if current_price != self.current_position.current_price:
                # Calculate unrealized P&L based on current price
                if self.current_position.status == PositionStatus.LONG:
                    unrealized_pnl = (
                        current_price - self.current_position.entry_price
                    ) * self.current_position.quantity
                elif self.current_position.status == PositionStatus.SHORT:
                    unrealized_pnl = (
                        self.current_position.entry_price - current_price
                    ) * self.current_position.quantity
                else:
                    unrealized_pnl = 0.0

                # Update position's unrealized P&L for tracking
                self.current_position.unrealized_pnl = unrealized_pnl

            # CORRECT CALCULATION: Total portfolio value = cash + current position market value
            total_value = self.current_capital + position_market_value

            # DEBUG: Log portfolio calculation details
            logger.debug(
                f"Portfolio value calculation: Cash=${self.current_capital:,.2f} + "
                f"Position(${position_market_value:,.2f}) = ${total_value:,.2f}"
            )

            # Check for impossible values
            if total_value < 0:
                logger.error(
                    f"IMPOSSIBLE: Negative portfolio value ${total_value:,.2f}"
                )
            if total_value > self.initial_capital * 100:  # 10000% gain
                logger.warning(
                    f"SUSPICIOUS: Portfolio value ${total_value:,.2f} is {(total_value/self.initial_capital)*100:.0f}% of initial capital"
                )

            return total_value
        return self.current_capital

    def can_execute_trade(
        self, signal: Signal, price: float, quantity: Optional[int] = None
    ) -> bool:
        """Check if a trade can be executed.

        Args:
            signal: Trading signal
            price: Execution price
            quantity: Optional specific quantity

        Returns:
            True if trade can be executed
        """
        if signal == Signal.HOLD:
            return False

        if signal == Signal.BUY:
            # Check if we have capital and aren't already long
            if self.current_position_status == PositionStatus.LONG:
                return False

            required_capital = self._calculate_required_capital(price, quantity)
            return self.available_capital >= required_capital

        elif signal == Signal.SELL:
            # Can sell if we have a long position
            return self.current_position_status == PositionStatus.LONG

        return False

    def execute_trade(
        self,
        signal: Signal,
        price: float,
        timestamp: pd.Timestamp,
        symbol: str = "UNKNOWN",
        decision_metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Trade]:
        """Execute a trading signal.

        Args:
            signal: Trading signal
            price: Execution price
            timestamp: Execution timestamp
            symbol: Trading symbol
            decision_metadata: Additional decision metadata

        Returns:
            Trade object if trade was executed, None otherwise
        """
        if not self.can_execute_trade(signal, price):
            return None

        if decision_metadata is None:
            decision_metadata = {}

        trade = None

        if signal == Signal.BUY:
            trade = self._execute_buy(price, timestamp, symbol, decision_metadata)
        elif signal == Signal.SELL and self.current_position:
            trade = self._execute_sell(price, timestamp, symbol, decision_metadata)

        return trade

    def _execute_buy(
        self,
        price: float,
        timestamp: pd.Timestamp,
        symbol: str,
        decision_metadata: dict[str, Any],
    ) -> Optional[Trade]:
        """Execute a buy order.

        Args:
            price: Buy price
            timestamp: Execution timestamp
            symbol: Trading symbol
            decision_metadata: Decision metadata

        Returns:
            Trade object if successful
        """
        # Calculate quantity based on available capital
        quantity = self._calculate_quantity(price)
        if quantity <= 0:
            return None

        # Apply slippage (buy at higher price)
        execution_price = price * (1 + self.slippage)

        # Calculate costs
        trade_value = execution_price * quantity
        commission_cost = trade_value * self.commission
        total_cost = trade_value + commission_cost

        # Check if we still have enough capital
        if total_cost > self.available_capital:
            logger.warning(
                f"Insufficient capital: Need ${total_cost:,.2f}, have ${self.available_capital:,.2f}"
            )
            # Recalculate with reduced quantity
            max_trade_value = self.available_capital / (1 + self.commission)
            quantity = int(max_trade_value / execution_price)
            if quantity <= 0:
                logger.warning(f"Cannot afford even 1 share at ${execution_price:.2f}")
                return None

            trade_value = execution_price * quantity
            commission_cost = trade_value * self.commission
            total_cost = trade_value + commission_cost
            logger.info(
                f"Reduced quantity to {quantity} shares, new cost: ${total_cost:,.2f}"
            )

        # Update capital
        logger.debug(
            f"BUY: Deducting ${total_cost:,.2f} from capital. Before: ${self.current_capital:,.2f}"
        )
        self.current_capital -= total_cost
        logger.debug(f"BUY: Capital after trade: ${self.current_capital:,.2f}")

        # Sanity check for negative capital
        if self.current_capital < 0:
            logger.error(
                f"CRITICAL: Negative capital after BUY: ${self.current_capital:,.2f}"
            )

        # Log trade entry details with timestamp
        logger.info(
            f"Position opened: BUY {quantity} shares at ${execution_price:.2f} on {timestamp.strftime('%Y-%m-%d %H:%M')}, Cost: ${total_cost:,.2f}"
        )

        # Create position
        self.current_position = Position(
            status=PositionStatus.LONG,
            entry_price=execution_price,
            entry_time=timestamp,
            quantity=quantity,
            current_price=execution_price,
            last_update_time=timestamp,
        )

        # Create a partial trade record to indicate successful position opening
        # Full trade record will be created when position is closed
        partial_trade = Trade(
            trade_id=self.next_trade_id,
            symbol=symbol,
            side="BUY_ENTRY",  # Indicate this is position opening
            entry_price=execution_price,
            entry_time=timestamp,
            exit_price=0.0,  # Not yet closed
            exit_time=timestamp,  # Placeholder
            quantity=quantity,
            gross_pnl=0.0,  # Not yet realized
            commission=commission_cost,
            slippage=(execution_price - price) * quantity,
            net_pnl=0.0,  # Not yet realized
            holding_period_hours=0.0,
            max_favorable_excursion=0.0,
            max_adverse_excursion=0.0,
            decision_metadata=decision_metadata,
        )

        return partial_trade

    def _execute_sell(
        self,
        price: float,
        timestamp: pd.Timestamp,
        symbol: str,
        decision_metadata: dict[str, Any],
    ) -> Optional[Trade]:
        """Execute a sell order.

        Args:
            price: Sell price
            timestamp: Execution timestamp
            symbol: Trading symbol
            decision_metadata: Decision metadata

        Returns:
            Trade object for the completed round trip
        """
        if not self.current_position:
            return None

        # Apply slippage (sell at lower price)
        execution_price = price * (1 - self.slippage)

        # Calculate proceeds
        trade_value = execution_price * self.current_position.quantity
        commission_cost = trade_value * self.commission
        net_proceeds = trade_value - commission_cost

        # Calculate P&L
        entry_value = self.current_position.entry_price * self.current_position.quantity
        gross_pnl = trade_value - entry_value

        # Entry commission was already deducted, so net P&L is:
        net_pnl = gross_pnl - commission_cost

        # Update capital
        logger.debug(
            f"SELL: Adding ${net_proceeds:,.2f} to capital. Before: ${self.current_capital:,.2f}"
        )
        self.current_capital += net_proceeds
        logger.debug(f"SELL: Capital after trade: ${self.current_capital:,.2f}")

        # Log trade completion details with timestamp
        logger.info(
            f"Position closed: SELL {self.current_position.quantity} shares at ${execution_price:.2f} on {timestamp.strftime('%Y-%m-%d %H:%M')}, P&L: ${net_pnl:,.2f}"
        )

        # Create trade record
        trade = Trade(
            trade_id=self.next_trade_id,
            symbol=symbol,
            side="LONG",  # This was a long trade (bought then sold)
            entry_price=self.current_position.entry_price,
            entry_time=self.current_position.entry_time,
            exit_price=execution_price,
            exit_time=timestamp,
            quantity=self.current_position.quantity,
            gross_pnl=gross_pnl,
            commission=commission_cost,  # Only exit commission (entry was already deducted)
            slippage=(price - execution_price) * self.current_position.quantity,
            net_pnl=net_pnl,
            holding_period_hours=self.current_position.holding_period,
            max_favorable_excursion=self.current_position.max_favorable_excursion,
            max_adverse_excursion=self.current_position.max_adverse_excursion,
            decision_metadata=decision_metadata,
        )

        # Add to trade history
        self.trade_history.append(trade)
        self.next_trade_id += 1

        # Close position
        self.current_position = None

        return trade

    def _calculate_quantity(self, price: float) -> int:
        """Calculate quantity to buy based on available capital.

        Args:
            price: Execution price

        Returns:
            Quantity to buy
        """
        # Use a fixed fraction approach (could be made configurable)
        fraction_to_invest = (
            0.25  # Use 25% of available capital for moderate position sizing
        )
        available = self.available_capital * fraction_to_invest

        # Account for commission in calculation
        max_trade_value = available / (1 + self.commission)
        quantity = int(max_trade_value / price)

        return quantity

    def _calculate_required_capital(self, price: float, quantity: Optional[int] = None) -> float:
        """Calculate required capital for a trade.

        Args:
            price: Execution price
            quantity: Quantity (if None, use default calculation)

        Returns:
            Required capital
        """
        if quantity is None:
            quantity = self._calculate_quantity(price)

        trade_value = price * quantity
        commission_cost = trade_value * self.commission
        return trade_value + commission_cost

    def update_position(self, current_price: float, timestamp: pd.Timestamp):
        """Update current position with market price.

        Args:
            current_price: Current market price
            timestamp: Current timestamp
        """
        if self.current_position:
            self.current_position.update(current_price, timestamp)

    def get_trade_history(self) -> list[Trade]:
        """Get complete trade history.

        Returns:
            List of completed trades
        """
        return self.trade_history.copy()

    def get_position_summary(self) -> dict[str, Any]:
        """Get current position summary.

        Returns:
            Dictionary with position information
        """
        if not self.current_position:
            return {
                "status": "FLAT",
                "capital": self.current_capital,
                "available_capital": self.available_capital,
            }

        return {
            "status": self.current_position.status.value,
            "entry_price": self.current_position.entry_price,
            "current_price": self.current_position.current_price,
            "quantity": self.current_position.quantity,
            "unrealized_pnl": self.current_position.unrealized_pnl,
            "holding_period_hours": self.current_position.holding_period,
            "capital": self.current_capital,
            "available_capital": self.available_capital,
        }

    def force_close_position(
        self,
        price: float,
        timestamp: pd.Timestamp,
        symbol: str,
        reason: str = "End of backtest",
    ) -> Optional[Trade]:
        """Force-close any open position at the end of the backtest.

        This ensures that all performance calculations are based on completed trades only,
        preventing unrealized losses from open positions from skewing the results.

        Args:
            price: Current market price to close at
            timestamp: Timestamp for the forced close
            symbol: Trading symbol
            reason: Reason for the forced close (for metadata)

        Returns:
            Trade object if a position was closed, None if no open position
        """
        if not self.current_position:
            return None

        # Force-close the position using the sell logic
        decision_metadata = {
            "signal_type": "FORCE_CLOSE",
            "reason": reason,
            "forced": True,
        }

        return self._execute_sell(price, timestamp, symbol, decision_metadata)

    def reset(self):
        """Reset position manager to initial state."""
        self.current_capital = self.initial_capital
        self.current_position = None
        self.trade_history.clear()
        self.next_trade_id = 1
