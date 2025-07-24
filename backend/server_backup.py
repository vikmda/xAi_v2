from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import json
import uuid
import requests
import logging
from pathlib import Path
import aiofiles
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

# MongoDB подключение
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "ai_sexter_bot")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# FastAPI приложение
app = FastAPI(title="AI Sexter Bot API", version="2.0.0")
api_router = APIRouter(prefix="/api")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class ChatRequest(BaseModel):
    model: str = Field(..., description="Название модели персонажа")
    user_id: str = Field(..., description="ID пользователя")
    message: str = Field(..., description="Сообщение пользователя")

class ChatResponse(BaseModel):
    response: str
    message_number: int
    is_semi: bool
    is_last: bool
    emotion: Optional[str] = None
    model_used: str

class RatingRequest(BaseModel):
    user_id: str
    message: str
    response: str
    rating: int = Field(..., ge=1, le=10)
    model: str

class TrainingRequest(BaseModel):
    question: str
    answer: str
    model: str
    priority: int = Field(default=1, ge=1, le=10)

class ModelConfig(BaseModel):
    name: str
    age: int
    country: str
    city: str
    language: str
    interests: List[str]
    mood: str
    message_count: int
    semi_message: str
    final_message: str
    learning_enabled: bool
    response_length: int
    use_emoji: bool
    personality_traits: List[str] = []

class TestRequest(BaseModel):
    message: str
    model: str

# Глобальные переменные
MODELS_DIR = Path(__file__).parent / "models"
loaded_models = {}
conversation_states = {}

# Создание директории для моделей
MODELS_DIR.mkdir(exist_ok=True)

