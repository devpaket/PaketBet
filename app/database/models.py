USERS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0 NOT NULL,
    gmpoints INTEGER DEFAULT 0 NOT NULL,
    games_played INTEGER DEFAULT 0 NOT NULL,
    duels_won INTEGER DEFAULT 0 NOT NULL,
    duel_wins INTEGER DEFAULT 0 NOT NULL,
    coins_lost INTEGER DEFAULT 0 NOT NULL,
    ref_by INTEGER,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_banned BOOLEAN DEFAULT FALSE NOT NULL,
    last_bonus_at TIMESTAMP,
    FOREIGN KEY (ref_by) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_users_ref_by ON users(ref_by);
"""
