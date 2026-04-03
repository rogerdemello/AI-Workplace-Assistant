-- Seed data for development
-- Run after schema.sql to populate initial data

BEGIN;

-- Departments
INSERT INTO departments (id, name) VALUES 
    (gen_random_uuid(), 'Engineering'),
    (gen_random_uuid(), 'Human Resources'),
    (gen_random_uuid(), 'Sales'),
    (gen_random_uuid(), 'Marketing'),
    (gen_random_uuid(), 'Operations')
ON CONFLICT (name) DO NOTHING;

-- Get department IDs for user inserts
DO $$
DECLARE
    eng_dept UUID;
    hr_dept UUID;
    sales_dept UUID;
    mkt_dept UUID;
    ops_dept UUID;
BEGIN
    SELECT id INTO eng_dept FROM departments WHERE name = 'Engineering' LIMIT 1;
    SELECT id INTO hr_dept FROM departments WHERE name = 'Human Resources' LIMIT 1;
    SELECT id INTO sales_dept FROM departments WHERE name = 'Sales' LIMIT 1;
    SELECT id INTO mkt_dept FROM departments WHERE name = 'Marketing' LIMIT 1;
    SELECT id INTO ops_dept FROM departments WHERE name = 'Operations' LIMIT 1;

    -- Sample Users
    INSERT INTO users (id, employee_id, name, email, role, department_id, designation, status) VALUES 
        (gen_random_uuid(), 'EMP001', 'John Doe', 'john.doe@example.com', 'employee', eng_dept, 'Software Engineer', 'active'),
        (gen_random_uuid(), 'EMP002', 'Jane Smith', 'jane.smith@example.com', 'hr', hr_dept, 'HR Manager', 'active'),
        (gen_random_uuid(), 'EMP003', 'Admin User', 'admin@example.com', 'admin', ops_dept, 'System Admin', 'active'),
        (gen_random_uuid(), 'EMP004', 'Alice Johnson', 'alice.johnson@example.com', 'employee', eng_dept, 'Senior Developer', 'active'),
        (gen_random_uuid(), 'EMP005', 'Bob Williams', 'bob.williams@example.com', 'employee', sales_dept, 'Sales Executive', 'active'),
        (gen_random_uuid(), 'EMP006', 'Carol Brown', 'carol.brown@example.com', 'employee', mkt_dept, 'Marketing Specialist', 'active')
    ON CONFLICT (email) DO NOTHING;

    -- Sample Rooms
    INSERT INTO rooms (id, name, capacity, location, facilities, is_active) VALUES 
        (gen_random_uuid(), 'Conference Room A', 10, 'Floor 1', '["projector", "whiteboard"]', true),
        (gen_random_uuid(), 'Meeting Room B', 6, 'Floor 2', '["whiteboard"]', true),
        (gen_random_uuid(), 'Huddle Space', 4, 'Floor 1', '[]', true),
        (gen_random_uuid(), 'Training Room', 20, 'Floor 3', '["projector", "whiteboard", "video_conferencing"]', true)
    ON CONFLICT (name) DO NOTHING;

    -- Sample Integration Provider
    INSERT INTO integration_providers (id, provider_key, provider_type, display_name, config, is_active) VALUES 
        (gen_random_uuid(), 'openai', 'embedding', 'OpenAI Embeddings', '{"model": "text-embedding-ada-002"}', true),
        (gen_random_uuid(), 'google_calendar', 'calendar', 'Google Calendar', '{}', true)
    ON CONFLICT (provider_key) DO NOTHING;
END $$;

COMMIT;
