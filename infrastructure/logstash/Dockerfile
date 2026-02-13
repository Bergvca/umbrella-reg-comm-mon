FROM docker.elastic.co/logstash/logstash:9.3.0

COPY config/logstash.yml /usr/share/logstash/config/logstash.yml
COPY config/pipelines.yml /usr/share/logstash/config/pipelines.yml
COPY pipeline/ /usr/share/logstash/pipeline/

USER logstash
