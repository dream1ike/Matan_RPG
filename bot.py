from dotenv import load_dotenv
load_dotenv()

import os
import random
import time
import asyncio
import asyncpg
from random import randint, choice
from aiogram import Bot, Dispatcher, types
from aiogram.client.bot import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

# В памяти: текущие битвы и квизы {chat_id: {...}}
active_battles: dict[int, dict] = {}
active_quiz: dict[int, dict] = {}

# Переменные окружения
DB_DSN = os.getenv("DATABASE_URL")
API_TOKEN = os.getenv("TG_TOKEN")

async def setup_locations(db):
    # Проверяем, если таблица пустая, то добавляем локации по умолчанию
    locations = await db.fetch("SELECT * FROM locations")
    if not locations:
        # Добавляем локации по умолчанию
        await db.execute(
            """
            INSERT INTO locations (name, description) VALUES
            ('Локация 1', 'Описание локации 1'),
            ('Локация 2', 'Описание локации 2'),
            ('Локация 3', 'Описание локации 3')
            """
        )

async def log_action(db, user_id, action):
    # Получаем текущее время (timestamp)
    ts = int(time.time())

    # Проверяем, существует ли пользователь в таблице users
    user_exists = await db.fetchrow(
        "SELECT id FROM users WHERE tg_id = $1", user_id
    )

    # Если пользователя нет, добавляем его в таблицу users
    if not user_exists:
        await db.execute(
            "INSERT INTO users(tg_id, username) VALUES($1, $2)",
            user_id, "unknown"  # Устанавливаем "unknown" как username, если его нет
        )
        user_exists = await db.fetchrow(
            "SELECT id FROM users WHERE tg_id = $1", user_id
        )

    # Теперь можно добавить запись в таблицу logs
    await db.execute(
        "INSERT INTO logs (user_id, action, ts) VALUES ($1, $2, to_timestamp($3))",
        user_exists['id'], action, ts
    )