# Утилиты для работы с моделями
async def load_model(model_name: str) -> ModelConfig:
    """Загрузка модели из JSON файла"""
    if model_name in loaded_models:
        return loaded_models[model_name]
    
    model_path = MODELS_DIR / f"{model_name}.json"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Модель {model_name} не найдена")
    
    async with aiofiles.open(model_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        model_data = json.loads(content)
        model_config = ModelConfig(**model_data)
        loaded_models[model_name] = model_config
        return model_config

async def save_model(model_name: str, config: ModelConfig):
    """Сохранение модели в JSON файл"""
    model_path = MODELS_DIR / f"{model_name}.json"
    async with aiofiles.open(model_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(config.dict(), ensure_ascii=False, indent=2))
    loaded_models[model_name] = config

def get_conversation_state(user_id: str, model: str):
    """Получение состояния диалога"""
    key = f"{user_id}_{model}"
    if key not in conversation_states:
        conversation_states[key] = {
            "message_count": 0,
            "messages": [],
            "last_activity": datetime.utcnow()
        }
    return conversation_states[key]

def detect_emotion(message: str) -> str:
    """Простое определение эмоции"""
    message_lower = message.lower()
    if any(word in message_lower for word in ["красив", "сексуальн", "привлекат"]):
        return "flirty"
    elif any(word in message_lower for word in ["люблю", "обожаю", "дорог"]):
        return "romantic"
    elif any(word in message_lower for word in ["хочу", "желаю", "страсть"]):
        return "seductive"
    elif any(word in message_lower for word in ["играть", "шалить", "веселье"]):
        return "playful"
    else:
        return "neutral"

async def adapt_model_to_platform(model_config: ModelConfig, platform_settings: dict) -> ModelConfig:
    """Автоматическая адаптация модели под настройки платформы"""
    if not platform_settings.get("auto_adapt", False):
        return model_config
    
    # Адаптируем возраст
    age_range = platform_settings.get("age_range", {"min": 18, "max": 35})
    model_config.age = min(max(model_config.age, age_range["min"]), age_range["max"])
    
    # Адаптируем страну и язык
    if platform_settings.get("default_country"):
        model_config.country = platform_settings["default_country"]
    if platform_settings.get("default_language"):
        model_config.language = platform_settings["default_language"]
    
    # Адаптируем количество сообщений
    msg_limits = platform_settings.get("message_limits", {"min": 3, "max": 8})
    model_config.message_count = min(max(model_config.message_count, msg_limits["min"]), msg_limits["max"])
    
    # Адаптируем стиль общения
    response_style = platform_settings.get("response_style", "flirty")
    if response_style not in model_config.personality_traits:
        model_config.personality_traits.append(response_style)
    
    # Адаптируем использование эмодзи
    model_config.use_emoji = platform_settings.get("emoji_usage", True)
    
    return model_config

async def get_ollama_response(message: str, character_name: str, personality: str) -> Optional[str]:
    """Получение ответа от локального Ollama ИИ"""
    try:
        prompt = f"Ты {character_name}. Твой характер: {personality}. Отвечай кратко (2-4 слова) и в характере. Вопрос: {message}"
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": prompt,
                "stream": False
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        logger.warning(f"Ollama недоступен: {e}")
    
    return None

async def generate_ai_response(message: str, model_config: ModelConfig, conversation_state: dict, model_name: str) -> str:
    """Генерация ответа от ИИ"""
    logger.info(f"Generating response for message: '{message}', model: '{model_name}' (display: '{model_config.name}')")
    
    # Проверяем, достиг ли диалог предпоследнего сообщения
    if conversation_state["message_count"] == model_config.message_count - 1:
        logger.info("Returning semi_message")
        return model_config.semi_message
    
    # Проверяем, достиг ли диалог последнего сообщения
    if conversation_state["message_count"] >= model_config.message_count:
        logger.info("Returning final_message")
        return model_config.final_message
    
    # Проверяем обученные ответы - используем model_name вместо model_config.name
    logger.info(f"Searching for trained response with model name: '{model_name}'")
    trained_response = await get_trained_response(message, model_name)
    if trained_response:
        logger.info(f"Found trained response: '{trained_response}'")
        return trained_response
    else:
        logger.warning(f"No trained response found, trying Ollama...")
    
    # Пробуем получить ответ от локального ИИ Ollama
    personality = ", ".join(model_config.personality_traits)
    ollama_response = await get_ollama_response(message, model_config.name, personality)
    if ollama_response:
        logger.info(f"Got Ollama response: '{ollama_response}'")
        return ollama_response
    else:
        logger.warning(f"Ollama unavailable, using default logic")
    
    # Базовая логика генерации ответа
    responses = {
        "ru": {
            "greetings": ["Привет красавчик! 😘", "Приветик! Как дела?", "Хай! Что делаешь?"],
            "compliments": ["Спасибо милый 😊", "Ты такой галантный!", "Мне приятно это слышать"],
            "questions": ["А ты что любишь делать?", "Расскажи о себе!", "Как тебя зовут?"],
            "flirty": ["Ммм, интересно... 😏", "Ты меня заинтриговал", "Хочешь узнать больше?"],
            "default": ["Интересно!", "Правда?", "Да, понимаю тебя"]
        },
        "en": {
            "greetings": ["Hey handsome! 😘", "Hi there! How are you?", "Hello! What's up?"],
            "compliments": ["Thank you sweetie 😊", "You're so sweet!", "I love hearing that"],
            "questions": ["What do you like to do?", "Tell me about yourself!", "What's your name?"],
            "flirty": ["Mmm, interesting... 😏", "You intrigue me", "Want to know more?"],
            "default": ["Interesting!", "Really?", "I understand you"]
        }
    }
    
    # Определяем тип сообщения и генерируем ответ
    message_lower = message.lower()
    lang_responses = responses.get(model_config.language, responses["ru"])
    
    if any(word in message_lower for word in ["привет", "hi", "hello", "hey"]):
        import random
        response = random.choice(lang_responses["greetings"])
        logger.info(f"Generated greeting response: '{response}'")
    elif any(word in message_lower for word in ["красив", "beautiful", "gorgeous"]):
        import random
        response = random.choice(lang_responses["compliments"])
        logger.info(f"Generated compliment response: '{response}'")
    elif any(word in message_lower for word in ["хочу", "want", "desire"]):
        import random
        response = random.choice(lang_responses["flirty"])
        logger.info(f"Generated flirty response: '{response}'")
    else:
        import random
        response = random.choice(lang_responses["default"])
        logger.info(f"Generated default response: '{response}'")
    
    # Добавляем эмодзи если включено
    if model_config.use_emoji and "😘" not in response and "😊" not in response and "😏" not in response:
        emojis = ["😘", "😊", "😉", "💕", "🔥", "😍"]
        import random
        response += f" {random.choice(emojis)}"
    
    return response

async def get_trained_response(message: str, model: str) -> Optional[str]:
    """Получение обученного ответа из базы данных с приоритизацией"""
    message_lower = message.lower().strip()
    
    # 1. Точное совпадение (сортировка по приоритету - высший приоритет первым)
    exact_match = await db.trained_responses.find_one({
        "question": message_lower,
        "model": model
    }, sort=[("priority", -1)])
    if exact_match:
        logger.info(f"Found exact match for '{message}' with priority {exact_match.get('priority', 1)}")
        return exact_match["answer"]
    
    # 2. Поиск по ключевым словам (с приоритизацией)
    words = message_lower.split()
    for word in words:
        if len(word) > 3:  # Только значимые слова
            responses = await db.trained_responses.find({
                "question": {"$regex": word, "$options": "i"},
                "model": model
            }).sort([("priority", -1)]).limit(5).to_list(length=None)
            
            if responses:
                # Возвращаем ответ с наивысшим приоритетом
                best_response = responses[0]
                logger.info(f"Found keyword match for '{message}' using word '{word}' with priority {best_response.get('priority', 1)}")
                return best_response["answer"]
    
    # 3. Поиск с частичным совпадением (с приоритизацией) 
    partial_matches = await db.trained_responses.find({
        "question": {"$regex": message_lower, "$options": "i"},
        "model": model
    }).sort([("priority", -1)]).limit(3).to_list(length=None)
    
    if partial_matches:
        best_match = partial_matches[0]
        logger.info(f"Found partial match for '{message}' with priority {best_match.get('priority', 1)}")
        return best_match["answer"]
    
    logger.info(f"No trained response found for '{message}'")
    return None

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "AI Sexter Bot API v2.0"}

