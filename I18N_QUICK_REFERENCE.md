# 🌍 FoodGuardian AI - 国际化快速参考

## 🚀 快速开始

### 1. 启动服务器
```bash
python food_guardian_ai_2.py
```

或运行测试脚本:
```bash
python test_i18n.py
```

### 2. 访问应用
浏览器打开: http://localhost:5000

### 3. 切换语言
点击右上角的 🌐 语言切换按钮

---

## ✅ 已支持多语言的功能

### AI生成内容 (100% 完成)

| 功能 | API端点 | 状态 |
|------|---------|------|
| 智能食谱生成 | `/api/generate_recipe` | ✅ |
| AI对话助手 | `/api/chat` | ✅ |
| 营养分析 | `/api/analyze_nutrition` | ✅ |
| 采购清单 | `/api/generate_shopping_list` | ✅ |

### 前端集成 (70% 完成)

| 组件 | 状态 | 说明 |
|------|------|------|
| i18n管理器 | ✅ | static/js/i18n.js |
| 语言文件 | ✅ | locales/*.json |
| API调用 | ✅ | 已添加language参数 |
| UI文本 | ⏳ | 需要添加data-i18n |

---

## 🔧 开发者指南

### 添加新的翻译键

#### 1. 在zh-CN.json中添加
```json
{
  "my_section": {
    "my_key": "中文文本"
  }
}
```

#### 2. 在en-US.json中添加对应英文
```json
{
  "my_section": {
    "my_key": "English text"
  }
}
```

#### 3. 在HTML中使用
```html
<!-- 静态文本 -->
<div data-i18n="my_section.my_key">中文文本</div>

<!-- JavaScript动态文本 -->
<script>
const text = window.i18n.t('my_section.my_key');
</script>
```

### 在API调用中传递语言

```javascript
// 获取当前语言
const language = window.i18n ? window.i18n.getCurrentLanguage() : 'zh-CN';

// 添加到请求体
fetch('/api/your_endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        // ... 其他参数
        language: language
    })
});
```

### 在后端处理多语言

```python
@app.route('/api/your_endpoint', methods=['POST'])
def your_endpoint():
    data = request.json
    language = data.get('language', 'zh-CN')
    
    if language == 'en-US':
        prompt = "Your English prompt..."
    else:
        prompt = "你的中文提示词..."
    
    # 调用AI API
    result = call_ai_api(prompt)
    return jsonify({'success': True, 'result': result['content']})
```

---

## 📊 翻译键组织结构

```
app.*          - 应用级别 (标题、副标题)
nav.*          - 导航栏
home.*         - 首页
recipe.*       - 智能食谱
nutrition.*    - 营养分析
fridge.*       - 冰箱管理
profile.*      - 个人中心
chat.*         - AI对话
camera.*       - 拍照识菜
voice.*        - 语音交互
shopping.*     - 采购清单
about.*        - 关于页面
common.*       - 通用提示和错误
```

---

## 🐛 常见问题

### Q1: 切换语言后UI没有变化?
**A**: UI静态文本需要手动添加`data-i18n`属性。AI生成的内容会自动切换。

### Q2: 如何添加新的语言?
**A**: 
1. 创建 `locales/xx-XX.json`
2. 复制zh-CN.json的结构
3. 翻译成目标语言
4. 在i18n.js中添加语言选项

### Q3: API返回的语言不对?
**A**: 检查前端是否正确传递了`language`参数,后端是否正确接收和处理。

### Q4: 如何调试i18n?
**A**: 
```javascript
// 在浏览器控制台
console.log(window.i18n.getCurrentLanguage());  // 查看当前语言
console.log(window.i18n.t('app.title'));        // 测试翻译
window.i18n.setLanguage('en-US');               // 手动切换
```

---

## 📝 待办事项清单

### 高优先级
- [ ] 为HTML静态文本添加data-i18n属性
- [ ] 实现autoTranslate自动替换功能
- [ ] 测试所有页面的中英文切换

### 中优先级
- [ ] 修改JavaScript中的硬编码提示文本
- [ ] 优化翻译质量
- [ ] 添加更多语言支持(日语、韩语等)

### 低优先级
- [ ] 添加RTL语言支持(阿拉伯语等)
- [ ] 实现按需加载语言文件
- [ ] 添加翻译管理系统

---

## 🔗 相关文档

- [完整实施方案](./I18N_IMPLEMENTATION_PLAN.md)
- [完成报告](./I18N_COMPLETION_REPORT.md)
- [i18n管理器源码](./static/js/i18n.js)
- [中文语言包](./locales/zh-CN.json)
- [英文语言包](./locales/en-US.json)

---

## 💡 最佳实践

1. **始终提供fallback**: 确保在i18n未加载时应用仍能工作
2. **保持翻译键一致**: zh-CN和en-US的键必须完全匹配
3. **使用语义化键名**: `section.element.purpose` 格式
4. **避免硬编码文本**: 所有用户可见文本都应通过i18n
5. **测试多种场景**: 不同语言、不同屏幕尺寸、不同浏览器

---

**最后更新**: 2026-04-23  
**版本**: v1.0  
**状态**: 85% 完成
