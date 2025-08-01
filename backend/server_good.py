from fastapi import FastAPI, HTTPException, APIRouter, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import datetime as dt
import os
import json
import requests
import logging
from pathlib import Path
import aiofiles
import asyncio
import re
import random

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
    triggers: List[str] = []  # Триггерные слова для мгновенного финального сообщения

class TestRequest(BaseModel):
    message: str
    model: str

class StatsClearRequest(BaseModel):
    model: str

# Глобальные переменные
MODELS_DIR = Path(__file__).parent / "models"
loaded_models = {}
conversation_states = {}

# Создание директории для моделей
MODELS_DIR.mkdir(exist_ok=True)
logger.info(f"MODELS_DIR set to: {MODELS_DIR}")

# Утилиты для работы с моделями
async def load_model(model_name: str) -> ModelConfig:
    """Загрузка модели из JSON файла"""
    logger.debug(f"Loading model: {model_name}")
    if model_name in loaded_models:
        logger.debug(f"Model {model_name} already loaded from cache")
        return loaded_models[model_name]
    
    model_path = MODELS_DIR / f"{model_name}.json"
    logger.debug(f"Checking model file at: {model_path}")
    if not model_path.exists():
        logger.error(f"Model file {model_path} does not exist")
        raise HTTPException(status_code=404, detail=f"Модель {model_name} не найдена")
    
    async with aiofiles.open(model_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        model_data = json.loads(content)
        model_config = ModelConfig(**model_data)
        loaded_models[model_name] = model_config
        logger.info(f"Model {model_name} loaded successfully from JSON")
        return model_config

async def save_model(model_name: str, config: ModelConfig):
    """Сохранение модели в JSON файл"""
    logger.debug(f"Saving model: {model_name}")
    model_path = MODELS_DIR / f"{model_name}.json"
    async with aiofiles.open(model_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(config.model_dump(), ensure_ascii=False, indent=2))
    loaded_models[model_name] = config
    logger.info(f"Model {model_name} saved successfully")

def get_conversation_state(user_id: str, model: str):
    """Получение состояния диалога"""
    key = f"{user_id}_{model}"
    if key not in conversation_states:
        conversation_states[key] = {
            "message_count": 0,
            "messages": [],
            "last_activity": datetime.now(dt.UTC)
        }
    return conversation_states[key]

def detect_emotion(message: str) -> str:
    """Простое определение эмоции"""
    message_lower = message.lower()
    if any(word in message_lower for word in ["красив", "сексуальн", "привлекат", "beautiful", "gorgeous", "hot"]):
        return "flirty"
    elif any(word in message_lower for word in ["люблю", "обожаю", "дорог", "love", "adore"]):
        return "romantic"
    elif any(word in message_lower for word in ["хочу", "желаю", "страсть", "want", "desire", "horny"]):
        return "seductive"
    elif any(word in message_lower for word in ["играть", "шалить", "веселье", "play", "naughty"]):
        return "playful"
    else:
        return "neutral"

async def get_ollama_response(message: str, model_config: ModelConfig) -> Optional[str]:
    """Получение ответа от локального Ollama ИИ с строгим следованием языку модели"""
    try:
        personality = ", ".join(model_config.personality_traits)
        interests = ", ".join(model_config.interests)
        
        # СТРОГО следуем языку модели из JSON настроек
        if model_config.language == "ru":
            prompt = (
                f"Ты {model_config.name}, {model_config.age}-летняя девушка из города {model_config.city}, {model_config.country}. "
                f"Твои интересы: {interests}. Твоё настроение: {model_config.mood}. Характер: {personality}. "
                f"ВАЖНО: Отвечай ТОЛЬКО на русском языке, строго 2-4 слова, в флиртующем стиле. "
                f"ЗАПРЕЩЕНЫ любые английские слова, предупреждения и длинные ответы. "
                f"ОБЯЗАТЕЛЬНО используй русские символы и не используй латиницу. "
                f"{'Используй эмодзи в конце.' if model_config.use_emoji else 'Без эмодзи.'} "
                f"Сообщение: {message}"
            )
            forbidden_phrases = ["provide information", "не могу", "illegal", "harmful", "sorry", "cannot", "english"]
        else:  # English
            prompt = (
                f"You are {model_config.name}, a {model_config.age}-year-old girl from {model_config.city}, {model_config.country}. "
                f"Your interests: {interests}. Your mood: {model_config.mood}. Personality: {personality}. "
                f"IMPORTANT: Reply ONLY in English, strictly 2-4 words, in a flirty style. "
                f"FORBIDDEN: Russian words, warnings, or long responses. "
                f"MUST use only English characters and avoid Cyrillic. "
                f"{'Add an emoji at the end.' if model_config.use_emoji else 'No emojis.'} "
                f"Message: {message}"
            )
            forbidden_phrases = ["provide information", "I cannot", "illegal", "harmful", "sorry", "не могу", "russian"]
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "max_tokens": 15
                }
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("response", "").strip()
            logger.debug(f"Ollama response for {model_config.language}: {answer}")
            
            # Проверяем на запрещенные фразы
            if any(phrase in answer.lower() for phrase in forbidden_phrases):
                logger.warning(f"Нежелательный ответ от Ollama: {answer}")
                return None
                
            # Проверяем длину
            if len(answer.split()) > 4:
                logger.warning(f"Ответ слишком длинный: {answer}")
                return None
                
            # Строгая проверка языка
            if model_config.language == "ru":
                # Проверяем что есть русские символы и нет английских букв
                has_cyrillic = any(1040 <= ord(c) <= 1279 for c in answer)
                has_latin = any(c.isalpha() and ord(c) < 1024 for c in answer if c not in ' !?.,😊😉😍😘💕🔥')
                if not has_cyrillic or has_latin:
                    logger.warning(f"Ответ содержит неправильные символы для русского языка: {answer}")
                    return None
            else:  # English
                # Проверяем что нет русских символов
                if any(1040 <= ord(c) <= 1279 for c in answer):
                    logger.warning(f"Ответ содержит русские символы для английского языка: {answer}")
                    return None
                    
            return answer
    except Exception as e:
        logger.warning(f"Ollama недоступен: {e}")
    
    return None

