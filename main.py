import os
import json
import schedule
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import threading
import time

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7462876426:AAEk4v1_se0UcnAzVB3Rltiou9FkZJN1WpQ')
bot = telebot.TeleBot(API_TOKEN)

DATA_FILE = 'data_store.json'
ADMIN_ID = 5724269563
GROUP_ID = -5216745239

comands_chelp = """
🔹 *КОМАНДЫ ПОЛЬЗОВАТЕЛЯ*:
/start - начать общение
/help - помощь в боте
/mylist - мой список дел  
/transfer - отправить отчет админу и в группу
/reset - сбросить список дел (баллы за день обнуляются)
/change - изменить список дел
/mypoints - баллы за все время
/pintday - баллы за день
/liderpoint - таблица лидеров
"""

comands_user = """
🔹 *КОМАНДЫ ПОЛЬЗОВАТЕЛЯ*:
/start - начать общение
/help - помощь в боте
/chelp - полный список команд
/mylist - мой список дел  
/transfer - отправить отчет админу и в группу
/reset - сбросить список дел (баллы за день обнуляются)
/change - изменить список дел
/mypoints - баллы за все время
/pintday - баллы за день
/liderpoint - таблица лидеров
"""

comands_admin = """
🔹 *АДМИН КОМАНДЫ*:
/ahelp - админ помощь
/homeuser - изменить план для всех  
/setgroup <ID> - изменить ID группы
/resetusers - сбросить всех пользователей
/points - управление баллами
/pointsadd <ID> <кол-во> - начислить баллы
/pointsremove <ID> <кол-во> - снять баллы
/pointsuser <ID> - баллы пользователя
/pointsresetall - обнулить баллы всем
"""


def load_data():
    """Загрузка данных из файла"""
    if not os.path.exists(DATA_FILE):
        return {
            'users_data': {},
            'default_tasks': [],
            'last_reset': None,
            'group_id': GROUP_ID
        }
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return {
            'users_data': {},
            'default_tasks': [],
            'last_reset': get_today_date_str(),
            'group_id': GROUP_ID
        }


def save_data(data):
    """Сохранение данных в файл"""
    try:
        data_copy = data.copy()
        data_copy['group_id'] = GROUP_ID
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=2)
        print("💾 Данные сохранены!")
    except Exception as e:
        print(f"❌ Ошибка сохранения данных: {e}")


def get_today_date_str():
    """Текущая дата в формате YYYY-MM-DD (по МСК)"""
    msk = datetime.now() + timedelta(hours=3)
    return msk.strftime('%Y-%m-%d')


def should_reset_today(data):
    """Проверить, нужно ли сбросить задачи сегодня"""
    today = get_today_date_str()
    return data.get('last_reset') != today


def reset_all_users_completed(data):
    """Сброс выполненных задач для всех пользователей"""
    reset_count = 0
    for user_id in list(data['users_data'].keys()):
        if user_id in data['users_data']:
            data['users_data'][user_id]['completed'] = []
            data['users_data'][user_id]['daily_completed_count'] = {}
            data['users_data'][user_id]['daily_points'] = 0
            reset_count += 1
    print(f"✅ Сброшены задачи для {reset_count} пользователей")
    return reset_count


def get_user_data(user_id):
    """Получить данные пользователя с автосозданием"""
    global users_data, default_tasks
    if user_id not in users_data:
        users_data[user_id] = {
            'tasks': [],
            'completed': [],
            'daily_completed_count': {},
            'total_points': 0,
            'daily_points': 0,
            'daily_earned_points': 0
        }
        refresh_persistent_storage()
    return users_data[user_id]


def add_points(user_id, points):
    """Начисление/списание баллов"""
    user_data = get_user_data(user_id)
    user_data['total_points'] += points
    user_data['daily_points'] += points
    if points > 0:
        user_data['daily_earned_points'] += points
    refresh_persistent_storage()