@api_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной эндпоинт для чата"""
    try:
        # Загружаем модель
        model_config = await load_model(request.model)
        
        # Получаем настройки платформы и адаптируем модель
        platform_settings = await get_platform_settings()
        model_config = await adapt_model_to_platform(model_config, platform_settings)
        
        # Получаем состояние диалога
        conversation_state = get_conversation_state(request.user_id, request.model)
        conversation_state["message_count"] += 1
        conversation_state["last_activity"] = datetime.utcnow()
        conversation_state["messages"].append({
            "user_message": request.message,
            "timestamp": datetime.utcnow()
        })
        
        # Генерируем ответ
        ai_response = await generate_ai_response(request.message, model_config, conversation_state, request.model)
        
        # Определяем статус сообщения
        is_semi = conversation_state["message_count"] == model_config.message_count - 1
        is_last = conversation_state["message_count"] >= model_config.message_count
        
        # Сохраняем в базу данных
        await db.conversations.insert_one({
            "user_id": request.user_id,
            "model": request.model,
            "user_message": request.message,
            "ai_response": ai_response,
            "message_number": conversation_state["message_count"],
            "is_semi": is_semi,
            "is_last": is_last,
            "emotion": detect_emotion(request.message),
            "platform_adapted": True,
            "timestamp": datetime.utcnow()
        })
        
        return ChatResponse(
            response=ai_response,
            message_number=conversation_state["message_count"],
            is_semi=is_semi,
            is_last=is_last,
            emotion=detect_emotion(request.message),
            model_used=request.model
        )
        
    except Exception as e:
        logger.error(f"Ошибка в chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/test")
async def test_chat(request: TestRequest):
    """Тестирование модели"""
    try:
        model_config = await load_model(request.model)
        
        # Создаем временное состояние для тестирования
        temp_state = {"message_count": 1, "messages": []}
        
        response = await generate_ai_response(request.message, model_config, temp_state, request.model)
        
        return {
            "response": response,
            "model": request.model,
            "emotion": detect_emotion(request.message)
        }
        
    except Exception as e:
        logger.error(f"Ошибка в test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/rate")
async def rate_response(request: RatingRequest):
    """Оценка ответа с автоматическим обучением при высоких оценках"""
    try:
        # Сохраняем рейтинг
        await db.ratings.insert_one({
            "user_id": request.user_id,
            "model": request.model,
            "message": request.message,
            "response": request.response,
            "rating": request.rating,
            "timestamp": datetime.utcnow()
        })
        
        # Обновляем статистику
        await db.statistics.update_one(
            {"type": "ratings", "model": request.model},
            {
                "$inc": {"total_ratings": 1, "total_score": request.rating},
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        # Автоматически добавляем в обучающие данные при высоком рейтинге (8, 9, 10)
        if request.rating >= 8:
            await db.trained_responses.update_one(
                {"question": request.message.lower().strip(), "model": request.model},
                {
                    "$set": {
                        "answer": request.response,
                        "priority": request.rating,  # Используем рейтинг как приоритет
                        "auto_trained": True,  # Помечаем как автоматически обученный
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            logger.info(f"Auto-trained response for '{request.message}' with rating {request.rating}")
        
        return {"message": "Рейтинг сохранен" + (" и ответ добавлен в обучение" if request.rating >= 8 else "")}
        
    except Exception as e:
        logger.error(f"Ошибка в rate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/train")
async def train_model(request: TrainingRequest):
    """Ручное обучение модели"""
    try:
        # Сохраняем обучающие данные
        await db.trained_responses.update_one(
            {"question": request.question.lower().strip(), "model": request.model},
            {
                "$set": {
                    "answer": request.answer,
                    "priority": request.priority,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {"message": "Обучающие данные сохранены"}
        
    except Exception as e:
        logger.error(f"Ошибка в train: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/models")
async def get_models():
    """Получение списка доступных моделей"""
    try:
        models = []
        for model_file in MODELS_DIR.glob("*.json"):
            model_name = model_file.stem
            try:
                model_config = await load_model(model_name)
                models.append({
                    "name": model_name,
                    "display_name": model_config.name,
                    "language": model_config.language,
                    "country": model_config.country
                })
            except Exception as e:
                logger.warning(f"Ошибка загрузки модели {model_name}: {e}")
        
        return {"models": models}
        
    except Exception as e:
        logger.error(f"Ошибка в get_models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/model/{model_name}")
async def get_model(model_name: str):
    """Получение конфигурации модели"""
    try:
        model_config = await load_model(model_name)
        return model_config.dict()
        
    except Exception as e:
        logger.error(f"Ошибка в get_model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/model/{model_name}")
async def save_model_config(model_name: str, config: ModelConfig):
    """Сохранение конфигурации модели"""
    try:
        await save_model(model_name, config)
        return {"message": f"Модель {model_name} сохранена"}
        
    except Exception as e:
        logger.error(f"Ошибка в save_model_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/statistics")
async def get_statistics():
    """Получение статистики системы"""
    try:
        # Общая статистика
        total_conversations = await db.conversations.count_documents({})
        total_users = len(await db.conversations.distinct("user_id"))
        
        # Статистика по моделям
        models_stats = await db.conversations.aggregate([
            {"$group": {
                "_id": "$model",
                "conversations": {"$sum": 1},
                "avg_rating": {"$avg": "$rating"}
            }}
        ]).to_list(length=None)
        
        # Топ ответов
        top_responses = await db.conversations.aggregate([
            {"$group": {
                "_id": "$ai_response",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        # Популярные вопросы
        top_questions = await db.conversations.aggregate([
            {"$group": {
                "_id": "$user_message",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        # Статистика рейтингов
        ratings_stats = await db.ratings.aggregate([
            {"$group": {
                "_id": "$model",
                "avg_rating": {"$avg": "$rating"},
                "total_ratings": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
        # Проблемные вопросы (низкие рейтинги)
        problem_questions = await db.ratings.find(
            {"rating": {"$lte": 3}},
            {"message": 1, "response": 1, "rating": 1, "model": 1}
        ).limit(10).to_list(length=None)
        
        return {
            "total_conversations": total_conversations,
            "total_users": total_users,
            "models_stats": models_stats,
            "top_responses": top_responses,
            "top_questions": top_questions,
            "ratings_stats": ratings_stats,
            "problem_questions": problem_questions,
            "system_status": {
                "database_connected": True,
                "models_loaded": len(loaded_models),
                "active_conversations": len(conversation_states)
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка в statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/settings")
async def save_settings(settings: dict):
    """Сохранение пользовательских настроек"""
    try:
        # Сохраняем настройки в базу данных
        await db.user_settings.update_one(
            {"type": "global_settings"},
            {
                "$set": {
                    **settings,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {"message": "Настройки сохранены", "status": "success"}
        
    except Exception as e:
        logger.error(f"Ошибка в save_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/platform-settings")
async def save_platform_settings(settings: dict):
    """Сохранение настроек платформы"""
    try:
        await db.platform_settings.update_one(
            {"type": "platform_config"},
            {
                "$set": {
                    **settings,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {"message": "Настройки платформы сохранены", "status": "success"}
    except Exception as e:
        logger.error(f"Ошибка в save_platform_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/platform-settings")
async def get_platform_settings():
    """Получение настроек платформы"""
    try:
        settings = await db.platform_settings.find_one({"type": "platform_config"})
        if settings:
            settings.pop("_id", None)
            settings.pop("type", None)
            return settings
        else:
            return {
                "default_country": "Россия",
                "default_language": "ru",
                "age_range": {"min": 18, "max": 35},
                "response_style": "flirty",
                "platform_type": "dating",
                "auto_adapt": True,
                "message_limits": {"min": 3, "max": 8},
                "emoji_usage": True,
                "nsfw_level": "medium"
            }
    except Exception as e:
        logger.error(f"Ошибка в get_platform_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings")
async def get_settings():
    """Получение пользовательских настроек"""
    try:
        settings = await db.user_settings.find_one({"type": "global_settings"})
        if settings:
            # Удаляем служебные поля
            settings.pop("_id", None)
            settings.pop("type", None)
            return settings
        else:
            return {"default_model": "", "auto_save": True}
    except Exception as e:
        logger.error(f"Ошибка в get_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@api_router.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    try:
        # Проверка подключения к базе данных
        await db.command("ping")
        db_status = True
    except:
        db_status = False
    
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": db_status,
        "models_loaded": len(loaded_models),
        "active_conversations": len(conversation_states),
        "timestamp": datetime.utcnow()
    }

# Подключение роутера
app.include_router(api_router)

# Создание дефолтных моделей при запуске
@app.on_event("startup")
async def create_default_models():
    """Создание дефолтных моделей при запуске"""
    default_models = [
        {
            "name": "rus_girl_1",
            "config": ModelConfig(
                name="Анна",
                age=23,
                country="Россия",
                city="Москва",
                language="ru",
                interests=["фотография", "путешествия", "музыка"],
                mood="игривое",
                message_count=5,
                semi_message="Хочешь увидеть мои фото? 📸",
                final_message="Переходи в мой телеграм @anna_model для большего 😘",
                learning_enabled=True,
                response_length=15,
                use_emoji=True,
                personality_traits=["flirty", "playful", "sweet"]
            )
        },
        {
            "name": "eng_girl_1",
            "config": ModelConfig(
                name="Emma",
                age=25,
                country="USA",
                city="New York",
                language="en",
                interests=["fitness", "travel", "photography"],
                mood="confident",
                message_count=5,
                semi_message="Want to see more of me? 💕",
                final_message="Check out my telegram @emma_model for exclusive content 😘",
                learning_enabled=True,
                response_length=12,
                use_emoji=True,
                personality_traits=["confident", "flirty", "adventurous"]
            )
        }
    ]
    
    for model_data in default_models:
        model_path = MODELS_DIR / f"{model_data['name']}.json"
        if not model_path.exists():
            await save_model(model_data['name'], model_data['config'])
            logger.info(f"Создана дефолтная модель: {model_data['name']}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)