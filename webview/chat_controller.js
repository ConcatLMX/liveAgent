/**
 * Live Agent 聊天界面JavaScript核心逻辑
 * 处理消息显示、用户输入、Markdown渲染等功能
 */

// 全局变量
let messageCounter = 0;
let isThinking = false;
let currentThinkingElement = null;

// Markdown转换器（简易版）
function convertMarkdown(text) {
    if (!text) return '';
    
    // 转义HTML
    text = text.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/"/g, '&quot;')
               .replace(/'/g, '&#x27;');
    
    // 代码块（三个反引号）
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
        return `<div class="code-block">
            <div class="code-header">${lang || 'code'}</div>
            <pre><code>${code.trim()}</code></pre>
        </div>`;
    });
    
    // 行内代码（单个反引号）
    text = text.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    
    // 标题处理（需要在换行之前处理）
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // 加粗
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // 斜体
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    
    // 无序列表
    text = text.replace(/^[\*\-\+] (.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // 有序列表
    text = text.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    
    // 引用块
    text = text.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
    
    // 段落处理（双换行变成段落）
    text = text.replace(/\n\n/g, '</p><p>');
    text = '<p>' + text + '</p>';
    
    // 单换行
    text = text.replace(/\n/g, '<br>');
    
    // 清理空段落
    text = text.replace(/<p><\/p>/g, '');
    text = text.replace(/<p><br><\/p>/g, '');
    
    return text;
}

// 创建消息元素
function createMessageElement(content, isUser = false, isThinking = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'} ${isThinking ? 'thinking' : ''}`;
    messageDiv.id = `message-${++messageCounter}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    if (isThinking) {
        messageContent.innerHTML = `
            <div class="thinking-animation">
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
            </div>
        `;
        currentThinkingElement = messageDiv;
    } else {
        if (isUser) {
            messageContent.textContent = content;
        } else {
            messageContent.innerHTML = convertMarkdown(content);
        }
    }
    
    messageDiv.appendChild(messageContent);
    
    // 添加时间戳
    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    timestamp.textContent = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
    });
    messageDiv.appendChild(timestamp);
    
    return messageDiv;
}

// 滚动到底部
function scrollToBottom() {
    const container = document.getElementById('chat-container');
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 100);
}

// 主要的聊天接口对象
window.chatInterface = {
    // 添加消息
    addMessage: function(content, isUser = false, isThinking = false) {
        console.log(`添加消息: ${content}, 用户: ${isUser}, 思考: ${isThinking}`);
        
        const container = document.getElementById('chat-container');
        if (!container) {
            console.error('找不到聊天容器');
            return null;
        }
        
        const messageElement = createMessageElement(content, isUser, isThinking);
        container.appendChild(messageElement);
        
        // 添加动画效果
        messageElement.style.opacity = '0';
        messageElement.style.transform = 'translateY(20px)';
        setTimeout(() => {
            messageElement.style.transition = 'all 0.3s ease';
            messageElement.style.opacity = '1';
            messageElement.style.transform = 'translateY(0)';
        }, 10);
        
        scrollToBottom();
        
        // 如果启用了数学公式渲染
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise([messageElement]).catch(function(err) {
                console.log('MathJax渲染错误:', err);
            });
        }
        
        return messageElement;
    },
    
    // 清空聊天记录
    clearChat: function() {
        console.log('清空聊天记录');
        const container = document.getElementById('chat-container');
        if (container) {
            container.innerHTML = '';
            messageCounter = 0;
            isThinking = false;
            currentThinkingElement = null;
        }
    },
    
    // 移除思考气泡
    removeThinkingBubble: function() {
        console.log('移除思考气泡');
        if (currentThinkingElement) {
            currentThinkingElement.style.transition = 'all 0.3s ease';
            currentThinkingElement.style.opacity = '0';
            currentThinkingElement.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                if (currentThinkingElement && currentThinkingElement.parentNode) {
                    currentThinkingElement.parentNode.removeChild(currentThinkingElement);
                }
                currentThinkingElement = null;
                isThinking = false;
            }, 300);
        }
    },
    
    // 设置AI处理状态
    setAIProcessing: function(processing) {
        console.log(`设置AI处理状态: ${processing}`);
        if (processing && !isThinking) {
            this.addMessage('', false, true);  // 空内容，只显示动效
            isThinking = true;
        } else if (!processing && isThinking) {
            this.removeThinkingBubble();
        }
    },
    
    // 加载历史消息
    loadHistory: function(messages) {
        console.log('加载历史消息:', messages);
        this.clearChat();
        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                const isUser = msg.role === 'user' || msg.sender === 'user';
                this.addMessage(msg.content, isUser, false);
            });
        }
    }
};

// 输入处理
function setupInputHandling() {
    console.log('🎛️ [INPUT_SETUP] ========== 设置输入处理开始 ==========');
    
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    
    if (!messageInput || !sendButton) {
        console.log('❌ [INPUT_ERROR] 找不到输入元素');
        return;
    }
    
    console.log('📝 [INPUT_FOUND] 输入元素找到，开始绑定事件');
    
    // 检查是否已经绑定过事件（防止重复绑定）
    if (messageInput.hasAttribute('data-events-bound')) {
        console.log('⚠️ [DUPLICATE_BINDING] 事件已绑定，跳过重复绑定');
        return;
    }
    
    // 输入框事件 - 使用多种事件确保实时响应
    console.log('⌨️ [INPUT_EVENT] 绑定输入框事件');
    
    // input事件 - 主要的内容变化事件
    messageInput.addEventListener('input', function() {
        const hasText = this.value.trim().length > 0;
        sendButton.disabled = !hasText;
        sendButton.style.opacity = hasText ? '1' : '0.5';
        
        // 如果完全清空则重置，否则检查行数变化
        if (!this.value) {
            resetInputHeight(this);
        } else {
            adjustInputHeight(this);
        }
    });
    
    // propertychange事件 - IE兼容性（虽然不太需要，但确保兼容性）
    messageInput.addEventListener('propertychange', function() {
        adjustInputHeight(this);
    });

    // 监听删除和粘贴事件
    console.log('⌨️ [PASTE_DELETE_EVENT] 绑定粘贴和删除事件');
    messageInput.addEventListener('paste', function() {
        // 粘贴后需要延迟调整高度，等待内容更新
        setTimeout(() => adjustInputHeight(this), 0);
    });
    
    messageInput.addEventListener('cut', function() {
        // 剪切后需要延迟调整高度
        setTimeout(() => adjustInputHeight(this), 0);
    });
    
    // 键盘事件
    console.log('⌨️ [KEYBOARD_EVENT] 绑定键盘事件');
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Shift+Enter 换行，不做处理，但需要调整高度
                setTimeout(() => adjustInputHeight(this), 0);
                return;
            } else {
                // Enter 发送消息
                e.preventDefault();
                console.log('⌨️ [ENTER_PRESSED] 回车键发送消息');
                sendMessage();
            }
        }
        
        // 对于删除键，立即进行一次快速调整预测
        if (e.key === 'Backspace' || e.key === 'Delete') {
            setTimeout(() => adjustInputHeight(this), 0);
        }
    });
    
    // 键盘释放事件 - 只在影响行数的操作后调整
    console.log('⌨️ [KEYUP_EVENT] 绑定键盘释放事件');
    messageInput.addEventListener('keyup', function(e) {
        // 只在可能影响行数的操作后调整高度
        if (e.key === 'Backspace' || e.key === 'Delete' || e.key === 'Enter' || e.key === 'Cut') {
            adjustInputHeight(this);
        }
    });
    
    // 发送按钮点击 - 只在这里绑定一次
    console.log('🔘 [BUTTON_EVENT] 绑定发送按钮点击事件');
    sendButton.addEventListener('click', function(e) {
        e.preventDefault(); // 防止表单提交
        console.log('🖱️ [BUTTON_CLICKED] 发送按钮被点击');
        sendMessage();
    });
    
    // 标记事件已绑定
    messageInput.setAttribute('data-events-bound', 'true');
    sendButton.setAttribute('data-events-bound', 'true');
    
    // 初始化按钮位置
    console.log('🎯 [INIT_POSITION] 初始化按钮位置');
    adjustInputHeight(messageInput);
    
    // 聚焦到输入框
    console.log('🎯 [FOCUS] 聚焦到输入框');
    messageInput.focus();
    
    console.log('🎛️ [INPUT_SETUP] ========== 设置输入处理完成 ==========');
}

// 重置输入框到最小高度（用于清空时）
function resetInputHeight(textarea) {
    const minHeight = 28; // 2倍行距的最小高度
    textarea.style.height = minHeight + 'px';
    textarea.style.overflowY = 'hidden';
    
    // 调整按钮位置
    adjustButtonPosition(minHeight);
    console.log(`🔄 [HEIGHT_RESET] 输入框已重置到最小高度: ${minHeight}px`);
}

// 动态调整输入框高度
function adjustInputHeight(textarea) {
    console.log('📏 [HEIGHT_ADJUST] 开始调整输入框高度');
    
    // 保存当前的滚动位置和焦点状态
    const scrollTop = textarea.scrollTop;
    const selectionStart = textarea.selectionStart;
    const selectionEnd = textarea.selectionEnd;
    
    const minHeight = 28; // 2倍行距 (14px * 2)
    const maxHeight = 112; // 8倍行距 (14px * 8)
    
    // 临时设置为auto以获取真实的scrollHeight
    const originalHeight = textarea.style.height;
    textarea.style.height = 'auto';
    let scrollHeight = textarea.scrollHeight;
    
    // 如果没有内容，使用最小高度
    if (!textarea.value.trim()) {
        scrollHeight = minHeight;
    }
    
    // 计算新高度
    let newHeight = Math.max(minHeight, Math.min(scrollHeight, maxHeight));
    
    // 获取当前高度（用于比较是否需要更新）
    const currentHeight = parseInt(originalHeight) || minHeight;
    
    // 只有当高度确实需要改变时才更新（避免不必要的DOM操作）
    if (Math.abs(newHeight - currentHeight) > 1) { // 允许1px的误差
        // 直接设置新高度，无动画
        textarea.style.height = newHeight + 'px';
        
        console.log(`📏 [HEIGHT_ADJUSTED] 高度变化: ${currentHeight}px -> ${newHeight}px (scrollHeight: ${scrollHeight}px)`);
        
        // 调整按钮位置到输入框中间高度
        adjustButtonPosition(newHeight);
    } else {
        // 恢复原始高度（如果没有变化）
        textarea.style.height = originalHeight;
    }
    
    // 动态滚动条控制
    if (scrollHeight > maxHeight) {
        textarea.style.overflowY = 'auto';
    } else {
        textarea.style.overflowY = 'hidden';
    }
    
    // 恢复滚动位置和焦点
    textarea.scrollTop = scrollTop;
    textarea.setSelectionRange(selectionStart, selectionEnd);
}

// 调整按钮位置到输入框中间高度
function adjustButtonPosition(inputHeight) {
    const sendButton = document.getElementById('send-button');
    if (sendButton) {
        // 检测是否为移动设备
        const isMobile = window.innerWidth <= 600;
        const buttonHeight = isMobile ? 38 : 42; // 根据屏幕大小选择按钮高度
        
        // 计算输入框的一半高度，并减去按钮高度的一半，使按钮居中对齐
        const offset = Math.max(0, (inputHeight - buttonHeight) / 2);
        sendButton.style.marginBottom = offset + 'px';
        console.log(`🔘 [BUTTON_POSITION] 按钮位置调整: margin-bottom: ${offset}px (输入框高度: ${inputHeight}px, 移动端: ${isMobile})`);
    }
}

// 发送消息
function sendMessage() {
    // ================== 防重复点击检查 ==================
    let sendButton = document.getElementById('send-button');
    if (sendButton && sendButton.hasAttribute('data-sending')) {
        console.log('⚠️ [DUPLICATE_CLICK] 检测到重复点击，忽略此次调用');
        return;
    }
    
    // ================== 最开始的日志 ==================
    console.log('🔥🔥🔥 [BUTTON_CLICK] 发送按钮被点击！开始执行sendMessage函数 🔥🔥🔥');
    console.log('⏰ [TIMESTAMP]', new Date().toISOString());
    
    const messageInput = document.getElementById('message-input');
    
    console.log('🔍 [DOM_CHECK] 检查DOM元素...');
    console.log('📝 [INPUT_ELEMENT]', messageInput ? '✅ 找到' : '❌ 未找到');
    console.log('🔘 [BUTTON_ELEMENT]', sendButton ? '✅ 找到' : '❌ 未找到');
    
    if (!messageInput || !sendButton) {
        console.log('❌ [ERROR] DOM元素缺失，终止执行');
        return;
    }
    
    const message = messageInput.value.trim();
    console.log('📄 [MESSAGE_CONTENT] 原始输入:', JSON.stringify(messageInput.value));
    console.log('� [MESSAGE_TRIMMED] 清理后内容:', JSON.stringify(message));
    console.log('📏 [MESSAGE_LENGTH] 消息长度:', message.length);
    
    if (!message) {
        console.log('⚠️ [VALIDATION] 消息为空，终止执行');
        return;
    }
    
    console.log('✅ [VALIDATION] 消息验证通过，开始处理流程');
    
    // ================== 设置发送锁定状态 ==================
    sendButton.setAttribute('data-sending', 'true');
    console.log('🔒 [SENDING_LOCK] 设置发送锁定状态，防止重复点击');
    
    // ================== UI更新阶段 ==================
    console.log('� [UI_UPDATE] 开始更新界面状态...');
    
    // 清空输入框
    messageInput.value = '';
    console.log('🧹 [INPUT_CLEAR] 输入框已清空');
    
    // 重置输入框到最小高度
    resetInputHeight(messageInput);
    console.log('📏 [HEIGHT_RESET] 输入框高度已重置到最小值');
    
    sendButton.disabled = true;
    sendButton.style.opacity = '0.5';
    console.log('🔒 [BUTTON_DISABLE] 发送按钮已禁用');
    
    // ================== 添加用户消息到界面 ==================
    console.log('💬 [UI_MESSAGE] 开始添加用户消息到界面...');
    
    try {
        if (window.chatInterface && typeof window.chatInterface.addMessage === 'function') {
            console.log('✅ [CHAT_INTERFACE] chatInterface可用');
            window.chatInterface.addMessage(message, true, false);
            console.log('✅ [USER_MESSAGE_ADDED] 用户消息已添加到界面');
        } else {
            console.log('❌ [CHAT_INTERFACE] chatInterface不可用');
            // 调试信息已移除
        }
    } catch (error) {
        console.log('❌ [UI_ERROR] 添加用户消息失败:', error);
    }
    
    // ================== 后端通信阶段 ==================
    console.log('🌉 [BACKEND_COMM] 开始与后端通信...');
    
    // 方法1：尝试使用Bridge（QWebChannel）
    console.log('🔍 [BRIDGE_CHECK] 检查Bridge可用性...');
    console.log('🔍 [BRIDGE_OBJECT] window.bridge:', typeof window.bridge);
    
    if (window.bridge && typeof window.bridge.send_message === 'function') {
        console.log('🌉 [BRIDGE_AVAILABLE] Bridge可用，使用QWebChannel方式');
        try {
            console.log('📡 [BRIDGE_SEND] 调用bridge.send_message...');
            window.bridge.send_message(message);
            console.log('✅ [BRIDGE_SUCCESS] Bridge消息发送成功');
        } catch (error) {
            console.log('❌ [BRIDGE_ERROR] Bridge发送失败:', error);
            console.log('🔄 [FALLBACK] 回退到控制台方式');
            sendViaConsole(message);
        }
    } else {
        console.log('⚠️ [BRIDGE_UNAVAILABLE] Bridge不可用，使用控制台方式');
        sendViaConsole(message);
    }
    
    // ================== 最终清理 ==================
    console.log('🎯 [CLEANUP] 执行清理工作...');
    
    // 延迟恢复按钮状态，防止快速重复点击
    setTimeout(() => {
        try {
            sendButton.removeAttribute('data-sending');
            sendButton.disabled = false;
            sendButton.style.opacity = '1';
            messageInput.focus();
            console.log('🎯 [STATE_RESTORED] 按钮状态和焦点已恢复');
        } catch (error) {
            console.log('❌ [RESTORE_ERROR] 恢复状态失败:', error);
        }
    }, 1000); // 1秒后恢复，防止快速重复点击
    
    console.log('🏁 [COMPLETE] sendMessage函数执行完成');
    console.log('🔥🔥🔥 [BUTTON_CLICK_END] 发送按钮处理流程结束 🔥🔥🔥');
}

// 控制台发送辅助函数
function sendViaConsole(message) {
    console.log('📺 [CONSOLE_SEND] 使用控制台方式发送消息...');
    console.log('🔍 [MESSAGE_TYPE_CHECK] 检查消息类型...');
    
    if (message.startsWith('--') || message === '-s') {
        console.log('🔧 [COMMAND_DETECTED] 检测到命令类型');
        const commandMessage = `EXECUTE_COMMAND:${message}`;
        console.log('📡 [CONSOLE_OUTPUT] 发送命令:', commandMessage);
        console.log(commandMessage);
    } else {
        console.log('💬 [MESSAGE_DETECTED] 检测到普通消息类型');
        const normalMessage = `SEND_MESSAGE:${message}`;
        console.log('📡 [CONSOLE_OUTPUT] 发送消息:', normalMessage);
        console.log(normalMessage);
    }
    
    console.log('✅ [CONSOLE_SEND_COMPLETE] 控制台发送完成');
}

// 添加系统消息
function addSystemMessage(content) {
    const chatContainer = document.getElementById('chat-container');
    if (!chatContainer) return;
    
    const messageEl = document.createElement('div');
    messageEl.className = 'message-container system-message';
    messageEl.innerHTML = `
        <div class="message-content">
            <div class="system-text">${content}</div>
        </div>
    `;
    
    chatContainer.appendChild(messageEl);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 [PAGE_LOAD] 页面DOM加载完成，开始初始化...');
    console.log('⏰ [TIMESTAMP]', new Date().toISOString());
    
    // 检查必要的DOM元素
    console.log('🔍 [DOM_INIT] 检查必要的DOM元素...');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatContainer = document.getElementById('chat-container');
    
    console.log('📝 [INPUT_CHECK]', messageInput ? '✅ 找到' : '❌ 未找到');
    console.log('🔘 [BUTTON_CHECK]', sendButton ? '✅ 找到' : '❌ 未找到');
    console.log('📋 [CONTAINER_CHECK]', chatContainer ? '✅ 找到' : '❌ 未找到');
    
    if (!chatContainer || !messageInput || !sendButton) {
        console.log('❌ [DOM_ERROR] 关键DOM元素缺失，初始化失败');
        return;
    }
    
    // 设置输入处理
    console.log('🎨 [INPUT_SETUP] 设置输入处理...');
    setupInputHandling();
    
    // 确保chatInterface已正确初始化
    if (window.chatInterface) {
        console.log('✅ [CHAT_READY] chatInterface已初始化');
    } else {
        console.log('❌ [CHAT_ERROR] chatInterface初始化失败');
    }
    
    // 初始化通信系统
    console.log('🌉 [COMM_INIT] 开始初始化通信系统...');
    initializeCommunication();
    
    console.log('🏁 [INIT_COMPLETE] DOM初始化完成');
});

// 通信系统初始化
function initializeCommunication() {
    console.log('🌉 [COMM_START] ========== 通信系统初始化开始 ==========');
    
    // 步骤1：检查Qt环境
    console.log('🔍 [QT_CHECK] 步骤1: 检查Qt环境...');
    console.log('🔍 [QT_OBJECT] typeof qt:', typeof qt);
    console.log('🔍 [QT_TRANSPORT] qt.webChannelTransport:', typeof qt !== 'undefined' ? (qt.webChannelTransport ? '✅ 可用' : '❌ 不可用') : 'qt未定义');
    
    // 步骤2：检查QWebChannel库
    console.log('🔍 [QWEB_LIB_CHECK] 步骤2: 检查QWebChannel库...');
    console.log('🔍 [QT_WEBCHANNEL] typeof QWebChannel:', typeof QWebChannel);
    
    // 步骤3：尝试初始化QWebChannel
    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
        console.log('✅ [QT_AVAILABLE] Qt环境可用');
        
        if (typeof QWebChannel !== 'undefined') {
            console.log('✅ [QWEB_LIB_AVAILABLE] QWebChannel库可用');
            initializeQWebChannel();
        } else {
            console.log('❌ [QWEB_LIB_MISSING] QWebChannel库未定义，尝试加载...');
            // 尝试动态加载QWebChannel
            loadQWebChannelScript();
        }
    } else {
        console.log('⚠️ [QT_UNAVAILABLE] Qt环境不可用，使用控制台通信');
        initializeConsoleMode();
    }
    
    console.log('🌉 [COMM_END] ========== 通信系统初始化完成 ==========');
}

// 初始化QWebChannel
function initializeQWebChannel() {
    console.log('🚀 [QWEB_INIT] ========== QWebChannel初始化开始 ==========');
    
    try {
        console.log('� [QWEB_CREATE] 创建QWebChannel实例...');
        new QWebChannel(qt.webChannelTransport, function(channel) {
            console.log('🎉 [QWEB_SUCCESS] QWebChannel连接成功！');
            console.log('🔍 [CHANNEL_OBJECTS] 可用对象:', Object.keys(channel.objects));
            
            if (channel.objects.bridge) {
                console.log('🌉 [BRIDGE_FOUND] 找到Bridge对象！');
                window.bridge = channel.objects.bridge;
                console.log('✅ [BRIDGE_READY] Bridge已设置为全局对象');
                
                // 测试Bridge连接
                if (typeof window.bridge.send_message === 'function') {
                    console.log('✅ [BRIDGE_FUNCTION] Bridge.send_message函数可用');
                    console.log('🎯 [COMMUNICATION_MODE] 通信模式: QWebChannel Bridge');
                } else {
                    console.log('❌ [BRIDGE_FUNCTION] Bridge.send_message函数不可用');
                    console.log('🔄 [FALLBACK] 回退到控制台通信模式');
                    initializeConsoleMode();
                }
            } else {
                console.log('❌ [BRIDGE_MISSING] 未找到Bridge对象');
                console.log('🔍 [AVAILABLE_OBJECTS] 可用对象列表:', Object.keys(channel.objects));
                console.log('🔄 [FALLBACK] 回退到控制台通信模式');
                initializeConsoleMode();
            }
        });
    } catch (error) {
        console.log('❌ [QWEB_ERROR] QWebChannel初始化失败:', error);
        console.log('🔄 [FALLBACK] 回退到控制台通信模式');
        initializeConsoleMode();
    }
    
    console.log('🚀 [QWEB_INIT] ========== QWebChannel初始化结束 ==========');
}

// 尝试加载QWebChannel脚本
function loadQWebChannelScript() {
    console.log('📦 [SCRIPT_LOAD] 尝试加载QWebChannel脚本...');
    
    // 创建script标签加载qwebchannel.js
    const script = document.createElement('script');
    script.src = './qwebchannel.js';
    script.onload = function() {
        console.log('✅ [SCRIPT_LOADED] QWebChannel脚本加载成功');
        // 重新检查QWebChannel
        if (typeof QWebChannel !== 'undefined') {
            console.log('✅ [QWEB_NOW_AVAILABLE] QWebChannel现在可用');
            initializeQWebChannel();
        } else {
            console.log('❌ [QWEB_STILL_MISSING] QWebChannel仍然不可用');
            initializeConsoleMode();
        }
    };
    script.onerror = function() {
        console.log('❌ [SCRIPT_ERROR] QWebChannel脚本加载失败');
        initializeConsoleMode();
    };
    document.head.appendChild(script);
}

// 初始化控制台通信模式
function initializeConsoleMode() {
    console.log('📺 [CONSOLE_MODE] ========== 控制台通信模式初始化 ==========');
    window.bridge = null;
    console.log('✅ [CONSOLE_READY] 控制台模式就绪');
    console.log('🎯 [COMMUNICATION_MODE] 通信模式: Console Log');
    console.log('📺 [CONSOLE_MODE] ========== 控制台通信模式完成 ==========');
}

// 确保页面完全加载后再初始化全局绑定
window.addEventListener('load', function() {
    console.log('页面完全加载完成');
    
    // 导出到全局作用域（确保Python能访问）
    if (window.chatInterface) {
        window.addMessage = window.chatInterface.addMessage.bind(window.chatInterface);
        window.clearChat = window.chatInterface.clearChat.bind(window.chatInterface);
        window.removeThinkingBubble = window.chatInterface.removeThinkingBubble.bind(window.chatInterface);
        window.setAIProcessing = window.chatInterface.setAIProcessing.bind(window.chatInterface);
        console.log('全局函数绑定完成');
    }
});

console.log('🚀 [SCRIPT_LOADED] Live Agent 聊天界面脚本加载完成');