def send_report_to_admins(report):
    """✅ HTML версия - 100% работает"""
    destinations = []

    # Конвертируем Markdown в HTML
    html_report = report.replace('*', '').replace('_', '')  # Убираем проблемные символы
    html_report = html_report.replace('📋', '📋').replace('✅', '✅')  # Эмодзи OK

    print(f"📤 Отправляем HTML отчет...")

    try:
        bot.send_message(ADMIN_ID, html_report, parse_mode='HTML')
        destinations.append("админу")
        print("✅ Админ OK")
    except Exception as e:
        print(f"❌ Админ: {e}")
        # Fallback без разметки
        try:
            bot.send_message(ADMIN_ID, html_report.replace('📋', '[📋]').replace('✅', '[✅]'))
            destinations.append("админу (plain)")
        except:
            destinations.append("❌ админ")

    try:
        bot.send_message(GROUP_ID, html_report, parse_mode='HTML')
        if destinations:
            destinations[-1] += " и группе"
        else:
            destinations.append("группе")
        print("✅ Группа OK")
    except Exception as e:
        print(f"❌ Группа: {e}")
        # Fallback без разметки
        try:
            bot.send_message(GROUP_ID, html_report.replace('📋', '[📋]').replace('✅', '[✅]'))
            destinations.append("группе (plain)")
        except:
            destinations.append("❌ группа")

    return destinations


def get_name(message):
    """Получение имени пользователя"""
    return (message.from_user.first_name or
            message.from_user.username or
            'Пользователь')


# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
data = load_data()
users_data = data.get('users_data', {})
default_tasks = data.get('default_tasks', [])
last_reset = data.get('last_reset', get_today_date_str())

if should_reset_today(data):
    print("🔄 Автосброс при запуске!")
    reset_all_users_completed(data)
    last_reset = get_today_date_str()
    data['last_reset'] = last_reset
    save_data(data)


def refresh_persistent_storage():
    """Обновление и сохранение данных"""
    global data
    data['users_data'] = users_data
    data['default_tasks'] = default_tasks
    data['last_reset'] = last_reset
    save_data(data)


def midnight_reset():
    """Сброс всех выполненных задач в полночь"""
    global last_reset
    today = get_today_date_str()
    if last_reset != today:
        print("🕛 Полуночный сброс!")
        reset_count = reset_all_users_completed(data)
        last_reset = today
        refresh_persistent_storage()
        try:
            notify_msg = f"🕛 Полуночный сброс! Обнулены задачи {reset_count} пользователей"
            bot.send_message(ADMIN_ID, notify_msg)
            bot.send_message(GROUP_ID, notify_msg)
        except:
            pass


def run_scheduler():
    """Планировщик задач"""
    schedule.every().day.at("00:00").do(midnight_reset)
    while True:
        schedule.run_pending()
        time.sleep(60)


