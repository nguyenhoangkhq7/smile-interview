-- ============================================================
-- V11: Seed Default ADMIN and HR Users
-- ============================================================

INSERT INTO users (id, username, email, password_hash, role, created_at)
VALUES 
    (
        'a1111111-1111-1111-1111-111111111111', 
        'System Admin', 
        'admin@smile.com', 
        '$2a$10$8.UnVuG9HHgffUDAlk8qfOUVGkqRzgVymGe07xd00DMxs.AQubh4a', 
        'ADMIN', 
        CURRENT_TIMESTAMP
    ),
    (
        'b2222222-2222-2222-2222-222222222222', 
        'HR Manager', 
        'hr@smile.com', 
        '$2a$10$8.UnVuG9HHgffUDAlk8qfOUVGkqRzgVymGe07xd00DMxs.AQubh4a', 
        'HR', 
        CURRENT_TIMESTAMP
    )
ON CONFLICT (email) DO NOTHING;
