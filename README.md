<p align="center">
  <img src="https://raw.githubusercontent.com/si21sio74kei-cmyk/food-ai-v3/main/assets/logo.jpg" width="128" height="128" alt="FoodGuardian AI Logo" style="border-radius: 28px;">
</p>

# 🌿 FoodGuardian AI - 智能食谱与家庭环保助手

**让每一口都不被浪费 · 智能食谱 + 营养评估 + 环保量化**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask-000000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Zhipu AI](https://img.shields.io/badge/Model-GLM--4%20%7C%20GLM--4V%20%7C%20GLM--ASR-blueviolet.svg)](https://open.bigmodel.cn/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/si21sio74kei-cmyk/food-ai-v3/pulls)

[功能全景](#-核心功能全景) • [科学模型](#-科学评估与量化模型) • [技术架构](#-技术架构与技术栈) • [快速上手](#-快速上手) • [接口文档](#-api-路由总览) • [未来路线](#-未来路线图-roadmap)

---

## 📸 核心效果预览

> 💡 **5秒看懂 FoodGuardian AI**：拍照秒级识别食材 $\rightarrow$ 实时 SSE 流式打字生成减损食谱 $\rightarrow$ 基于 FAO 模型动态量化水/碳节约量。

<!-- 建议录制 10 秒操作 GIF 放入 assets/demo.gif，将下方注释解开即可展示 -->
<!-- ![FoodGuardian AI 交互动图](assets/demo.gif) -->

---

## 📖 项目简介

**FoodGuardian AI** 是一款将**前沿生成式人工智能**、**WHO/FAO 膳食营养科学**与**家庭微环保理念**深度融合的全栈 Web 应用。

通过精准计算每餐烹饪份量、自动识别冰箱剩余食材、多模态智能交互（语音输入与图像识别）以及量化每一餐节约的粮食、水与碳排放，FoodGuardian AI 帮助现代家庭从“被动扔掉过期食材”转向“主动拥抱绿色高品质生活”。

## ✨ 核心亮点

* 🍳 **零浪费动态配比**：根据用餐人数（1-20人）、个人饭量系数（0.7-2.0）及就餐场景（家常/健康/素食/宴客），精准计算每道菜克重配比。

* 📊 **循证营养评估引擎**：严格对标**世界卫生组织 (WHO) 健康饮食原则**与《中国居民膳食指南 (2022)》，支持儿童、青少年、成年人、老年人及“多人群对比”的专业营养诊断。

* 🔄 **三餐自动化闭环流程**：

  1. 第 1-2 餐：生成食谱并自动估算、录入摄入数据。

  2. 第 3 餐：生成完成后自动触发当日全天营养健康评估。

  3. 智能预测：根据全天摄入缺口与冰箱库存，自动规划次日饮食推荐。

* 🎙️ **多模态 AI 交互**：

  * **GLM-ASR 语音对话**：浏览器端 WebM 实时捕获并重采样为 PCM/WAV，实现极速语音问答。

  * **GLM-4V 视觉识菜**：拍照或上传图片，毫秒级提取食材列表并无缝导入食谱与记录表。

* ⚡ **全链路流式响应 (SSE)**：食谱生成、营养分析、购物清单与 AI 聊天均采用 Server-Sent Events 流式传输，打字机般丝滑输出。

* 🛡️ **双轨弹性数据架构**：支持本地轻量 SQLite / JSON 存储与云端 Supabase PostgreSQL 同步，提供防暴破安全门禁与 12 位一次性应急恢复码。

## 🧭 核心功能全景

| 模块 | 功能说明 | 核心交互与特点 | 
| ----- | ----- | ----- | 
| **🏠 绿色看板 (Home)** | 用户档案、人群设定、累计环保成就展示 | 实时展示食物减损量 (g)、节水 (L) 与碳减排 (g)；支持近 7 天历史回溯与单条记录行内编辑 | 
| **🍳 智能食谱 (Recipes)** | 基于 AI 的个性化菜谱生成器 | 支持关联冰箱库存、4 种餐饮风格、动态饭量缩放，附带详细烹饪步骤与环保量化 | 
| **🥗 营养分析 (Nutrition)** | 深度营养素拆解与健康评分 | 深度解析热量、宏量营养素、微量元素（钙/铁/维生素），提供高蛋白/低卡等健康标签 | 
| **🤖 AI 对话助手 (Chat)** | 全能型烹饪与营养顾问 | 预设高频痛点问题（如土豆发芽辨别、肉类去腥），支持上下文打字机流式回复 | 
| **🎤 语音交互 (Voice)** | 按住说话，智能问答 | 基于 Web Audio API 进行前端音频重编码，智谱专用 ASR 转换，可编辑文本后提问 | 
| **📸 拍照识菜 (Camera)** | 图像智能识别食材 | 调用浏览器摄像头或文件上传，结合视觉大模型提取食材，一键填充到食谱与摄入表 | 
| **🧊 智能冰箱 (Fridge)** | 家庭食材存量管理 | 实时登记食材克重与保质期，烹饪时可勾选“优先消耗冰箱现有食材” | 
| **🛒 采购清单 (Shopping)** | 按超市动线智能生成的采购单 | 蔬菜区/肉类区/冷冻区分区归纳，提供地区价格校准器与购买预算区间估算 | 

## 🔬 科学评估与量化模型

### 1. 环保量化换算模型

环保影响基于粮食及农业组织 (FAO) 与 Water Footprint Network 的实证统计平均系数构建：

1. **基准消耗量计算**：

  `Total Portion = Σ (BasePortion × People × Multiplier × Appetite)`

2. **避免浪费量（传统家庭平均浪费率约** $25\%$**）**：

  `Waste Reduced (g) = Total Portion × 0.25`

3. **水资源节约量（中国膳食加权平均每克食材水足迹约** $0.5\text{ L}$**）**：

  `Water Saved (L) = Waste Reduced × 0.5`

4. **碳排放减少量（中国膳食混合平均碳排放强度约** $3.0\text{ g CO}_2\text{e/g}$**）**：

  `CO₂ Reduced (g) = Waste Reduced × 3.0`

### 2. 人群营养摄入参考基准 (每日标准)

系统内嵌 `un_nutrition_standards.json`，各项膳食边界依据中国营养学会与 WHO 推荐设定：

| 人群标签 | 年龄段 | 蔬菜类推荐 | 水果类推荐 | 肉类推荐 | 蛋类推荐 | 核心关照重点 | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | 
| **成年人 (Adults)** | 18-60 岁 | 400 - 800 g | 200 - 400 g | 50 - 150 g | 30 - 70 g | 宏量营养均衡，控制饱和脂肪与加工肉类 | 
| **青少年 (Teens)** | 13-17 岁 | 300 - 600 g | 150 - 350 g | 50 - 120 g | 40 - 80 g | 优质蛋白、骨骼发育所需的钙质与微量元素 | 
| **儿童 (Children)** | 6-12 岁 | 200 - 500 g | 100 - 300 g | 30 - 100 g | 30 - 60 g | 营养密度高、少油少盐、趣味饮食形态 | 
| **老年人 (Elderly)** | 60 岁以上 | 300 - 600 g | 150 - 300 g | 40 - 100 g | 30 - 60 g | 易消化软烂食材、高钙吸收、控制胆固醇 | 

## 🏗️ 技术架构与技术栈

### 架构拓扑

```
┌────────────────────────────────────────────────────────┐
│             Web Client (HTML5 / Vanilla ES6+)          │
│   iOS Frosted Glass Style · CSS Variables · SSE Reader │
└──────────────┬───────────────────────────▲─────────────┘
               │ HTTP / SSE                │ Streaming
┌──────────────▼───────────────────────────┴─────────────┐
│                 Flask Application Core                 │
│  - Session Control & Anti-Brute-Force Rate Limiter    │
│  - Nutrition Assessment & Recipe Generation Engine     │
│  - Audio Format Transcoder (WebM -> WAV)               │
└──────────┬───────────────────────────────┬─────────────┘
           │                               │
┌──────────▼──────────┐         ┌──────────▼─────────────┐
│    Cloud / Local    │         │       AI Models        │
│      Databases      │         │   (Zhipu Open Platform)│
├─────────────────────┤         ├────────────────────────┤
│ • Supabase (Cloud)  │         │ • GLM-4-Air / Flash    │
│ • SQLite (Local)    │         │ • GLM-4V-Flash         │
│ • Local JSON Fallback│        │ • GLM-ASR-2512         │
└─────────────────────┘         └────────────────────────┘


```

### 技术栈清单

* **后端开发**：Python 3.9+ / Flask 框架

* **大模型生态**：智谱 AI 开放平台开放大模型

  * 文本生成与推理：`glm-4-air`, `glm-4-flash`

  * 多模态图文识别：`glm-4v-flash`

  * 实时语音转写：`glm-asr-2512`

* **数据库与存储**：

  * 本地：SQLite3（预置用户表、凭证表与每餐摄入流水表）

  * 云端：Supabase (PostgreSQL) RESTful API 同步

* **前端架构**：

  * 纯原生标准驱动（No Webpack/Vite 捆绑，加载速度极快）

  * 响应式设计（自适应桌面端左侧悬浮导航与移动端沉浸式 TabBar）

  * Web Audio API（浏览器端 PCM 数据编码）与 HTML5 MediaDevices API

* **安全加固**：

  * 基于 Werkzeug 的 PBKDF2/SHA-256 凭据哈希

  * IP + 账号粒度暴力破解拦截器（15 分钟内超 5 次错误锁定 15 分钟）

  * 3 天滑动会话注销策略与历史记录滚动窗口剪裁（数据仅保留近 7 天）

## 🚀 快速上手

### 1. 克隆代码仓库

```bash
git clone https://github.com/si21sio74kei-cmyk/food-ai-v3.git
cd food-ai-v3
  

```

### 2. 创建并激活虚拟环境

```
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate


```

### 3. 安装依赖包

```
pip install flask requests python-dotenv werkzeug pillow


```

### 4. 配置环境变量

在项目根目录下创建 `.env` 文件，填入智谱开放平台的 API 凭据：

```
# ==================== AI 接口配置 (必填) ====================
ZHIPU_API_KEY=your_zhipu_api_key_here
ZHIPU_API_KEY_TEXT=your_zhipu_api_key_text_here

# ==================== 安全与会话配置 ====================
SESSION_SECRET=fgai-secret-key-production-random-string

# ==================== 云端数据库 (选填，不填则默认使用本地 SQLite) ====================
# SUPABASE_URL=https://your-project-id.supabase.co
# SUPABASE_KEY=your_supabase_service_role_key


```

### 5. 启动服务

```
python food_guardian_ai_2.py


```

终端输出如下提示即代表启动成功：

```
======================================================================
🍽️  FoodGuardian AI v3.0 - 智能食谱助手 (Web版)
======================================================================
📱 正在启动服务器...
🌐 访问地址: http://localhost:5000
💡 按 Ctrl+C 停止服务器
======================================================================


```

打开浏览器访问 `http://localhost:5000` 即可开始使用。

## ⚙️ 环境变量详细配置表

| 变量名 | 是否必填 | 默认值 | 作用描述 | 
| ----- | ----- | ----- | ----- | 
| `ZHIPU_API_KEY` | **是** | 空 | 智谱 AI 平台的主密钥（用于多模态识别与语音转写） | 
| `ZHIPU_API_KEY_TEXT` | 否 | `ZHIPU_API_KEY` | 专门用于文本生成与对话的 API 密钥 | 
| `SESSION_SECRET` | 否 | `fgai-dev-secret...` | Flask 会话签名密钥（生产环境建议配置长随机串） | 
| `SUPABASE_URL` | 否 | 空 | Supabase 项目的基础 URL | 
| `SUPABASE_KEY` | 否 | 空 | Supabase `service_role` 或专用后端密钥 | 
| `LOCAL_ACCOUNT_DB` | 否 | `fgai_accounts.db` | 本地 SQLite 账号库的文件路径 | 
| `ENABLE_LOCAL_ACCOUNTS` | 否 | `1` | 是否启用本地账号数据库兜底 | 

## 📡 API 路由总览

### 1. 认证鉴权模块

| 路径 | 方法 | 功能说明 | 
| ----- | ----- | ----- | 
| `/api/auth/register` | `POST` | 注册新用户（自动签发 12 位一次性应急恢复码） | 
| `/api/auth/login` | `POST` | 用户登录（支持防爆破锁定） | 
| `/api/auth/recover` | `POST` | 基于恢复码直接重设密码 | 
| `/api/auth/logout` | `POST` | 安全退出并清理会话 | 
| `/api/auth/me` | `GET` | 查询当前会话状态及数据后端类型 | 

### 2. 核心业务与流式接口

| 路径 | 方法 | 传输协议 | 业务功能 | 
| ----- | ----- | ----- | ----- | 
| `/api/generate_recipe_stream` | `POST` | `SSE` | 智能食谱流式输出 + 环保减损实时计算 | 
| `/api/analyze_nutrition_stream` | `POST` | `SSE` | 深度营养拆解评估流式输出 | 
| `/api/chat_stream` | `POST` | `SSE` | 烹饪营养问题实时流式解答 | 
| `/api/generate_shopping_list_stream` | `POST` | `SSE` | 智能采购清单分区生成与地域预算估算 | 
| `/api/generate_daily_recommendation_stream` | `POST` | `SSE` | 基于全天摄入缺口预测次日营养补全推荐 | 
| `/api/calculate_impact` | `POST` | `JSON` | 轻量化本地环保影响实时防抖计算 | 
| `/api/nutrition_assess` | `POST` | `JSON` | 提交单日饮食汇总生成图文诊断报告 | 

### 3. 多模态与边缘工具

| 路径 | 方法 | 业务功能 | 
| ----- | ----- | ----- | 
| `/api/image_recognize` | `POST` | 图像食材视觉识别（GLM-4V） | 
| `/api/voice_recognize` | `POST` | WAV 音频流转文本识别（GLM-ASR） | 
| `/api/food_weight/query` | `POST` | 食材估重查询（本地离线库 + AI 兜底） | 
| `/api/fridge/add` | `POST` | 添加冰箱库存条目 | 
| `/api/fridge/list` | `GET` | 获取当前冰箱剩余食材列表 | 
| `/api/save_intake` | `POST` | 记录餐次实际摄入数据并触发阈值健康告警 | 
| `/api/intake/history/7days` | `GET` | 提取滚动 7 天每日营养摄入报表 | 

## 🔒 隐私与安全性规范

1. **零个人敏感数据暴露**：本系统不强制收集手机号、邮箱等个人实名信息；注册仅需用户名与密码。

2. **凭据安全**：密码均使用不可逆的 Salted Hash 算法加密保存。忘记密码时仅能通过注册时展示一次的恢复码重设。

3. **数据生命周期管理**：

   * 饮食摄入数据在后端采用 **滚动 7 天窗口策略**，第 8 天历史自动被物理删除，减少不必要的个人数据堆积。

   * 对话记录仅在当前浏览器生命周期保留，不作持久化云端存储。

4. **频率限制与防护**：内置 IP + 账号维度的失败重试熔断器，全方位杜绝脚本化暴力猜测。

## 🤝 参与贡献

欢迎对本项目提出建议与改进！请遵照以下流程：

1. Fork 本仓库。

2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)。

3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)。

4. 推送到远程分支 (`git push origin feature/AmazingFeature`)。

5. 新建 Pull Request。

## 📄 开源许可

本项目依据 [MIT License](https://opensource.org/licenses/MIT) 开源，欢迎自由用于教育、科普研究及二次开发。

  ---

## 🗺️ 未来路线图 (Roadmap)

- [ ] 支持超市小票拍照智能识别并批量录入食材
- [ ] 接入 Home Assistant，联动智能冰箱传感器
- [ ] 增加微信小程序 / PWA 移动端免安装支持
- [ ] 引入轻量级本地边缘端语音模型（支持纯离线问答）

---

## 📈 Star 走势图

如果这个项目对你的家庭生活或学术研究有所启发，欢迎给个 ⭐ 支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=si21sio74kei-cmyk/food-ai-v3&type=Date)](https://star-history.com/#si21sio74kei-cmyk/food-ai-v3&Date)