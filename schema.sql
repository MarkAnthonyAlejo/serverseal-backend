CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bol_number VARCHAR(100) UNIQUE NOT NULL, 
    origin VARCHAR(255) NOT NULL, 
    destination VARCHAR(255) NOT NULL, 
    status VARCHAR(50) DEFAULT 'Pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP 
); 

CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shipment_id UUID REFERENCES shipments(shipment_id) ON DELETE CASCADE, 
    event_type VARCHAR(50) NOT NULL, -- e.g pickup, mid-transit or delivery 
    location VARCHAR(255), 
    hardware_details TEXT, -- For serial numbers / asset tags 
    notes TEXT, 
    handler_id VARCHAR(100), -- Who performed the action 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)
