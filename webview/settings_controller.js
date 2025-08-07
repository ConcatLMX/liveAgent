/**
 * 设置窗口控制器
 * 处理设置界面的交互和数据管理
 */

class SettingsController {
    constructor() {
        this.bridge = null;
        this.config = {};
        this.emailAccounts = []; // 存储邮箱账户数据
        this.initWebChannel();
        this.initEventListeners();
    }

    /**
     * 初始化WebChannel通信
     */
    initWebChannel() {
        if (typeof qt !== 'undefined' && qt.webChannelTransport) {
            new QWebChannel(qt.webChannelTransport, (channel) => {
                this.bridge = channel.objects.bridge;
                console.log('WebChannel连接成功');
                this.loadSettings(); // 在连接成功后加载设置
            });
        } else {
            console.log('WebChannel不可用，使用模拟数据');
            this.loadMockData();
        }
    }

    /**
     * 初始化事件监听器
     */
    initEventListeners() {
        // 保存按钮
        document.getElementById('save-btn').addEventListener('click', () => {
            this.saveSettings();
        });

        // API配置编辑按钮
        document.getElementById('edit-api-config').addEventListener('click', () => {
            this.openApiConfigModal();
        });

        // 滑块值实时更新
        document.getElementById('temperature').addEventListener('input', (e) => {
            document.getElementById('temperature-value').textContent = e.target.value;
        });

        document.getElementById('cosine_similarity').addEventListener('input', (e) => {
            document.getElementById('cosine_similarity-value').textContent = e.target.value;
        });

        // 主题色选择器
        document.getElementById('theme-color').addEventListener('input', (e) => {
            this.updateThemeColor(e.target.value);
            this.updateThemeColorPreview(e.target.value);
        });

        document.getElementById('theme-color').addEventListener('change', (e) => {
            // 颜色改变时立即保存
            this.saveThemeColorOnly(e.target.value);
        });

        // 底部按钮
        document.getElementById('system-prompt-btn').addEventListener('click', () => {
            this.openSystemPromptModal();
        });

        document.getElementById('email-config-btn').addEventListener('click', () => {
            this.openEmailConfigModal();
        });

        document.getElementById('about-btn').addEventListener('click', () => {
            this.showAbout();
        });

        // 清除对话历史按钮
        document.getElementById('clear-history-btn').addEventListener('click', () => {
            this.openClearHistoryModal();
        });

        // 系统提示词弹窗事件
        this.initSystemPromptModal();
        
        // 邮箱配置弹窗事件
        this.initEmailConfigModal();
        
        // API配置弹窗事件
        this.initApiConfigModal();
        
        // 清除历史记录弹窗事件
        this.initClearHistoryModal();
    }

    /**
     * 加载设置数据
     */
    loadSettings() {
        if (this.bridge && this.bridge.getSettings) {
            this.bridge.getSettings((configArray) => {
                // 处理不同的返回格式
                let config;
                if (Array.isArray(configArray) && configArray.length > 0) {
                    // 如果是数组格式，取第一个元素
                    config = configArray[0];
                } else if (configArray && typeof configArray === 'object') {
                    // 如果直接是对象格式
                    config = configArray;
                } else {
                    config = null;
                }
                
                if (config && typeof config === 'object' && Object.keys(config).length > 0) {
                    this.config = config;
                    this.populateForm();
                    console.log('成功加载设置:', config);
                } else {
                    console.error("从后端获取的配置为空或格式错误:", configArray);
                    this.loadMockData();
                }
            });
        } else {
            console.log('Bridge或getSettings不可用，加载模拟数据');
            this.loadMockData();
        }
    }

    /**
     * 加载模拟数据（用于开发测试）
     */
    loadMockData() {
        this.config = {
            max_day: 7,
            model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            hotkey: "Alt+Q",
            apikey: "",
            api_baseurl: "",
            temperature: 0.7,
            receiveemail: false,
            cosine_similarity: 0.5,
            api_model: "",
            live2d_uri: "ws://127.0.0.1:10086/api",
            live2d_listen: false,
            theme_color: "#ff69b4"
        };
        this.populateForm();
    }

