#!/bin/bash

set -e

ES_HOST="${ELASTICSEARCH_HOST:-http://elasticsearch:9200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Waiting for Elasticsearch to be healthy..."
until curl -s -f "${ES_HOST}/_cluster/health?wait_for_status=yellow" > /dev/null; do
  echo "Elasticsearch not ready, waiting..."
  sleep 5
done

echo "Elasticsearch is healthy. Loading templates..."

# Load ILM policy
echo "Loading ILM policy..."
curl -X PUT "${ES_HOST}/_ilm/policy/umbrella-retention" \
  -H "Content-Type: application/json" \
  -d @"${SCRIPT_DIR}/index-templates/ilm-policy.json"
echo ""

# Load messages index template
echo "Loading messages index template..."
curl -X PUT "${ES_HOST}/_index_template/messages-template" \
  -H "Content-Type: application/json" \
  -d @"${SCRIPT_DIR}/index-templates/messages-template.json"
echo ""

# Load alerts index template
echo "Loading alerts index template..."
curl -X PUT "${ES_HOST}/_index_template/alerts-template" \
  -H "Content-Type: application/json" \
  -d @"${SCRIPT_DIR}/index-templates/alerts-template.json"
echo ""

echo "Templates and ILM policy loaded successfully!"
