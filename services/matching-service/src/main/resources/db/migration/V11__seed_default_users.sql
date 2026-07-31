-- ============================================================
-- V11: Seed Default ADMIN and HR Users
-- ============================================================

INSERT INTO users (id, username, email, password_hash, role, created_at)
VALUES 
    (
        'a1111111-1111-1111-1111-111111111111', 
        'System Admin', 
        'admin@smile.com', 
        '$2a$10$vD9CgZ9k2mS2dJ6G2F8z9.hG5J7k8L9m0N1O2P3Q4R5S6T7U8V9W0', 
        'ADMIN', 
        CURRENT_TIMESTAMP
    ),
    (
        'b2222222-2222-2222-2222-222222222222', 
        'HR Manager', 
        'hr@smile.com', 
        '$2a$10$vD9CgZ9k2mS2dJ6G2F8z9.hG5J7k8L9m0N1O2P3Q4R5S6T7U8V9W0', 
        'HR', 
        CURRENT_TIMESTAMP
    )
ON CONFLICT (email) DO NOTHING;