    /**
     * 填充表单数据
     */
    populateForm() {
        // 基础设置
        document.getElementById('max_day').value = this.config.max_day || 7;
        document.getElementById('hotkey').value = this.config.hotkey || "Alt+Q";
        document.getElementById('model').value = this.config.model || "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2";

        // API设置 - 只显示模型名称
        const apiModelDisplay = document.getElementById('api-model-display');
        apiModelDisplay.textContent = this.config.api_model || "未设置";
        
        // 滑块
        const tempSlider = document.getElementById('temperature');
        tempSlider.value = this.config.temperature || 0.7;
        document.getElementById('temperature-value').textContent = tempSlider.value;
        
        const cosineSlider = document.getElementById('cosine_similarity');
        cosineSlider.value = this.config.cosine_similarity || 0.5;
        document.getElementById('cosine_similarity-value').textContent = cosineSlider.value;

        // 开关
        document.getElementById('receiveemail').checked = this.config.receiveemail || false;
        document.getElementById('live2d_listen').checked = this.config.live2d_listen || false;
        document.getElementById('live2d_uri').value = this.config.live2d_uri || "ws://127.0.0.1:10086/api";
        
        // 主题色
        const themeColor = this.config.theme_color || "#ff69b4";
        document.getElementById('theme-color').value = themeColor;
        this.updateThemeColorPreview(themeColor);
        this.updateThemeColor(themeColor);
    }

    /**
     * 收集表单数据
     */
    collectFormData() {
        return {
            max_day: parseInt(document.getElementById('max_day').value) || 7,
            hotkey: document.getElementById('hotkey').value.trim() || "Alt+Q",
            model: document.getElementById('model').value,
            // API配置从当前config中获取，而不是从表单
            apikey: this.config.apikey || "",
            api_baseurl: this.config.api_baseurl || "",
            api_model: this.config.api_model || "",
            temperature: parseFloat(document.getElementById('temperature').value) || 0.7,
            cosine_similarity: parseFloat(document.getElementById('cosine_similarity').value) || 0.5,
            receiveemail: document.getElementById('receiveemail').checked,
            live2d_listen: document.getElementById('live2d_listen').checked,
            live2d_uri: document.getElementById('live2d_uri').value.trim() || "ws://127.0.0.1:10086/api",
            theme_color: document.getElementById('theme-color').value || "#ff69b4"
        };
    }

    /**
     * 保存设置
     */
    saveSettings() {
        const formData = this.collectFormData();
        
        // 验证数据
        if (!this.validateFormData(formData)) {
            return;
        }

        this.showLoading('正在保存设置...');

        if (this.bridge && this.bridge.saveSettings) {
            this.bridge.saveSettings(formData, (result) => {
                this.hideLoading();
                
                console.log('保存回调返回值:', result, '类型:', typeof result);
                
                // 处理不同的回调格式
                let success, message;
                
                if (Array.isArray(result)) {
                    if (result.length >= 2) {
                        // 数组格式: [success, message]
                        success = result[0];
                        message = result[1];
                    } else if (result.length === 1) {
                        // 只有success值
                        success = result[0];
                        message = success ? '保存成功' : '保存失败';
                    } else {
                        // 空数组
                        success = false;
                        message = '返回空数组';
                    }
                } else if (typeof result === 'boolean') {
                    // 直接是布尔值
                    success = result;
                    message = success ? '保存成功' : '保存失败';
                } else if (typeof result === 'object' && result !== null) {
                    // 对象格式
                    success = result.success || false;
                    message = result.message || (success ? '保存成功' : '保存失败');
                } else {
                    // 其他格式，根据全局配置重新加载成功来判断
                    console.log('收到未知格式，但配置重新加载成功，判断为保存成功');
                    success = true;
                    message = '保存成功';
                }
                
                if (success) {
                    this.showSuccessMessage(`设置保存成功，请重启以生效！${message && message !== '保存成功' ? ': ' + message : ''}`);
                    this.config = formData;
                    console.log('设置保存成功:', formData);
                } else {
                    this.showErrorMessage(`保存设置失败${message ? ': ' + message : ''}`);
                    console.error('设置保存失败:', message);
                }
            });
        } else {
            // 模拟保存
            setTimeout(() => {
                this.hideLoading();
                this.config = formData;
                this.showSuccessMessage('设置保存成功，请重启以生效！');
                console.log('保存的设置:', formData);
            }, 1000);
        }
    }

