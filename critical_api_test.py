#!/usr/bin/env python3
"""
Critical API Testing for xAi_v4 - Focus on ZennoPoster Integration
Tests the most important endpoints with specific focus on POST /api/chat
"""

import requests
import json
import uuid
import time
from datetime import datetime

# Configuration
BACKEND_URL = "https://d744b112-db75-446e-b4c9-9896dc82005d.preview.emergentagent.com/api"
TEST_USER_ID = str(uuid.uuid4())

def test_basic_endpoints():
    """Test basic endpoints"""
    print("🔍 Testing Basic Endpoints...")
    
    # Test GET /api/
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/ - {data.get('message', 'OK')}")
        else:
            print(f"❌ GET /api/ - HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ GET /api/ - Exception: {e}")
    
    # Test GET /api/health
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GET /api/health - Status: {data.get('status')}, DB: {data.get('database')}")
        else:
            print(f"❌ GET /api/health - HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ GET /api/health - Exception: {e}")

def test_models_endpoint():
    """Test models endpoint and return available models"""
    print("\n👥 Testing Models Endpoint...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            print(f"✅ GET /api/models - Found {len(models)} models:")
            for model in models:
                print(f"   - {model['name']} ({model['display_name']}) - {model['language']}")
            return [model['name'] for model in models]
        else:
            print(f"❌ GET /api/models - HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ GET /api/models - Exception: {e}")
    
    return []

def test_chat_endpoint_comprehensive(models):
    """Comprehensive testing of POST /api/chat - Critical for ZennoPoster"""
    print("\n💬 CRITICAL: Testing POST /api/chat (ZennoPoster Integration)")
    
    # Test messages in Russian and English
    test_scenarios = [
        {
            "model": "rus_girl_1",
            "messages": [
                "Привет!",
                "Как дела красавица?", 
                "Ты очень красивая",
                "Что ты любишь делать?",
                "Хочу тебя лучше узнать"
            ]
        },
        {
            "model": "rus_girl_2", 
            "messages": [
                "Привет красотка!",
                "Как настроение?",
                "Расскажи о себе"
            ]
        },
        {
            "model": "eng_girl_1",
            "messages": [
                "Hello beautiful!",
                "How are you doing?",
                "You look amazing"
            ]
        }
    ]
    
    for scenario in test_scenarios:
        model_name = scenario["model"]
        if model_name not in models:
            print(f"⚠️  Model {model_name} not available, skipping...")
            continue
            
        print(f"\n🎯 Testing {model_name} conversation flow:")
        user_id = str(uuid.uuid4())  # New user for each model
        
        for i, message in enumerate(scenario["messages"]):
            try:
                chat_data = {
                    "model": model_name,
                    "user_id": user_id,
                    "message": message
                }
                
                response = requests.post(f"{BACKEND_URL}/chat", json=chat_data, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Validate required fields
                    required_fields = ["response", "message_number", "is_semi", "is_last", "model_used"]
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"❌ Message {i+1}: Missing fields: {missing_fields}")
                        continue
                    
                    # Check response format
                    response_text = data["response"]
                    msg_num = data["message_number"]
                    is_semi = data["is_semi"]
                    is_last = data["is_last"]
                    
                    status = "🔥 SEMI" if is_semi else "🏁 FINAL" if is_last else "💬 REGULAR"
                    print(f"✅ Msg {msg_num}: {status} - '{response_text[:60]}{'...' if len(response_text) > 60 else ''}'")
                    
                    # Validate message flow logic
                    if msg_num != i + 1:
                        print(f"⚠️  Message number mismatch: expected {i+1}, got {msg_num}")
                    
                else:
                    print(f"❌ Message {i+1}: HTTP {response.status_code} - {response.text[:100]}")
                    break
                    
                # Small delay between messages
                time.sleep(0.3)
                
            except Exception as e:
                print(f"❌ Message {i+1}: Exception - {e}")
                break

def test_training_and_priority():
    """Test training system and priority handling"""
    print("\n🎓 Testing Training System & Priority Logic...")
    
    model = "rus_girl_1"
    test_question = "Как тебя зовут милая?"
    test_answer = "Меня зовут Катя, очень приятно познакомиться! 😘"
    
    # 1. Manual training with high priority
    try:
        training_data = {
            "question": test_question,
            "answer": test_answer,
            "model": model,
            "priority": 10
        }
        
        response = requests.post(f"{BACKEND_URL}/train", json=training_data, timeout=10)
        if response.status_code == 200:
            print("✅ Manual training successful")
        else:
            print(f"❌ Manual training failed: HTTP {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Manual training exception: {e}")
        return
    
    # 2. Test if trained response is returned
    time.sleep(1)  # Wait for training to be processed
    
    try:
        test_data = {
            "message": test_question,
            "model": model
        }
        
        response = requests.post(f"{BACKEND_URL}/test", json=test_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "")
            
            if "Катя" in response_text:
                print(f"✅ Trained response working: '{response_text}'")
            else:
                print(f"❌ Trained response not working. Got: '{response_text}'")
        else:
            print(f"❌ Test endpoint failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Test endpoint exception: {e}")

def test_rating_auto_training():
    """Test rating system with auto-training"""
    print("\n⭐ Testing Rating System & Auto-Training...")
    
    model = "rus_girl_1"
    user_id = str(uuid.uuid4())
    
    # Test high rating (should trigger auto-training)
    try:
        rating_data = {
            "user_id": user_id,
            "message": "Какое у тебя сегодня настроение?",
            "response": "У меня отличное настроение! Готова к флирту 😘💕",
            "rating": 9,
            "model": model
        }
        
        response = requests.post(f"{BACKEND_URL}/rate", json=rating_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            message = data.get("message", "")
            
            if "обучение" in message.lower():
                print(f"✅ Auto-training triggered: {message}")
            else:
                print(f"✅ Rating saved: {message}")
        else:
            print(f"❌ Rating failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Rating exception: {e}")

def test_statistics_endpoint():
    """Test statistics endpoint"""
    print("\n📊 Testing Statistics Endpoint...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/statistics", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Statistics retrieved:")
            print(f"   - Total conversations: {data.get('total_conversations', 0)}")
            print(f"   - Total users: {data.get('total_users', 0)}")
            print(f"   - Models loaded: {data.get('system_status', {}).get('models_loaded', 0)}")
            print(f"   - Database connected: {data.get('system_status', {}).get('database_connected', False)}")
            
        else:
            print(f"❌ Statistics failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Statistics exception: {e}")

def main():
    """Run critical API tests"""
    print("🚀 CRITICAL API TESTING - xAi_v4 Backend")
    print(f"Backend URL: {BACKEND_URL}")
    print("=" * 80)
    
    # Test basic endpoints
    test_basic_endpoints()
    
    # Test models and get available models
    models = test_models_endpoint()
    
    if not models:
        print("❌ CRITICAL: No models available, cannot continue testing")
        return
    
    # Test critical chat endpoint
    test_chat_endpoint_comprehensive(models)
    
    # Test training system
    test_training_and_priority()
    
    # Test rating system
    test_rating_auto_training()
    
    # Test statistics
    test_statistics_endpoint()
    
    print("\n" + "=" * 80)
    print("🎯 CRITICAL TESTING COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()