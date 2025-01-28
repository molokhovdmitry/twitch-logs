-- Create messages table
CREATE TABLE messages (
    message_id SERIAL PRIMARY KEY,  -- Auto-increment unique message ID
    timestamp TIMESTAMP(2) NOT NULL,  -- Timestamp with milliseconds precision
    channel VARCHAR(100) NOT NULL,  -- Channel where the message was posted
    username VARCHAR(100) NOT NULL,  -- Reference to the user who posted the message
    text TEXT NOT NULL  -- Message content
);