    /**
     * 验证表单数据
     */
    validateFormData(data) {
        if (data.max_day < 1 || data.max_day > 365) {
            this.showErrorMessage('历史保留天数必须在1-365之间');
            return false;
        }

        if (!data.hotkey) {
            this.showErrorMessage('热键不能为空');
            return false;
        }

        if (data.temperature < 0 || data.temperature > 2) {
            this.showErrorMessage('Temperature必须在0-2之间');
            return false;
        }

        if (data.cosine_similarity < 0 || data.cosine_similarity > 1) {
            this.showErrorMessage('相似度阈值必须在0-1之间');
            return false;
        }

        return true;
    }

    /**
     * 更新主题色预览文本
     */
    updateThemeColorPreview(colorValue) {
        const preview = document.getElementById('theme-color-preview');
        const colorNames = {
            '#ff69b4': '粉色',
            '#007acc': '蓝色', 
            '#ff4444': '红色',
            '#44ff44': '绿色',
            '#ff8c00': '橙色',
            '#9966cc': '紫色',
            '#ffd700': '金色',
            '#ff1493': '深粉色',
            '#0055ff': '蓝色'
        };
        
        preview.textContent = colorNames[colorValue.toLowerCase()] || '自定义';
        preview.style.color = colorValue;
    }

    /**
     * 应用主题色到界面
     */
    updateThemeColor(colorValue) {
        // 更新CSS变量
        const root = document.documentElement;
        root.style.setProperty('--theme-color', colorValue);
        root.style.setProperty('--theme-color-hover', this.darkenColor(colorValue, 0.2));
        root.style.setProperty('--theme-color-light', this.lightenColor(colorValue, 0.2));
    }

    /**
     * 颜色加深工具方法
     */
    darkenColor(color, amount) {
        const hex = color.replace('#', '');
        const num = parseInt(hex, 16);
        const red = Math.max(0, (num >> 16) - Math.round(255 * amount));
        const green = Math.max(0, (num >> 8 & 0x00FF) - Math.round(255 * amount));
        const blue = Math.max(0, (num & 0x0000FF) - Math.round(255 * amount));
        return `#${((red << 16) | (green << 8) | blue).toString(16).padStart(6, '0')}`;
    }

    /**
     * 颜色变浅工具方法
     */
    lightenColor(color, amount) {
        const hex = color.replace('#', '');
        const num = parseInt(hex, 16);
        const red = Math.min(255, (num >> 16) + Math.round(255 * amount));
        const green = Math.min(255, (num >> 8 & 0x00FF) + Math.round(255 * amount));
        const blue = Math.min(255, (num & 0x0000FF) + Math.round(255 * amount));
        return `#${((red << 16) | (green << 8) | blue).toString(16).padStart(6, '0')}`;
    }

    /**
     * 单独保存主题色（立即保存）
     */
    saveThemeColorOnly(colorValue) {
        // 更新当前配置
        this.config.theme_color = colorValue;
        const formData = this.collectFormData();
        
        if (this.bridge && this.bridge.saveSettings) {
            this.bridge.saveSettings(formData, (result) => {
                console.log('主题色保存结果:', result);
            });
        } else {
            console.log('主题色已更新:', colorValue);
        }
    }

    /**
     * 打开系统提示词编辑器
     */
    openSystemPromptEditor() {
        if (this.bridge && this.bridge.openSystemPromptEditor) {
            try {
                this.bridge.openSystemPromptEditor();
                console.log('调用系统提示词编辑器');
            } catch (error) {
                console.error('打开系统提示词编辑器失败:', error);
                this.showErrorMessage('打开系统提示词编辑器失败: ' + error.message);
            }
        } else {
            console.log('Bridge或openSystemPromptEditor方法不可用');
            this.showErrorMessage('系统提示词编辑器功能暂时不可用，请检查后端连接');
        }
    }

