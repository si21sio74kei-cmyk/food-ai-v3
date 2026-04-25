# FoodGuardian AI - 国际化完整实施方案

## ✅ 已完成的工作

### 1. 语言文件 (100% 完成)
- ✅ `locales/zh-CN.json` - 277个翻译键,无重复
- ✅ `locales/en-US.json` - 277个翻译键,完全匹配
- ✅ 两个文件的键完全一致

### 2. 后端API多语言支持 (80% 完成)
- ✅ `/api/generate_recipe` - 已支持多语言Prompt
- ✅ `/api/chat` - 已添加中英文Prompt切换
- ✅ `/api/analyze_nutrition` - 已添加中英文Prompt切换
- ⚠️ 其他API端点需要前端传递language参数

---

## 📋 待完成工作清单

### 3. HTML静态文本国际化 (需要手动添加data-i18n)

#### 方法A: 手动添加(推荐用于生产环境)
在HTML元素上添加 `data-i18n` 属性:

```html
<!-- 示例 -->
<div class="card-title" data-i18n="home.population_label">🏷️ 选择您的人群标签</div>
<button data-i18n="common.confirm">确认</button>
<input placeholder="输入您的问题..." data-i18n-placeholder="chat.input_placeholder">
```

#### 方法B: JavaScript动态替换(快速方案)
在页面加载时自动替换文本:

```javascript
// 在 i18n.js 中添加
window.i18n.autoTranslate = function() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        const text = this.t(key);
        if (text) {
            el.textContent = text;
        }
    });
    
    // 处理placeholder
    const placeholders = document.querySelectorAll('[data-i18n-placeholder]');
    placeholders.forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const text = this.t(key);
        if (text) {
            el.placeholder = text;
        }
    });
};

// 在语言切换时调用
document.addEventListener('languageChanged', () => {
    window.i18n.autoTranslate();
});
```

---

### 4. JavaScript动态内容国际化 (关键修改)

需要在以下函数中添加多语言支持:

#### 4.1 updateWelcomeMessage (第1904行)
```javascript
// ❌ 当前
welcomeEl.textContent = `欢迎回来,${appData.nickname}!今天也一起为地球省下一点点资源吧。`;

// ✅ 修改后
const msg = window.i18n ? 
    window.i18n.t('home.welcome_back', {nickname: appData.nickname}) :
    `欢迎回来,${appData.nickname}!今天也一起为地球省下一点点资源吧。`;
welcomeEl.textContent = msg;
```

#### 4.2 saveNickname (第1913行)
```javascript
// ❌ 当前
showToast('请输入一个昵称');
showToast('✅ 昵称已保存');

// ✅ 修改后
if (!nickname) {
    showToast(window.i18n ? window.i18n.t('common.nickname_required') : '请输入一个昵称');
    return;
}
// ...
showToast(window.i18n ? window.i18n.t('common.nickname_saved') : '✅ 昵称已保存');
```

#### 4.3 resetStats (第1926行)
```javascript
// ❌ 当前
if (confirm('确定要清零本机的所有环保统计吗?此操作不可恢复。')) {
// ...
showToast('✅ 统计已重置');

// ✅ 修改后
const confirmMsg = window.i18n ? 
    window.i18n.t('common.confirm_reset') : 
    '确定要清零本机的所有环保统计吗?此操作不可恢复。';
    
if (confirm(confirmMsg)) {
    // ...
    showToast(window.i18n ? window.i18n.t('common.stats_reset_success') : '✅ 统计已重置');
}
```

#### 4.4 resetGenerationCounter (第2019行)
```javascript
// ❌ 当前
if (!confirm('确定要重置食谱生成进度吗？\n\n这将：\n1. 清除当前的生成进度（从第0次重新开始）\n2. 清空今日所有饮食摄入记录\n\n此操作不可恢复！')) {
// ...
showToast('✅ 已完全重置！现在从第0次开始重新计算');

// ✅ 修改后
const resetConfirm = window.i18n ?
    window.i18n.t('recipe.reset_confirm') :
    '确定要重置食谱生成进度吗？...';
    
if (!confirm(resetConfirm)) {
    return;
}
// ...
showToast(window.i18n ? window.i18n.t('recipe.reset_success') : '✅ 已完全重置！现在从第0次开始重新计算');
```

---

### 5. API调用添加language参数

需要在所有fetch调用中添加language参数:

#### 5.1 generateRecipe (约第2150行)
```javascript
// ❌ 当前
body: JSON.stringify({
    custom_ingredients: customIngredients,
    people_num: peopleNum,
    // ...
})

// ✅ 修改后
body: JSON.stringify({
    custom_ingredients: customIngredients,
    people_num: peopleNum,
    language: window.i18n ? window.i18n.getCurrentLanguage() : 'zh-CN',
    // ...
})
```

#### 5.2 chat API (约第2695行)
```javascript
// ❌ 当前
body: JSON.stringify({ message })

// ✅ 修改后
body: JSON.stringify({ 
    message,
    language: window.i18n ? window.i18n.getCurrentLanguage() : 'zh-CN'
})
```

#### 5.3 analyzeNutrition API
```javascript
// ❌ 当前
body: JSON.stringify({
    food_input: foodInput,
    people: peopleNum
})

// ✅ 修改后
body: JSON.stringify({
    food_input: foodInput,
    people: peopleNum,
    language: window.i18n ? window.i18n.getCurrentLanguage() : 'zh-CN'
})
```

---

## 🎯 实施建议

### 方案A: 分阶段实施 (推荐)

**阶段1 - 核心功能 (1-2小时)**
1. 修改JavaScript中的硬编码文本(约20处)
2. 在所有API调用中添加language参数(约8处)
3. 测试中英文切换功能

**阶段2 - UI完善 (2-3小时)**
1. 为HTML静态文本添加data-i18n属性
2. 实现autoTranslate功能
3. 测试所有页面的显示

**阶段3 - 优化 (1小时)**
1. 添加缺失的翻译键
2. 优化翻译质量
3. 性能测试

### 方案B: 一次性完成 (需要3-4小时)

直接按照上述清单逐项修改所有文件。

---

## 🔧 快速测试方法

1. 启动服务器: `python food_guardian_ai_2.py`
2. 访问: http://localhost:5000
3. 点击右上角语言切换按钮
4. 检查以下内容:
   - ✅ 导航栏文字是否切换
   - ✅ 首页内容是否切换
   - ✅ AI对话回复是否为英文
   - ✅ 营养分析结果是否为英文
   - ✅ 错误提示是否为英文

---

## 📝 注意事项

1. **向后兼容**: 所有修改都应包含fallback,确保在i18n未加载时仍能正常工作
2. **性能**: 避免在循环中频繁调用翻译函数
3. **用户体验**: 语言切换时应立即生效,无需刷新页面
4. **数据持久化**: 用户的语言选择应保存在localStorage中

---

## ✨ 总结

**当前进度**: 70% 完成
- ✅ 语言文件: 100%
- ✅ 后端API: 80%
- ⏳ HTML/UI: 20%
- ⏳ JavaScript: 30%

**预计剩余工作量**: 2-3小时

**下一步行动**: 
1. 修改JavaScript中的硬编码文本
2. 在API调用中添加language参数
3. 测试并验证功能
