# Sample EML Files

Test email messages for validating the Umbrella email processing pipeline.

## Files

### test-email.eml

**Type**: Multipart/mixed (text + HTML + PDF attachment)

**Features**:
- Multiple recipients (To + Cc)
- Both plain text and HTML bodies
- PDF attachment (base64 encoded)
- Full email headers (DKIM, Return-Path, etc.)

**Use case**: Full-featured test covering all MIME parsing scenarios

### simple-text.eml

**Type**: Plain text

**Features**:
- Single recipient
- Plain text body only
- Minimal headers

**Use case**: Basic email parsing test

### multipart-alternative.eml

**Type**: Multipart/alternative (text + HTML)

**Features**:
- Multiple recipients (group address)
- Alternative text/HTML bodies
- No attachments

**Use case**: Newsletter-style message with rich formatting

## Using Sample EMLs

### With the Test Script

The test script (`test-pipeline-minikube.sh`) generates its own inline EML. To use these samples instead:

1. Upload to MinIO:
```bash
kubectl run mc --rm -i --image=minio/mc -n umbrella-storage -- \
  sh -c "mc alias set local http://minio:9000 minioadmin minioadmin && \
         mc mb --ignore-existing local/umbrella/raw/email && \
         cat | mc pipe local/umbrella/raw/email/sample.eml" < scripts/sample-eml/test-email.eml
```

2. Create corresponding RawMessage and inject to Kafka (adjust the JSON to match the file).

### Manual Testing

#### Upload to MinIO
```bash
# Port-forward MinIO
kubectl port-forward -n umbrella-storage svc/minio 9000:9000

# Use mc client locally
mc alias set local http://localhost:9000 minioadmin minioadmin
mc cp scripts/sample-eml/test-email.eml local/umbrella/raw/email/
```

#### Inject to Kafka

Create a RawMessage JSON referencing the EML:

```json
{
  "raw_message_id": "test-email-001",
  "channel": "email",
  "raw_payload": {
    "envelope": {
      "message_id": "<20260212143520.12345@example.com>",
      "subject": "Q1 2026 Compliance Report - Review Required",
      "from": "alice.smith@example.com",
      "to": ["bob.jones@acme.com"],
      "cc": ["carol.white@acme.com"],
      "bcc": [],
      "date": "Wed, 12 Feb 2026 14:35:20 +0000"
    },
    "s3_uri": "s3://umbrella/raw/email/test-email.eml",
    "size_bytes": 3500
  },
  "raw_format": "eml_ref",
  "metadata": {
    "imap_uid": "12345",
    "mailbox": "INBOX",
    "imap_host": "imap.example.com"
  },
  "ingested_at": "2026-02-12T14:35:25Z"
}
```

Produce to Kafka:
```bash
kubectl run kafka-producer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic raw-messages < raw-message.json
```

## Verifying Results

### Check parsed-messages topic
```bash
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic parsed-messages \
  --from-beginning \
  --max-messages 1
```

### Check normalized-messages topic
```bash
kubectl run kafka-consumer --rm -i --image=apache/kafka:4.1.1 -n umbrella-streaming -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic normalized-messages \
  --from-beginning \
  --max-messages 1
```

### Check Elasticsearch
```bash
kubectl port-forward -n umbrella-storage svc/elasticsearch 9200:9200

# Search by message ID
curl -s http://localhost:9200/messages-*/_search?q=message_id:20260212143520* | jq

# Get all messages
curl -s http://localhost:9200/messages-*/_search?pretty
```

## Creating Custom Test Messages

To create your own test EML:

1. Use an email client to compose and send a real email
2. Use "View Source" or "Show Original" to get the raw EML
3. Save to a `.eml` file
4. Or use Python:
   ```python
   from email.message import EmailMessage

   msg = EmailMessage()
   msg['From'] = 'sender@example.com'
   msg['To'] = 'recipient@acme.com'
   msg['Subject'] = 'Test Subject'
   msg.set_content('Test body')

   with open('custom.eml', 'w') as f:
       f.write(msg.as_string())
   ```

## EML Format Reference

RFC 5322 (Internet Message Format): https://www.rfc-editor.org/rfc/rfc5322
RFC 2045-2049 (MIME): https://www.rfc-editor.org/rfc/rfc2045