    /**
     * 打开邮箱配置
     */
    openEmailConfig() {
        if (this.bridge && this.bridge.openEmailConfig) {
            try {
                this.bridge.openEmailConfig();
                console.log('调用邮箱配置窗口');
            } catch (error) {
                console.error('打开邮箱配置失败:', error);
                this.showErrorMessage('打开邮箱配置失败: ' + error.message);
            }
        } else {
            console.log('Bridge或openEmailConfig方法不可用');
            this.showErrorMessage('邮箱配置功能暂时不可用，请检查后端连接');
        }
    }

    /**
     * 显示关于信息
     */
    showAbout() {
        this.showInfoMessage(`liveAgent v0.2.2`);
    }

    /**
     * 关闭窗口
     */
    closeWindow() {
        if (this.bridge && this.bridge.closeWindow) {
            this.bridge.closeWindow();
        } else {
            console.log('CLOSE_WINDOW');
            window.close();
        }
    }

    /**
     * 显示成功消息
     */
    showSuccessMessage(message) {
        this.showMessage(message, 'success');
    }

    /**
     * 显示错误消息
     */
    showErrorMessage(message) {
        this.showMessage(message, 'error');
    }

    /**
     * 显示信息消息
     */
    showInfoMessage(message) {
        this.showMessage(message, 'info');
    }

    /**
     * 显示消息（简单实现）
     */
    showMessage(message, type = 'info') {
        // 创建消息元素
        const messageEl = document.createElement('div');
        messageEl.className = `message-toast message-${type}`;
        messageEl.textContent = message;
        
        // 添加样式
        Object.assign(messageEl.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 20px',
            borderRadius: '8px',
            zIndex: '10000',
            fontSize: '14px',
            fontWeight: '500',
            maxWidth: '300px',
            wordWrap: 'break-word',
            whiteSpace: 'pre-line',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            transition: 'all 0.3s ease'
        });

        // 设置类型特定样式
        if (type === 'success') {
            Object.assign(messageEl.style, {
                backgroundColor: '#d4edda',
                color: '#155724',
                border: '1px solid #c3e6cb'
            });
        } else if (type === 'error') {
            Object.assign(messageEl.style, {
                backgroundColor: '#f8d7da',
                color: '#721c24',
                border: '1px solid #f5c6cb'
            });
        } else {
            Object.assign(messageEl.style, {
                backgroundColor: '#d1ecf1',
                color: '#0c5460',
                border: '1px solid #bee5eb'
            });
        }

        document.body.appendChild(messageEl);

