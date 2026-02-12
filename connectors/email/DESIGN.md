# Email Connector Design — Two-Stage Architecture

## Context

PLAN.md specifies an email connector using IMAP polling / journaling. The connector plugin framework (`umbrella_connector`) is fully implemented — `BaseConnector` handles Kafka, ingestion API, retry/dead-letter, health server, and shutdown. This is the first connector built on the framework.

**Regulatory constraint**: no data loss — raw data must be durably captured before any processing.
**Size constraint**: raw EML messages are 3–20 MB, too large for Kafka's default 1 MB limit.

## Two-Stage Architecture

**Stage 1 — `EmailConnector`** (BaseConnector subclass, runs as K8s deployment)
1. Poll IMAP for new messages
2. Upload raw EML bytes to S3 immediately (claim-check pattern)
3. Quick-extract envelope headers (From, To, Subject, Date, Message-ID) — no full MIME walk
4. Yield lightweight `RawMessage` (~1–2 KB) to framework → Kafka `raw-messages` topic

**Stage 2 — `EmailProcessor`** (Kafka consumer, runs as separate K8s deployment)
1. Consume `RawMessage` from `raw-messages` topic (filtered by `channel == EMAIL`)
2. Download raw EML from S3 via the reference in `raw_payload`
3. Full MIME parse: extract body text/HTML, decode attachments
4. Upload individual attachments to S3
5. Publish structured `ParsedEmail` message to `parsed-messages` Kafka topic

Both stages live in the same `connectors/email/` package and share config/parser/S3 code, but run as separate processes with separate entry points.

### Claim-Check Pattern (large message handling)

```
┌───────────┐    raw EML bytes     ┌────┐
│   IMAP    │ ──────────────────── │ S3 │  (3-20 MB, durable)
│   Server  │                      └──┬─┘
└─────┬─────┘                         │
      │                               │ s3://bucket/raw/email/{uid}.eml
      │ envelope headers              │
      ▼                               ▼
┌───────────────┐  RawMessage (~1KB)  ┌───────────┐
│ EmailConnector│ ─────────────────── │   Kafka   │
│  (Stage 1)    │  {s3_ref, from,     │raw-messages│
└───────────────┘   to, subject, ...} └─────┬─────┘
                                            │
                                            ▼
                                   ┌────────────────┐  download EML   ┌────┐
                                   │ EmailProcessor  │ ◄───────────── │ S3 │
                                   │  (Stage 2)      │                └────┘
                                   └───────┬────────┘
                                           │ full parse + upload attachments
                                           ▼
                                   ┌───────────────┐
                                   │     Kafka      │
                                   │parsed-messages │
                                   └───────────────┘
```

Kafka messages never exceed a few KB. Raw EML (3–20 MB) only lives in S3.

## RawMessage Shape (Stage 1 output)

```python
RawMessage(
    raw_message_id="<Message-ID-header>",
    channel=Channel.EMAIL,
    raw_payload={
        "envelope": {
            "subject": "...",
            "from": "alice@example.com",
            "to": ["bob@example.com"],
            "cc": [],
            "bcc": [],
            "date": "2025-06-01T12:00:00Z",
            "message_id": "<abc@example.com>",
        },
        "s3_uri": "s3://bucket/raw/email/1234.eml",   # claim-check ref
        "size_bytes": 5242880,
    },
    raw_format="eml_ref",          # signals this is a reference, not inline
    attachment_refs=[],             # populated by Stage 2, not Stage 1
    metadata={"imap_uid": "1234", "mailbox": "INBOX", "imap_host": "imap.example.com"},
)
```

## File Structure

```
connectors/email/
├── pyproject.toml
├── DESIGN.md                          # ← this file
├── umbrella_email/
│   ├── __init__.py
│   ├── config.py              # EmailConnectorConfig, EmailProcessorConfig, ImapConfig, S3Config
│   ├── imap_client.py         # AsyncImapClient (imaplib + to_thread)
│   ├── envelope.py            # Quick envelope-only header extraction (no MIME walk)
│   ├── parser.py              # Full MimeParser (Stage 2): body, HTML, attachments
│   ├── s3.py                  # S3Store: upload raw EML + upload parsed attachments + download
│   ├── connector.py           # Stage 1: EmailConnector(BaseConnector)
│   ├── processor.py           # Stage 2: EmailProcessor (Kafka consumer → parse → publish)
│   └── __main__.py            # Entry point with --mode connector|processor
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_imap_client.py
    ├── test_envelope.py
    ├── test_parser.py
    ├── test_s3.py
    ├── test_connector.py
    └── test_processor.py
```

## Module Design

### `config.py`

- **`ImapConfig`** (`env_prefix="IMAP_"`): `host`, `port` (993), `use_ssl` (True), `username`, `password` (SecretStr), `mailbox` ("INBOX"), `poll_interval_seconds` (30.0)
- **`S3Config`** (`env_prefix="S3_"`): `bucket`, `prefix` ("raw/email"), `region` ("us-east-1"), `endpoint_url` (None for MinIO)
- **`EmailConnectorConfig`** (extends `ConnectorConfig`): adds `imap: ImapConfig`, `s3: S3Config`
- **`EmailProcessorConfig`** (BaseSettings, `env_prefix="PROCESSOR_"`): `kafka_bootstrap_servers`, `source_topic` ("raw-messages"), `output_topic` ("parsed-messages"), `consumer_group` ("email-processor"), `s3: S3Config`, `attachments_prefix` ("raw/email/attachments")

