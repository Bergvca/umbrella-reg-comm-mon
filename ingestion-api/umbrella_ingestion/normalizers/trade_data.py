"""Trade data normalizer — transforms parsed trade records into NormalizedMessage."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from umbrella_schema import (
    Channel,
    Direction,
    NormalizedMessage,
    Participant,
)

from .base import BaseNormalizer

logger = structlog.get_logger()


class TradeDataNormalizer(BaseNormalizer):
    """Normalize parsed trade records into the canonical schema."""

    def __init__(self, monitored_accounts: list[str] | None = None) -> None:
        self._monitored_accounts = set(monitored_accounts or [])

    @property
    def channel(self) -> Channel:
        return Channel.TRADE_DATA

    def normalize(self, parsed: dict) -> NormalizedMessage:
        direction = self._detect_direction(parsed)
        participants = self._build_participants(parsed)
        body_text = self._build_body_text(parsed)
        timestamp = self._parse_timestamp(parsed.get("timestamp", ""))

        metadata = {
            "ticker": parsed.get("ticker"),
            "side": parsed.get("side"),
            "quantity": parsed.get("quantity"),
            "price": parsed.get("price"),
            "notional": parsed.get("notional"),
            "currency": parsed.get("currency", "USD"),
            "order_type": parsed.get("order_type"),
            "venue": parsed.get("venue"),
            "execution_id": parsed.get("execution_id"),
            "asset_class": parsed.get("asset_class", "equity"),
            "account_id": parsed.get("account_id"),
            "settlement_date": parsed.get("settlement_date"),
            "order_id": parsed.get("order_id"),
        }
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return NormalizedMessage(
            message_id=parsed.get("message_id", parsed.get("execution_id", "")),
            channel=Channel.TRADE_DATA,
            direction=direction,
            timestamp=timestamp,
            participants=participants,
            body_text=body_text,
            metadata=metadata,
        )

    def _detect_direction(self, parsed: dict) -> Direction:
        side = (parsed.get("side") or "").lower()
        account_type = (parsed.get("account_type") or "").lower()

        if account_type == "internal":
            return Direction.INTERNAL
        if side == "buy":
            return Direction.INBOUND
        if side == "sell":
            return Direction.OUTBOUND
        return Direction.INTERNAL

    def _build_participants(self, parsed: dict) -> list[Participant]:
        participants: list[Participant] = []

        trader = parsed.get("trader")
        if isinstance(trader, dict) and trader:
            participants.append(Participant(
                id=trader.get("id", "unknown"),
                name=trader.get("name", "Unknown Trader"),
                role="trader",
            ))
        elif isinstance(trader, str) and trader:
            participants.append(Participant(
                id=trader,
                name=trader,
                role="trader",
            ))

        counterparty = parsed.get("counterparty") or {}
        if isinstance(counterparty, dict) and counterparty:
            participants.append(Participant(
                id=counterparty.get("id", "unknown"),
                name=counterparty.get("name", "Unknown Counterparty"),
                role="counterparty",
            ))
        elif isinstance(counterparty, str) and counterparty:
            participants.append(Participant(
                id=counterparty,
                name=counterparty,
                role="counterparty",
            ))

        # Ensure at least one participant
        if not participants:
            participants.append(Participant(
                id=parsed.get("account_id", "unknown"),
                name="Unknown",
                role="trader",
            ))

        return participants

    def _build_body_text(self, parsed: dict) -> str:
        side = (parsed.get("side") or "UNKNOWN").upper()
        quantity = parsed.get("quantity", 0)
        ticker = parsed.get("ticker", "UNKNOWN")
        price = parsed.get("price")
        venue = parsed.get("venue")
        asset_class = parsed.get("asset_class", "equity")

        if asset_class == "option":
            text = f"{side} {quantity:,} {ticker} contracts"
        else:
            text = f"{side} {quantity:,} {ticker}"

        if price is not None:
            text += f" @ ${price:,.2f}"
        if venue:
            text += f" via {venue}"

        return text

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime:
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError):
                logger.warning("trade_timestamp_parse_failed", timestamp=ts)
        return datetime.now(timezone.utc)
