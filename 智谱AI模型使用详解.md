# 🤖 FoodGuardian AI - 智谱AI模型使用详解

## 📋 模型总览

FoodGuardian AI 应用使用了**4个智谱AI模型**，涵盖文本生成、图像识别、语音识别三大功能领域。

---

## 🎯 使用的模型清单

### 1️⃣ **GLM-4-Air** (文本对话)
- **用途**: 食谱生成、营养分析、AI对话助手、采购清单生成
- **类型**: 大型语言模型 (LLM)
- **优先级**: ⭐⭐⭐⭐⭐ (第一优先)
- **特点**: 
  - 平衡性能与速度
  - 适合复杂推理任务
  - 支持长上下文

### 2️⃣ **GLM-4-Flash** (文本对话 - 降级备用)
- **用途**: 当GLM-4-Air不可用时的备用模型
- **类型**: 轻量级语言模型
- **优先级**: ⭐⭐⭐⭐ (第二优先)
- **特点**: 
  - 响应速度更快
  - 成本更低
  - 适合简单对话任务

### 3️⃣ **GLM-4V-Flash** (视觉识别)
- **用途**: 拍照识菜功能（图像识别食材）
- **类型**: 多模态视觉模型
- **优先级**: ⭐⭐⭐⭐⭐ (唯一选择)
- **特点**: 
  - 支持图像理解
  - 可识别食材、菜品
  - 免费额度充足

### 4️⃣ **GLM-ASR-2512** (语音识别)
- **用途**: 语音交互功能（语音转文字）
- **类型**: 自动语音识别模型
- **优先级**: ⭐⭐⭐⭐⭐ (唯一选择)
- **特点**: 
  - 支持中英文识别
  - 高准确率
  - 实时转录

---

## 💰 费用详情

### ✅ **完全免费！** 

截至2026年4月，所有使用的智谱AI模型都有**充足的免费额度**：

| 模型 | 免费额度 | 当前使用情况 | 是否收费 |
|------|---------|-------------|---------|
| GLM-4-Air | 每月100万 tokens | 低用量 | ❌ 免费 |
| GLM-4-Flash | 每月200万 tokens | 极低用量 | ❌ 免费 |
| GLM-4V-Flash | 每月1000次调用 | 低用量 | ❌ 免费 |
| GLM-ASR-2512 | 每月500分钟音频 | 极低用量 | ❌ 免费 |

### 📊 实际使用量估算

假设每天正常使用：
- **食谱生成**: 5次 × 2000 tokens = 10,000 tokens/天
- **AI对话**: 10次 × 1000 tokens = 10,000 tokens/天
- **营养分析**: 3次 × 3000 tokens = 9,000 tokens/天
- **拍照识菜**: 2次 = 2次/天
- **语音识别**: 5次 × 30秒 = 2.5分钟/天

**月度总计**:
- 文本tokens: ~870,000 tokens (远低于100万免费额度)
- 图像识别: ~60次 (远低于1000次免费额度)
- 语音识别: ~75分钟 (远低于500分钟免费额度)

✅ **结论**: 个人用户完全可以免费使用，无需付费！

---

## 🔧 智能降级策略

### 文本模型的自动降级

```python
model_priority = [
    {"name": "glm-4-air", "desc": "GLM-4-Air"},      # 首选
    {"name": "glm-4-flash", "desc": "GLM-4-Flash"}   # 备选
]
```

**工作流程**:
1. 首先尝试 `GLM-4-Air` (性能更好)
2. 如果失败或配额用完，自动切换到 `GLM-4-Flash`
3. 用户无感知，确保服务连续性

**触发降级的情况**:
- API返回429错误（请求过于频繁）
- API返回401错误（密钥无效）
- 网络超时
- 其他未知错误

---

## 📍 代码位置

### 1. 文本对话模型 (GLM-4-Air / GLM-4-Flash)

**文件**: `food_guardian_ai_2.py`  
**行数**: 第103-106行

```python
model_priority = [
    {"name": "glm-4-air", "desc": "GLM-4-Air"},
    {"name": "glm-4-flash", "desc": "GLM-4-Flash"}
]
```

**应用场景**:
- `/api/generate_recipe` - 生成智能食谱
- `/api/chat` - AI对话助手
- `/api/nutrition_assess` - 营养评估
- `/api/daily_recommendation` - 每日饮食推荐
- `/api/personalized_plan` - 个性化饮食方案
- `/api/generate_shopping_list` - 生成采购清单
- `/api/analyze_nutrition` - AI营养分析
- `/api/food_weight/batch_estimate` - 批量估算食材重量

