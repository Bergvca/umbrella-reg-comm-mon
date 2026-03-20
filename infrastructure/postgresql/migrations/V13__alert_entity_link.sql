CREATE TABLE alert.alert_entities (
    alert_id  UUID NOT NULL REFERENCES alert.alerts(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entity.entities(id) ON DELETE CASCADE,
    PRIMARY KEY (alert_id, entity_id)
);
CREATE INDEX idx_alert_entities_entity ON alert.alert_entities(entity_id);
