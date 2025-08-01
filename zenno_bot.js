(function () {
    try {
        // === КОНФИГУРАЦИЯ ===
        const CONFIG = {
            chatAuth: "{-Variable.chatAuth-}",
            model: "{-Variable.model-}",
            server: "wss://noname.chat/socket.io/",
            maxDialogs: 20,
            inactivityTimeout: 15000, // Изменено с 30000 на 15000 (15 секунд)
            typingDelay: [2000, 6000],
            responseDelay: [2000, 6000],
            searchTimeout: 30000,
            firstDialogTimeout: 30000,
            localApiUrl: "http://127.0.0.1:8001/api/chat",
            alternativeApiUrl: "http://192.168.0.49:8001/api/chat",
            maxRestoreAttempts: 1,
            reconnectDelay: [10000, 30000],
            maxReconnectAttempts: 5
        };

        // === ЧЁРНЫЙ СПИСОК ===
        const BLACKLIST = [
            "эй ты", "ты бот", "То самое 18+ Ищи в тг: SNAROGA","спам"
        ];

        // === ПРОВЕРКА КОНФИГУРАЦИИ ===
        if (CONFIG.chatAuth.includes("{-Variable") || CONFIG.model.includes("{-Variable") || CONFIG.server.includes("{-Variable")) {
            throw new Error("Не заменены переменные ZennoPoster! Установите chatAuth, model и server.");
        }

        // === СОСТОЯНИЕ БОТА ===
        let log = [];
        let processedPeers = [];
        let inactivePeers = new Set();
        let currentDialog = {
            active: false,
            peerId: null,
            chatId: null,
            messageCount: 0,
            startTime: null,
            lastMessageTime: null,
            inactivityTimer: null
        };
        let ws = null;
        let status = "start";
        let dialogCount = 0;
        let successfulDialogs = 0;
        let ackIdCounter = Math.floor(Date.now() / 1000) + Math.floor(Math.random() * 100000);
        let searchTimeout = null;
        let sessionId = null;
        let userConfig = null;
        let searchLimit = { current: 0, max: 50 };
        let isTyping = false;
        let restoreAttempts = {};
        let reconnectAttempts = 0;
        const threadId = Math.random().toString(36).substr(2, 5);

        // === УТИЛИТЫ ===
        function logAdd(msg) {
            const time = new Date().toLocaleTimeString('ru-RU');
            const line = `[${time}] [${threadId}] ${msg}`;
            log.push(line);
            
            if (log.length > 1000) {
                logAdd(`ℹ️ Лог обрезан до 1000 строк, удалено ${log.length - 1000} записей`);
                log = log.slice(-1000);
            }
            
            window.__zp_log = log.join("\n");
            console.log(line);
        }

        function normalize(text) {
            return text.toLowerCase().replace(/[^a-zа-я0-9\s@./]/gi, '');
        }

        function getRandomDelay(range) {
            return Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
        }

        function hasBlacklistTrigger(text) {
            const cleaned = normalize(text);
            const foundTrigger = BLACKLIST.find(trigger => cleaned.includes(trigger));
            if (foundTrigger) {
                logAdd(`str: ${currentDialog.peerId} | 🚫 Обнаружен триггер чёрного списка: ${foundTrigger}`);
                return true;
            }
            return false;
        }

        function startTyping() {
            if (ws?.readyState === WebSocket.OPEN && currentDialog.active && !isTyping) {
                isTyping = true;
                ws.send(`42${ackIdCounter}["back:start_typing"]`);
                logAdd(`📝 Начинаем печатать для ${currentDialog.peerId} | ackId: ${ackIdCounter}`);
                ackIdCounter++;
            }
        }

        function stopTyping() {
            if (ws?.readyState === WebSocket.OPEN && currentDialog.active && isTyping) {
                isTyping = false;
                ws.send(`42${ackIdCounter}["back:stop_typing"]`);
                logAdd(`✋ Прекращаем печатать для ${currentDialog.peerId} | ackId: ${ackIdCounter}`);
                ackIdCounter++;
            }
        }

        // === ФУНКЦИЯ ЗАПРОСА К ИИ ===
        function getAIResponse(peerId, message) {
            try {
                logAdd(`str: ${peerId} | Запрос к ИИ (модель: ${CONFIG.model}, user_id: ${peerId})`);
                
                const requestBody = JSON.stringify({
                    model: CONFIG.model,
                    user_id: peerId,
                    message: message
                });

                let response = null;
                let apiUrl = CONFIG.localApiUrl;
                
                try {
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

                logAdd(`str: ${currentDialog.peerId} | Ответ: ${data.response.substring(0, 50)}`);
                
                return { 
                    response: data.response, 
                    isLast: data.is_last === true 
                };
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
                    reconnectAttempts = 0;
                    ws.send('40');
                    logAdd(`✅ WebSocket открыт ${threadId} | Отправлено: 40`);
                };
                
                ws.onmessage = (event) => {
                    logAdd(`📨 WebSocket получил: ${event.data.substring(0, 100)}`);
                    handleMessage(event.data);
                };
                
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
            status = "stop";
            window.__zp_status = status;
            window.__zp_error = `WebSocket закрыт с кодом ${code}`;
            logAdd(`🛑 Остановка: WebSocket закрыт с кодом ${code}`);

            if (reconnectAttempts < CONFIG.maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = getRandomDelay(CONFIG.reconnectDelay);
                logAdd(`🔄 Попытка переподключения ${reconnectAttempts}/${CONFIG.maxReconnectAttempts} через ${delay}мс`);
                setTimeout(connect, delay);
            } else {
                logAdd(`🚫 Превышен лимит попыток переподключения (${CONFIG.maxReconnectAttempts})`);
            }
        }

        function cleanup() {
            if (searchTimeout) clearTimeout(searchTimeout);
            if (currentDialog.inactivityTimer) clearTimeout(currentDialog.inactivityTimer);
            isTyping = false;
            currentDialog.active = false;
        }

        function sendMessage(text) {
            if (ws?.readyState === WebSocket.OPEN && currentDialog.active) {
                const message = JSON.stringify(["back:send_message", {
                    text, 
                    isImage: false, 
                    peerOffline: false
                }]);
                ws.send(`42${ackIdCounter}${message}`);
                logAdd(`📤 we: ${text.substring(0, 30)} -> ${currentDialog.peerId} | ackId: ${ackIdCounter}`);
                ackIdCounter++;
            } else {
                logAdd(`🚫 Не отправлено сообщение: WebSocket закрыт или диалог неактивен`);
            }
        }

        function startSearch() {
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(`42${ackIdCounter}["back:start_search",null]`);
                logAdd(`🔍 Начинаем поиск собеседника | ackId: ${ackIdCounter}`);
                ackIdCounter++;
                searchTimeout = setTimeout(() => {
                    if (!currentDialog.active) {
                        logAdd(`⏳ Таймаут поиска истек`);
                        endDialog("таймаут поиска");
                    }
                }, CONFIG.searchTimeout);
            }
        }

        function endDialog(reason = "") {
            if (!currentDialog.active) {
                if (dialogCount < CONFIG.maxDialogs && ws?.readyState === WebSocket.OPEN) {
                    setTimeout(() => {
                        logAdd(`⏳ Ожидание нового диалога ${threadId}`);
                        ws.send(`42${ackIdCounter}["back:init"]`);
                        logAdd(`📤 Реинициализация: back:init | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                    }, getRandomDelay([4000, 12000]));
                }
                return;
            }
            
            const duration = Date.now() - currentDialog.startTime;
            const isSuccessful = reason.includes("финальное сообщение");
            
            logAdd(`🏁 Диалог завершен ${currentDialog.peerId} | ${reason} | ${Math.round(duration/1000)}с | Успешный: ${isSuccessful}`);
            
            if (isSuccessful) {
                successfulDialogs++;
                logAdd(`🎉 Успешных диалогов: ${successfulDialogs}`);
            }
            
            stopTyping();
            currentDialog.active = false;
            dialogCount++;
            
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(`42${ackIdCounter}["back:stop_dialog"]`);
                logAdd(`📤 Отправлено: back:stop_dialog | ackId: ${ackIdCounter}`);
                ackIdCounter++;
            }
            
            cleanup();
            
            currentDialog = {
                active: false,
                peerId: null,
                chatId: null,
                messageCount: 0,
                startTime: null,
                lastMessageTime: null,
                inactivityTimer: null
            };
            
            if (dialogCount < CONFIG.maxDialogs) {
                setTimeout(() => {
                    logAdd(`⏳ Ожидание нового диалога ${threadId}`);
                    if (ws?.readyState === WebSocket.OPEN) {
                        ws.send(`42${ackIdCounter}["back:init"]`);
                        logAdd(`📤 Реинициализация: back:init | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                    }
                }, getRandomDelay([4000, 12000]));
            } else {
                logAdd(`🎯 Завершение работы: ${dialogCount} диалогов, ${successfulDialogs} успешных`);
                status = "stop";
                window.__zp_status = status;
                if (ws?.readyState === WebSocket.OPEN) ws.close();
            }
        }

        // === ОБРАБОТКА СООБЩЕНИЙ ===
        function handleMessage(data) {
            if (ws?.readyState !== WebSocket.OPEN) {
                logAdd(`🚫 Игнорируем сообщение: WebSocket закрыт (readyState: ${ws?.readyState})`);
                return;
            }

            if (data === '40') {
                ws.send(`42${ackIdCounter}["back:init"]`);
                logAdd(`📤 Отправлено: back:init | ackId: ${ackIdCounter}`);
                ackIdCounter++;
                return;
            }
            
            if (data.startsWith('40{')) {
                try {
                    const sessionData = JSON.parse(data.slice(2));
                    if (sessionData.sid) {
                        sessionId = sessionData.sid;
                        logAdd(`🔐 Получен session ID: ${sessionData.sid}`);
                        
                        ws.send(`42${ackIdCounter}["back:init"]`);
                        logAdd(`📤 Отправлено: back:init после session ID | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                    }
                } catch (e) {
                    logAdd(`❌ Ошибка парсинга session ID: ${e.message}`);
                }
                return;
            }
            
            if (data === '2') {
                ws.send('3');
                logAdd(`💓 Ping-pong: получен 2, отправлен 3`);
                return;
            }

            if (data === '41' || data.startsWith('44')) {
                logAdd(`🚨 Получен сигнал завершения сессии: ${data}`);
                if (data.includes('need refresh')) {
                    logAdd(`🚫 Обнаружен need refresh, возможно пересечение IP прокси. Останавливаем скрипт.`);
                    status = "stop";
                    window.__zp_status = status;
                    window.__zp_error = "Остановка из-за need refresh (возможное пересечение IP прокси)";
                    cleanup();
                    if (ws?.readyState === WebSocket.OPEN) {
                        ws.close();
                        logAdd(`🔴 WebSocket закрыт из-за need refresh`);
                    }
                    return;
                }
                if (ws?.readyState === WebSocket.OPEN) {
                    logAdd(`🔄 Пробуем реинициализацию без разрыва`);
                    ws.send(`42${ackIdCounter}["back:init"]`);
                    logAdd(`📤 Отправлено: back:init | ackId: ${ackIdCounter}`);
                    ackIdCounter++;
                    setTimeout(() => {
                        if (ws?.readyState !== WebSocket.OPEN) {
                            logAdd(`🔴 Соединение закрыто, инициируем переподключение`);
                            handleDisconnect(1005);
                        }
                    }, getRandomDelay([6000, 9000]));
                } else {
                    logAdd(`🔴 WebSocket закрыт, инициируем переподключение`);
                    handleDisconnect(1005);
                }
                return;
            }

            if (data.startsWith('42') || data.startsWith('43')) {
                try {
                    let eventJson = data.slice(2);
                    let ackId = null;
                    
                    const ackMatch = eventJson.match(/^(\d+)(\[.*\]$)/);
                    if (ackMatch) {
                        ackId = ackMatch[1];
                        eventJson = ackMatch[2];
                    }
                    
                    const eventData = JSON.parse(eventJson);
                    handleEvent(eventData, ackId, data.startsWith('43'));
                } catch (e) {
                    logAdd(`❌ Ошибка парсинга: ${e.message} | Data: ${data.substring(0, 100)}`);
                }
            }
        }

        function handleEvent(eventData, ackId = null, isAckResponse = false) {
            if (ws?.readyState !== WebSocket.OPEN) {
                logAdd(`🚫 Игнорируем событие ${JSON.stringify(eventData)}: WebSocket закрыт`);
                return;
            }

            if (isAckResponse) {
                logAdd(`✅ Получен ack: ${ackId} | EventData: ${JSON.stringify(eventData).substring(0, 100)}`);
                
                if (eventData && eventData[0] && typeof eventData[0] === 'object' && eventData[0].userSex !== undefined) {
                    userConfig = eventData[0];
                    logAdd(`⚙️ Конфигурация пользователя: ${JSON.stringify(userConfig)}`);
                    
                    if (userConfig.needRestoreDialog) {
                        ws.send(`42${ackIdCounter}["back:restore_dialog_with_messages"]`);
                        logAdd(`📤 Отправлено: back:restore_dialog_with_messages | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                    } else {
                        setTimeout(() => {
                            startSearch();
                        }, getRandomDelay([2000, 3000]));
                    }
                } else if (eventData && eventData[0] === "no_peer") {
                    logAdd(`🔍 Нет доступных собеседников, начинаем новый поиск`);
                    setTimeout(() => {
                        startSearch();
                    }, getRandomDelay([2000, 3000]));
                }
                return;
            }

            const [eventName, ...args] = eventData;

            switch (eventName) {
                case 'front:start_dialog':
                    const userData = args[0];
                    const peerId = userData?.nickname || 'Unknown';
                    
                    if (processedPeers.includes(peerId)) {
                        restoreAttempts[peerId] = (restoreAttempts[peerId] || 0) + 1;
                        logAdd(`🔄 str: ${peerId} | Повторный собеседник | Попытка: ${restoreAttempts[peerId]}`);
                        
                        if (restoreAttempts[peerId] >= CONFIG.maxRestoreAttempts) {
                            logAdd(`🚫 str: ${peerId} | Превышен лимит попыток восстановления (${CONFIG.maxRestoreAttempts})`);
                            inactivePeers.add(peerId);
                            ws.send(`42${ackIdCounter}["back:stop_dialog"]`);
                            logAdd(`📤 Отправлено: back:stop_dialog для ${peerId} | ackId: ${ackIdCounter}`);
                            ackIdCounter++;
                            setTimeout(() => startSearch(), getRandomDelay([2000, 3000]));
                            return;
                        }
                        
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
                        chatId: `chat_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
                        messageCount: 0,
                        startTime: Date.now(),
                        lastMessageTime: Date.now(),
                        inactivityTimer: null
                    };
                    
                    logAdd(`🎬 str: ${peerId} | Диалог начат | UserData: ${JSON.stringify(userData)}`);
                    status = "start";
                    window.__zp_status = status;
                    
                    if (searchTimeout) clearTimeout(searchTimeout);
                    
                    // Устанавливаем таймер на 15 секунд - если нет сообщений, переключаемся
                    currentDialog.inactivityTimer = setTimeout(() => {
                        if (currentDialog.active) {
                            endDialog("нет сообщений в течение 15 секунд");
                        }
                    }, CONFIG.inactivityTimeout);
                    
                    if (ws?.readyState === WebSocket.OPEN) {
                        ws.send(`42${ackIdCounter}["back:stop_search",true]`);
                        logAdd(`📤 Отправлено: back:stop_search | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                    }
                    break;

                case 'front:send_message':
                    if (!currentDialog.active) return;
                    
                    const messageData = args[0];
                    
                    if (ackId && ws?.readyState === WebSocket.OPEN) {
                        ws.send(`43${ackId}[true]`);
                        logAdd(`📤 Отправлен ack: ${ackId}`);
                    }
                    
                    if (messageData?.system && messageData?.id === "remove_after_message") {
                        logAdd(`📩 str: ${currentDialog.peerId} | Получено системное сообщение: ${messageData.text}`);
                        startTyping();
                        setTimeout(() => {
                            if (currentDialog.active && ws?.readyState === WebSocket.OPEN) {
                                stopTyping();
                                sendMessage("Привет");
                                setTimeout(() => {
                                    endDialog("системное сообщение о завершении диалога");
                                }, getRandomDelay([2000, 3000]));
                            }
                        }, getRandomDelay(CONFIG.typingDelay));
                        return;
                    }
                    
                    if (messageData?.system || messageData?.isImage) return;
                    const text = messageData?.text;
                    if (!text) return;

                    logAdd(`📥 str: ${currentDialog.peerId} | ${text.substring(0, 50)}`);

                    // Проверка на чёрный список
                    if (hasBlacklistTrigger(text)) {
                        setTimeout(() => {
                            endDialog("триггер чёрного списка в сообщении собеседника");
                        }, getRandomDelay([2000, 3000]));
                        return;
                    }

                    currentDialog.messageCount++;
                    currentDialog.lastMessageTime = Date.now();
                    
                    // Обновляем таймер при получении сообщения
                    if (currentDialog.inactivityTimer) clearTimeout(currentDialog.inactivityTimer);
                    currentDialog.inactivityTimer = setTimeout(() => {
                        if (currentDialog.active) {
                            endDialog("нет сообщений в течение 15 секунд");
                        }
                    }, CONFIG.inactivityTimeout);

                    const aiResult = getAIResponse(currentDialog.peerId, text);
                    
                    if (aiResult && aiResult.response) {
                        const typingDelay = getRandomDelay(CONFIG.typingDelay);
                        const responseDelay = getRandomDelay(CONFIG.responseDelay);
                        
                        startTyping();
                        
                        setTimeout(() => {
                            if (currentDialog.active && ws?.readyState === WebSocket.OPEN) {
                                stopTyping();
                                sendMessage(aiResult.response);
                                
                                if (aiResult.isLast) {
                                    logAdd(`🏁 str: ${currentDialog.peerId} | Получен флаг is_last: true, завершаем диалог через 20-30 секунд`);
                                    setTimeout(() => {
                                        endDialog("финальное сообщение от ИИ (is_last: true)");
                                    }, getRandomDelay([20000, 30000]));
                                }
                            }
                        }, responseDelay);
                    } else {
                        logAdd(`❌ str: ${currentDialog.peerId} | Нет ответа от ИИ`);
                    }
                    break;

                case 'front:stop_dialog':
                    if (currentDialog.active) {
                        const reason = args[0] || "неизвестная причина";
                        endDialog(`собеседник завершил чат: ${reason}`);
                    }
                    break;

                case 'front:peer_is_online':
                    if (currentDialog.active) {
                        logAdd(`🟢 str: ${currentDialog.peerId} | Собеседник онлайн`);
                    }
                    break;

                case 'front:show_peer_typing':
                    if (currentDialog.active) {
                        logAdd(`⌨️ str: ${currentDialog.peerId} | Собеседник печатает`);
                    }
                    break;

                case 'front:hide_peer_typing':
                    if (currentDialog.active) {
                        logAdd(`✋ str: ${currentDialog.peerId} | Собеседник прекратил печатать`);
                    }
                    break;

                case 'front:update_search_limit':
                    const limitData = args[0];
                    if (limitData) {
                        searchLimit = limitData;
                        logAdd(`📊 Лимит поиска обновлен: ${limitData.current}/${limitData.max}`);
                        
                        if (limitData.current >= limitData.max) {
                            logAdd(`🚫 Достигнут лимит поиска!`);
                            status = "stop";
                            window.__zp_status = status;
                            if (ws?.readyState === WebSocket.OPEN) ws.close();
                        }
                    }
                    break;

                case 'front:stop_search':
                    logAdd(`🛑 Поиск остановлен`);
                    break;

                case 'front:refresh_page':
                    logAdd(`🚨 Получен front:refresh_page, проверяем состояние`);
                    if (ws?.readyState === WebSocket.OPEN) {
                        logAdd(`🔄 Пробуем реинициализацию без разрыва`);
                        ws.send(`42${ackIdCounter}["back:init"]`);
                        logAdd(`📤 Отправлено: back:init | ackId: ${ackIdCounter}`);
                        ackIdCounter++;
                        setTimeout(() => {
                            if (ws?.readyState !== WebSocket.OPEN) {
                                logAdd(`🔴 Соединение закрыто, инициируем переподключение`);
                                handleDisconnect(1005);
                            }
                        }, getRandomDelay([6000, 9000]));
                    } else {
                        logAdd(`🔴 WebSocket закрыт, инициируем переподключение`);
                        handleDisconnect(1005);
                    }
                    break;

                default:
                    logAdd(`❓ Неизвестное событие: ${eventName} | Args: ${JSON.stringify(args).substring(0, 100)}`);
                    break;
            }
        }

        // === ЗАПУСК БОТА ===
        logAdd(`🚀 Запуск адаптированного бота ${threadId} | Модель: ${CONFIG.model}`);
        logAdd(`🔢 Начальный ackIdCounter: ${ackIdCounter}`);
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