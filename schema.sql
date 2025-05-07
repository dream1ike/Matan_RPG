-- users и персонажи
CREATE TABLE users (
  id   SERIAL PRIMARY KEY,
  tg_id BIGINT UNIQUE NOT NULL,
  username TEXT
);

CREATE TABLE characters (
  user_id   INT PRIMARY KEY REFERENCES users(id),
  hp         INT NOT NULL DEFAULT 100,
  mana       INT NOT NULL DEFAULT 50,
  exp        INT NOT NULL DEFAULT 0
);

-- локации и монстры
CREATE TABLE locations (
  id          SERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT
);

CREATE TABLE creatures (
  id             SERIAL PRIMARY KEY,
  location_id    INT NOT NULL REFERENCES locations(id),
  name           TEXT NOT NULL,
  hp             INT NOT NULL,
  loot_table_id  INT
);

-- предметы и таблицы добычи
CREATE TABLE items (
  id     SERIAL PRIMARY KEY,
  name   TEXT NOT NULL,
  effect JSONB  -- {"hp":10,"exp":5}
);

CREATE TABLE loot_tables (
  id      SERIAL PRIMARY KEY,
  item_id INT NOT NULL REFERENCES items(id),
  chance  FLOAT NOT NULL CHECK (chance > 0 AND chance <= 1)
);

-- лидерборд и логи
CREATE TABLE logs (
  id        SERIAL PRIMARY KEY,
  user_id   INT NOT NULL REFERENCES users(id),
  action    TEXT NOT NULL,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now()
);
