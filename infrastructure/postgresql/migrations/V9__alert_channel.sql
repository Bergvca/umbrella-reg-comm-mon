-- V9: Add channel column to alerts for dashboard aggregation

ALTER TABLE alert.alerts ADD COLUMN channel TEXT;

-- Backfill: all existing alerts come from email messages
UPDATE alert.alerts SET channel = 'email' WHERE channel IS NULL;

ALTER TABLE alert.alerts ALTER COLUMN channel SET NOT NULL;

CREATE INDEX ON alert.alerts (channel);
