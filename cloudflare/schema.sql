PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  candidate_name TEXT NOT NULL,
  candidate_email TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT,
  duration_minutes INTEGER NOT NULL DEFAULT 45,
  status TEXT NOT NULL DEFAULT 'scheduled',
  monitoring_json TEXT NOT NULL DEFAULT '{}',
  invitation_token TEXT NOT NULL UNIQUE,
  room_name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrity_events (
  id TEXT PRIMARY KEY,
  interview_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  confidence REAL,
  severity TEXT NOT NULL DEFAULT 'info',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY,
  interview_id TEXT NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
  reviewer_id TEXT NOT NULL REFERENCES users(id),
  decision TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_interviews_org ON interviews(organization_id);
CREATE INDEX IF NOT EXISTS idx_events_interview ON integrity_events(interview_id);
