// =============================================================================
// УНИВЕРСАЛЬНЫЙ JS КОД ДЛЯ ZENNOPOSTER
// Версия: 2.0
// Описание: Универсальный бот для чатов с ИИ-поддержкой
// =============================================================================

(function () {
    try {
        // === КОНФИГУРАЦИЯ ===
        const CONFIG = {
            chatAuth: "{-Variable.chatAuth-}",      // Токен авторизации чата
            model: "{-Variable.model-}",            // Модель ИИ (rus_girl_1, eng_girl_1, etc.)
            server: "wss://noname.chat/socket.io/", // WebSocket сервер (ИЗМЕНИТЬ ПОД СВОЙ ЧАТ)
            maxDialogs: 80,                         // Максимум диалогов
            inactivityTimeout: 18000,               // Таймаут неактивности (мс)
            typingDelay: [1500, 3000],             // Задержка typing (мс)
            responseDelay: [2000, 4000],           // Задержка ответа (мс)
            reconnectDelay: 5000,                  // Задержка переподключения (мс)
            searchTimeout: 20000,                  // Таймаут поиска (мс)
            firstDialogTimeout: 30000,             // Таймаут первого диалога (мс)
            localApiUrl: "http://127.0.0.1:8001/api/chat",    // Основной API
            alternativeApiUrl: "http://192.168.0.49:8001/api/chat" // Альтернативный API
        };

        // === ТРИГГЕРЫ ЗАВЕРШЕНИЯ ===
        // Слова/фразы, при обнаружении которых диалог завершается
        const END_TRIGGERS = [
            "http://", "https://", "www.", ".com", ".ru", ".org", ".net",
            "тг", "телеграм", "telegram", "@", "t.me/", "tg://",
            "переходи", "ссылка", "жми", "кликай", "перейди", "заходи",
            "инст", "инста", "instagram", "вк", "вконтакте", "facebook"
        ];

        // === ПРОВЕРКА КОНФИГУРАЦИИ ===
        if (CONFIG.chatAuth.includes("{-Variable") || CONFIG.model.includes("{-Variable")) {
            throw new Error("Не заменены переменные ZennoPoster! Установите chatAuth и model.");
        }

        // === СОСТОЯНИЕ БОТА ===
        let log = [];
        let processedPeers = [];
        let currentDialog = {
            active: false,
            peerId: null,
            messageCount: 0,
            startTime: null,
            lastMessageTime: null,
            inactivityTimer: null
        };
        let ws = null;
        let status = "start";
        let dialogCount = 0;
        let successfulDialogs = 0;
        let ackIdCounter = 422;
        let searchTimeout = null;
        const threadId = Math.random().toString(36).substr(2, 5);

        // === УТИЛИТЫ ===
        function logAdd(msg) {
            const time = new Date().toLocaleTimeString('ru-RU');
            const line = `[${time}] [${threadId}] ${msg}`;
            log.push(line);
            window.__zp_log = log.join("\n");
            console.log(line);
        }

        function normalize(text) {
            return text.toLowerCase().replace(/[^a-zа-я0-9\s@./]/gi, '');
        }

        function getRandomDelay(range) {
            return Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
        }

        function hasEndTrigger(text) {
            const cleaned = normalize(text);
            return END_TRIGGERS.some(trigger => cleaned.includes(trigger));
        }

        // === ФУНКЦИЯ ЗАПРОСА К ИИ ===
        function getAIResponse(peerId, message) {
            try {
                logAdd(`str: ${peerId} | Запрос к ИИ (модель: ${CONFIG.model})`);
                
                const requestBody = JSON.stringify({
                    model: CONFIG.model,
                    user_id: peerId,
                    message: message
                });

                let response = null;
                let apiUrl = CONFIG.localApiUrl;
                
                try {
                    // Основной API
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', apiUrl, false);
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.send(requestBody);
                    
                    if (xhr.status === 200) {
                        response = xhr.responseText;
                    } else {
                        throw new Error(`HTTP ${xhr.status}: ${xhr.statusText}`);
                    }
                } catch (e) {
                    logAdd(`str: ${peerId} | Ошибка основного API: ${e.message}`);
                    
                    // Альтернативный API
                    apiUrl = CONFIG.alternativeApiUrl;
                    try {
                        const xhr2 = new XMLHttpRequest();
                        xhr2.open('POST', apiUrl, false);
                        xhr2.setRequestHeader('Content-Type', 'application/json');
                        xhr2.send(requestBody);
                        
                        if (xhr2.status === 200) {
                            response = xhr2.responseText;
                            logAdd(`str: ${peerId} | Переключен на альтернативный API`);
                        } else {
                            throw new Error(`HTTP ${xhr2.status}: ${xhr2.statusText}`);
                        }
                    } catch (e2) {
                        logAdd(`str: ${peerId} | Ошибка альтернативного API: ${e2.message}`);
                        throw e2;
                    }
                }

                if (!response) {
                    throw new Error("Пустой ответ от ИИ");
                }

                const data = JSON.parse(response);
                if (!data.response) {
                    throw new Error("Нет поля 'response' в ответе ИИ");
                }

                logAdd(`str: ${peerId} | Ответ: ${data.response.substring(0, 50)}...`);
                
                // Проверяем на триггеры завершения
                if (hasEndTrigger(data.response)) {
                    logAdd(`str: ${peerId} | 🎯 Обнаружен триггер завершения!`);
                    return { response: data.response, shouldEnd: true };
                }
                
                return { response: data.response, shouldEnd: false };
            } catch (e) {
                logAdd(`str: ${peerId} | ❌ Ошибка ИИ: ${e.message}`);
                return null;
            }
        }

        // === WEBSOCKET ФУНКЦИИ ===
        function connect() {
            const url = `${CONFIG.server}?EIO=4&transport=websocket&chatAuth=${CONFIG.chatAuth}`;
            logAdd(`🚀 Старт ${threadId} | Модель: ${CONFIG.model} | Успешных: ${successfulDialogs}`);

            try {
                ws = new WebSocket(url);
                
                ws.onopen = () => {
                    ws.send('40');
                    logAdd(`✅ WebSocket открыт ${threadId}`);
                    setTimeout(() => startSearch(), 1000);
                };
                
                ws.onmessage = (event) => handleMessage(event.data);
                
                ws.onclose = (event) => {
                    logAdd(`🔴 WebSocket закрыт: ${event.code}`);
                    handleDisconnect(event.code);
                };
                
                ws.onerror = (error) => {
                    logAdd(`❌ WebSocket ошибка: ${error.message || 'Неизвестная'}`);
                    handleDisconnect(1006);
                };
                
            } catch (e) {
                logAdd(`❌ Ошибка WebSocket: ${e.message}`);
                handleDisconnect(1006);
            }
        }

        function handleDisconnect(code) {
            cleanup();
            
            if (code === 1006) {
                setTimeout(() => window.__zp_restartThread(), CONFIG.reconnectDelay);
            } else if (code === 1005 && dialogCount === 0) {
                status = "badproxy";
                window.__zp_status = status;
                window.__zp_error = "badproxy";
                logAdd(`🚫 Остановка: плохой прокси`);
            } else {
                status = "stop";
                window.__zp_status = status;
                logAdd(`🛑 Остановка: нет диалогов`);
            }
            
            if (dialogCount < CONFIG.maxDialogs && status !== "badproxy") {
                setTimeout(reconnect, CONFIG.reconnectDelay);
            }
        }

        function cleanup() {
            if (searchTimeout) clearTimeout(searchTimeout);
            if (currentDialog.inactivityTimer) clearTimeout(currentDialog.inactivityTimer);
        }

        function reconnect() {
            if (status !== "stop" && status !== "badproxy" && dialogCount < CONFIG.maxDialogs) {
                logAdd(`🔄 Переподключение ${threadId}`);
                connect();
            }
        }

        function startSearch() {
            if (ws?.readyState === WebSocket.OPEN && dialogCount < CONFIG.maxDialogs) {
                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: эта команда может отличаться!
                ws.send(`42${ackIdCounter}["back:start_search",null]`);
                logAdd(`🔍 Поиск начат ${threadId}`);
                ackIdCounter++;
                
                status = "start";
                window.__zp_status = status;
                
                if (searchTimeout) clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    status = dialogCount === 0 ? "badproxy" : "stop";
                    window.__zp_status = status;
                    logAdd(`⏰ Таймаут поиска`);
                    if (ws?.readyState === WebSocket.OPEN) ws.close();
                }, dialogCount === 0 ? CONFIG.firstDialogTimeout : CONFIG.searchTimeout);
            }
        }

        function sendMessage(text) {
            if (ws?.readyState === WebSocket.OPEN && currentDialog.active) {
                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: формат сообщения может отличаться!
                const message = JSON.stringify(["back:send_message", {
                    text, 
                    isImage: false, 
                    peerOffline: false
                }]);
                ws.send(`42${ackIdCounter}${message}`);
                logAdd(`📤 we: ${text.substring(0, 30)}... -> ${currentDialog.peerId}`);
                ackIdCounter++;
            }
        }

        function endDialog(reason = "") {
            if (!currentDialog.active) return;
            
            const duration = Date.now() - currentDialog.startTime;
            const isSuccessful = reason.includes("триггер завершения");
            
            logAdd(`🏁 Диалог завершен ${currentDialog.peerId} | ${reason} | ${Math.round(duration/1000)}с | Успешный: ${isSuccessful}`);
            
            if (isSuccessful) {
                successfulDialogs++;
                logAdd(`🎉 Успешных диалогов: ${successfulDialogs}`);
            }
            
            currentDialog.active = false;
            dialogCount++;
            
            if (ws?.readyState === WebSocket.OPEN) {
                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: команда остановки диалога может отличаться!
                ws.send(`42${ackIdCounter}["back:stop_dialog"]`);
                ackIdCounter++;
            }
            
            cleanup();
            
            // Сброс состояния
            currentDialog = {
                active: false, peerId: null, messageCount: 0,
                startTime: null, lastMessageTime: null, inactivityTimer: null
            };
            
            if (dialogCount < CONFIG.maxDialogs) {
                setTimeout(startSearch, getRandomDelay([2000, 4000]));
            } else {
                logAdd(`🎯 Завершение работы: ${dialogCount} диалогов, ${successfulDialogs} успешных`);
                status = "stop";
                window.__zp_status = status;
                if (ws?.readyState === WebSocket.OPEN) ws.close();
            }
        }

        // === ОБРАБОТКА СООБЩЕНИЙ ===
        function handleMessage(data) {
            if (data === '40' || data.startsWith('0')) return;
            if (data === '2') return ws.send('3');

            if (data.startsWith('42')) {
                try {
                    let eventJson = data.slice(2);
                    let ackId = null;
                    
                    const ackMatch = eventJson.match(/^(\d+)(\[.*\]$)/);
                    if (ackMatch) {
                        ackId = ackMatch[1];
                        eventJson = ackMatch[2];
                    }
                    
                    const eventData = JSON.parse(eventJson);
                    handleEvent(eventData, ackId);
                } catch (e) {
                    logAdd(`❌ Ошибка парсинга: ${e.message}`);
                }
            }
        }

        function handleEvent([eventName, ...args], ackId = null) {
            switch (eventName) {
                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: названия событий могут отличаться!
                case 'front:start_dialog':
                    const userData = args[0];
                    const peerId = userData?.nickname || 'Unknown';
                    
                    if (processedPeers.includes(peerId)) {
                        logAdd(`🔄 str: ${peerId} | Повторный собеседник`);
                        endDialog("повторный собеседник");
                        return;
                    }
                    
                    processedPeers.push(peerId);
                    if (processedPeers.length > 1000) {
                        processedPeers = processedPeers.slice(-500);
                    }
                    
                    currentDialog = {
                        active: true,
                        peerId: peerId,
                        messageCount: 0,
                        startTime: Date.now(),
                        lastMessageTime: Date.now(),
                        inactivityTimer: null
                    };
                    
                    logAdd(`🎬 str: ${peerId} | Диалог начат`);
                    status = "start";
                    window.__zp_status = status;
                    
                    if (searchTimeout) clearTimeout(searchTimeout);
                    
                    currentDialog.inactivityTimer = setTimeout(() => {
                        if (currentDialog.active) {
                            endDialog("собеседник неактивен");
                        }
                    }, CONFIG.inactivityTimeout);
                    
                    if (ws?.readyState === WebSocket.OPEN) {
                        // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: команда остановки поиска может отличаться!
                        ws.send(`42${ackIdCounter}["back:stop_search",true]`);
                        ackIdCounter++;
                    }
                    break;

                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: название события может отличаться!
                case 'front:send_message':
                    if (!currentDialog.active) return;
                    
                    const messageData = args[0];
                    if (ackId && ws?.readyState === WebSocket.OPEN) {
                        ws.send(`43${ackId}[true]`);
                    }
                    
                    if (messageData?.system || messageData?.isImage) return;
                    const text = messageData?.text;
                    if (!text) return;

                    logAdd(`📥 str: ${currentDialog.peerId} | ${text.substring(0, 50)}...`);

                    currentDialog.messageCount++;
                    currentDialog.lastMessageTime = Date.now();
                    
                    // Сброс таймера неактивности
                    if (currentDialog.inactivityTimer) clearTimeout(currentDialog.inactivityTimer);
                    currentDialog.inactivityTimer = setTimeout(() => {
                        if (currentDialog.active) {
                            endDialog("собеседник неактивен");
                        }
                    }, CONFIG.inactivityTimeout);

                    // Получаем ответ от ИИ
                    const aiResult = getAIResponse(currentDialog.peerId, text);
                    
                    if (aiResult && aiResult.response) {
                        const typingDelay = getRandomDelay(CONFIG.typingDelay);
                        const responseDelay = getRandomDelay(CONFIG.responseDelay);
                        
                        setTimeout(() => {
                            if (currentDialog.active && ws?.readyState === WebSocket.OPEN) {
                                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: команда typing может отличаться!
                                ws.send(`42${ackIdCounter}["back:start_typing"]`);
                                ackIdCounter++;
                                
                                setTimeout(() => {
                                    if (currentDialog.active) {
                                        sendMessage(aiResult.response);
                                        
                                        // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: команда остановки typing может отличаться!
                                        ws.send(`42${ackIdCounter}["back:stop_typing"]`);
                                        ackIdCounter++;
                                        
                                        // Проверяем на завершение
                                        if (aiResult.shouldEnd) {
                                            setTimeout(() => {
                                                endDialog("триггер завершения в ответе ИИ");
                                            }, 2000);
                                        }
                                    }
                                }, responseDelay);
                            }
                        }, typingDelay);
                    } else {
                        logAdd(`❌ str: ${currentDialog.peerId} | Нет ответа от ИИ`);
                    }
                    break;

                // ИЗМЕНИТЬ ПОД СВОЙ ЧАТ: названия событий могут отличаться!
                case 'front:stop_dialog':
                    if (currentDialog.active) {
                        endDialog("собеседник вышел");
                    }
                    break;

                case 'front:peer_is_offline':
                case 'front:peer_is_inactive':
                    if (currentDialog.active) {
                        endDialog("собеседник неактивен");
                    }
                    break;
            }
        }

        // === ЗАПУСК БОТА ===
        logAdd(`🚀 Запуск бота ${threadId} | Модель: ${CONFIG.model}`);
        status = "start";
        window.__zp_status = status;
        connect();

    } catch (e) {
        console.error("❌ Критическая ошибка:", e);
        logAdd(`❌ Критическая ошибка: ${e.message}`);
        status = "stop";
        window.__zp_status = status;
        window.__zp_error = e.message;
    }
})();