def update_tasks_message(chat_id, message_id=None):
    """Обновление сообщения со списком задач"""
    user_data = get_user_data(chat_id)

    tasks_text = "📋 *Ваш список дел на сегодня:*\n\n"
    if not user_data['tasks']:
        tasks_text += "❌ Нет задач\n"

    for i, task in enumerate(user_data['tasks'], start=1):
        count_info = ""
        if task['name'] in user_data['completed']:
            status = "✅"
            if task['type'] == 'multiple' and task['name'] in user_data['daily_completed_count']:
                count_done = user_data['daily_completed_count'][task['name']]
                count_info = f" ({count_done}/{task['count']} раз)"
        else:
            status = "❌"
            if task['type'] == 'multiple':
                count_info = f" ({task['count']} раз)"

        tasks_text += f"{i}. {status} {task['name']}{count_info}\n"

    markup = InlineKeyboardMarkup(row_width=1)
    for task in user_data['tasks']:
        if task['name'] in user_data['completed']:
            status = "✅"
            count_info = f" ({user_data['daily_completed_count'].get(task['name'], 0)}/{task['count']} раз)" if task[
                                                                                                                    'type'] == 'multiple' else ""
        else:
            status = "❌"
            count_info = f" ({task['count']} раз)" if task['type'] == 'multiple' else ""
        button_text = f"{status} {task['name']}{count_info}"
        markup.add(InlineKeyboardButton(button_text, callback_data=f"toggle_task:{task['name']}"))

    if message_id:
        try:
            bot.edit_message_text(tasks_text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
            return True
        except:
            pass

    bot.send_message(chat_id, tasks_text, reply_markup=markup, parse_mode='Markdown')
    return False


# Обработчики команд
@bot.message_handler(commands=['start'])
def start_message(message):
    name = get_name(message)
    user_id = str(message.chat.id)
    get_user_data(user_id)
    bot.send_message(message.chat.id,
                     f"Привет, {name}! 👋\n\n"
                     f"📱 Бот для ежедневных отчетов.\n"
                     f"✅ Отмечай задачи кнопками.\n"
                     f"🕛 *Сброс в 00:00 МСК*\n\n"
                     f"/chelp - полный список команд", parse_mode='Markdown')


@bot.message_handler(commands=['help'])
def help_users(message):
    bot.send_message(message.chat.id, comands_user, parse_mode='Markdown')


@bot.message_handler(commands=['chelp'])
def chelp_command(message):
    bot.send_message(message.chat.id, comands_chelp, parse_mode='Markdown')


@bot.message_handler(commands=['ahelp'])
def help_admin(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет прав!")
        return
    bot.send_message(message.chat.id, comands_admin, parse_mode='Markdown')


@bot.message_handler(commands=['mylist'])
def home_command(message):
    user_id = str(message.chat.id)
    update_tasks_message(user_id)


@bot.message_handler(commands=['transfer'])
def peredat_command(message):
    user_id = str(message.chat.id)
    user_data = get_user_data(user_id)

    # -1 балл за каждую невыполненную задачу
    for task in user_data['tasks']:
        if task['name'] not in user_data['completed']:
            add_points(user_id, -1)

    report = f"📋 *ОТЧЕТ ПО ЗАДАЧАМ*\n"
    report += f"👤 Пользователь: @{message.from_user.username or 'Неизвестный'}\n"
    report += f"🆔 ID: {user_id}\n"
    report += f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

    report += "📝 *СПИСОК ЗАДАЧ:*\n"
    completed_list = []
    not_completed_list = []

    for task in user_data['tasks']:
        count_info = ""
        if task['type'] == 'multiple' and task['name'] in user_data['daily_completed_count']:
            count_info = f" ({user_data['daily_completed_count'][task['name']]}/{task['count']})"
        elif task['type'] == 'multiple':
            count_info = f" (0/{task['count']})"

        if task['name'] in user_data['completed']:
            completed_list.append(f"✅ {task['name']}{count_info}")
        else:
            not_completed_list.append(f"❌ {task['name']}{count_info}")

    if completed_list:
        report += "✅ *ВЫПОЛНЕННЫЕ:*\n" + "\n".join(completed_list) + "\n\n"
    if not_completed_list:
        report += "❌ *НЕ ВЫПОЛНЕННЫЕ:*\n" + "\n".join(not_completed_list) + "\n\n"

    total = len(user_data['tasks'])
    completed = len(user_data['completed'])
    percentage = 0 if total == 0 else (completed / total) * 100
    report += f"📊 *СТАТИСТИКА:* {completed}/{total} ({percentage:.1f}%)\n"
    report += f"⭐ *БАЛЛЫ ЗА ДЕНЬ:* {user_data.get('daily_points', 0)}\n"
    report += f"⭐ *ОБЩИЕ БАЛЛЫ:* {user_data.get('total_points', 0)}"

    destinations = send_report_to_admins(report)
    dest_text = " и ".join(destinations) if destinations else "❌ никуда"
    bot.send_message(message.chat.id, f"📤 Отчет отправлен {dest_text}!")


@bot.message_handler(commands=['reset'])
def reset_us_command(message):
    user_id = str(message.chat.id)
    if user_id in users_data:
        # Вычитаем заработанные сегодня баллы из общих
        daily_earned = users_data[user_id].get('daily_earned_points', 0)
        users_data[user_id]['total_points'] -= daily_earned
        users_data[user_id]['completed'] = []
        users_data[user_id]['daily_completed_count'] = {}
        users_data[user_id]['daily_points'] = 0
        users_data[user_id]['daily_earned_points'] = 0
        refresh_persistent_storage()

    bot.send_message(message.chat.id, "🔄 Список дел и баллы за день сброшены!")
    update_tasks_message(user_id)


@bot.message_handler(commands=['mypoints'])
def mypoints_command(message):
    user_id = str(message.chat.id)
    user_data = get_user_data(user_id)
    bot.send_message(message.chat.id,
                     f"⭐ *Ваши баллы:*\n"
                     f"📊 За сегодня: {user_data.get('daily_points', 0)}\n"
                     f"📈 Всего: {user_data.get('total_points', 0)}",
                     parse_mode='Markdown')


@bot.message_handler(commands=['pintday'])
def pintday_command(message):
    user_id = str(message.chat.id)
    user_data = get_user_data(user_id)
    bot.send_message(message.chat.id, f"📊 Баллы за сегодня: {user_data.get('daily_points', 0)}")


@bot.message_handler(commands=['liderpoint'])
def liderpoint_command(message):
    sorted_users = sorted(users_data.items(), key=lambda x: x[1].get('total_points', 0), reverse=True)
    text = "🏆 *ТАБЛИЦА ЛИДЕРОВ* (топ-10):\n\n"
    for i, (user_id, data) in enumerate(sorted_users[:10], 1):
        points = data.get('total_points', 0)
        text += f"{i}. Пользователь {user_id}: {points} баллов\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(commands=['change'])
def change_command(message):
    user_id = str(message.chat.id)
    user_data = get_user_data(user_id)

    markup = InlineKeyboardMarkup(row_width=1)
    if user_data['tasks']:
        for task in user_data['tasks']:
            count_info = f" ({task['count']} раз)" if task['type'] == 'multiple' else ""
            markup.add(InlineKeyboardButton(f"🗑 Удалить {task['name']}{count_info}",
                                            callback_data=f"remove_task:{task['name']}"))
    markup.add(InlineKeyboardButton("➕ Добавить задание", callback_data="add_task_menu"))

    text = "✏️ *Редактирование списка:*"
    if not user_data['tasks']:
        text += "\n❌ Нет задач"

    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')


# Callback handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_task:'))
def remove_task_callback(call):
    user_id = str(call.message.chat.id)
    task_name = call.data.split(':', 1)[1]
    user_data = get_user_data(user_id)

    user_data['tasks'] = [t for t in user_data['tasks'] if t['name'] != task_name]
    if task_name in user_data['completed']:
        user_data['completed'].remove(task_name)
        if task_name in user_data['daily_completed_count']:
            del user_data['daily_completed_count'][task_name]
    refresh_persistent_storage()
    bot.answer_callback_query(call.id, f"🗑 Задание удалено!")
    change_command_type = type(call.message)
    bot.edit_message_text("✏️ *Редактирование списка:*", user_id, call.message.message_id,
                          reply_markup=InlineKeyboardMarkup(row_width=1).add(
                              InlineKeyboardButton("📝 Обычное задание", callback_data="add_normal_task"),
                              InlineKeyboardButton("🔢 Многократное задание", callback_data="add_multiple_task")
                          ), parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'add_task_menu')
def add_task_menu_callback(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📝 Обычное задание", callback_data="add_normal_task"))
    markup.add(InlineKeyboardButton("🔢 Многократное задание", callback_data="add_multiple_task"))
    bot.edit_message_text("Выберите тип задания:", call.message.chat.id, call.message.message_id,
                          reply_markup=markup, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == 'add_normal_task')
def add_normal_task_callback(call):
    user_id = str(call.message.chat.id)
    msg = bot.send_message(user_id, "📝 Введите название обычного задания:")
    bot.register_next_step_handler(msg, process_normal_task)


@bot.callback_query_handler(func=lambda call: call.data == 'add_multiple_task')
def add_multiple_task_callback(call):
    user_id = str(call.message.chat.id)
    msg = bot.send_message(user_id, "🔢 Введите количество повторений:")
    bot.register_next_step_handler(msg, process_multiple_count_step)


def process_normal_task(message):
    user_id = str(message.chat.id)
    task_name = message.text.strip()
    if not task_name:
        bot.send_message(user_id, "❌ Пустое задание!")
        return

    user_data = get_user_data(user_id)
    task_exists = any(t['name'] == task_name for t in user_data['tasks'])
    if not task_exists:
        user_data['tasks'].append({'name': task_name, 'count': 1, 'type': 'normal'})
        refresh_persistent_storage()
        bot.send_message(user_id, f"✅ '{task_name}' добавлено!")
    update_tasks_message(user_id)


def process_multiple_count_step(message):
    user_id = str(message.chat.id)
    try:
        count = int(message.text.strip())
        if count < 1:
            raise ValueError
        bot.send_message(user_id, f"🔢 Задание на {count} раз. Введите название:")
        bot.register_next_step_handler(message, lambda m: process_multiple_task(m, count))
    except:
        bot.send_message(user_id, "❌ Введите корректное число!")
        msg = bot.send_message(user_id, "🔢 Введите количество повторений:")
        bot.register_next_step_handler(msg, process_multiple_count_step)


def process_multiple_task(message, count):
    user_id = str(message.chat.id)
    task_name = message.text.strip()
    if not task_name:
        bot.send_message(user_id, "❌ Пустое задание!")
        return

    user_data = get_user_data(user_id)
    task_exists = any(t['name'] == task_name for t in user_data['tasks'])
    if not task_exists:
        user_data['tasks'].append({'name': task_name, 'count': count, 'type': 'multiple'})
        refresh_persistent_storage()
        bot.send_message(user_id, f"✅ '{task_name}' ({count} раз) добавлено!")
    update_tasks_message(user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_task:'))
def toggle_task_callback(call):
    user_id = str(call.message.chat.id)
    message_id = call.message.message_id
    task_name = call.data.split(':', 1)[1]
    user_data = get_user_data(user_id)

    if task_name not in user_data['completed']:
        task = next((t for t in user_data['tasks'] if t['name'] == task_name), None)
        if task and task['type'] == 'multiple':
            markup = InlineKeyboardMarkup(row_width=5)
            for i in range(1, 11):
                markup.add(InlineKeyboardButton(str(i), callback_data=f"set_count:{task_name}:{i}"))
            markup.add(InlineKeyboardButton("Другое", callback_data=f"custom_count:{task_name}"))
            bot.edit_message_text(
                f"🔢 Сколько раз выполнено '{task_name}'?",
                user_id, message_id, reply_markup=markup, parse_mode='Markdown'
            )
        else:
            user_data['completed'].append(task_name)
            user_data['daily_completed_count'][task_name] = 1
            add_points(user_id, 2)
            bot.answer_callback_query(call.id, "✅ Выполнено! +2 балла")
            refresh_persistent_storage()
            update_tasks_message(user_id, message_id)
    else:
        bot.answer_callback_query(call.id, "⚠️ Выполненные задания нельзя отменить!")


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_count:'))
def set_count_callback(call):
    user_id = str(call.message.chat.id)
    message_id = call.message.message_id
    parts = call.data.split(':')
    task_name = parts[1]
    completed_count = int(parts[2])

    user_data = get_user_data(user_id)
    task = next(t for t in user_data['tasks'] if t['name'] == task_name)

    user_data['completed'].append(task_name)
    user_data['daily_completed_count'][task_name] = completed_count

    if completed_count >= task['count']:
        add_points(user_id, 3)
        bot.answer_callback_query(call.id, f"✅ Полное выполнение! +3 балла")
    else:
        add_points(user_id, 2)
        bot.answer_callback_query(call.id, f"✅ {completed_count} раз (+2 балла)")

    refresh_persistent_storage()
    update_tasks_message(user_id, message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('custom_count:'))
def custom_count_callback(call):
    user_id = str(call.message.chat.id)
    task_name = call.data.split(':', 2)[1]
    msg = bot.send_message(user_id, f"🔢 Введите точное количество выполнений '{task_name}':")
    bot.register_next_step_handler(msg, lambda m: process_custom_count(m, task_name))


def process_custom_count(message, task_name):
    user_id = str(message.chat.id)
    try:
        completed_count = int(message.text.strip())
        if completed_count < 1:
            raise ValueError

        user_data = get_user_data(user_id)
        task = next(t for t in user_data['tasks'] if t['name'] == task_name)

        user_data['completed'].append(task_name)
        user_data['daily_completed_count'][task_name] = completed_count

        if completed_count >= task['count']:
            add_points(user_id, 3)
            bot.send_message(user_id, f"✅ Полное выполнение '{task_name}'! +3 балла")
        else:
            add_points(user_id, 2)
            bot.send_message(user_id, f"✅ '{task_name}' выполнено {completed_count} раз. +2 балла")

        refresh_persistent_storage()
        update_tasks_message(user_id)
    except:
        bot.send_message(user_id, "❌ Введите корректное число!")


# Админские команды
@bot.message_handler(commands=['resetusers'])
def reset_all_command(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет прав!")
        return
    reset_count = reset_all_users_completed(data)
    global last_reset
    last_reset = get_today_date_str()
    refresh_persistent_storage()
    bot.send_message(message.chat.id, f"🔄 Сброшено {reset_count} пользователей!")


@bot.message_handler(commands=['setgroup'])
def set_group_command(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет прав!")
        return
    try:
        global GROUP_ID
        GROUP_ID = int(message.text.split()[1])
        refresh_persistent_storage()
        bot.send_message(message.chat.id, f"✅ Группа изменена на {GROUP_ID}")
    except:
        bot.send_message(message.chat.id, "❌ Используйте: /setgroup -1002423429127")


@bot.message_handler(commands=['homeuser'])
def admin_edit_tasks(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет прав!")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for task in default_tasks:
        markup.add(InlineKeyboardButton(f"🗑 Удалить {task}", callback_data=f"remove_global_task:{task}"))
    markup.add(InlineKeyboardButton("➕ Добавить для всех", callback_data="add_global_task"))
    bot.send_message(message.chat.id, f"🔧 Общий список задач:\nГруппа: {GROUP_ID}", reply_markup=markup)


@bot.message_handler(commands=['points'])
def admin_points_command(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет прав!")
        return
    text = """
🔧 *Управление баллами*

/pointsadd <ID> <количество> - начислить баллы
/pointsremove <ID> <количество> - снять баллы  
/pointsuser <ID> - посмотреть баллы пользователя
/pointsresetall - обнулить баллы всем
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(commands=['pointsadd'])
def admin_pointsadd(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = parts[1]
        points = int(parts[2])
        add_points(user_id, points)
        bot.send_message(message.chat.id, f"✅ {user_id}: +{points} баллов")
    except:
        bot.send_message(message.chat.id, "❌ Формат: /pointsadd ID количество")


@bot.message_handler(commands=['pointsremove'])
def admin_pointsremove(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = parts[1]
        points = int(parts[2])
        add_points(user_id, -points)
        bot.send_message(message.chat.id, f"✅ {user_id}: -{points} баллов")
    except:
        bot.send_message(message.chat.id, "❌ Формат: /pointsremove ID количество")


@bot.message_handler(commands=['pointsuser'])
def admin_pointsuser(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        user_id = message.text.split()[1]
        user_data = get_user_data(user_id)
        bot.send_message(message.chat.id,
                         f"👤 {user_id}:\n"
                         f"📊 За день: {user_data.get('daily_points', 0)}\n"
                         f"📈 Всего: {user_data.get('total_points', 0)}")
    except:
        bot.send_message(message.chat.id, "❌ Формат: /pointsuser ID")


@bot.message_handler(commands=['pointsresetall'])
def admin_pointsresetall(message):
    if message.chat.id != ADMIN_ID:
        return
    for user_id in users_data:
        users_data[user_id]['total_points'] = 0
        users_data[user_id]['daily_points'] = 0
        users_data[user_id]['daily_earned_points'] = 0
    refresh_persistent_storage()
    bot.send_message(message.chat.id, "✅ Баллы обнулены для всех пользователей!")


if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print(f"📁 Файл данных: {DATA_FILE}")
    print(f"👑 Админ: {ADMIN_ID}")
    print(f"👥 Группа: {GROUP_ID}")
    print(f"📅 Последний сброс: {last_reset}")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен!")
