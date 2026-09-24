CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    card_number TEXT NOT NULL,
    balance NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

INSERT INTO users (username, password, email, role) VALUES
    ('admin', 'password123', 'admin@cyberops.local', 'admin'),
    ('petro', 'qwerty', 'petro@cyberops.local', 'user'),
    ('oksana', '123456', 'oksana@cyberops.local', 'user');

INSERT INTO customers (name, email, card_number, balance) VALUES
    ('Petro K', 'petro@cyberops.local', '4111 1111 1111 1111', 1250.50),
    ('Oksana S', 'oksana@cyberops.local', '5500 0000 0000 0004', 8900.00),
    ('Admin A', 'admin@cyberops.local', '3400 0000 0000 009', 42.00);

INSERT INTO orders (user_id, product, amount, status) VALUES
    (1, 'VPS root server', 99.00, 'active'),
    (2, 'SSL wildcard', 15.00, 'finished'),
    (3, 'Cloud storage 1TB', 24.99, 'active');