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
);

CREATE TABLE IF NOT EXISTS media (
    media_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(event_id) ON DELETE CASCADE, -- The Pointer to the Event
    media_type VARCHAR(20) NOT NULL, -- 'image' or 'video'
    file_path TEXT NOT NULL, -- Where the file is stored (e.g., S3 or local)
    captured_at TIMESTAMP WITH TIME ZONE, -- From the photo's EXIF data 
    latitude DECIMAL(9,6), 
    longitude DECIMAL(9,6), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
