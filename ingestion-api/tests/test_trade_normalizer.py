"""Tests for the TradeDataNormalizer."""

from umbrella_schema import Channel, Direction

from umbrella_ingestion.normalizers.trade_data import TradeDataNormalizer


class TestTradeDataNormalizer:
    def setup_method(self):
        self.normalizer = TradeDataNormalizer()

    def test_channel(self):
        assert self.normalizer.channel == Channel.TRADE_DATA

    def test_normalize_buy_trade(self):
        parsed = {
            "message_id": "EX-2026-00142",
            "channel": "trade_data",
            "timestamp": "2026-03-10T14:30:00Z",
            "side": "buy",
            "ticker": "MRDN",
            "quantity": 5000,
            "price": 45.20,
            "notional": 226000.00,
            "currency": "USD",
            "order_type": "limit",
            "venue": "NYSE",
            "execution_id": "EX-2026-00142",
            "asset_class": "equity",
            "account_id": "ACME-PROP-001",
            "trader": {"id": "marcus.webb", "name": "Marcus Webb"},
            "counterparty": {"id": "broker-001", "name": "Goldman Sachs"},
        }

        result = self.normalizer.normalize(parsed)

        assert result.channel == Channel.TRADE_DATA
        assert result.direction == Direction.INBOUND  # buy = inbound
        assert result.message_id == "EX-2026-00142"
        assert result.body_text == "BUY 5,000 MRDN @ $45.20 via NYSE"
        assert result.metadata["ticker"] == "MRDN"
        assert result.metadata["quantity"] == 5000
        assert result.metadata["price"] == 45.20
        assert len(result.participants) == 2
        assert result.participants[0].role == "trader"
        assert result.participants[0].name == "Marcus Webb"
        assert result.participants[1].role == "counterparty"

    def test_normalize_sell_trade(self):
        parsed = {
            "message_id": "EX-2026-00200",
            "timestamp": "2026-03-14T10:00:00Z",
            "side": "sell",
            "ticker": "MRDN",
            "quantity": 26500,
            "price": 62.30,
            "venue": "NYSE",
            "trader": {"id": "marcus.webb", "name": "Marcus Webb"},
        }

        result = self.normalizer.normalize(parsed)

        assert result.direction == Direction.OUTBOUND  # sell = outbound
        assert result.body_text == "SELL 26,500 MRDN @ $62.30 via NYSE"

    def test_normalize_option_trade(self):
        parsed = {
            "message_id": "EX-2026-00150",
            "timestamp": "2026-03-12T11:00:00Z",
            "side": "buy",
            "ticker": "MRDN Apr $50 Call",
            "quantity": 200,
            "price": 2.15,
            "asset_class": "option",
            "trader": "marcus.webb",
        }

        result = self.normalizer.normalize(parsed)

        assert "200 MRDN Apr $50 Call contracts" in result.body_text
        assert result.participants[0].id == "marcus.webb"
        assert result.participants[0].role == "trader"

    def test_normalize_missing_trader_uses_account(self):
        parsed = {
            "message_id": "EX-2026-00300",
            "timestamp": "2026-03-12T09:00:00Z",
            "side": "buy",
            "ticker": "AAPL",
            "quantity": 100,
            "price": 150.00,
            "account_id": "ACC-001",
        }

        result = self.normalizer.normalize(parsed)

        assert len(result.participants) == 1
        assert result.participants[0].id == "ACC-001"

    def test_none_values_stripped_from_metadata(self):
        parsed = {
            "message_id": "EX-001",
            "timestamp": "2026-03-10T10:00:00Z",
            "side": "buy",
            "ticker": "TSLA",
            "quantity": 100,
            "price": 200.0,
            "trader": {"id": "t1", "name": "Trader"},
        }

        result = self.normalizer.normalize(parsed)

        assert "settlement_date" not in result.metadata
        assert "order_id" not in result.metadata
        assert result.metadata["ticker"] == "TSLA"

    def test_internal_direction(self):
        parsed = {
            "message_id": "EX-002",
            "timestamp": "2026-03-10T10:00:00Z",
            "side": "buy",
            "ticker": "TSLA",
            "quantity": 50,
            "price": 200.0,
            "account_type": "internal",
            "trader": {"id": "t1", "name": "Trader"},
        }

        result = self.normalizer.normalize(parsed)

        assert result.direction == Direction.INTERNAL
