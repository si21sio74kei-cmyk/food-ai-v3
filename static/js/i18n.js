/**
 * FoodGuardian AI - Internationalization Module
 * 支持中英文自由切换
 */

class I18nManager {
    constructor() {
        this.currentLang = localStorage.getItem('fgai_language') || 'zh-CN';
        this.translations = {};
        this.isInitialized = false;
    }

    /**
     * 初始化语言管理器
     */
    async init() {
        if (this.isInitialized) return;
        
        try {
            // 加载当前语言的翻译文件
            await this.loadLanguage(this.currentLang);
            
            // 应用翻译到页面
            this.applyTranslations();
            
            // 更新 HTML lang 属性
            document.documentElement.lang = this.currentLang;
            
            this.isInitialized = true;
            console.log(`[i18n] Initialized with language: ${this.currentLang}`);
        } catch (error) {
            console.error('[i18n] Initialization failed:', error);
        }
    }

    /**
     * 加载指定语言的翻译文件
     */
    async loadLanguage(lang) {
        try {
            const response = await fetch(`/locales/${lang}.json`);
            if (!response.ok) {
                throw new Error(`Failed to load language file: ${lang}`);
            }
            this.translations[lang] = await response.json();
            console.log(`[i18n] Loaded language: ${lang}`);
        } catch (error) {
            console.error(`[i18n] Error loading ${lang}:`, error);
            // 降级到中文
            if (lang !== 'zh-CN') {
                await this.loadLanguage('zh-CN');
            }
        }
    }

    /**
     * 获取翻译文本
     * @param {string} key - 翻译键（如 "nav.home"）
     * @param {object} params - 可选参数（用于动态替换）
     * @returns {string} 翻译后的文本
     */
    t(key, params = {}) {
        const keys = key.split('.');
        let value = this.translations[this.currentLang];
        
        // 逐级查找
        for (const k of keys) {
            if (value && typeof value === 'object') {
                value = value[k];
            } else {
                value = undefined;
                break;
            }
        }
        
        // 如果未找到，返回键名本身
        if (value === undefined || value === null) {
            console.warn(`[i18n] Missing translation for key: ${key}`);
            return key;
        }
        
        // 替换参数
        let result = value;
        for (const [paramKey, paramValue] of Object.entries(params)) {
            result = result.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), paramValue);
        }
        
        return result;
    }

    /**
     * 切换语言
     */
    async switchLanguage(lang) {
        if (lang === this.currentLang) return;
        
        console.log(`[i18n] Switching language from ${this.currentLang} to ${lang}`);
        
        // 如果目标语言未加载，先加载
        if (!this.translations[lang]) {
            await this.loadLanguage(lang);
        }
        
        // 更新当前语言
        this.currentLang = lang;
        localStorage.setItem('fgai_language', lang);
        
        // 更新 HTML lang 属性
        document.documentElement.lang = lang;
        
        // 重新应用翻译
        this.applyTranslations();
        
        // 触发自定义事件（供其他模块监听）
        window.dispatchEvent(new CustomEvent('languageChanged', { 
            detail: { language: lang } 
        }));
        
        console.log(`[i18n] Language switched to: ${lang}`);
    }

    /**
     * 应用翻译到所有带 data-i18n 属性的元素
     */
    applyTranslations() {
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.t(key);
            
            // 根据元素类型设置内容
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                if (el.hasAttribute('placeholder')) {
                    el.placeholder = translation;
                }
            } else {
                el.textContent = translation;
            }
        });
        
        // 处理 data-i18n-placeholder（专门用于 placeholder）
        const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
        placeholderElements.forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            el.placeholder = this.t(key);
        });
        
        // 处理 data-i18n-title（用于 title 属性）
        const titleElements = document.querySelectorAll('[data-i18n-title]');
        titleElements.forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            el.title = this.t(key);
        });
    }

    /**
     * 获取当前语言
     */
    getCurrentLanguage() {
        return this.currentLang;
    }

    /**
     * 获取语言显示名称
     */
    getLanguageDisplayName(lang) {
        const names = {
            'zh-CN': '中文',
            'en-US': 'English'
        };
        return names[lang] || lang;
    }

    /**
     * 获取国旗图标
     */
    getLanguageFlag(lang) {
        const flags = {
            'zh-CN': '🇨🇳',
            'en-US': '🇺🇸'
        };
        return flags[lang] || '🌐';
    }
}

// 创建全局实例
window.i18n = new I18nManager();
console.log('[i18n] Global instance created');

// DOM 加载完成后自动初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('[i18n] DOMContentLoaded event fired');
    window.i18n.init().then(() => {
        console.log('[i18n] Initialization completed successfully');
    }).catch(err => {
        console.error('[i18n] Auto-initialization failed:', err);
    });
});
