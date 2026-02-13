FROM docker.elastic.co/elasticsearch/elasticsearch:9.3.0

COPY config/elasticsearch.yml /usr/share/elasticsearch/config/elasticsearch.yml
COPY config/index-templates/ /usr/share/elasticsearch/index-templates/
COPY config/init-templates.sh /usr/share/elasticsearch/init-templates.sh

RUN chmod +x /usr/share/elasticsearch/init-templates.sh

USER elasticsearch
