FROM apache/kafka:4.1.1

# Copy topic creation script for use by init containers / Jobs
COPY scripts/create-topics.sh /opt/kafka/scripts/create-topics.sh
USER root
RUN chmod +x /opt/kafka/scripts/create-topics.sh
USER appuser