def parse_spin_syntax(text: str) -> str:
    """Парсинг спинтакса вида {вариант1|вариант2|вариант3}"""
    logger.debug(f"Parsing spin syntax for text: {text}")
    spin_regex = r'{([^}]+)}'
    def replace_spin(match):
        options = [opt.strip() for opt in match.group(1).split('|')]
        return random.choice(options)
    parsed_text = re.sub(spin_regex, replace_spin, text)
    logger.debug(f"Parsed text: {parsed_text}")
    return parsed_text

async def generate_ai_response(message: str, model_config: ModelConfig, conversation_state: dict, model_name: str) -> str:
    """Генерация ответа от ИИ строго по настройкам модели"""
    logger.info(f"Generating response for message: '{message}', model: '{model_name}' (display: '{model_config.name}'), language: '{model_config.language}'")
    
    # Проверяем триггеры для мгновенного финального сообщения
    message_lower = message.lower().strip()
    for trigger in model_config.triggers:
        if trigger.lower().strip() in message_lower:
            logger.info(f"Trigger '{trigger}' detected! Returning final message immediately.")
            return parse_spin_syntax(model_config.final_message)
    
    # Проверяем, достиг ли диалог предпоследнего сообщения
    if conversation_state["message_count"] == model_config.message_count - 1:
        logger.info("Returning semi_message")
        return parse_spin_syntax(model_config.semi_message)
    
    # Проверяем, достиг ли диалог последнего сообщения
    if conversation_state["message_count"] >= model_config.message_count:
        logger.info("Returning final_message")
        return parse_spin_syntax(model_config.final_message)
    
    # Проверяем обученные ответы
    logger.info(f"Searching for trained response with model name: '{model_name}'")
    trained_response = await get_trained_response(message, model_name)
    if trained_response:
        logger.info(f"Found trained response: '{trained_response}'")
        # ИСПРАВЛЕНИЕ: Применяем parse_spin_syntax к обученному ответу
        parsed_response = parse_spin_syntax(trained_response)
        logger.info(f"Parsed trained response: '{parsed_response}'")
        return parsed_response
    else:
        logger.warning(f"No trained response found, trying Ollama...")
    
    # Пробуем получить ответ от Ollama
    ollama_response = await get_ollama_response(message, model_config)
    if ollama_response:
        logger.info(f"Got Ollama response: '{ollama_response}'")
        return parse_spin_syntax(ollama_response)
    else:
        logger.warning(f"Ollama unavailable, using default logic")
    
    # Базовая логика генерации ответа СТРОГО по языку модели
    if model_config.language == "ru":
        responses = {
            "greetings": ["Привет, красавчик! 😊", "Приветик! 😘", "Хай, как дела? 😉", "Привет милый! 💕", "Приветствую! 😍"],
            "age_questions": [f"{model_config.age}, а тебе? 😉", "Юная, а ты? 😘", "Возраст — секрет! 😍", f"Мне {model_config.age}! 💕", "Молодая! 😊"],
            "location_questions": [f"Из {model_config.city}! 😍", f"{model_config.city}, ты где? 😉", f"{model_config.country}! 💕", f"Живу в {model_config.city}! 😊"],
            "flirty": ["Ого, смело! 😏", "Интересно, продолжай! 😉", "Ты интригуешь! 😍", "Жарко говоришь! 🔥", "Смелый какой! 😘"],
            "default": ["Круто! 😊", "Серьёзно? 😉", "Расскажи ещё! 😍", "Интересно! 💕", "Ого! 😘", "Здорово! 🔥"]
        }
    else:  # English
        responses = {
            "greetings": ["Hey handsome! 😊", "Hi there! 😘", "Yo, what's up? 😉", "Hello cutie! 💕", "Hi gorgeous! 😍"],
            "age_questions": [f"{model_config.age}, you? 😉", "Young, you? 😘", "Age's a secret! 😍", f"I'm {model_config.age}! 💕", "Young! 😊"],
            "location_questions": [f"From {model_config.city}! 😍", f"{model_config.city}, you? 😉", f"{model_config.country}! 💕", f"Live in {model_config.city}! 😊"],
            "flirty": ["Oh, naughty! 😏", "Keep talking! 😉", "You're intriguing! 😍", "Hot talk! 🔥", "Bold boy! 😘"],
            "default": ["Cool! 😊", "Really? 😉", "Tell me more! 😍", "Interesting! 💕", "Wow! 😘", "Great! 🔥"]
        }
    
    # Выбираем ответы для текущего языка модели
    lang_responses = responses
    
    if any(word in message_lower for word in ["привет", "hi", "hey", "hello", "хай"]):
        response = random.choice(lang_responses["greetings"])
        logger.info(f"Generated greeting response: '{response}'")
    elif any(word in message_lower for word in ["ск лет", "age", "сколько лет", "how old", "возраст"]):
        response = random.choice(lang_responses["age_questions"])
        logger.info(f"Generated age response: '{response}'")
    elif any(word in message_lower for word in ["откуда", "from", "город", "where", "city"]):
        response = random.choice(lang_responses["location_questions"])
        logger.info(f"Generated location response: '{response}'")
    elif any(word in message_lower for word in ["шалить", "horny", "хочу", "want", "m or f", "naughty", "секс"]):
        response = random.choice(lang_responses["flirty"])
        logger.info(f"Generated flirty response: '{response}'")
    else:
        response = random.choice(lang_responses["default"])
        logger.info(f"Generated default response: '{response}'")
    
    # Добавляем эмодзи если нужно
    if model_config.use_emoji and not any(emoji in response for emoji in ["😘", "😊", "😉", "💕", "🔥", "😍"]):
        emojis = ["😘", "😊", "😉", "💕", "🔥", "😍"]
        response += f" {random.choice(emojis)}"
    
    return parse_spin_syntax(response)

