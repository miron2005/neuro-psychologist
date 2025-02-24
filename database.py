import sqlite3
import json


def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (chat_id INT PRIMARY KEY, 
                  progress TEXT,
                  current_course INT,
                  current_module INT,
                  current_lesson INT)''')
    conn.commit()
    conn.close()


def get_user_data(chat_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    result = c.fetchone()
    conn.close()

    if result:
        return {
            "chat_id": result[0],
            "progress": json.loads(result[1]) if result[1] else {},
            "current_course": result[2],
            "current_module": result[3],
            "current_lesson": result[4]
        }
    return None


def update_user_data(chat_id, data):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    progress = data.get("progress", {})
    progress_json = json.dumps(progress) if progress else json.dumps({})

    c.execute('''INSERT OR REPLACE INTO users 
                 VALUES (?, ?, ?, ?, ?)''',
              (chat_id,
               progress_json,
               data.get("current_course"),
               data.get("current_module"),
               data.get("current_lesson")))
    conn.commit()
    conn.close()