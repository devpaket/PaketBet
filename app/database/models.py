USERS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0 NOT NULL,
    gmpoints INTEGER DEFAULT 0 NOT NULL,
    donatecoin INTEGER DEFAULT 0 NOT NULL,
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
TRANSFERS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    fee REAL DEFAULT 0.0,
    sent_at TEXT NOT NULL,
    FOREIGN KEY (from_user_id) REFERENCES users(user_id),
    FOREIGN KEY (to_user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_transfers_from_user_id ON transfers(from_user_id);
CREATE INDEX IF NOT EXISTS idx_transfers_to_user_id ON transfers(to_user_id);
"""


GAMES_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_type TEXT NOT NULL,
    bet INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'win', 'lose')),
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id);
"""

REFERRALS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER NOT NULL,
    invited INTEGER NOT NULL,
    rewarded BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, invited),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (invited) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_referrals_user_id ON referrals(user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_invited ON referrals(invited);
"""

BONUS_CLAIMS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS bonus_claims (
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('daily', 'hourly', 'promo')),
    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, type),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_bonus_claims_user_id ON bonus_claims(user_id);
CREATE INDEX IF NOT EXISTS idx_bonus_claims_type ON bonus_claims(type);
"""
