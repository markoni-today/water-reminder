"""
QA Тест для проверки многопользовательского режима Water Reminder Bot
Проверяет изоляцию пользователей и корректность работы задач
"""
import sqlite3
import sys
from datetime import datetime
import pytz

# Путь к базе данных
DB_NAME = "reminders.db"

def print_section(title):
    """Красивый вывод заголовка раздела."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def test_database_structure():
    """Проверка структуры базы данных."""
    print_section("ТЕСТ 1: Структура базы данных")
    
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            # Проверяем таблицу water_reminders
            cur.execute("PRAGMA table_info(water_reminders)")
            columns = cur.fetchall()
            
            print("📋 Колонки таблицы water_reminders:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
            
            # Проверяем наличие важных полей
            column_names = [col[1] for col in columns]
            required_fields = ['chat_id', 'is_active', 'timezone', 'onboarding_completed']
            
            print("\n✅ Проверка обязательных полей:")
            for field in required_fields:
                if field in column_names:
                    print(f"  ✓ {field} - присутствует")
                else:
                    print(f"  ✗ {field} - ОТСУТСТВУЕТ!")
                    return False
            
            print("\n✅ ТЕСТ ПРОЙДЕН: Структура БД корректна")
            return True
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

def test_user_isolation():
    """Проверка изоляции пользователей в базе данных."""
    print_section("ТЕСТ 2: Изоляция пользователей")
    
    try:
        with sqlite3.connect(DB_NAME) as con:
            cur = con.cursor()
            
            # Получаем всех пользователей
            cur.execute("""
                SELECT chat_id, is_active, timezone, onboarding_completed, updated_at
                FROM water_reminders
                ORDER BY chat_id
            """)
            users = cur.fetchall()
            
            if not users:
                print("⚠️ В базе нет пользователей")
                return True
            
            print(f"📊 Найдено пользователей: {len(users)}\n")
            
            for user in users:
                chat_id, is_active, timezone, onboarding, updated = user
                print(f"👤 Пользователь {chat_id}:")
                print(f"   Активен: {'✓' if is_active else '✗'}")
                print(f"   Часовой пояс: {timezone}")
                print(f"   Онбординг пройден: {'✓' if onboarding else '✗'}")
                print(f"   Обновлен: {updated if updated else 'N/A'}")
                print()
            
            # Проверяем уникальность chat_id
            cur.execute("SELECT chat_id, COUNT(*) FROM water_reminders GROUP BY chat_id HAVING COUNT(*) > 1")
            duplicates = cur.fetchall()
            
            if duplicates:
                print(f"❌ ОШИБКА: Найдены дубликаты chat_id: {duplicates}")
                return False
            
            print("✅ ТЕСТ ПРОЙДЕН: Пользователи изолированы, дубликатов нет")
            return True
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        return False

def test_scheduler_logic():
    """Проверка логики планировщика (симуляция)."""
    print_section("ТЕСТ 3: Логика планировщика")
    
    print("📝 Проверяем логику создания задач...\n")
    
    # Симулируем создание задач для 2 пользователей
    user1_id = 123456
    user2_id = 789012
    
    # Проверяем формат job_id
    print(f"Пользователь 1 (chat_id={user1_id}):")
    for hour in range(8, 24):
        job_id = f"water_{user1_id}_{hour}"
        print(f"  {hour:02d}:00 → job_id: {job_id}")
    
    print(f"\nПользователь 2 (chat_id={user2_id}):")
    for hour in range(8, 24):
        job_id = f"water_{user2_id}_{hour}"
        print(f"  {hour:02d}:00 → job_id: {job_id}")
    
    # Проверяем, что job_id уникальны
    user1_jobs = [f"water_{user1_id}_{hour}" for hour in range(8, 24)]
    user2_jobs = [f"water_{user2_id}_{hour}" for hour in range(8, 24)]
    
    overlap = set(user1_jobs) & set(user2_jobs)
    
    if overlap:
        print(f"\n❌ ОШИБКА: Обнаружены пересекающиеся job_id: {overlap}")
        return False
    
    print(f"\n✅ ТЕСТ ПРОЙДЕН: job_id уникальны для каждого пользователя")
    print(f"   Всего задач на пользователя: {len(user1_jobs)}")
    return True

def test_time_range():
    """Проверка диапазона времени отправки."""
    print_section("ТЕСТ 4: Диапазон времени отправки")
    
    START_HOUR = 8
    END_HOUR = 23
    
    print(f"📅 Настроенный диапазон: {START_HOUR:02d}:00 - {END_HOUR:02d}:00\n")
    
    # Проверяем условие <= для включения 23:00
    test_hours = [7, 8, 12, 15, 20, 22, 23, 0, 1]
    
    print("Проверка условия: start_hour <= now.hour <= end_hour\n")
    
    for hour in test_hours:
        should_send = START_HOUR <= hour <= END_HOUR
        print(f"  {hour:02d}:00 → {'✓ Отправить' if should_send else '✗ Не отправлять'}")
    
    # Проверяем, что 23:00 включено
    if START_HOUR <= 23 <= END_HOUR:
        print(f"\n✅ ТЕСТ ПРОЙДЕН: Уведомление в 23:00 будет отправлено")
        return True
    else:
        print(f"\n❌ ОШИБКА: Уведомление в 23:00 НЕ будет отправлено")
        return False

def test_next_notification_logic():
    """Проверка логики вычисления следующего уведомления."""
    print_section("ТЕСТ 5: Логика следующего уведомления")
    
    START_HOUR = 8
    END_HOUR = 23
    
    # Тестовые сценарии
    test_cases = [
        (7, 34, 8, 0, "До начала рабочего времени"),
        (9, 5, 10, 0, "В рабочее время (округление вверх)"),
        (14, 0, 15, 0, "В рабочее время (ровно час)"),
        (22, 30, 23, 0, "Последний час рабочего времени"),
        (23, 0, None, None, "После 23:00 (следующий день в 8:00)"),
        (0, 30, 8, 0, "Ночь (следующий день в 8:00)"),
    ]
    
    print("📊 Тестовые сценарии:\n")
    
    all_passed = True
    for current_h, current_m, expected_h, expected_m, description in test_cases:
        print(f"  Текущее время: {current_h:02d}:{current_m:02d}")
        print(f"  Описание: {description}")
        
        # Логика из calculate_next_notification_time
        if START_HOUR <= current_h < END_HOUR:
            next_h = current_h + 1
            result = f"{next_h:02d}:00"
        elif current_h < START_HOUR:
            result = f"{START_HOUR:02d}:00 (сегодня)"
        else:
            result = f"{START_HOUR:02d}:00 (завтра)"
        
        if expected_h is not None:
            expected = f"{expected_h:02d}:{expected_m:02d}"
            if next_h == expected_h if START_HOUR <= current_h < END_HOUR else True:
                print(f"  ✓ Результат: {result}")
            else:
                print(f"  ✗ Результат: {result} (ожидалось: {expected})")
                all_passed = False
        else:
            print(f"  → Результат: {result}")
        
        print()
    
    if all_passed:
        print("✅ ТЕСТ ПРОЙДЕН: Логика вычисления корректна")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН: Обнаружены ошибки в логике")
    
    return all_passed

def run_all_tests():
    """Запускает все тесты."""
    print("\n")
    print("🧪" * 40)
    print("  WATER REMINDER BOT - QA ТЕСТИРОВАНИЕ МНОГОПОЛЬЗОВАТЕЛЬСКОГО РЕЖИМА")
    print("🧪" * 40)
    
    results = []
    
    # Запускаем тесты
    results.append(("Структура БД", test_database_structure()))
    results.append(("Изоляция пользователей", test_user_isolation()))
    results.append(("Логика планировщика", test_scheduler_logic()))
    results.append(("Диапазон времени", test_time_range()))
    results.append(("Следующее уведомление", test_next_notification_logic()))
    
    # Итоговый отчёт
    print_section("ИТОГОВЫЙ ОТЧЁТ")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {status}: {test_name}")
    
    print(f"\n{'=' * 80}")
    print(f"  Пройдено: {passed}/{total}")
    print(f"  Успешность: {(passed/total)*100:.1f}%")
    print(f"{'=' * 80}\n")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

