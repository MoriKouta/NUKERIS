PRAGMA foreign_keys = ON;
CREATE TABLE players (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  nickname TEXT NOT NULL,
  country TEXT NOT NULL,
  region TEXT NOT NULL
);
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  player_id TEXT NOT NULL REFERENCES players(id),
  mode TEXT NOT NULL,
  ruleset TEXT NOT NULL,
  issued_ms INTEGER NOT NULL,
  expires_ms INTEGER NOT NULL
);
CREATE INDEX runs_player ON runs(player_id);
CREATE TABLE submissions (
  run_id TEXT PRIMARY KEY REFERENCES runs(id),
  player_id TEXT NOT NULL REFERENCES players(id),
  mode TEXT NOT NULL,
  ruleset TEXT NOT NULL,
  score INTEGER NOT NULL CHECK(score >= 0),
  time_ms INTEGER NOT NULL CHECK(time_ms > 0),
  lines INTEGER NOT NULL CHECK(lines >= 0),
  pieces INTEGER NOT NULL CHECK(pieces >= 0),
  version TEXT NOT NULL
);
CREATE TABLE personal_bests (
  player_id TEXT NOT NULL REFERENCES players(id),
  mode TEXT NOT NULL,
  ruleset TEXT NOT NULL,
  score INTEGER NOT NULL CHECK(score >= 0),
  time_ms INTEGER NOT NULL CHECK(time_ms > 0),
  lines INTEGER NOT NULL,
  pieces INTEGER NOT NULL,
  version TEXT NOT NULL,
  PRIMARY KEY(player_id, mode, ruleset)
);
CREATE INDEX pb_score ON personal_bests(mode, ruleset, score DESC);
CREATE INDEX pb_time ON personal_bests(mode, ruleset, time_ms);
CREATE INDEX players_area ON players(country, region);
