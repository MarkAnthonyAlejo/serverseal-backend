-- Migration: QA Inspector role + QA inspection workflow
-- Run: psql -U <user> -d serverseal_db -f migrations/add_qa_tables.sql

-- 1. Update users role constraint to include QA Inspector
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('Admin', 'Driver', 'Client', 'QA Inspector'));

-- 2. Add assigned_qa_id to shipments
ALTER TABLE shipments
    ADD COLUMN IF NOT EXISTS assigned_qa_id UUID REFERENCES users(user_id) ON DELETE SET NULL;

-- 3. QA Inspections — one per shipment
CREATE TABLE IF NOT EXISTS qa_inspections (
    inspection_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id         UUID NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    assigned_qa_id      UUID NOT NULL REFERENCES users(user_id),
    status              VARCHAR(20) NOT NULL DEFAULT 'Pending'
                            CHECK (status IN ('Pending', 'In Progress', 'Passed', 'Failed', 'On Hold')),
    overall_disposition VARCHAR(20)
                            CHECK (overall_disposition IN ('Pass', 'Fail', 'QA Hold', 'Conditional')),
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES users(user_id),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP WITH TIME ZONE
);

-- 4. QA Checklist Items — one row per hardware unit
CREATE TABLE IF NOT EXISTS qa_checklist_items (
    item_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id       UUID NOT NULL REFERENCES qa_inspections(inspection_id) ON DELETE CASCADE,
    manufacturer        TEXT,
    model               TEXT,
    serial_number       TEXT,
    quantity            INTEGER DEFAULT 1,
    visual_condition    VARCHAR(10) CHECK (visual_condition IN ('Pass', 'Fail')),
    packaging_condition VARCHAR(10) CHECK (packaging_condition IN ('Pass', 'Fail')),
    damage_notes        TEXT,
    disposition         VARCHAR(20)
                            CHECK (disposition IN ('Pass', 'Fail', 'Use-as-is', 'Return to Vendor', 'Scrap')),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
