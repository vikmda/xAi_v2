import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Компонент для выбора модели
const ModelSelector = ({ models, selectedModel, onModelChange }) => {
  // Группируем модели по языку для лучшего отображения
  const russianModels = models.filter(model => model.language === 'ru');
  const englishModels = models.filter(model => model.language === 'en');

  return (
    <div className="flex-1 mr-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        🤖 Выберите модель персонажа:
      </label>
      <select
        value={selectedModel}
        onChange={(e) => onModelChange(e.target.value)}
        className="w-full p-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900"
      >
        <option value="">Выберите модель...</option>
        
        {russianModels.length > 0 && (
          <optgroup label="🇷🇺 Русскоязычные модели">
            {russianModels.map((model) => (
              <option key={model.name} value={model.name}>
                {model.display_name} - {model.country}
              </option>
            ))}
          </optgroup>
        )}
        
        {englishModels.length > 0 && (
          <optgroup label="🇺🇸 Англоязычные модели">
            {englishModels.map((model) => (
              <option key={model.name} value={model.name}>
                {model.display_name} - {model.country}
              </option>
            ))}
          </optgroup>
        )}
      </select>
    </div>
  );
};

// Компонент для тестирования
const TestComponent = ({ selectedModel }) => {
  const [message, setMessage] = useState('');
  const [response, setResponse] = useState('');
  const [rating, setRating] = useState(5);
  const [loading, setLoading] = useState(false);

  const handleTest = async () => {
    if (!selectedModel || !message.trim()) return;
    
    setLoading(true);
    try {
      const res = await axios.post(`${API}/test`, {
        message: message.trim(),
        model: selectedModel
      });
      setResponse(res.data.response);
    } catch (error) {
      console.error('Ошибка тестирования:', error);
      setResponse('❌ Ошибка при получении ответа');
    } finally {
      setLoading(false);
    }
  };

  const handleRating = async () => {
    if (!response || !message.trim()) return;
    
    try {
      await axios.post(`${API}/rate`, {
        user_id: 'test_user',
        message: message.trim(),
        response: response,
        rating: rating,
        model: selectedModel
      });
      alert('✅ Рейтинг сохранен успешно!');
    } catch (error) {
      console.error('Ошибка рейтинга:', error);
      alert('❌ Ошибка при сохранении рейтинга');
    }
  };

  // Примеры сообщений для тестирования
  const exampleMessages = [
    "Привет! Как дела?",
    "Что любишь делать?",
    "Ты очень красивая",
    "Хочу познакомиться поближе",
    "Расскажи о себе"
  ];

  const handleExampleClick = (exampleMsg) => {
    setMessage(exampleMsg);
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
        🧪 Тестирование модели
      </h3>
      
      {!selectedModel && (
        <div className="text-center py-8 text-gray-500">
          <p className="text-lg">⚠️ Выберите модель для тестирования</p>
          <p className="text-sm mt-2">Используйте выпадающий список выше</p>
        </div>
      )}

      {selectedModel && (
        <>
          {/* Примеры сообщений */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              💡 Быстрые примеры:
            </label>
            <div className="flex flex-wrap gap-2">
              {exampleMessages.map((example, index) => (
                <button
                  key={index}
                  onClick={() => handleExampleClick(example)}
                  className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-full transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              💬 Введите сообщение для тестирования:
            </label>
            <div className="relative">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Напишите сообщение для персонажа..."
                className="w-full p-3 pr-12 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                onKeyPress={(e) => e.key === 'Enter' && handleTest()}
              />
              <div className="absolute right-3 top-3 text-gray-400">
                💬
              </div>
            </div>
          </div>

          <button
            onClick={handleTest}
            disabled={!selectedModel || !message.trim() || loading}
            className="bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 disabled:bg-gray-400 mb-4 font-medium transition-colors flex items-center gap-2"
          >
            {loading ? '🔄 Тестирование...' : '🚀 Протестировать'}
          </button>

          {response && (
            <div className="mb-4 p-4 border-2 border-blue-100 rounded-lg bg-blue-50">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                🤖 Ответ персонажа:
              </label>
              <div className="p-3 bg-white rounded-lg border-l-4 border-blue-400">
                <textarea
                  value={response}
                  onChange={(e) => setResponse(e.target.value)}
                  className="w-full p-2 text-gray-800 border border-gray-200 rounded-md resize-none"
                  rows={3}
                  placeholder="Ответ персонажа..."
                />
              </div>
              <div className="mt-2 text-xs text-gray-600">
                💡 Можете отредактировать ответ перед оценкой
              </div>
              
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-gray-700">
                    ⭐ Оцените качество ответа (1-10):
                  </label>
                  <span className="text-lg font-bold text-blue-600">{rating}/10</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={rating}
                  onChange={(e) => setRating(parseInt(e.target.value))}
                  className="w-full mb-3"
                />
                <div className="flex justify-between text-xs text-gray-500 mb-3">
                  <span>1 (Очень плохо)</span>
                  <span>5 (Нормально)</span>
                  <span>10 (Отлично)</span>
                </div>
                <button
                  onClick={handleRating}
                  className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 font-medium transition-colors flex items-center gap-2"
                >
                  📊 Сохранить оценку
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// Компонент для ручного обучения
const TrainingComponent = ({ selectedModel }) => {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [priority, setPriority] = useState(5);
  const [loading, setLoading] = useState(false);

  const handleTrain = async () => {
    if (!selectedModel || !question.trim() || !answer.trim()) return;
    
    setLoading(true);
    try {
      await axios.post(`${API}/train`, {
        question: question.trim(),
        answer: answer.trim(),
        model: selectedModel,
        priority: priority
      });
      alert('✅ Обучающие данные успешно сохранены!');
      setQuestion('');
      setAnswer('');
      setPriority(5);
    } catch (error) {
      console.error('Ошибка обучения:', error);
      alert('❌ Ошибка при сохранении обучающих данных');
    } finally {
      setLoading(false);
    }
  };

  // Примеры для обучения
  const trainingExamples = [
    {
      question: "Привет, как дела?",
      answer: "Привет красавчик! У меня все отлично, особенно когда вижу таких милых 😘"
    },
    {
      question: "Что любишь делать?",
      answer: "Люблю танцевать, фотографироваться... А еще очень люблю общаться с интересными мужчинами 💕"
    },
    {
      question: "Ты красивая",
      answer: "Спасибо милый! Ты такой галантный 😊 А ты тоже симпатичный?"
    }
  ];

  const handleExampleClick = (example) => {
    setQuestion(example.question);
    setAnswer(example.answer);
  };

  const getPriorityLabel = (priority) => {
    if (priority <= 3) return "🔸 Низкий";
    if (priority <= 6) return "🔶 Средний";
    if (priority <= 8) return "🔸 Высокий";
    return "🔥 Критичный";
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
        🎓 Ручное обучение модели
      </h3>
      
      {!selectedModel && (
        <div className="text-center py-8 text-gray-500">
          <p className="text-lg">⚠️ Выберите модель для обучения</p>
          <p className="text-sm mt-2">Обучение поможет улучшить ответы персонажа</p>
        </div>
      )}

      {selectedModel && (
        <>
          {/* Примеры для обучения */}
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h4 className="font-medium text-blue-800 mb-3">💡 Примеры обучения:</h4>
            <div className="space-y-2">
              {trainingExamples.map((example, index) => (
                <div
                  key={index}
                  onClick={() => handleExampleClick(example)}
                  className="p-3 bg-white border border-blue-100 rounded-lg cursor-pointer hover:border-blue-300 transition-colors"
                >
                  <div className="text-sm text-gray-600">
                    <strong>Вопрос:</strong> {example.question}
                  </div>
                  <div className="text-sm text-blue-700 mt-1">
                    <strong>Ответ:</strong> {example.answer}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                ❓ Вопрос/Сообщение пользователя:
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Например: Привет, как дела?"
                rows={3}
                className="w-full p-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                💬 Правильный ответ персонажа:
              </label>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Например: Привет красавчик! У меня все отлично 😘"
                rows={3}
                className="w-full p-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              ⚡ Приоритет обучения: {getPriorityLabel(priority)}
            </label>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">1</span>
              <input
                type="range"
                min="1"
                max="10"
                value={priority}
                onChange={(e) => setPriority(parseInt(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm text-gray-500">10</span>
              <span className="text-lg font-bold text-blue-600 min-w-[2rem] text-center">
                {priority}
              </span>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Высокий приоритет означает, что этот ответ будет использоваться чаще
            </div>
          </div>

          <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-start gap-2">
              <span className="text-yellow-600 mt-0.5">💡</span>
              <div className="text-sm text-yellow-800">
                <strong>Советы по обучению:</strong>
                <ul className="mt-1 space-y-1">
                  <li>• Используйте естественный язык и эмодзи</li>
                  <li>• Добавляйте флиртовые элементы для персонажа</li>
                  <li>• Высокий приоритет (8-10) для самых важных ответов</li>
                  <li>• Учитывайте характер и настроение персонажа</li>
                </ul>
              </div>
            </div>
          </div>

          <button
            onClick={handleTrain}
            disabled={!selectedModel || !question.trim() || !answer.trim() || loading}
            className="mt-6 bg-green-500 hover:bg-green-600 text-white px-6 py-3 rounded-lg font-medium disabled:bg-gray-400 transition-colors flex items-center gap-2"
          >
            {loading ? '💾 Сохранение...' : '🎓 Обучить модель'}
          </button>
        </>
      )}
    </div>
  );
};

// Компонент для редактирования персонажей
const CharacterEditor = ({ selectedModel }) => {
  const [character, setCharacter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [originalCharacter, setOriginalCharacter] = useState(null);

  useEffect(() => {
    if (selectedModel) {
      loadCharacter();
    } else {
      setCharacter(null);
    }
  }, [selectedModel]);

  const loadCharacter = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/model/${selectedModel}`);
      setCharacter(response.data);
      setOriginalCharacter(JSON.parse(JSON.stringify(response.data)));
    } catch (error) {
      console.error('Ошибка загрузки персонажа:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!character || !selectedModel) return;
    
    setSaving(true);
    try {
      await axios.post(`${API}/model/${selectedModel}`, character);
      alert('✅ Персонаж успешно сохранен!');
      setOriginalCharacter(JSON.parse(JSON.stringify(character)));
    } catch (error) {
      console.error('Ошибка сохранения персонажа:', error);
      alert('❌ Ошибка при сохранении персонажа');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (originalCharacter) {
      setCharacter(JSON.parse(JSON.stringify(originalCharacter)));
    }
  };

  const hasChanges = () => {
    return JSON.stringify(character) !== JSON.stringify(originalCharacter);
  };

  if (!selectedModel) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="text-center text-gray-500">
          <p className="text-lg">🎭 Редактор персонажей</p>
          <p className="text-sm mt-2">Выберите модель для редактирования персонажа</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p>Загрузка персонажа...</p>
        </div>
      </div>
    );
  }

  if (!character) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <p className="text-center text-red-500">Ошибка загрузки персонажа</p>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">🎭 Редактор персонажа</h3>
        {hasChanges() && (
          <span className="text-sm text-orange-600 bg-orange-100 px-2 py-1 rounded">
            Есть несохраненные изменения
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Основная информация */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            👤 Имя персонажа:
          </label>
          <input
            type="text"
            value={character.name}
            onChange={(e) => setCharacter({...character, name: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🎂 Возраст:
          </label>
          <input
            type="number"
            min="18"
            max="99"
            value={character.age}
            onChange={(e) => setCharacter({...character, age: parseInt(e.target.value)})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🌍 Страна:
          </label>
          <input
            type="text"
            value={character.country}
            onChange={(e) => setCharacter({...character, country: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🏙️ Город:
          </label>
          <input
            type="text"
            value={character.city}
            onChange={(e) => setCharacter({...character, city: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            🗣️ Язык:
          </label>
          <select
            value={character.language}
            onChange={(e) => setCharacter({...character, language: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          >
            <option value="ru">Русский</option>
            <option value="en">Английский</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            📱 Количество сообщений до завершения:
          </label>
          <input
            type="number"
            min="3"
            max="15"
            value={character.message_count}
            onChange={(e) => setCharacter({...character, message_count: parseInt(e.target.value)})}
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Настроения и интересы */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            😊 Настроение:
          </label>
          <input
            type="text"
            value={character.mood}
            onChange={(e) => setCharacter({...character, mood: e.target.value})}
            placeholder="игривое, романтичное, дерзкое..."
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            💭 Интересы (через запятую):
          </label>
          <input
            type="text"
            value={character.interests.join(', ')}
            onChange={(e) => setCharacter({...character, interests: e.target.value.split(',').map(s => s.trim())})}
            placeholder="фотография, танцы, музыка..."
            className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Сообщения */}
      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          💕 Предпоследнее сообщение (с намеком):
        </label>
        <textarea
          value={character.semi_message}
          onChange={(e) => setCharacter({...character, semi_message: e.target.value})}
          rows={2}
          className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          🔗 Финальное сообщение (с ссылкой на Telegram):
        </label>
        <textarea
          value={character.final_message}
          onChange={(e) => setCharacter({...character, final_message: e.target.value})}
          rows={2}
          className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Черты характера */}
      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          🎨 Черты характера (через запятую):
        </label>
        <input
          type="text"
          value={character.personality_traits.join(', ')}
          onChange={(e) => setCharacter({...character, personality_traits: e.target.value.split(',').map(s => s.trim())})}
          placeholder="flirty, playful, sweet, romantic..."
          className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Настройки */}
      <div className="mt-4 flex items-center gap-6">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={character.use_emoji}
            onChange={(e) => setCharacter({...character, use_emoji: e.target.checked})}
            className="w-4 h-4 text-blue-600"
          />
          <span className="text-sm text-gray-700">😀 Использовать эмодзи</span>
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={character.learning_enabled}
            onChange={(e) => setCharacter({...character, learning_enabled: e.target.checked})}
            className="w-4 h-4 text-blue-600"
          />
          <span className="text-sm text-gray-700">🧠 Обучение включено</span>
        </label>
      </div>

      {/* Кнопки управления */}
      <div className="mt-6 flex gap-3">
        <button
          onClick={handleSave}
          disabled={!hasChanges() || saving}
          className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-md font-medium disabled:bg-gray-400 transition-colors"
        >
          {saving ? '💾 Сохранение...' : '💾 Сохранить персонажа'}
        </button>
        
        <button
          onClick={handleReset}
          disabled={!hasChanges()}
          className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-md font-medium disabled:bg-gray-400 transition-colors"
        >
          🔄 Отменить изменения
        </button>

        <button
          onClick={loadCharacter}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
        >
          🔄 Перезагрузить
        </button>
      </div>
    </div>
  );
};
// Компонент настроек чат-платформ - УДАЛЕН по запросу пользователя

const StatisticsComponent = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStatistics();
  }, []);

  const loadStatistics = async () => {
    try {
      const response = await axios.get(`${API}/statistics`);
      setStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Загрузка статистики...</div>;
  if (!stats) return <div>Ошибка загрузки статистики</div>;

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-lg font-semibold mb-4">Статистика системы</h3>
      
      {/* Общая статистика */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 p-4 rounded-lg">
          <h4 className="font-medium text-blue-900">Всего диалогов</h4>
          <p className="text-2xl font-bold text-blue-600">{stats.total_conversations}</p>
        </div>
        <div className="bg-green-50 p-4 rounded-lg">
          <h4 className="font-medium text-green-900">Всего пользователей</h4>
          <p className="text-2xl font-bold text-green-600">{stats.total_users}</p>
        </div>
        <div className="bg-purple-50 p-4 rounded-lg">
          <h4 className="font-medium text-purple-900">Активных моделей</h4>
          <p className="text-2xl font-bold text-purple-600">{stats.system_status.models_loaded}</p>
        </div>
      </div>

      {/* Статус системы */}
      <div className="mb-6">
        <h4 className="font-medium mb-2">Статус системы</h4>
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 ${stats.system_status.database_connected ? 'text-green-600' : 'text-red-600'}`}>
            <div className={`w-3 h-3 rounded-full ${stats.system_status.database_connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            База данных
          </div>
          <div className="text-blue-600">
            Активных диалогов: {stats.system_status.active_conversations}
          </div>
        </div>
      </div>

      {/* Статистика по моделям */}
      {stats.models_stats && stats.models_stats.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium mb-2">Статистика по моделям</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">Модель</th>
                  <th className="px-4 py-2 text-left">Диалоги</th>
                  <th className="px-4 py-2 text-left">Средний рейтинг</th>
                </tr>
              </thead>
              <tbody>
                {stats.models_stats.map((model, index) => (
                  <tr key={index} className="border-t">
                    <td className="px-4 py-2">{model._id}</td>
                    <td className="px-4 py-2">{model.conversations}</td>
                    <td className="px-4 py-2">{model.avg_rating ? model.avg_rating.toFixed(1) : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Топ ответов */}
      {stats.top_responses && stats.top_responses.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium mb-2">Популярные ответы</h4>
          <div className="space-y-2">
            {stats.top_responses.slice(0, 5).map((response, index) => (
              <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                <span className="text-sm truncate">{response._id}</span>
                <span className="text-sm font-medium">{response.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Популярные вопросы */}
      {stats.top_questions && stats.top_questions.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium mb-2">Популярные вопросы</h4>
          <div className="space-y-2">
            {stats.top_questions.slice(0, 5).map((question, index) => (
              <div key={index} className="flex justify-between items-center p-2 bg-green-50 rounded">
                <span className="text-sm truncate">{question._id}</span>
                <span className="text-sm font-medium text-green-600">{question.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Проблемные вопросы */}
      {stats.problem_questions && stats.problem_questions.length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Проблемные вопросы (низкий рейтинг)</h4>
          <div className="space-y-2">
            {stats.problem_questions.slice(0, 3).map((item, index) => (
              <div key={index} className="p-2 bg-red-50 rounded">
                <div className="text-sm text-red-800">
                  <strong>Вопрос:</strong> {item.message}
                </div>
                <div className="text-sm text-red-600">
                  <strong>Ответ:</strong> {item.response}
                </div>
                <div className="text-sm text-red-500">
                  Рейтинг: {item.rating}/10 | Модель: {item.model}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={loadStatistics}
        className="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600"
      >
        Обновить статистику
      </button>
    </div>
  );
};

// Основной компонент
const App = () => {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [activeTab, setActiveTab] = useState('test');
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState({ auto_save: true });
  const [saveStatus, setSaveStatus] = useState('');

  useEffect(() => {
    loadModels();
    loadSettings();
  }, []);

  // Убираем автосохранение - пользователь хочет кнопку мгновенного сохранения

  const loadModels = async () => {
    try {
      const response = await axios.get(`${API}/models`);
      setModels(response.data.models);
      if (response.data.models.length > 0) {
        setSelectedModel(response.data.models[0].name);
      }
    } catch (error) {
      console.error('Ошибка загрузки моделей:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await axios.get(`${API}/settings`);
      setSettings(response.data);
      if (response.data.default_model) {
        setSelectedModel(response.data.default_model);
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек:', error);
    }
  };

  const saveSettings = async (newSettings) => {
    try {
      await axios.post(`${API}/settings`, newSettings);
      setSaveStatus('Настройки сохранены ✓');
      setTimeout(() => setSaveStatus(''), 3000);
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      setSaveStatus('Ошибка сохранения ✗');
      setTimeout(() => setSaveStatus(''), 3000);
    }
  };

  const handleModelChange = (modelName) => {
    setSelectedModel(modelName);
  };

  const handleSaveSettings = async () => {
    const newSettings = { 
      default_model: selectedModel,
      auto_save: false  // Убираем автосохранение
    };
    setSettings(newSettings);
    await saveSettings(newSettings);
  };

  const toggleAutoSave = () => {
    // Эта функция больше не нужна, но оставляем для совместимости
    const newAutoSave = !settings.auto_save;
    const newSettings = { ...settings, auto_save: newAutoSave };
    setSettings(newSettings);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p>Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2 flex items-center justify-center gap-2">
            <span>🤖</span>
            AI Секс-бот Панель Управления
          </h1>
          <p className="text-lg text-gray-600">
            Профессиональная система управления AI персонажами для чат-ботов
          </p>
          <div className="mt-2 text-sm text-gray-500">
            Настройка, обучение и тестирование умных персонажей
          </div>
        </header>

        <div className="max-w-4xl mx-auto">
          {/* Панель настроек */}
          <div className="bg-white p-4 rounded-lg shadow-md mb-6">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <ModelSelector
                models={models}
                selectedModel={selectedModel}
                onModelChange={handleModelChange}
              />
              <div className="flex items-center gap-4">
                <button
                  onClick={handleSaveSettings}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
                  disabled={!selectedModel}
                >
                  💾 Сохранить настройки
                </button>
                {saveStatus && (
                  <div className={`text-sm font-medium ${saveStatus.includes('✓') ? 'text-green-600' : 'text-red-600'}`}>
                    {saveStatus}
                  </div>
                )}
              </div>
            </div>
            
            {/* Информация о выбранной модели */}
            {selectedModel && (
              <div className="mt-3 p-3 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-600">
                  <span className="font-medium">Выбранная модель:</span> {models.find(m => m.name === selectedModel)?.display_name} 
                  <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                    {models.find(m => m.name === selectedModel)?.language === 'ru' ? '🇷🇺 Русская' : '🇺🇸 Английская'}
                  </span>
                  <span className="ml-2 text-gray-500">({models.find(m => m.name === selectedModel)?.country})</span>
                </p>
              </div>
            )}
          </div>

          {/* Табы */}
          <div className="mb-6">
            <nav className="flex space-x-1 bg-white rounded-lg p-1">
              <button
                onClick={() => setActiveTab('test')}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                  activeTab === 'test'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                🧪 Тестирование
              </button>
              <button
                onClick={() => setActiveTab('training')}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                  activeTab === 'training'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                🎓 Обучение
              </button>
              <button
                onClick={() => setActiveTab('character')}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                  activeTab === 'character'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                🎭 Персонаж
              </button>
              <button
                onClick={() => setActiveTab('statistics')}
                className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                  activeTab === 'statistics'
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                📊 Статистика
              </button>
            </nav>
          </div>

          {/* Контент табов */}
          {activeTab === 'test' && <TestComponent selectedModel={selectedModel} />}
          {activeTab === 'training' && <TrainingComponent selectedModel={selectedModel} />}
          {activeTab === 'character' && <CharacterEditor selectedModel={selectedModel} />}
          {activeTab === 'statistics' && <StatisticsComponent />}
        </div>
      </div>
    </div>
  );
};

export default App;