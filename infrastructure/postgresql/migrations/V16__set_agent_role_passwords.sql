-- Set passwords for agent DB roles so services can authenticate.
ALTER ROLE agent_rw WITH PASSWORD 'changeme-agent';
ALTER ROLE agent_readonly WITH PASSWORD 'changeme-agent-ro';