async def main():
    db = await asyncpg.create_pool(dsn=DB_DSN)
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Настроим локации по умолчанию
    await setup_locations(db)

    # Главная клавиатура
    main_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/status"), KeyboardButton(text="/locations")],
            [KeyboardButton(text="/inventory"), KeyboardButton(text="/stats")],
        ],
        resize_keyboard=True
    )

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        # Регистрация пользователя и персонажа
        await db.execute(
            """
            INSERT INTO users (tg_id, username)
            VALUES ($1, $2)
            ON CONFLICT (tg_id) DO NOTHING
            """,
            message.from_user.id,
            message.from_user.username,
        )
        row = await db.fetchrow(
            "SELECT id FROM users WHERE tg_id = $1",
            message.from_user.id,
        )
        await db.execute(
            """
            INSERT INTO characters (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            row["id"],
        )
        await message.answer(
            "Добро пожаловать в SQL-Adventure! 👋\n"
            "Твой персонаж создан. /status — чтобы посмотреть параметры."
        )

    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        # Проверяем состояние персонажа перед выводом статуса
        rec = await db.fetchrow(
            "SELECT hp, max_hp, mana, max_mana, exp "
            "FROM characters c JOIN users u ON c.user_id=u.id "
            "WHERE u.tg_id=$1", message.from_user.id
        )
        
        # Если HP <= 0, восстанавливаем параметры персонажа
        if rec['hp'] <= 0:
            # Восстановление HP, Mana и Exp
            await db.execute(
                """
                UPDATE characters 
                SET hp = 100, mana = 50, exp = 0 
                WHERE user_id = (SELECT id FROM users WHERE tg_id = $1)
                """, message.from_user.id
            )
            rec = await db.fetchrow(
                "SELECT hp, max_hp, mana, max_mana, exp "
                "FROM characters c JOIN users u ON c.user_id=u.id "
                "WHERE u.tg_id=$1", message.from_user.id
            )
            await message.answer(
                "💀 Вы погибли! Ваши параметры были восстановлены.\n"
                "Выберите действие:", reply_markup=main_kb
            )
        
        await message.answer(
            f"❤️ HP: {rec['hp']}/{rec['max_hp']}\n"
            f"🔮 Mana: {rec['mana']}/{rec['max_mana']}\n"
            f"⭐ Exp: {rec['exp']}",
            reply_markup=main_kb
        )

    @dp.message(Command("locations"))
    async def cmd_locations(message: types.Message):
        rows = await db.fetch("SELECT id,name FROM locations ORDER BY id")
        buttons = [InlineKeyboardButton(text=f"{r['id']}. {r['name']}", callback_data=f"explore_{r['id']}") for r in rows]
        inline_rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
        await message.answer("📍 Выберите локацию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_rows))

    @dp.callback_query(lambda c: c.data and c.data.startswith("explore_"))
    async def explore_callback(cb: types.CallbackQuery):
        loc_id = int(cb.data.split("_")[1])
        cr = await db.fetchrow(
            "SELECT id,name,hp FROM creatures WHERE location_id=$1 ORDER BY RANDOM() LIMIT 1", loc_id
        )
        if not cr:
            await cb.message.edit_text("Локация пуста или не найдена.")
            return await cb.answer()
        active_battles[cb.message.chat.id] = {"id": cr['id'], "name": cr['name'], "hp": cr['hp']}
        # Кнопки степеней атаки
        btn1 = InlineKeyboardButton(text="🥉 Линейное (10)", callback_data="quiz_1")
        btn2 = InlineKeyboardButton(text="🥈 Квадратное (20)", callback_data="quiz_2")
        btn3 = InlineKeyboardButton(text="🥇 Кубическое (30)", callback_data="quiz_3")
        markup = InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2, btn3]])
        await cb.message.edit_text(
            f"👾 <b>{cr['name']}</b> (HP: {cr['hp']}) появился! Выберите степень атаки:",
            reply_markup=markup
        )
        await cb.answer()

    @dp.callback_query(lambda c: c.data and c.data.startswith("quiz_"))
    async def quiz_callback(cb: types.CallbackQuery):
        degree = int(cb.data.split("_")[1])
        dmg = degree * 10
        # Сохраняем в active_quiz
        quiz_data = {"degree": degree, "dmg": dmg}
        if degree == 1:
            a = randint(1, 10)
            x = randint(-10, 10)
            b = -a * x
            question = f"{a}x + {b} = 0"
            correct = f"x={x}"
            opts = [correct]
            for _ in range(3):
                xw = x + choice([-5, -3, -2, 2, 3, 5])
                opts.append(f"x={xw}")
            random.shuffle(opts)
            quiz_data.update({"type": "linear", "question": question, "options": opts, "correct_answer": correct})
        elif degree == 2:
            x1, x2 = randint(-5, 5), randint(-5, 5)
            a = randint(1, 5)
            b = -a * (x1 + x2)
            c_ = a * x1 * x2
            question = f"{a}x² + {b}x + {c_} = 0"
            correct = f"x₁={x1},x₂={x2}"
            opts = [correct]
            for _ in range(3):
                opts.append(f"x₁={x1 + choice([-2, 2])},x₂={x2 + choice([-2, 2])}")
            random.shuffle(opts)
            quiz_data.update({"type": "quadratic", "question": question, "options": opts, "correct_answer": correct})
        else:
            # кубическое с тремя корнями
            roots = [randint(-3, 3) for _ in range(3)]
            a = randint(1, 3)
            r1, r2, r3 = roots
            b = -a * (r1 + r2 + r3)
            c_ = a * (r1 * r2 + r1 * r3 + r2 * r3)
            d = -a * r1 * r2 * r3
            question = f"{a}x³ + {b}x² + {c_}x + {d} = 0"
            correct = f"x₁={r1},x₂={r2},x₃={r3}"
            opts = [correct]
            for _ in range(3):
                w = [r + choice([-1, 1, 2, -2]) for r in roots]
                opts.append(f"x₁={w[0]},x₂={w[1]},x₃={w[2]}")
            random.shuffle(opts)
            quiz_data.update({"type": "cubic", "question": question, "options": opts, "correct_answer": correct})

        active_quiz[cb.message.chat.id] = quiz_data
        # Кнопки ответов
        keyboard = []
        opts = quiz_data["options"]
        for i in range(0, 4, 2):
            row = []
            for j in range(2):
                row.append(InlineKeyboardButton(text=opts[i + j], callback_data=f"ans_{i + j}"))
            keyboard.append(row)
        await cb.message.edit_text(quiz_data["question"], reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await cb.answer()

    @dp.message(Command("inventory"))
    async def cmd_inventory(message: types.Message):
        # Получаем все предметы пользователя из инвентаря
        user_id = message.from_user.id
        inventory_items = await db.fetch(
            """
            SELECT i.name, iv.count
            FROM inventory iv
            JOIN items i ON iv.item_id = i.id
            WHERE iv.user_id = (SELECT id FROM users WHERE tg_id = $1)
            """, user_id
        )

        if not inventory_items:
            await message.answer("У вас нет предметов в инвентаре.")
            return

        # Строим сообщение с инвентарем
        inventory_message = "Ваш инвентарь:\n"
        for item in inventory_items:
            inventory_message += f"{item['name']} (x{item['count']})\n"

        # Отправляем инвентарь пользователю
        await message.answer(inventory_message)


    async def get_loot(db, user_id, username):
        # Проверяем, существует ли пользователь в таблице users
        user_exists = await db.fetchrow(
            "SELECT id FROM users WHERE tg_id = $1", user_id
        )

        if not user_exists:
            # Если пользователя нет в таблице users, добавляем его
            await db.execute(
                "INSERT INTO users(tg_id, username) VALUES($1, $2)",
                user_id, username
            )
            # Получаем id нового пользователя
            user_exists = await db.fetchrow(
                "SELECT id FROM users WHERE tg_id = $1", user_id
            )

        # Извлекаем все предметы из базы данных
        items = await db.fetch("SELECT * FROM items")

        # Случайный выбор предмета
        selected_item = random.choice(items)
        item_name = selected_item['name']
        item_id = selected_item['id']

        # Проверяем, есть ли уже этот предмет в инвентаре
        inventory = await db.fetchrow(
            "SELECT count FROM inventory WHERE user_id = $1 AND item_id = $2", user_exists['id'], item_id
        )
        
        if inventory:
            # Если предмет уже есть в инвентаре, увеличиваем его количество
            new_count = inventory['count'] + 1
            await db.execute(
                "UPDATE inventory SET count = $1 WHERE user_id = $2 AND item_id = $3",
                new_count, user_exists['id'], item_id
            )
            effect_message = f"Вы получили {item_name} (x{new_count})!"
        else:
            # Если предмета нет в инвентаре, добавляем его с количеством 1
            await db.execute(
                "INSERT INTO inventory (user_id, item_id, count) VALUES ($1, $2, $3)",
                user_exists['id'], item_id, 1
            )
            effect_message = f"Вы получили {item_name}!"

        return f"🎉 Вы нашли {item_name}! {effect_message}"

    @dp.callback_query(lambda c: c.data.startswith("ans_"))
    async def answer_callback(cb: types.CallbackQuery):
        user_id = cb.from_user.id
        idx = int(cb.data.split("_")[1])
        quiz = active_quiz.pop(cb.message.chat.id, None)
        if not quiz:
            return await cb.answer()

        battle = active_battles.get(cb.message.chat.id)
        sel = quiz["options"][idx]
        correct_answer = quiz["correct_answer"]
        

        if sel.strip() == correct_answer.strip():
            battle['hp'] -= quiz['dmg']
            if battle['hp'] <= 0:
                battle['hp'] = 0
                result = f"✅ Верно! Урон {quiz['dmg']}. Осталось HP врага: {battle['hp']}"
                await cb.message.edit_text(result)
                congrats = f"🏆 Вы победили <b>{battle['name']}</b>!"
                await cb.message.reply(congrats, reply_markup=main_kb)
                await log_action(db, user_id, congrats)
                # Логика выпадения лута и добавление в инвентарь
                loot_message = await get_loot(db, cb.from_user.id, cb.from_user.username)  # Получаем лут из базы данных
                await cb.message.reply(loot_message)
                await log_action(db, user_id, loot_message)

                # Очистка текущей битвы и возврат к выбору локации
                active_battles.pop(cb.message.chat.id, None)
                await asyncio.sleep(2)  # Задержка перед переходом
                await cmd_locations(cb.message)  # Переход к меню локации

            else:
                result = f"✅ Верно! Урон {quiz['dmg']}. Осталось HP врага: {battle['hp']}"
                await cb.message.edit_text(result)
                # Новая атака
                btns = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🥉 Линейное (10)", callback_data="quiz_1"),
                    InlineKeyboardButton(text="🥈 Квадратное (20)", callback_data="quiz_2"),
                    InlineKeyboardButton(text="🥇 Кубическое (30)", callback_data="quiz_3")
                ]])
                await cb.message.reply("Выберите степень атаки:", reply_markup=btns)
        else:
            await handle_incorrect_answer(cb, quiz)

    async def handle_incorrect_answer(cb: types.CallbackQuery, quiz):
        # Логика для неправильного ответа
        await db.execute(
            "UPDATE characters SET hp=hp-$1 WHERE user_id=(SELECT id FROM users WHERE tg_id=$2)",
            quiz['dmg'], cb.from_user.id
        )
        rec2 = await db.fetchrow(
            "SELECT hp FROM characters WHERE user_id=(SELECT id FROM users WHERE tg_id=$1)",
            cb.from_user.id
        )
        if not rec2:
            return await cb.answer("Не удалось обновить информацию о персонаже.")
        
        if rec2['hp'] <= 0:
            await db.execute(
                "UPDATE characters SET hp=0 WHERE user_id=(SELECT id FROM users WHERE tg_id=$1)",
                cb.from_user.id
            )
            result = f"❌ Ошибка! Вы потеряли {quiz['dmg']} HP. Ваш HP: {rec2['hp']}"
            await cb.message.edit_text(result)
            await cb.message.reply("💀 Вы погибли! Конец игры. Хотите переиграть?", reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Переиграть", callback_data="replay")]]
            ))
            active_battles.pop(cb.message.chat.id, None)
        else:
            result = f"❌ Ошибка! Вы потеряли {quiz['dmg']} HP. Ваш HP: {rec2['hp']}"
            await cb.message.edit_text(result)
            # Новая атака
            btns = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🥉 Линейное (10)", callback_data="quiz_1"),
                InlineKeyboardButton(text="🥈 Квадратное (20)", callback_data="quiz_2"),
                InlineKeyboardButton(text="🥇 Кубическое (30)", callback_data="quiz_3")
            ]])
            await cb.message.reply("Выберите степень атаки:", reply_markup=btns)

        await cb.answer()

    @dp.message(Command("stats"))
    async def cmd_stats(message: types.Message):
        # Получаем все логи пользователя
        user_id = message.from_user.id
        logs = await db.fetch(
            """
            SELECT action, ts
            FROM logs
            WHERE user_id = (SELECT id FROM users WHERE tg_id = $1)
            ORDER BY ts DESC
            """, user_id
        )

        if not logs:
            await message.answer("У вас нет действий в логе.")
            return

        # Строим сообщение с логами
        logs_message = "Ваши действия:\n"
        for log in logs:
            timestamp = log['ts'].strftime('%Y-%m-%d %H:%M:%S')  # Используем .strftime для объекта datetime
            logs_message += f"{timestamp} - {log['action']}\n"

        # Отправляем логи пользователю
        await message.answer(logs_message)



    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