// =============================================================================
// ИНСТРУКЦИЯ ПО АДАПТАЦИИ ПОД НОВЫЙ ЧАТ:
// =============================================================================
// 
// 1. Измените CONFIG.server на адрес вашего WebSocket сервера
// 
// 2. Найдите и измените следующие команды WebSocket:
//    - "back:start_search" -> команда начала поиска в вашем чате
//    - "back:stop_search" -> команда остановки поиска
//    - "back:send_message" -> команда отправки сообщения
//    - "back:stop_dialog" -> команда завершения диалога
//    - "back:start_typing" -> команда начала набора текста
//    - "back:stop_typing" -> команда остановки набора текста
// 
// 3. Найдите и измените следующие события:
//    - "front:start_dialog" -> событие начала диалога
//    - "front:send_message" -> событие получения сообщения
//    - "front:stop_dialog" -> событие завершения диалога
//    - "front:peer_is_offline" -> событие офлайн собеседника
//    - "front:peer_is_inactive" -> событие неактивности собеседника
// 
// 4. Проверьте структуру объектов userData и messageData
// 
// 5. Настройте переменные ZennoPoster:
//    - {-Variable.chatAuth-} = "ваш_токен_авторизации"
//    - {-Variable.model-} = "rus_girl_1" (или другая модель)
// 
// 6. При необходимости добавьте дополнительные триггеры в END_TRIGGERS
// 
// 7. Протестируйте на одном потоке перед массовым запуском
// 
// =============================================================================