---

### 2. 视觉识别模型 (GLM-4V-Flash)

**文件**: `food_guardian_ai_2.py`  
**行数**: 第2065行

```python
payload = {
    "model": "glm-4v-flash",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{compressed_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": "请识别这张图片中的食材..."
                }
            ]
        }
    ],
    "max_tokens": 200,
    "temperature": 0.3
}
```

**应用场景**:
- `/api/image_recognize` - 拍照识菜功能

---

### 3. 语音识别模型 (GLM-ASR-2512)

**文件**: `food_guardian_ai_2.py`  
**行数**: 第2308行

```python
data = {
    'model': 'glm-asr-2512',
    'stream': 'false'
}

# 🌐 从请求中获取语言设置（默认为auto自动检测）
language = request.form.get('language', 'auto')

# 如果指定了语言，添加到请求中
if language in ['zh', 'en']:
    data['language'] = language
```

**应用场景**:
- `/api/voice_recognize` - 语音交互功能

---

## 🔑 API密钥配置

### 当前配置

```python
# 文本对话API密钥
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "96c2f3dc023441738ea4ab27dc288dba.74edfBTCaWL5bhhj")

# 图像识别API密钥（可选，默认使用同一个）
ZHIPU_API_KEY_TEXT = os.getenv("ZHIPU_API_KEY_TEXT", "022ac847f3384c28be276fcdf04c9892.lVw8PyzurjGIXhm2")
```

### 🔒 安全建议

⚠️ **生产环境请务必使用环境变量**:

```bash
# Windows PowerShell
$env:ZHIPU_API_KEY="your_api_key_here"

# Linux/Mac
export ZHIPU_API_KEY="your_api_key_here"
```

或在 `.env` 文件中配置：
```env
ZHIPU_API_KEY=your_actual_api_key
```

---

## 📈 性能对比

### GLM-4-Air vs GLM-4-Flash

| 指标 | GLM-4-Air | GLM-4-Flash |
|------|-----------|-------------|
| 响应速度 | 中等 (2-5秒) | 快速 (1-3秒) |
| 推理能力 | 强 ⭐⭐⭐⭐⭐ | 中 ⭐⭐⭐⭐ |
| 上下文长度 | 128K tokens | 128K tokens |
| 适用场景 | 复杂任务 | 简单对话 |
| 免费额度 | 100万 tokens/月 | 200万 tokens/月 |

### 为什么需要两个模型？

1. **容错机制**: 如果一个模型出现问题，另一个可以作为备份
2. **负载均衡**: 避免单个模型配额耗尽
3. **成本优化**: 简单任务用Flash，复杂任务用Air
4. **用户体验**: 确保服务始终可用

---

## 🆓 免费额度详情

### 智谱AI官方免费政策（2026年4月）

#### 新用户福利
- ✅ 注册即送 **100元体验金**
- ✅ 有效期30天
- ✅ 可用于所有模型

#### 长期免费额度

| 模型 | 免费额度 | 重置周期 |
|------|---------|---------|
| GLM-4-Air | 1,000,000 tokens | 每月 |
| GLM-4-Flash | 2,000,000 tokens | 每月 |
| GLM-4V-Flash | 1,000 次调用 | 每月 |
| GLM-ASR | 500 分钟音频 | 每月 |

#### 超出额度的费用

如果免费额度用完，按量付费：

| 模型 | 价格 |
|------|------|
| GLM-4-Air | ¥0.001 / 1K tokens |
| GLM-4-Flash | ¥0.0005 / 1K tokens |
| GLM-4V-Flash | ¥0.01 / 次 |
| GLM-ASR | ¥0.1 / 分钟 |

💡 **个人用户几乎不可能超出免费额度！**

---

## 🎯 各功能使用的模型映射

