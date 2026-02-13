#!/usr/bin/env bash
# Idempotent topic creation for the Umbrella platform.
# Called by docker-compose init container or K8s Job.
#
# Requires:
#   KAFKA_BOOTSTRAP — bootstrap server address (e.g. kafka:9092)

set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:?KAFKA_BOOTSTRAP env var is required}"

# Path to kafka-topics.sh inside the official apache/kafka image
KAFKA_TOPICS="/opt/kafka/bin/kafka-topics.sh"

# Wait for Kafka to be reachable
echo "Waiting for Kafka at ${BOOTSTRAP}..."
attempts=0
max_attempts=30
until "${KAFKA_TOPICS}" --bootstrap-server "${BOOTSTRAP}" --list >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "${attempts}" -ge "${max_attempts}" ]; then
        echo "ERROR: Kafka not reachable after ${max_attempts} attempts"
        exit 1
    fi
    sleep 2
done
echo "Kafka is ready."

# MVP: partitions=1, replication-factor=1 (single broker)
PARTITIONS=1
REPLICATION=1

TOPICS=(
    "raw-messages"
    "parsed-messages"
    "normalized-messages"
    "processing-results"
    "alerts"
    "dead-letter"
    "normalized-messages-dlq"
)

for topic in "${TOPICS[@]}"; do
    echo "Creating topic: ${topic}"
    "${KAFKA_TOPICS}" \
        --bootstrap-server "${BOOTSTRAP}" \
        --create \
        --if-not-exists \
        --topic "${topic}" \
        --partitions "${PARTITIONS}" \
        --replication-factor "${REPLICATION}"
done

echo "All topics created:"
"${KAFKA_TOPICS}" --bootstrap-server "${BOOTSTRAP}" --list
