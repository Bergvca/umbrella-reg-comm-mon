-- alert_rw needs read access to entity schema for the alert-entity join.
-- The role is created by test-pipeline-minikube.sh; guard against it not existing yet.
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'alert_rw') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA entity TO alert_rw';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA entity TO alert_rw';
    END IF;
END;
$$;