async def get_trained_response(message: str, model: str) -> Optional[str]:
    """Получение обученного ответа из базы данных с приоритизацией"""
    message_lower = message.lower().strip()
    logger.debug(f"Checking trained response for message: '{message}', model: '{model}'")
    
    exact_match = await db.trained_responses.find_one({
        "question": message_lower,
        "model": model
    }, sort=[("priority", -1)])
    if exact_match:
        logger.info(f"Found exact match for '{message}' with priority {exact_match.get('priority', 1)}")
        return exact_match["answer"]
    
    words = message_lower.split()
    for word in words:
        if len(word) > 3:
            responses = await db.trained_responses.find({
                "question": {"$regex": word, "$options": "i"},
                "model": model
            }).sort([("priority", -1)]).limit(5).to_list(length=None)
            
            if responses:
                best_response = responses[0]
                logger.info(f"Found keyword match for '{message}' using word '{word}' with priority {best_response.get('priority', 1)}")
                return best_response["answer"]
    
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
    logger.debug("Received request to /api/")
    return {"message": "AI Sexter Bot API v2.0"}

@api_router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной эндпоинт для чата"""
    logger.debug(f"Received chat request: {request.model_dump()}")
    try:
        # Загружаем модель СТРОГО из JSON файла
        model_config = await load_model(request.model)
        
        conversation_state = get_conversation_state(request.user_id, request.model)
        conversation_state["message_count"] += 1
        conversation_state["last_activity"] = datetime.now(dt.UTC)
        conversation_state["messages"].append({
            "user_message": request.message,
            "timestamp": datetime.now(dt.UTC)
        })
        
        ai_response = await generate_ai_response(request.message, model_config, conversation_state, request.model)
        
        # Логируем активность
        await db.bot_activities.insert_one({
            "model": request.model,
            "action": "chat_response",
            "user_message": request.message,
            "ai_response": ai_response,
            "timestamp": datetime.now(dt.UTC)
        })
        
        # Check if trigger was detected (response equals final_message)
        trigger_detected = ai_response == parse_spin_syntax(model_config.final_message)
        
        is_semi = conversation_state["message_count"] == model_config.message_count - 1 and not trigger_detected
        is_last = conversation_state["message_count"] >= model_config.message_count or trigger_detected
        
        await db.conversations.insert_one({
            "user_id": request.user_id,
            "model": request.model,
            "user_message": request.message,
            "ai_response": ai_response,
            "message_number": conversation_state["message_count"],
            "is_semi": is_semi,
            "is_last": is_last,
            "emotion": detect_emotion(request.message),
            "timestamp": datetime.now(dt.UTC)
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
    logger.debug(f"Received test request: {request.model_dump()}")
    try:
        model_config = await load_model(request.model)
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
    logger.debug(f"Received rate request: {request.model_dump()}")
    try:
        await db.ratings.insert_one({
            "user_id": request.user_id,
            "model": request.model,
            "message": request.message,
            "response": request.response,
            "rating": request.rating,
            "timestamp": datetime.now(dt.UTC)
        })
        
        await db.statistics.update_one(
            {"type": "ratings", "model": request.model},
            {
                "$inc": {"total_ratings": 1, "total_score": request.rating},
                "$set": {"updated_at": datetime.now(dt.UTC)}
            },
            upsert=True
        )
        
        if request.rating >= 8:
            await db.trained_responses.update_one(
                {"question": request.message.lower().strip(), "model": request.model},
                {
                    "$set": {
                        "answer": request.response,
                        "priority": request.rating,
                        "auto_trained": True,
                        "updated_at": datetime.now(dt.UTC)
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
    logger.debug(f"Received train request: {request.model_dump()}")
    try:
        await db.trained_responses.update_one(
            {"question": request.question.lower().strip(), "model": request.model},
            {
                "$set": {
                    "answer": request.answer,
                    "priority": request.priority,
                    "updated_at": datetime.now(dt.UTC)
                }
            },
            upsert=True
        )
        
        return {"message": "Обучающие данные сохранены"}
        
    except Exception as e:
        logger.error(f"Ошибка в train: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/train-file")
async def train_from_file(model: str, file: UploadFile = File(...)):
    """Загрузка файла обучения"""
    try:
        content = await file.read()
        content = content.decode('utf-8')
        
        lines = content.split('\n')
        processed = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Поддержка разных форматов разделителей
            separators = [' - ', ' | ', '\t']
            question, answer = None, None
            
            for sep in separators:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        question = parts[0].strip()
                        answer = parts[1].strip()
                        break
            
            if question and answer:
                await db.trained_responses.update_one(
                    {"question": question.lower(), "model": model},
                    {
                        "$set": {
                            "answer": answer,
                            "priority": 5,
                            "file_trained": True,
                            "updated_at": datetime.now(dt.UTC)
                        }
                    },
                    upsert=True
                )
                processed += 1
        
        return {"message": f"Обработано {processed} записей из файла"}
        
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/models")
async def get_models():
    """Получение списка доступных моделей"""
    logger.debug("Received request to /api/models")
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
    logger.debug(f"Received request to /api/model/{model_name}")
    try:
        model_config = await load_model(model_name)
        return model_config.model_dump()
        
    except Exception as e:
        logger.error(f"Ошибка в get_model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/model/{model_name}")
async def save_model_config(model_name: str, config: ModelConfig):
    """Сохранение конфигурации модели"""
    logger.debug(f"Received request to save model: {model_name}")
    try:
        await save_model(model_name, config)
        return {"message": f"Модель {model_name} сохранена"}
        
    except Exception as e:
        logger.error(f"Ошибка в save_model_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/statistics")
async def get_statistics():
    """Получение общей статистики системы"""
    logger.debug("Received request to /api/statistics")
    try:
        total_conversations = await db.conversations.count_documents({})
        total_users = len(await db.conversations.distinct("user_id"))
        
        models_stats = await db.conversations.aggregate([
            {"$group": {
                "_id": "$model",
                "conversations": {"$sum": 1},
                "avg_rating": {"$avg": "$rating"}
            }}
        ]).to_list(length=None)
        
        top_responses = await db.conversations.aggregate([
            {"$group": {
                "_id": "$ai_response",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        top_questions = await db.conversations.aggregate([
            {"$group": {
                "_id": "$user_message",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        ratings_stats = await db.ratings.aggregate([
            {"$group": {
                "_id": "$model",
                "avg_rating": {"$avg": "$rating"},
                "total_ratings": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
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

@api_router.get("/statistics/{model_name}")
async def get_model_statistics(model_name: str):
    """Получение статистики конкретной модели"""
    logger.debug(f"Received request to /api/statistics/{model_name}")
    try:
        total_conversations = await db.conversations.count_documents({"model": model_name})
        total_users = len(await db.conversations.distinct("user_id", {"model": model_name}))
        
        top_responses = await db.conversations.aggregate([
            {"$match": {"model": model_name}},
            {"$group": {
                "_id": "$ai_response",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        top_questions = await db.conversations.aggregate([
            {"$match": {"model": model_name}},
            {"$group": {
                "_id": "$user_message",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(length=None)
        
        avg_rating = await db.ratings.aggregate([
            {"$match": {"model": model_name}},
            {"$group": {
                "_id": None,
                "avg_rating": {"$avg": "$rating"},
                "total_ratings": {"$sum": 1}
            }}
        ]).to_list(length=None)
        
        rating_info = avg_rating[0] if avg_rating else {"avg_rating": 0, "total_ratings": 0}
        
        problem_questions = await db.ratings.find(
            {"model": model_name, "rating": {"$lte": 3}},
            {"message": 1, "response": 1, "rating": 1}
        ).limit(10).to_list(length=None)
        
        trained_count = await db.trained_responses.count_documents({"model": model_name})
        
        return {
            "model": model_name,
            "total_conversations": total_conversations,
            "total_users": total_users,
            "avg_rating": rating_info["avg_rating"],
            "total_ratings": rating_info["total_ratings"],
            "trained_responses": trained_count,
            "top_responses": top_responses,
            "top_questions": top_questions,
            "problem_questions": problem_questions
        }
        
    except Exception as e:
        logger.error(f"Ошибка в model statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/statistics/{model_name}")
async def clear_model_statistics(model_name: str):
    """Очистка статистики конкретной модели с сохранением обученных ответов"""
    logger.debug(f"Received request to clear statistics for model: {model_name}")
    try:
        # Удаляем диалоги
        conversations_deleted = await db.conversations.delete_many({"model": model_name})
        
        # Удаляем рейтинги
        ratings_deleted = await db.ratings.delete_many({"model": model_name})
        
        # Удаляем активности
        activities_deleted = await db.bot_activities.delete_many({"model": model_name})
        
        # Удаляем статистику
        stats_deleted = await db.statistics.delete_many({"model": model_name})
        
        # НЕ УДАЛЯЕМ trained_responses - они должны остаться!
        
        return {
            "message": f"Статистика модели {model_name} очищена",
            "deleted": {
                "conversations": conversations_deleted.deleted_count,
                "ratings": ratings_deleted.deleted_count,
                "activities": activities_deleted.deleted_count,
                "statistics": stats_deleted.deleted_count
            },
            "preserved": {
                "trained_responses": "сохранены"
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings")
async def get_settings():
    """Получение пользовательских настроек"""
    logger.debug("Received request to /api/settings")
    try:
        settings = await db.user_settings.find_one({"type": "global_settings"})
        if settings:
            settings.pop("_id", None)
            settings.pop("type", None)
            return settings
        else:
            return {"default_model": "", "auto_save": True}
    except Exception as e:
        logger.error(f"Ошибка в get_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/settings")
async def save_settings(settings: dict):
    """Сохранение пользовательских настроек"""
    logger.debug(f"Received request to save settings: {settings}")
    try:
        await db.user_settings.update_one(
            {"type": "global_settings"},
            {
                "$set": {
                    **settings,
                    "updated_at": datetime.now(dt.UTC)
                }
            },
            upsert=True
        )
        
        return {"message": "Настройки сохранены", "status": "success"}
        
    except Exception as e:
        logger.error(f"Ошибка в save_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    logger.debug("Received request to /api/health")
    try:
        await db.command("ping")
        db_status = True
    except:
        db_status = False
    
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": db_status,
        "models_loaded": len(loaded_models),
        "active_conversations": len(conversation_states),
        "timestamp": datetime.now(dt.UTC)
    }

# Подключение api_router к приложению
app.include_router(api_router)

# Функция создания дополнительных обученных ответов при запуске (НЕ СОЗДАЕМ МОДЕЛИ!)
@app.on_event("startup")
async def add_more_trained_responses():
    """Добавление дополнительных обученных ответов для разнообразия"""
    logger.info("Adding more trained responses for variety...")
    
    # Расширенные ответы для русских моделей
    russian_responses = [
        {"question": "привет", "answer": "{Приветик красавчик!|Хай милый!|Привет солнышко!|Приветик дорогой!} 😊", "model": "rus_girl_1", "priority": 10},
        {"question": "как дела", "answer": "{Отлично, особенно с тобой!|Супер, а у тебя как?|Все круто, рассказывай о себе!|Замечательно!} 😉", "model": "rus_girl_1", "priority": 9},
        {"question": "что делаешь", "answer": "{Скучаю... А ты?|Думаю о приятном|Отдыхаю дома|Жду интересного общения} 😊", "model": "rus_girl_1", "priority": 8},
        {"question": "ты красивая", "answer": "{Спасибо милый!|Ты такой галантный!|Ты тоже симпатичный!|Приятно слышать!} 😘", "model": "rus_girl_1", "priority": 9},
        {"question": "хочу познакомиться", "answer": "{Давай знакомиться!|Я тоже хочу!|Будем друзьями?|С удовольствием!} 💕", "model": "rus_girl_1", "priority": 8},
        
        {"question": "привет", "answer": "{Приветик!|Хай!|Привет дорогой!|Здравствуй милый!} 😊", "model": "rus_girl_2", "priority": 10},
        {"question": "как дела", "answer": "{Хорошо, а у тебя?|Все отлично!|Прекрасно!|Замечательно!} 😉", "model": "rus_girl_2", "priority": 9},
        {"question": "что делаешь", "answer": "{Читаю|Слушаю музыку|Готовлю|Отдыхаю} 😊", "model": "rus_girl_2", "priority": 8},
    ]
    
    # Расширенные ответы для английских моделей
    english_responses = [
        {"question": "hey", "answer": "{Hey cutie!|Hi handsome!|Hello there!|Hey gorgeous!} 💕", "model": "eng_girl_1", "priority": 10},
        {"question": "how are you", "answer": "{Great, you?|Amazing!|Fantastic!|Perfect!} 😉", "model": "eng_girl_1", "priority": 9},
        {"question": "what are you doing", "answer": "{Missing you|Thinking of you|Just relaxing|Waiting for you} 😊", "model": "eng_girl_1", "priority": 8},
        {"question": "you're beautiful", "answer": "{Thank you babe!|You're sweet!|So are you!|Aww thanks!} 😘", "model": "eng_girl_1", "priority": 9},
        {"question": "wanna chat", "answer": "{Of course!|Always!|Sure thing!|Let's talk!} 💕", "model": "eng_girl_1", "priority": 8},
        
        {"question": "hey", "answer": "{Hi there!|Hello!|Hey babe!|Hi cutie!} 💕", "model": "eng_girl_1_joingy", "priority": 10},
        {"question": "how are you", "answer": "{Great!|Amazing!|Perfect!|Wonderful!} 😉", "model": "eng_girl_1_joingy", "priority": 9},
        {"question": "what are you doing", "answer": "{Relaxing|Waiting for you|Just chilling|Having fun} 😊", "model": "eng_girl_1_joingy", "priority": 8},
    ]
    
    # Объединяем все ответы
    all_responses = russian_responses + english_responses
    
    for response in all_responses:
        await db.trained_responses.update_one(
            {"question": response["question"], "model": response["model"]},
            {
                "$set": {
                    "answer": response["answer"],
                    "priority": response["priority"],
                    "startup_added": True,
                    "updated_at": datetime.now(dt.UTC)
                }
            },
            upsert=True
        )
        logger.info(f"Added enhanced response for '{response['question']}' in model '{response['model']}'")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)