        // 3秒后自动消失
        setTimeout(() => {
            messageEl.style.opacity = '0';
            messageEl.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.parentNode.removeChild(messageEl);
                }
            }, 300);
        }, 3000);
    }

    /**
     * 显示加载状态
     */
    showLoading(message) {
        // 简单实现：禁用保存按钮并显示加载文本
        const saveBtn = document.getElementById('save-btn');
        saveBtn.disabled = true;
        saveBtn.textContent = message;
    }

    /**
     * 隐藏加载状态
     */
    hideLoading() {
        const saveBtn = document.getElementById('save-btn');
        saveBtn.disabled = false;
        saveBtn.textContent = '保存设置';
    }

    // ==================== 系统提示词弹窗相关方法 ====================

    /**
     * 初始化系统提示词弹窗事件
     */
    initSystemPromptModal() {
        const modal = document.getElementById('system-prompt-modal');
        const closeBtn = document.getElementById('close-system-prompt');
        const saveBtn = document.getElementById('save-system-prompt');
        const templateBtns = document.querySelectorAll('.template-btn');

        // 关闭弹窗事件
        closeBtn.onclick = () => this.closeSystemPromptModal();
        
        // 点击弹窗外部关闭
        window.onclick = (event) => {
            if (event.target === modal) {
                this.closeSystemPromptModal();
            }
        };

        // 保存按钮
        saveBtn.onclick = () => this.saveSystemPrompt();

        // 模板按钮
        templateBtns.forEach(btn => {
            btn.onclick = () => this.applyTemplate(btn.dataset.template);
        });
    }

    /**
     * 打开系统提示词弹窗
     */
    openSystemPromptModal() {
        const modal = document.getElementById('system-prompt-modal');
        modal.style.display = 'block';
        this.loadSystemPrompt();
    }

    /**
     * 关闭系统提示词弹窗
     */
    closeSystemPromptModal() {
        const modal = document.getElementById('system-prompt-modal');
        modal.style.display = 'none';
    }

    /**
     * 加载系统提示词
     */
    loadSystemPrompt() {
        if (this.bridge && this.bridge.getSystemPrompt) {
            this.bridge.getSystemPrompt((prompt) => {
                const textarea = document.getElementById('system-prompt-content');
                textarea.value = prompt || '';
            });
        }
    }

    /**
     * 保存系统提示词
     */
    saveSystemPrompt() {
        const textarea = document.getElementById('system-prompt-content');
        const prompt = textarea.value.trim();

        if (this.bridge && this.bridge.saveSystemPrompt) {
            this.bridge.saveSystemPrompt(prompt, (result) => {
                console.log('系统提示词保存回调结果:', result, '类型:', typeof result);
                
                // 处理不同的回调格式
                let success, message;
                
                if (Array.isArray(result)) {
                    if (result.length >= 2) {
                        // 数组格式: [success, message]
                        success = result[0];
                        message = result[1];
                    } else if (result.length === 1) {
                        // 只有success值
                        success = result[0];
                        message = success ? '保存成功' : '保存失败';
                    } else {
                        // 空数组
                        success = false;
                        message = '返回空数组';
                    }
                } else if (typeof result === 'boolean') {
                    // 直接是布尔值
                    success = result;
                    message = success ? '保存成功' : '保存失败';
                } else if (typeof result === 'object' && result !== null) {
                    // 对象格式
                    success = result.success || false;
                    message = result.message || (success ? '保存成功' : '保存失败');
                } else {
                    // 其他格式，默认为成功
                    success = true;
                    message = '保存成功';
                }
                
                if (success) {
                    this.showSuccessMessage('系统提示词保存成功');
                    this.closeSystemPromptModal();
                } else {
                    this.showErrorMessage('保存失败: ' + message);
                }
            });
        } else {
            this.showErrorMessage('系统提示词功能暂不可用');
        }
    }

    /**
     * 应用模板
     */
    applyTemplate(template) {
        const textarea = document.getElementById('system-prompt-content');
        const templates = {
            professional: `你是一个专业的AI助手，请以友好、专业的态度回答用户的问题。在回答时请注意：
1. 保持客观中立的立场
2. 提供准确、有用的信息
3. 如果不确定答案，请明确说明
4. 保持礼貌和耐心`,
            
            friendly: `你是一个温暖友好的AI助手，请以亲切、关怀的态度与用户交流。特点：
- 使用温暖、亲切的语言表达
- 主动表达关心和理解
- 给予正面的反馈和鼓励
- 在适当时候使用温馨的表情符号
- 展现耐心和共情能力`,
            
            creative: `你是一个富有创意的AI助手，擅长提供创新的思路和解决方案。特色：
• 用创造性的方式思考问题
• 提供多角度的观点和建议
• 鼓励用户发散思维
• 结合实际给出可行的创意方案`
        };

        textarea.value = templates[template] || '';
    }

    // ==================== API配置弹窗相关方法 ====================

    /**
     * 初始化API配置弹窗事件
     */
    initApiConfigModal() {
        const modal = document.getElementById('api-config-modal');
        const closeBtn = document.getElementById('close-api-config');
        const saveBtn = document.getElementById('save-api-config');
        const cancelBtn = document.getElementById('cancel-api-config');
        const toggleBtn = document.getElementById('toggle-modal-apikey');

        // 关闭弹窗事件
        closeBtn.onclick = () => this.closeApiConfigModal();
        cancelBtn.onclick = () => this.closeApiConfigModal();
        
        // 点击弹窗外部关闭
        window.onclick = (event) => {
            if (event.target === modal) {
                this.closeApiConfigModal();
            }
        };

        // 保存按钮
        saveBtn.onclick = () => this.saveApiConfig();
        
        // API密钥显示/隐藏切换
        toggleBtn.onclick = () => this.toggleModalApiKeyVisibility();
    }

    /**
     * 打开API配置弹窗
     */
    openApiConfigModal() {
        const modal = document.getElementById('api-config-modal');
        modal.style.display = 'block';
        this.loadApiConfig();
    }

    /**
     * 关闭API配置弹窗
     */
    closeApiConfigModal() {
        const modal = document.getElementById('api-config-modal');
        modal.style.display = 'none';
    }

    /**
     * 加载API配置到弹窗
     */
    loadApiConfig() {
        document.getElementById('modal-apikey').value = this.config.apikey || "";
        document.getElementById('modal-api-baseurl').value = this.config.api_baseurl || "";
        document.getElementById('modal-api-model').value = this.config.api_model || "";
    }

    /**
     * 保存API配置
     */
    saveApiConfig() {
        // 从弹窗获取API配置
        const apikey = document.getElementById('modal-apikey').value.trim();
        const api_baseurl = document.getElementById('modal-api-baseurl').value.trim();
        const api_model = document.getElementById('modal-api-model').value.trim();

        // 更新当前配置
        this.config.apikey = apikey;
        this.config.api_baseurl = api_baseurl;
        this.config.api_model = api_model;

        // 更新主页面的显示
        const apiModelDisplay = document.getElementById('api-model-display');
        apiModelDisplay.textContent = api_model || "未设置";

        // 关闭弹窗
        this.closeApiConfigModal();

        // 提示用户保存
        this.showSuccessMessage('API配置已更新');
    }

    /**
     * 切换API密钥可见性（弹窗中）
     */
    toggleModalApiKeyVisibility() {
        const apiKeyInput = document.getElementById('modal-apikey');
        const toggleBtn = document.getElementById('toggle-modal-apikey');
        
        if (apiKeyInput.type === 'password') {
            apiKeyInput.type = 'text';
            toggleBtn.textContent = '🙈';
        } else {
            apiKeyInput.type = 'password';
            toggleBtn.textContent = '👁';
        }
    }

    // ==================== 邮箱配置弹窗相关方法 ====================

    /**
     * 初始化邮箱配置弹窗事件
     */
    initEmailConfigModal() {
        const modal = document.getElementById('email-config-modal');
        const closeBtn = document.getElementById('close-email-config');
        const saveBtn = document.getElementById('save-email-config');
        const addBtn = document.getElementById('add-email-account');

        // 关闭弹窗事件
        closeBtn.onclick = () => this.closeEmailConfigModal();
        
        // 点击弹窗外部关闭
        window.onclick = (event) => {
            if (event.target === modal) {
                this.closeEmailConfigModal();
            }
        };

        // 保存按钮
        saveBtn.onclick = () => this.saveEmailConfig();
        
        // 添加账户按钮
        addBtn.onclick = () => this.addEmailAccount();
    }

    /**
     * 打开邮箱配置弹窗
     */
    openEmailConfigModal() {
        const modal = document.getElementById('email-config-modal');
        modal.style.display = 'block';
        this.loadEmailConfig();
    }

    /**
     * 关闭邮箱配置弹窗
     */
    closeEmailConfigModal() {
        const modal = document.getElementById('email-config-modal');
        modal.style.display = 'none';
    }

    /**
     * 加载邮箱配置
     */
    loadEmailConfig() {
        if (this.bridge && this.bridge.getEmailConfig) {
            this.bridge.getEmailConfig((config) => {
                // 填充基础设置
                document.getElementById('email-check-interval').value = config.checkInterval || 5;
                
                // 填充邮箱账户
                this.renderEmailAccounts(config.emails || []);
            });
        }
    }

    /**
     * 渲染邮箱账户列表
     */
    renderEmailAccounts(accounts) {
        const container = document.getElementById('email-accounts-container');
        container.innerHTML = '';
        
        // 更新内部数组
        this.emailAccounts = [...accounts];
        
        accounts.forEach((account, index) => {
            const accountEl = this.createEmailAccountItem(account, index);
            container.appendChild(accountEl);
        });
    }

    /**
     * 创建邮箱账户输入表单
     */
    createEmailInputForm() {
        const div = document.createElement('div');
        div.className = 'email-input-form';
        div.id = 'email-input-form';
        div.innerHTML = `
            <div class="email-form-fields">
                <input type="email" placeholder="邮箱地址" data-field="address" class="email-form-input">
                <input type="password" placeholder="密码或授权码" data-field="password" class="email-form-input">
                <input type="text" placeholder="IMAP服务器" data-field="imapServer" class="email-form-input">
                <input type="number" placeholder="端口" value="993" data-field="imapPort" min="1" max="65535" class="email-form-input">
                <label class="ssl-checkbox">
                    <input type="checkbox" checked data-field="useSSL"> SSL
                </label>
                <button class="add-email-btn" onclick="settingsController.submitEmailAccount()">添加</button>
            </div>
        `;
        return div;
    }

    /**
     * 创建邮箱账户显示项
     */
    createEmailAccountItem(account, index) {
        const div = document.createElement('div');
        div.className = 'email-account-display';
        div.dataset.index = index;
        div.innerHTML = `
            <span class="email-address">${account.address || ''}</span>
            <button class="delete-email-btn" onclick="settingsController.removeEmailAccount(${index})">×</button>
        `;
        return div;
    }

    /**
     * 显示添加邮箱表单
     */
    addEmailAccount() {
        const container = document.getElementById('email-accounts-container');
        
        // 检查是否已经有输入表单
        const existingForm = document.getElementById('email-input-form');
        if (existingForm) {
            return; // 如果已经有表单，不重复添加
        }
        
        const formEl = this.createEmailInputForm();
        container.appendChild(formEl);
        
        // 聚焦到第一个输入框
        const firstInput = formEl.querySelector('input[data-field="address"]');
        if (firstInput) {
            firstInput.focus();
        }
    }

    /**
     * 提交邮箱账户
     */
    submitEmailAccount() {
        const form = document.getElementById('email-input-form');
        if (!form) return;
        
        const inputs = form.querySelectorAll('input');
        const account = {};
        
        // 收集表单数据
        inputs.forEach(input => {
            if (input.dataset.field) {
                if (input.type === 'checkbox') {
                    account[input.dataset.field] = input.checked;
                } else {
                    account[input.dataset.field] = input.value;
                }
            }
        });

        // 验证必填字段
        if (!account.address || !account.password || !account.imapServer) {
            this.showErrorMessage('请填写完整的邮箱信息');
            return;
        }

        // 简单的邮箱格式验证
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(account.address)) {
            this.showErrorMessage('请输入有效的邮箱地址');
            return;
        }

        // 添加到当前邮箱列表中
        this.addAccountToList(account);
        
        // 移除输入表单
        form.remove();
        
        this.showSuccessMessage('邮箱账户添加成功');
    }

    /**
     * 添加账户到列表
     */
    addAccountToList(account) {
        const container = document.getElementById('email-accounts-container');
        
        // 添加到内部数组
        this.emailAccounts.push(account);
        
        // 计算新的索引
        const index = this.emailAccounts.length - 1;
        
        const accountEl = this.createEmailAccountItem(account, index);
        container.appendChild(accountEl);
    }

    /**
     * 删除邮箱账户
     */
    removeEmailAccount(index) {
        if (index >= 0 && index < this.emailAccounts.length) {
            // 从内部数组中删除
            this.emailAccounts.splice(index, 1);
            
            // 重新渲染整个列表
            this.renderEmailAccounts(this.emailAccounts);
        }
    }

    /**
     * 重新编号邮箱账户
     */
    reindexEmailAccounts() {
        const container = document.getElementById('email-accounts-container');
        const accountItems = container.querySelectorAll('.email-account-display');
        
        accountItems.forEach((item, index) => {
            item.dataset.index = index;
            const deleteBtn = item.querySelector('.delete-email-btn');
            if (deleteBtn) {
                deleteBtn.onclick = () => this.removeEmailAccount(index);
            }
        });
    }

    /**
     * 保存邮箱配置
     */
    saveEmailConfig() {
        const config = {
            checkInterval: parseInt(document.getElementById('email-check-interval').value) || 5,
            emails: [...this.emailAccounts] // 直接使用内部数组
        };

        if (this.bridge && this.bridge.saveEmailConfig) {
            this.bridge.saveEmailConfig(config, (result) => {
                // 处理不同的回调格式
                let success, message;
                
                if (Array.isArray(result)) {
                    if (result.length >= 2) {
                        // 数组格式: [success, message]
                        success = result[0];
                        message = result[1];
                    } else if (result.length === 1) {
                        // 只有success值
                        success = result[0];
                        message = success ? '保存成功' : '保存失败';
                    } else {
                        // 空数组
                        success = false;
                        message = '返回空数组';
                    }
                } else if (typeof result === 'boolean') {
                    // 直接是布尔值
                    success = result;
                    message = success ? '保存成功' : '保存失败';
                } else if (typeof result === 'object' && result !== null) {
                    // 对象格式
                    success = result.success || false;
                    message = result.message || (success ? '保存成功' : '保存失败');
                } else {
                    // 其他格式，默认为成功
                    success = true;
                    message = '保存成功';
                }
                
                if (success) {
                    this.showSuccessMessage('邮箱配置保存成功');
                    this.closeEmailConfigModal();
                } else {
                    this.showErrorMessage('保存失败: ' + message);
                }
            });
        } else {
            // Bridge不可用
            this.showErrorMessage('邮箱配置功能暂不可用');
        }
    }

    // ==================== 原有方法保持兼容 ====================

    /**
     * 打开系统提示词编辑器（兼容方法）
     */
    openSystemPromptEditor() {
        this.openSystemPromptModal();
    }

    /**
     * 打开邮箱配置（兼容方法）
     */
    openEmailConfig() {
        this.openEmailConfigModal();
    }

    /**
     * 打开清除历史记录模态窗口
     */
    openClearHistoryModal() {
        const modal = document.getElementById('clear-history-modal');
        modal.style.display = 'block';
    }

    /**
     * 初始化清除历史记录模态窗口事件
     */
    initClearHistoryModal() {
        const modal = document.getElementById('clear-history-modal');
        const closeBtn = document.getElementById('close-clear-history');
        const confirmBtn = document.getElementById('confirm-clear-history');
        const cancelBtn = document.getElementById('cancel-clear-history');

        // 关闭按钮
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // 取消按钮
        cancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // 确认清除按钮
        confirmBtn.addEventListener('click', () => {
            this.clearChatHistory();
        });

        // 点击模态窗口外部关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    /**
     * 清除聊天历史记录
     */
    clearChatHistory() {
        try {
            // 通过桥接执行清除命令
            if (this.bridge && this.bridge.execute_command) {
                this.bridge.execute_command('--history_clear()');
            } else {
                // 备用方案：通过控制台消息
                console.log('COMMAND: --history_clear()');
            }

            // 关闭模态窗口
            const modal = document.getElementById('clear-history-modal');
            modal.style.display = 'none';

            // 显示成功提示
            this.showToast('对话历史记录已清除', 'success');

        } catch (error) {
            console.error('清除历史记录失败:', error);
            this.showToast('清除失败，请重试', 'error');
        }
    }

    /**
     * 显示Toast提示消息
     */
    showToast(message, type = 'success') {
        const toast = document.getElementById('success-toast');
        const messageSpan = document.getElementById('toast-message');
        
        messageSpan.textContent = message;
        
        // 清除之前的类型样式
        toast.classList.remove('success', 'error');
        // 添加新的类型样式
        toast.classList.add(type);
        toast.classList.add('show');

        // 3秒后自动隐藏
        setTimeout(() => {
            toast.classList.remove('show');
            toast.classList.add('hide');
            
            // 动画完成后移除hide类
            setTimeout(() => {
                toast.classList.remove('hide');
            }, 300);
        }, 3000);
    }

    /**
     * 显示成功提示消息（保持向后兼容）
     */
    showSuccessToast(message) {
        this.showToast(message, 'success');
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.settingsController = new SettingsController();
    console.log('设置控制器初始化完成');
});
