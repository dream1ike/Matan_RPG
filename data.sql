-- 1) Удаляем существующие таблицы, если они есть
DROP TABLE IF EXISTS logs, inventory, creatures, locations, loot_entries, loot_groups, users, items CASCADE;

-- 2) Создаем таблицу локаций, если она не существует
CREATE TABLE IF NOT EXISTS locations (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE,
  description TEXT
);

-- 3) Заполняем таблицу локаций (если она пустая)
INSERT INTO locations (name, description) 
SELECT * 
FROM (VALUES 
  ('Локация 1', 'Описание локации 1'),
  ('Локация 2', 'Описание локации 2'),
  ('Локация 3', 'Описание локации 3'),
  ('Локация 4', 'Описание локации 4'),
  ('Локация 5', 'Описание локации 5')
) AS new_locations(name, description)
ON CONFLICT (name) DO NOTHING;

-- 4) Создаем таблицу для пользователей
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  tg_id BIGINT NOT NULL UNIQUE,
  username VARCHAR(100)
);

-- 5) Создаем таблицу монстров (creatures)
CREATE TABLE IF NOT EXISTS creatures (
  id SERIAL PRIMARY KEY,
  location_id INT REFERENCES locations(id),
  name VARCHAR(100),
  hp INT,
  damage INT
);
-- Добавляем уникальное ограничение для столбца name в таблице creatures
ALTER TABLE creatures ADD CONSTRAINT unique_creature_name UNIQUE (name);

CREATE TABLE IF NOT EXISTS characters (
    user_id INT PRIMARY KEY REFERENCES users(id),
    hp INT DEFAULT 100,
    mana INT DEFAULT 50,
    exp INT DEFAULT 0,
    max_hp INT DEFAULT 100,
    max_mana INT DEFAULT 50
);


-- 5) Заполняем таблицу монстров (если она пустая)
INSERT INTO creatures (location_id, name, hp, damage)
SELECT * FROM (VALUES
  (1, 'Обычный монстр', 50, 10),
  (1, 'Скелет', 70, 20),
  (1, 'Гоблин', 100, 25),
  (2, 'Демон', 150, 40),
  (2, 'Скелет', 70, 20),
  (3, 'Гоблин', 100, 25),
  (3, 'Дракон', 300, 60),
  (4, 'Обычный монстр', 50, 10),
  (4, 'Скелет', 70, 20),
  (5, 'Гоблин', 100, 25),
  (5, 'Демон', 150, 40),
  (5, 'Дракон', 300, 60)
) AS new_creatures(location_id, name, hp, damage)
ON CONFLICT (name) DO NOTHING;

-- 7) Создаем таблицу для лута
CREATE TABLE IF NOT EXISTS loot_groups (
  id SERIAL PRIMARY KEY
);

-- 8) Создаем таблицу для предметов (items)
CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE,  -- Добавлен уникальный индекс
  effect JSONB
);

-- 9) Заполняем таблицу предметов
INSERT INTO items (name, effect) 
VALUES
  ('Малое зелье здоровья', '{"hp": 20}'),
  ('Большое зелье здоровья', '{"hp": 50}'),
  ('Манна-кристалл', '{"mana": 30}'),
  ('Свиток опыты', '{"exp": 10}')
ON CONFLICT (name) DO NOTHING;

-- 10) Создаем таблицу для инвентаря
CREATE TABLE IF NOT EXISTS inventory (
  user_id INT REFERENCES users(id),
  item_id INT REFERENCES items(id),
  count INT DEFAULT 1,
  PRIMARY KEY (user_id, item_id)
);

-- 11) Логирование действий
CREATE TABLE IF NOT EXISTS logs (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id),
  action TEXT,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
