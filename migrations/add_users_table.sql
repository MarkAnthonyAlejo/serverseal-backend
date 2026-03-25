-- Run this once against your serverseal_db
-- psql -U <your_user> -d serverseal_db -f migrations/add_users_table.sql

CREATE TABLE IF NOT EXISTS users (
    user_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email        TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('Admin', 'Driver', 'Client')),
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