### `imap_client.py` — Stage 1 only

`AsyncImapClient` wraps `imaplib.IMAP4_SSL` with `asyncio.to_thread()`.

- `connect()` / `disconnect()`
- `poll_new_messages() → list[FetchedEmail]` — UID SEARCH, returns uid + raw_bytes
- `search_by_date_range(since, before) → list[FetchedEmail]` — for backfill
- `is_connected() → bool` — NOOP check

`FetchedEmail`: dataclass with `uid: str`, `raw_bytes: bytes`

### `envelope.py` — Stage 1 only (fast, lightweight)

`extract_envelope(raw_bytes) → dict`

Quick header-only extraction using `email.parser.BytesHeaderParser` (does NOT parse the body or walk MIME parts). Returns `{subject, from, to, cc, bcc, date, message_id}`. This is O(header-size) not O(message-size).

### `parser.py` — Stage 2 only (full parse)

`MimeParser.parse(raw_bytes) → ParsedEmail`

Full MIME walk using `email.message_from_bytes(raw_bytes, policy=email.policy.default)`:
- Extract body_text (text/plain) and body_html (text/html)
- Extract attachments → `ParsedAttachment(filename, content_type, payload: bytes)`
- Decode encoded headers (RFC 2047)
- Handle nested multipart

### `s3.py` — shared by both stages

`S3Store` wraps boto3 with `asyncio.to_thread()`:
- `upload_raw_eml(uid, raw_bytes) → str` — returns `s3://bucket/prefix/{uid}.eml`
- `download_raw_eml(s3_uri) → bytes` — fetches EML for Stage 2
- `upload_attachment(email_uid, attachment) → str` — returns `s3://bucket/attachments_prefix/{uid}/{hash}_{filename}`
- `start()` / `stop()` — boto3 client lifecycle

### `connector.py` — Stage 1

```
EmailConnector(BaseConnector):
    ingest():
        connect IMAP + start S3
        loop:
            poll_new_messages()
            for each FetchedEmail:
                s3_uri = upload_raw_eml(uid, raw_bytes)
                envelope = extract_envelope(raw_bytes)
                yield RawMessage(channel=EMAIL, raw_format="eml_ref",
                    raw_payload={envelope, s3_uri, size_bytes},
                    metadata={imap_uid, mailbox, host})
            sleep(poll_interval)

    health_check(): imap_connected, last_poll, last_uid, messages_ingested

    backfill(request): search_by_date_range → same upload+yield pattern
```

### `processor.py` — Stage 2

```
EmailProcessor:
    __init__(config: EmailProcessorConfig)
        creates AIOKafkaConsumer, AIOKafkaProducer, S3Store, MimeParser

    run():
        start consumer (raw-messages, group=email-processor)
        start producer
        start S3
        start health server
        consume loop:
            for each message where channel == EMAIL:
                raw_bytes = s3.download(raw_payload["s3_uri"])
                parsed = parser.parse(raw_bytes)
                attachment_uris = upload each attachment to S3
                publish to parsed-messages topic:
                    {message_id, channel, subject, from, to, cc, bcc,
                     date, body_text, body_html, attachment_refs, headers}
```

### `__main__.py`

```python
# python -m umbrella_email connector   → runs Stage 1
# python -m umbrella_email processor   → runs Stage 2
```

## Dependencies

| Dependency | Purpose |
|---|---|
| `umbrella-connector-framework` | BaseConnector, config, models (local) |
| `boto3` | S3 upload/download (sync, `to_thread`) |
| `aiokafka` | Stage 2 Kafka consumer + producer (already in framework) |

No additional IMAP or MIME deps — all stdlib (`imaplib`, `email`).

## Implementation Order

1. `config.py` — all config classes
2. `envelope.py` — lightweight header extraction (Stage 1)
3. `parser.py` — full MIME parser (Stage 2)
4. `imap_client.py` — async IMAP wrapper
5. `s3.py` — S3 upload/download store
6. `connector.py` — Stage 1 EmailConnector
7. `processor.py` — Stage 2 EmailProcessor
8. `__main__.py` + `__init__.py` + `pyproject.toml`
9. Tests for all modules
10. Install and verify

## Key Files to Reference

- `connectors/connector-framework/umbrella_connector/base.py` — BaseConnector to extend
- `connectors/connector-framework/umbrella_connector/config.py` — ConnectorConfig to inherit
- `connectors/connector-framework/umbrella_connector/models.py` — RawMessage, BackfillRequest
- `connectors/connector-framework/tests/test_base.py` — test patterns

## Verification

1. `uv pip install -e connectors/email/ --python .venv/bin/python3`
2. `python -c "from umbrella_email import EmailConnector, EmailProcessor"`
3. `pytest connectors/email/tests/ -v` — all tests pass
