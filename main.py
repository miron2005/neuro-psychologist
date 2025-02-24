import logging
import telebot
import os
import openai
import json
from database import init_db, get_user_data, update_user_data
from dotenv import load_dotenv

load_dotenv()
init_db()

bot = telebot.TeleBot(os.getenv("TG_BOT_TOKEN"))
openai.api_key = os.getenv("PROXY_API_KEY")
openai.api_base = "https://api.proxyapi.ru/openai/v1"

with open('courses.json', 'r', encoding='utf-8') as f:
    courses = json.load(f)["courses"]

with open('tests.json', 'r', encoding='utf-8') as f:
    tests = json.load(f)["tests"]

user_tests = {}


def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 Курсы", "💬 Вопрос ментору")
    markup.add("📝 Тесты", "🏆 Прогресс")
    return markup


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user = get_user_data(message.chat.id) or {
        "progress": {},
        "current_course": None,
        "current_module": None,
        "current_lesson": None
    }
    update_user_data(message.chat.id, user)
    bot.send_message(message.chat.id, "👋 Привет! Я твой личный ментор. Выбери действие:", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📚 Курсы")
def show_courses(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for course in courses:
        markup.add(f"🎓 {course['title']}")
    markup.add("🔙 На главную")
    bot.send_message(message.chat.id, "Доступные курсы:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text.startswith("🎓"))
def handle_course(message):
    course_title = message.text[2:]
    course = next((c for c in courses if c['title'] == course_title), None)

    if course:
        user = get_user_data(message.chat.id) or {}
        user["current_course"] = course["id"]
        user["current_module"] = None
        update_user_data(message.chat.id, user)

        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for module in course["modules"]:
            markup.add(f"📦 Модуль {module['id']}: {module['title']}")
        markup.add("🔙 Назад")
        bot.send_message(message.chat.id, f"📚 Курс: {course['title']}\nВыберите модуль:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text.startswith("📦"))
def handle_module(message):
    user = get_user_data(message.chat.id) or {}
    module_id = int(message.text.split(":")[0].split()[-1])

    course = next((c for c in courses if c["id"] == user.get("current_course")), None)
    module = next((m for m in course["modules"] if m["id"] == module_id), None)

    if module:
        user["current_module"] = module_id
        update_user_data(message.chat.id, user)

        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for lesson in module["lessons"]:
            status = "✅" if lesson["id"] in user.get("progress", {}).get(str(module_id), []) else ""
            markup.add(f"📖 Урок {lesson['id']} {status}")
        markup.add("🔙 Назад")
        bot.send_message(message.chat.id, f"📦 Модуль: {module['title']}\n{module['description']}", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text.startswith("📖"))
def handle_lesson(message):
    user = get_user_data(message.chat.id) or {}
    lesson_id = int(message.text.split()[1])

    course = next((c for c in courses if c["id"] == user.get("current_course")), None)
    module = next((m for m in course["modules"] if m["id"] == user.get("current_module")), None)
    lesson = next((l for l in module["lessons"] if l["id"] == lesson_id), None)

    if lesson:
        response = f"📌 {lesson['title']}\n\n{lesson['content']}\n\n✏️ Задание: {lesson['task']}"
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        if lesson_id < len(module["lessons"]):
            markup.add("➡️ Следующий урок")
        markup.add("🔙 К модулю", "🏠 На главную")

        bot.send_message(message.chat.id, response, reply_markup=markup)

        progress = user.get("progress", {})
        module_progress = progress.get(str(module["id"]), [])
        if lesson_id not in module_progress:
            module_progress.append(lesson_id)
            progress[str(module["id"])] = module_progress
            user["progress"] = progress
            update_user_data(message.chat.id, user)


@bot.message_handler(func=lambda m: m.text == "➡️ Следующий урок")
def next_lesson(message):
    user = get_user_data(message.chat.id) or {}
    user["current_lesson"] = user.get("current_lesson", 0) + 1
    update_user_data(message.chat.id, user)
    handle_lesson(message)


@bot.message_handler(func=lambda m: m.text == "📝 Тесты")
def show_tests(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for test in tests:
        markup.add(f"🧪 {test['title']}")
    markup.add("🔙 На главную")
    bot.send_message(message.chat.id, "Доступные тесты:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text.startswith("🧪"))
def start_test(message):
    test_title = message.text[2:]
    test = next((t for t in tests if t['title'] == test_title), None)

    if test:
        user_tests[message.chat.id] = {
            "test_id": test["id"],
            "current_question": 0,
            "score": 0
        }
        ask_test_question(message.chat.id, test["questions"][0])


def ask_test_question(chat_id, question):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for option in question["options"]:
        markup.add(option)
    bot.send_message(chat_id, question["text"], reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in user_tests)
def handle_test_answer(message):
    chat_id = message.chat.id
    test_data = user_tests[chat_id]
    current_test = next(t for t in tests if t["id"] == test_data["test_id"])
    current_question = current_test["questions"][test_data["current_question"]]

    answer_index = current_question["options"].index(message.text)
    test_data["score"] += current_question["scores"][answer_index]
    test_data["current_question"] += 1

    if test_data["current_question"] >= len(current_test["questions"]):
        total_score = test_data["score"]
        result_text = "Результаты теста:\n"
        for score_range, recommendation in current_test["results"].items():
            min_s, max_s = map(int, score_range.split("-"))
            if min_s <= total_score <= max_s:
                result_text += recommendation
                break

        bot.send_message(chat_id, result_text, reply_markup=main_menu())
        del user_tests[chat_id]
    else:
        ask_test_question(chat_id, current_test["questions"][test_data["current_question"]])

@ bot.message_handler(func=lambda m: m.text == "🏆 Прогресс")

def show_progress(message):
    user = get_user_data(message.chat.id) or {}
    progress = user.get("progress", {})

    response = "Ваш прогресс:\n\n"
    for course in courses:
        if str(course["id"]) in progress:
            response += f"📚 {course['title']}:\n"
            for module in course["modules"]:
                completed = len(progress[str(course["id"])].get(str(module["id"]), []))
                total = len(module["lessons"])
                response += f"  📦 {module['title']}: {completed}/{total} уроков\n"

    bot.send_message(message.chat.id, response)


@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if message.text == "🔙 На главную":
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
        return

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message.text}],
            temperature=0.7,
            max_tokens=500
        )
        bot.send_message(message.chat.id, response.choices[0].message['content'])
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {str(e)}")


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)