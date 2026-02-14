-- V6: Seed default roles and decision statuses

-- Default roles
INSERT INTO iam.roles (name, description) VALUES
    ('admin',      'Full administrative access'),
    ('supervisor', 'Can create queues, assign batches, and view all reviews'),
    ('reviewer',   'Can review alerts in assigned batches')
ON CONFLICT (name) DO NOTHING;

-- Default decision statuses
INSERT INTO review.decision_statuses (name, description, is_terminal, display_order) VALUES
    ('acknowledged',   'Reviewed and acknowledged, no further action',    true,  10),
    ('false_positive', 'Alert determined to be a false positive',         true,  20),
    ('breach',         'Confirmed policy breach, escalate to compliance', true,  30),
    ('escalated',      'Escalated to senior reviewer',                    false, 40),
    ('pending_info',   'Awaiting additional information',                 false, 50)
ON CONFLICT (name) DO NOTHING;
