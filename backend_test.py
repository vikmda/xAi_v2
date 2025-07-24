#!/usr/bin/env python3
"""
Comprehensive Backend Testing for xAi_v3 AI Sexter Bot
Tests all API endpoints and MongoDB functionality
"""

import requests
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List

# Configuration
BACKEND_URL = "https://d744b112-db75-446e-b4c9-9896dc82005d.preview.emergentagent.com/api"
TEST_USER_ID = str(uuid.uuid4())

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if response_data and not success:
            print(f"   Response: {response_data}")
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "status" in data and "database" in data:
                    self.log_test("Health Check", True, f"Status: {data.get('status')}, DB: {data.get('database')}", data)
                    return True
                else:
                    self.log_test("Health Check", False, "Missing required fields in response", data)
            else:
                self.log_test("Health Check", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
        return False
    
    def test_models_endpoint(self):
        """Test /api/models endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/models", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "models" in data and isinstance(data["models"], list):
                    models_count = len(data["models"])
                    self.log_test("Get Models", True, f"Found {models_count} models", data)
                    return data["models"]
                else:
                    self.log_test("Get Models", False, "Invalid response format", data)
            else:
                self.log_test("Get Models", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test("Get Models", False, f"Exception: {str(e)}")
        return []
    
    def test_model_config_endpoints(self, model_name: str):
        """Test GET and POST /api/model/{model_name} endpoints"""
        # Test GET model config
        try:
            response = self.session.get(f"{BACKEND_URL}/model/{model_name}", timeout=10)
            if response.status_code == 200:
                config = response.json()
                self.log_test(f"Get Model Config ({model_name})", True, f"Retrieved config for {config.get('name', 'Unknown')}")
                
                # Test POST model config (save)
                try:
                    # Modify config slightly for testing
                    config["mood"] = "тестовое настроение"
                    save_response = self.session.post(f"{BACKEND_URL}/model/{model_name}", 
                                                    json=config, timeout=10)
                    if save_response.status_code == 200:
                        save_data = save_response.json()
                        self.log_test(f"Save Model Config ({model_name})", True, save_data.get("message", "Saved"))
                        return True
                    else:
                        self.log_test(f"Save Model Config ({model_name})", False, f"HTTP {save_response.status_code}", save_response.text)
                except Exception as e:
                    self.log_test(f"Save Model Config ({model_name})", False, f"Exception: {str(e)}")
            else:
                self.log_test(f"Get Model Config ({model_name})", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test(f"Get Model Config ({model_name})", False, f"Exception: {str(e)}")
        return False
    
    def test_chat_endpoint(self, model_name: str):
        """Test /api/chat endpoint with realistic messages"""
        test_messages = [
            "Привет красавица! Как дела?",
            "Ты очень красивая",
            "Что ты любишь делать?",
            "Хочу тебя лучше узнать"
        ]
        
        for i, message in enumerate(test_messages):
            try:
                chat_data = {
                    "model": model_name,
                    "user_id": TEST_USER_ID,
                    "message": message
                }
                
                response = self.session.post(f"{BACKEND_URL}/chat", json=chat_data, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    required_fields = ["response", "message_number", "is_semi", "is_last", "model_used"]
                    if all(field in data for field in required_fields):
                        self.log_test(f"Chat Message {i+1} ({model_name})", True, 
                                    f"Response: '{data['response'][:50]}...', Msg #{data['message_number']}")
                    else:
                        self.log_test(f"Chat Message {i+1} ({model_name})", False, "Missing required fields", data)
                else:
                    self.log_test(f"Chat Message {i+1} ({model_name})", False, f"HTTP {response.status_code}", response.text)
                    break
                
                # Small delay between messages
                time.sleep(0.5)
                
            except Exception as e:
                self.log_test(f"Chat Message {i+1} ({model_name})", False, f"Exception: {str(e)}")
                break
    
    def test_test_endpoint(self, model_name: str):
        """Test /api/test endpoint"""
        try:
            test_data = {
                "message": "Привет! Как настроение?",
                "model": model_name
            }
            
            response = self.session.post(f"{BACKEND_URL}/test", json=test_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "response" in data and "model" in data:
                    self.log_test(f"Test Model ({model_name})", True, f"Test response: '{data['response'][:50]}...'")
                    return True
                else:
                    self.log_test(f"Test Model ({model_name})", False, "Missing required fields", data)
            else:
                self.log_test(f"Test Model ({model_name})", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test(f"Test Model ({model_name})", False, f"Exception: {str(e)}")
        return False
    
    def test_rating_endpoint(self, model_name: str):
        """Test /api/rate endpoint with auto-training"""
        try:
            # Test high rating (should trigger auto-training)
            rating_data = {
                "user_id": TEST_USER_ID,
                "message": "Какое у тебя настроение сегодня?",
                "response": "У меня отличное настроение! Готова к общению 😘",
                "rating": 10,
                "model": model_name
            }
            
            response = self.session.post(f"{BACKEND_URL}/rate", json=rating_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                message = data.get("message", "")
                if "обучение" in message.lower():
                    self.log_test(f"Rating with Auto-Training ({model_name})", True, f"High rating triggered training: {message}")
                else:
                    self.log_test(f"Rating ({model_name})", True, f"Rating saved: {message}")
                return True
            else:
                self.log_test(f"Rating ({model_name})", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test(f"Rating ({model_name})", False, f"Exception: {str(e)}")
        return False
    
    def test_training_endpoint(self, model_name: str):
        """Test /api/train endpoint"""
        try:
            training_data = {
                "question": "Как тебя зовут красавица?",
                "answer": "Меня зовут Катя, а тебя как? 😊",
                "model": model_name,
                "priority": 9
            }
            
            response = self.session.post(f"{BACKEND_URL}/train", json=training_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test(f"Manual Training ({model_name})", True, data.get("message", "Training completed"))
                return True
            else:
                self.log_test(f"Manual Training ({model_name})", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test(f"Manual Training ({model_name})", False, f"Exception: {str(e)}")
        return False
    
    def test_trained_response(self, model_name: str):
        """Test if trained responses are working"""
        try:
            # Test the question we just trained
            test_data = {
                "message": "Как тебя зовут красавица?",
                "model": model_name
            }
            
            response = self.session.post(f"{BACKEND_URL}/test", json=test_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                response_text = data.get("response", "")
                if "Катя" in response_text:
                    self.log_test(f"Trained Response Test ({model_name})", True, f"Got trained response: '{response_text}'")
                    return True
                else:
                    self.log_test(f"Trained Response Test ({model_name})", False, f"Expected trained response but got: '{response_text}'")
            else:
                self.log_test(f"Trained Response Test ({model_name})", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test(f"Trained Response Test ({model_name})", False, f"Exception: {str(e)}")
        return False
    
    def test_statistics_endpoint(self):
        """Test /api/statistics endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/statistics", timeout=10)
            if response.status_code == 200:
                data = response.json()
                required_fields = ["total_conversations", "total_users", "system_status"]
                if all(field in data for field in required_fields):
                    stats = f"Conversations: {data['total_conversations']}, Users: {data['total_users']}"
                    self.log_test("Statistics", True, stats, data)
                    return True
                else:
                    self.log_test("Statistics", False, "Missing required fields", data)
            else:
                self.log_test("Statistics", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test("Statistics", False, f"Exception: {str(e)}")
        return False
    
    def test_settings_endpoints(self):
        """Test GET and POST /api/settings endpoints"""
        try:
            # Test GET settings
            response = self.session.get(f"{BACKEND_URL}/settings", timeout=10)
            if response.status_code == 200:
                settings = response.json()
                self.log_test("Get Settings", True, f"Retrieved settings: {list(settings.keys())}")
                
                # Test POST settings
                test_settings = {
                    "default_model": "rus_girl_1",
                    "auto_save": True,
                    "test_setting": "test_value"
                }
                
                save_response = self.session.post(f"{BACKEND_URL}/settings", json=test_settings, timeout=10)
                if save_response.status_code == 200:
                    save_data = save_response.json()
                    self.log_test("Save Settings", True, save_data.get("message", "Settings saved"))
                    return True
                else:
                    self.log_test("Save Settings", False, f"HTTP {save_response.status_code}", save_response.text)
            else:
                self.log_test("Get Settings", False, f"HTTP {response.status_code}", response.text)
        except Exception as e:
            self.log_test("Settings", False, f"Exception: {str(e)}")
        return False
    
    def run_comprehensive_test(self):
        """Run all backend tests"""
        print("🚀 Starting Comprehensive Backend Testing for xAi_v3 AI Sexter Bot")
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Test User ID: {TEST_USER_ID}")
        print("=" * 80)
        
        # 1. Health Check
        print("\n📋 Testing System Health...")
        health_ok = self.test_health_endpoint()
        
        # 2. Models
        print("\n👥 Testing Models Management...")
        models = self.test_models_endpoint()
        
        if models:
            # Test with first available model
            test_model = models[0]["name"]
            print(f"\n🔧 Testing Model Configuration with: {test_model}")
            self.test_model_config_endpoints(test_model)
            
            # 3. Chat functionality
            print(f"\n💬 Testing Chat Functionality with: {test_model}")
            self.test_chat_endpoint(test_model)
            
            # 4. Test endpoint
            print(f"\n🧪 Testing Model Testing with: {test_model}")
            self.test_test_endpoint(test_model)
            
            # 5. Training system
            print(f"\n🎓 Testing Training System with: {test_model}")
            self.test_training_endpoint(test_model)
            
            # Wait a moment for training to be processed
            time.sleep(1)
            
            # 6. Test trained response
            print(f"\n🎯 Testing Trained Response with: {test_model}")
            self.test_trained_response(test_model)
            
            # 7. Rating system
            print(f"\n⭐ Testing Rating System with: {test_model}")
            self.test_rating_endpoint(test_model)
        
        # 8. Statistics
        print("\n📊 Testing Statistics...")
        self.test_statistics_endpoint()
        
        # 9. Settings
        print("\n⚙️ Testing Settings...")
        self.test_settings_endpoints()
        
        # Summary
        print("\n" + "=" * 80)
        print("📋 TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        # Show failed tests
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        return passed, total, failed_tests

if __name__ == "__main__":
    tester = BackendTester()
    passed, total, failed = tester.run_comprehensive_test()
    
    # Exit with appropriate code
    if failed:
        exit(1)
    else:
        print("\n🎉 All tests passed!")
        exit(0)