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

-- Note: We will add the 'events' and 'media' table later 