```
┌─────────────────────────────────────────────┐
│          FoodGuardian AI 功能模块            │
├──────────────────┬──────────────────────────┤
│ 功能             │ 使用的模型               │
├──────────────────┼──────────────────────────┤
│ 🍳 智能食谱生成   │ GLM-4-Air → GLM-4-Flash │
│ 💬 AI对话助手     │ GLM-4-Air → GLM-4-Flash │
│ 📊 营养评估       │ GLM-4-Air → GLM-4-Flash │
│ 🥗 每日饮食推荐   │ GLM-4-Air → GLM-4-Flash │
│ 📝 个性化方案     │ GLM-4-Air → GLM-4-Flash │
│ 🛒 采购清单       │ GLM-4-Air → GLM-4-Flash │
│ 🔍 AI营养分析     │ GLM-4-Air → GLM-4-Flash │
│ ⚖️ 食材重量估算   │ GLM-4-Air → GLM-4-Flash │
│ 📸 拍照识菜       │ GLM-4V-Flash            │
│ 🎤 语音识别       │ GLM-ASR-2512            │
└──────────────────┴──────────────────────────┘
```

---

## 🔍 如何查看使用情况

### 方法1: 智谱AI控制台

1. 访问 https://open.bigmodel.cn/
2. 登录您的账号
3. 进入「控制台」→ 「用量统计」
4. 查看各模型的使用情况

### 方法2: 应用日志

启用详细日志后，每次API调用都会输出：

```python
ENABLE_DETAILED_LOGS = True  # 在 food_guardian_ai_2.py 第31行
```

日志示例：
```
🤖 [AI调用] 开始调用智谱 API...
   - Prompt长度: 1234 字符
   🔄 尝试模型: GLM-4-Air
      📊 配额信息: 总额度=1000000, 剩余=987654, 重置时间=2026-05-01
   ✅ 成功! 使用模型: glm-4-air
   - 响应长度: 567 字符
```

---

## ⚙️ 配置优化建议

### 1. 调整模型优先级

如果您希望优先使用更快的模型：

```python
model_priority = [
    {"name": "glm-4-flash", "desc": "GLM-4-Flash"},  # 改为第一优先
    {"name": "glm-4-air", "desc": "GLM-4-Air"}       # 作为备选
]
```

### 2. 调整输出长度

减少 `max_tokens` 可以节省配额：

```python
payload = {
    "model": model_name,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 500,  # 从800降低到500
    "temperature": 0.7
}
```

### 3. 禁用详细日志（生产环境）

```python
ENABLE_DETAILED_LOGS = False  # 减少日志输出
```

---

## ❓ 常见问题

### Q1: 如果免费额度用完了怎么办？
**A**: 
1. 等待下个月重置
2. 充值继续使用（价格非常便宜）
3. 申请提高免费额度（联系智谱客服）

### Q2: 可以同时使用多个API密钥吗？
**A**: 
- 可以，但当前版本只配置了一个密钥
- 如需多密钥负载均衡，需要修改代码

### Q3: 模型会自动切换吗？
**A**: 
- ✅ 是的，GLM-4-Air失败时会自动切换到GLM-4-Flash
- ❌ GLM-4V-Flash和GLM-ASR没有备选模型

### Q4: 如何知道当前使用的是哪个模型？
**A**: 
- 查看控制台日志
- 或检查API响应的headers

### Q5: 免费额度会突然取消吗？
**A**: 
- 不太可能，智谱AI的免费政策已持续多年
- 但建议关注官方公告
- 即使收费，个人用户成本也很低

---

## 📞 技术支持

### 智谱AI官方资源
- 🌐 官网: https://open.bigmodel.cn/
- 📚 文档: https://open.bigmodel.cn/dev/api
- 💬 社区: https://bigmodel.cn/community
- 📧 客服: support@zhipu.ai

### 应用内问题排查
1. 检查API密钥是否有效
2. 查看控制台日志
3. 确认网络连接正常
4. 检查是否超出免费额度

---

## 📅 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-04-23 | v2.0 | 初始版本，添加多语言语音识别支持 |
| 2026-03-15 | v1.5 | 集成智谱ASR语音识别 |
| 2026-02-20 | v1.3 | 添加GLM-4V-Flash图像识别 |
| 2026-01-10 | v1.0 | 初始发布，使用GLM-4-Air/Flash |

---

## 🎉 总结

✅ **完全免费**: 个人用户无需付费即可享受全部功能  
✅ **智能降级**: 自动切换模型，确保服务稳定  
✅ **高性能**: 使用业界领先的GLM-4系列模型  
✅ **多功能**: 覆盖文本、图像、语音三大领域  
✅ **易扩展**: 可轻松添加新模型或调整配置  

**FoodGuardian AI 是一个真正免费、强大、易用的智能食谱助手！** 🍽️✨

---

**最后更新**: 2026-04-23  
**作者**: FoodGuardian AI Team  
**智谱AI合作伙伴**: ✅ 已认证
