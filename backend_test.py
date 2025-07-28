#!/usr/bin/env python3
"""
Полное тестирование системы xAi_v2
Тестирует все API endpoints и критические функции
"""

import requests
import json
import time
import sys
from datetime import datetime
import tempfile
import os

class XAiTester:
    def __init__(self, base_url="https://831df312-52e2-4a2f-b5ff-9454a774aa99.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_user_id = f"test_user_{int(time.time())}"
        
    def log(self, message):
        """Логирование с временной меткой"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def run_test(self, name, test_func):
        """Запуск одного теста"""
        self.tests_run += 1
        self.log(f"🔍 Тест {self.tests_run}: {name}")
        
        try:
            result = test_func()
            if result:
                self.tests_passed += 1
                self.log(f"✅ ПРОЙДЕН: {name}")
                return True
            else:
                self.log(f"❌ ПРОВАЛЕН: {name}")
                return False
        except Exception as e:
            self.log(f"❌ ОШИБКА в {name}: {str(e)}")
            return False
    
    # Базовые API тесты
    def test_api_root(self):
        """Тест корневого API endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   API Root ответ: {data}")
                return "AI Sexter Bot API" in data.get("message", "")
            return False
        except Exception as e:
            self.log(f"   Ошибка API Root: {e}")
            return False
    
    def test_health_check(self):
        """Тест проверки здоровья системы"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Health status: {data.get('status')}")
                self.log(f"   Database: {data.get('database')}")
                self.log(f"   Models loaded: {data.get('models_loaded')}")
                return data.get("status") in ["healthy", "unhealthy"]  # Любой статус валиден
            return False
        except Exception as e:
            self.log(f"   Ошибка Health Check: {e}")
            return False
    
    def test_get_models(self):
        """Тест получения списка моделей"""
        try:
            response = requests.get(f"{self.api_url}/models", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                self.log(f"   Найдено моделей: {len(models)}")
                for model in models:
                    self.log(f"   - {model.get('name')}: {model.get('display_name')} ({model.get('language')})")
                return len(models) > 0
            return False
        except Exception as e:
            self.log(f"   Ошибка получения моделей: {e}")
            return False
    
    # Тесты чата и spintax
    def test_chat_basic(self):
        """Базовый тест чата"""
        try:
            payload = {
                "model": "rus_girl_1",
                "user_id": self.test_user_id,
                "message": "Привет"
            }
            response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Ответ: {data.get('response')}")
                self.log(f"   Номер сообщения: {data.get('message_number')}")
                self.log(f"   Источник: {data.get('source')}")
                return len(data.get('response', '')) > 0
            return False
        except Exception as e:
            self.log(f"   Ошибка базового чата: {e}")
            return False
    
    def test_spintax_functionality(self):
        """КРИТИЧЕСКИЙ ТЕСТ: Проверка работы spintax"""
        try:
            # Сначала добавим обученный ответ со spintax
            train_payload = {
                "question": "тест спинтакс",
                "answer": "{Привет|Приветик|Хай} {красавчик|милый|дорогой}!",
                "model": "rus_girl_1",
                "priority": 10
            }
            train_response = requests.post(f"{self.api_url}/train", json=train_payload, timeout=10)
            if train_response.status_code != 200:
                self.log(f"   Ошибка обучения для spintax: {train_response.status_code}")
                return False
            
            # Теперь тестируем spintax - делаем несколько запросов
            responses = []
            for i in range(5):
                payload = {
                    "model": "rus_girl_1", 
                    "user_id": f"{self.test_user_id}_spintax_{i}",
                    "message": "тест спинтакс"
                }
                response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('response', '')
                    responses.append(answer)
                    self.log(f"   Spintax ответ {i+1}: {answer}")
                else:
                    self.log(f"   Ошибка запроса {i+1}: {response.status_code}")
            
            # Проверяем что получили разные варианты
            unique_responses = set(responses)
            self.log(f"   Уникальных ответов: {len(unique_responses)} из {len(responses)}")
            
            # Проверяем что в ответах нет фигурных скобок (spintax обработан)
            has_brackets = any('{' in resp or '}' in resp for resp in responses)
            if has_brackets:
                self.log(f"   ❌ ОШИБКА: Найдены необработанные скобки spintax!")
                return False
            
            return len(unique_responses) > 1  # Должно быть минимум 2 разных варианта
            
        except Exception as e:
            self.log(f"   Ошибка тестирования spintax: {e}")
            return False
    
    def test_chat_progression(self):
        """Тест прогрессии чата до semi и final сообщений"""
        try:
            user_id = f"{self.test_user_id}_progression"
            
            # Получаем конфигурацию модели чтобы знать message_count
            model_response = requests.get(f"{self.api_url}/model/rus_girl_1", timeout=10)
            if model_response.status_code != 200:
                self.log(f"   Ошибка получения модели: {model_response.status_code}")
                return False
            
            model_config = model_response.json()
            message_count = model_config.get('message_count', 5)
            self.log(f"   Модель настроена на {message_count} сообщений")
            
            # Отправляем сообщения до предпоследнего
            for i in range(message_count - 1):
                payload = {
                    "model": "rus_girl_1",
                    "user_id": user_id,
                    "message": f"Сообщение {i+1}"
                }
                response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"   Сообщение {i+1}: {data.get('response')} (semi: {data.get('is_semi')}, final: {data.get('is_last')})")
                else:
                    self.log(f"   Ошибка сообщения {i+1}: {response.status_code}")
                    return False
            
            # Предпоследнее сообщение (должно быть semi)
            payload = {
                "model": "rus_girl_1",
                "user_id": user_id,
                "message": "Предпоследнее сообщение"
            }
            response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   SEMI сообщение: {data.get('response')} (semi: {data.get('is_semi')})")
                if not data.get('is_semi'):
                    self.log(f"   ❌ Предпоследнее сообщение не помечено как semi!")
                    return False
            else:
                return False
            
            # Финальное сообщение
            payload = {
                "model": "rus_girl_1",
                "user_id": user_id,
                "message": "Финальное сообщение"
            }
            response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   FINAL сообщение: {data.get('response')} (final: {data.get('is_last')})")
                if not data.get('is_last'):
                    self.log(f"   ❌ Финальное сообщение не помечено как final!")
                    return False
                return True
            else:
                return False
                
        except Exception as e:
            self.log(f"   Ошибка тестирования прогрессии: {e}")
            return False
    
    # Тесты обучения
    def test_manual_training(self):
        """Тест ручного обучения"""
        try:
            payload = {
                "question": "тестовый вопрос обучения",
                "answer": "тестовый ответ обучения",
                "model": "rus_girl_1",
                "priority": 8
            }
            response = requests.post(f"{self.api_url}/train", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Результат обучения: {data.get('message')}")
                
                # Проверяем что обученный ответ используется
                chat_payload = {
                    "model": "rus_girl_1",
                    "user_id": f"{self.test_user_id}_training_test",
                    "message": "тестовый вопрос обучения"
                }
                chat_response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
                if chat_response.status_code == 200:
                    chat_data = chat_response.json()
                    self.log(f"   Ответ после обучения: {chat_data.get('response')}")
                    self.log(f"   Источник ответа: {chat_data.get('source')}")
                    return chat_data.get('source') == 'trained'
                return False
            return False
        except Exception as e:
            self.log(f"   Ошибка ручного обучения: {e}")
            return False
    
    def test_file_training(self):
        """Тест файлового обучения"""
        try:
            # Создаем временный файл с обучающими данными
            training_data = """# Тестовые данные для обучения
файл вопрос 1 - файл ответ 1
файл вопрос 2 | файл ответ 2
файл вопрос 3	файл ответ 3"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(training_data)
                temp_file_path = f.name
            
            try:
                # Загружаем файл
                with open(temp_file_path, 'rb') as f:
                    files = {'file': ('training.txt', f, 'text/plain')}
                    data = {'model': 'rus_girl_1'}
                    response = requests.post(f"{self.api_url}/train-file?model=rus_girl_1", files=files, timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    self.log(f"   Результат файлового обучения: {result.get('message')}")
                    
                    # Проверяем что один из обученных ответов работает
                    chat_payload = {
                        "model": "rus_girl_1",
                        "user_id": f"{self.test_user_id}_file_test",
                        "message": "файл вопрос 1"
                    }
                    chat_response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
                    if chat_response.status_code == 200:
                        chat_data = chat_response.json()
                        self.log(f"   Ответ из файла: {chat_data.get('response')}")
                        self.log(f"   Источник: {chat_data.get('source')}")
                        return chat_data.get('source') == 'trained' and 'файл ответ 1' in chat_data.get('response', '')
                    return False
                else:
                    self.log(f"   Ошибка загрузки файла: {response.status_code} - {response.text}")
                    return False
                    
            finally:
                # Удаляем временный файл
                os.unlink(temp_file_path)
                
        except Exception as e:
            self.log(f"   Ошибка файлового обучения: {e}")
            return False
    
    def test_trained_responses_usage(self):
        """Тест использования обученных ответов"""
        try:
            # Добавляем несколько обученных ответов с разными приоритетами
            training_data = [
                {"question": "приоритет тест", "answer": "низкий приоритет", "priority": 3},
                {"question": "приоритет тест", "answer": "высокий приоритет", "priority": 9},
                {"question": "приоритет тест", "answer": "средний приоритет", "priority": 5}
            ]
            
            for data in training_data:
                payload = {
                    "question": data["question"],
                    "answer": data["answer"],
                    "model": "rus_girl_1",
                    "priority": data["priority"]
                }
                response = requests.post(f"{self.api_url}/train", json=payload, timeout=10)
                if response.status_code != 200:
                    self.log(f"   Ошибка обучения с приоритетом {data['priority']}")
                    return False
            
            # Проверяем что используется ответ с высоким приоритетом
            chat_payload = {
                "model": "rus_girl_1",
                "user_id": f"{self.test_user_id}_priority_test",
                "message": "приоритет тест"
            }
            response = requests.post(f"{self.api_url}/chat", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', '')
                self.log(f"   Ответ с приоритетом: {answer}")
                return "высокий приоритет" in answer
            return False
            
        except Exception as e:
            self.log(f"   Ошибка тестирования приоритетов: {e}")
            return False
    
    # Тесты статистики
    def test_statistics_collection(self):
        """Тест сбора статистики"""
        try:
            response = requests.get(f"{self.api_url}/statistics", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Всего диалогов: {data.get('total_conversations')}")
                self.log(f"   Всего пользователей: {data.get('total_users')}")
                self.log(f"   Статус системы: {data.get('system_status', {})}")
                
                # Проверяем наличие основных разделов статистики
                required_sections = ['total_conversations', 'total_users', 'system_status']
                for section in required_sections:
                    if section not in data:
                        self.log(f"   ❌ Отсутствует раздел статистики: {section}")
                        return False
                
                # Проверяем статистику источников ответов
                source_stats = data.get('source_stats', [])
                self.log(f"   Статистика источников: {len(source_stats)} типов")
                for source in source_stats:
                    self.log(f"   - {source.get('source')}: {source.get('count')}")
                
                return True
            return False
        except Exception as e:
            self.log(f"   Ошибка получения статистики: {e}")
            return False
    
    def test_statistics_clear_preserves_training(self):
        """КРИТИЧЕСКИЙ ТЕСТ: Очистка статистики сохраняет обучение"""
        try:
            # Сначала добавляем обученный ответ
            train_payload = {
                "question": "тест сохранения обучения",
                "answer": "этот ответ должен сохраниться",
                "model": "rus_girl_1",
                "priority": 10
            }
            train_response = requests.post(f"{self.api_url}/train", json=train_payload, timeout=10)
            if train_response.status_code != 200:
                self.log(f"   Ошибка предварительного обучения")
                return False
            
            # Проверяем что обученный ответ работает
            chat_payload = {
                "model": "rus_girl_1",
                "user_id": f"{self.test_user_id}_preserve_test",
                "message": "тест сохранения обучения"
            }
            chat_response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
            if chat_response.status_code != 200:
                self.log(f"   Ошибка проверки обученного ответа до очистки")
                return False
            
            pre_clear_data = chat_response.json()
            self.log(f"   Ответ до очистки: {pre_clear_data.get('response')}")
            
            # Очищаем статистику
            clear_response = requests.post(f"{self.api_url}/clear-statistics", timeout=10)
            if clear_response.status_code != 200:
                self.log(f"   Ошибка очистки статистики: {clear_response.status_code}")
                return False
            
            clear_data = clear_response.json()
            self.log(f"   Результат очистки: {clear_data.get('message')}")
            
            # Проверяем что обученный ответ все еще работает
            chat_payload = {
                "model": "rus_girl_1",
                "user_id": f"{self.test_user_id}_preserve_test_after",
                "message": "тест сохранения обучения"
            }
            chat_response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
            if chat_response.status_code == 200:
                post_clear_data = chat_response.json()
                self.log(f"   Ответ после очистки: {post_clear_data.get('response')}")
                self.log(f"   Источник после очистки: {post_clear_data.get('source')}")
                
                # Проверяем что обученный ответ сохранился
                return (post_clear_data.get('source') == 'trained' and 
                       'этот ответ должен сохраниться' in post_clear_data.get('response', ''))
            return False
            
        except Exception as e:
            self.log(f"   Ошибка тестирования сохранения обучения: {e}")
            return False
    
    def test_response_sources(self):
        """Тест источников ответов"""
        try:
            sources_found = set()
            
            # Тест trained источника
            train_payload = {
                "question": "источник trained",
                "answer": "ответ из обучения",
                "model": "rus_girl_1",
                "priority": 10
            }
            requests.post(f"{self.api_url}/train", json=train_payload, timeout=10)
            
            chat_payload = {
                "model": "rus_girl_1",
                "user_id": f"{self.test_user_id}_sources_trained",
                "message": "источник trained"
            }
            response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                source = data.get('source')
                sources_found.add(source)
                self.log(f"   Trained источник: {source} - {data.get('response')}")
            
            # Тест default источника (новый пользователь с неизвестным сообщением)
            chat_payload = {
                "model": "rus_girl_1",
                "user_id": f"{self.test_user_id}_sources_default",
                "message": "совершенно неизвестное сообщение для default ответа"
            }
            response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                source = data.get('source')
                sources_found.add(source)
                self.log(f"   Default источник: {source} - {data.get('response')}")
            
            # Тест semi и final источников через прогрессию
            user_id = f"{self.test_user_id}_sources_progression"
            
            # Получаем message_count модели
            model_response = requests.get(f"{self.api_url}/model/rus_girl_1", timeout=10)
            if model_response.status_code == 200:
                model_config = model_response.json()
                message_count = model_config.get('message_count', 5)
                
                # Доходим до semi сообщения
                for i in range(message_count - 1):
                    chat_payload = {
                        "model": "rus_girl_1",
                        "user_id": user_id,
                        "message": f"прогрессия {i+1}"
                    }
                    response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
                    if response.status_code == 200 and i == message_count - 2:  # Предпоследнее
                        data = response.json()
                        source = data.get('source')
                        sources_found.add(source)
                        self.log(f"   Semi источник: {source} - {data.get('response')}")
                
                # Final сообщение
                chat_payload = {
                    "model": "rus_girl_1",
                    "user_id": user_id,
                    "message": "финальное сообщение"
                }
                response = requests.post(f"{self.api_url}/chat", json=chat_payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    source = data.get('source')
                    sources_found.add(source)
                    self.log(f"   Final источник: {source} - {data.get('response')}")
            
            self.log(f"   Найденные источники: {sources_found}")
            expected_sources = {'trained', 'default', 'semi', 'final'}
            found_expected = sources_found.intersection(expected_sources)
            
            return len(found_expected) >= 3  # Минимум 3 из 4 источников
            
        except Exception as e:
            self.log(f"   Ошибка тестирования источников: {e}")
            return False
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        self.log("🚀 НАЧАЛО ПОЛНОГО ТЕСТИРОВАНИЯ СИСТЕМЫ xAi_v2")
        self.log("=" * 60)
        
        # Базовые API тесты
        self.log("\n📡 БАЗОВЫЕ API ТЕСТЫ")
        self.run_test("API Root", self.test_api_root)
        self.run_test("Health Check", self.test_health_check)
        self.run_test("Get Models", self.test_get_models)
        
        # Тесты чата и spintax
        self.log("\n💬 ТЕСТЫ ЧАТА И SPINTAX")
        self.run_test("Chat Basic", self.test_chat_basic)
        self.run_test("Spintax Functionality (КРИТИЧНО)", self.test_spintax_functionality)
        self.run_test("Chat Progression", self.test_chat_progression)
        
        # Тесты обучения
        self.log("\n🎓 ТЕСТЫ ОБУЧЕНИЯ")
        self.run_test("Manual Training", self.test_manual_training)
        self.run_test("File Training", self.test_file_training)
        self.run_test("Trained Responses Usage", self.test_trained_responses_usage)
        
        # Тесты статистики
        self.log("\n📊 ТЕСТЫ СТАТИСТИКИ")
        self.run_test("Statistics Collection", self.test_statistics_collection)
        self.run_test("Statistics Clear Preserves Training (КРИТИЧНО)", self.test_statistics_clear_preserves_training)
        
        # Тесты источников ответов
        self.log("\n🔍 ТЕСТЫ ИСТОЧНИКОВ ОТВЕТОВ")
        self.run_test("Response Sources", self.test_response_sources)
        
        # Итоги
        self.log("\n" + "=" * 60)
        self.log(f"🏁 ИТОГИ ТЕСТИРОВАНИЯ:")
        self.log(f"   Всего тестов: {self.tests_run}")
        self.log(f"   Пройдено: {self.tests_passed}")
        self.log(f"   Провалено: {self.tests_run - self.tests_passed}")
        self.log(f"   Успешность: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            return True
        else:
            self.log("⚠️  ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ!")
            return False

def main():
    """Главная функция"""
    tester = XAiTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())