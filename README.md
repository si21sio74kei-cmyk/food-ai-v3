# Food AI - 智能饮食管理助手

一个基于 AI 的智能饮食管理和营养分析工具。

## ✨ 功能特性

- 🤖 AI 智能对话 - 与 AI 助手讨论饮食和营养问题
- 📊 营养分析 - 自动分析食物的营养成分（基于联合国WHO标准）
- 🍽️ 食谱生成 - 根据需求生成个性化食谱
- 🌍 国际化支持 - 支持中文和英文
- 🎨 现代化 UI - 优雅的 iOS 风格界面
- 📱 Web 应用 - 基于 Flask 的 Web 版本

## 🚀 快速开始

### 本地运行

#### 安装依赖

```bash
pip install -r requirements.txt
```

或者双击运行：
```
安装依赖.bat
```

#### 启动应用

```bash
python food_guardian_ai_2.py
```

或者双击运行：
```
启动应用.bat
```

访问 http://localhost:5000

### ☁️ 在线部署（免费）

本项目支持免费部署到云端，让任何人都可以访问！

#### 推荐方案：Vercel 部署

1. **上传到 GitHub**
   ```bash
   git add .
   git commit -m "准备部署"
   git push origin main
   ```

2. **在 Vercel 上部署**
   - 访问 https://vercel.com
   - 使用 GitHub 账号登录
   - 导入你的仓库
   - 配置环境变量：
     - `ZHIPU_API_KEY`
     - `ZHIPU_API_KEY_TEXT`
   - 点击 Deploy

3. **获取在线地址**
   - 部署完成后，你会得到一个 URL
   - 例如：`https://food-ai.vercel.app`

详细部署步骤请查看：[部署指南.md](./部署指南.md)

## 📁 项目结构

```
Food AI/
├── food_guardian_ai.py          # 主程序
├── food_guardian_ai_2.py        # 主程序v2
├── fgai_local_data.json         # 本地数据
├── un_nutrition_standards.json  # 营养标准数据
├── food_weight_database.json    # 食材重量数据库
├── locales/                     # 国际化文件
│   ├── zh-CN.json
│   └── en-US.json
├── static/                      # 静态资源
│   └── js/
│       └── i18n.js
├── templates/                   # HTML 模板
│   └── index.html
├── requirements.txt             # Python依赖
├── .gitignore                   # Git忽略配置
├── *.bat                        # 启动脚本
└── *.md                         # 文档说明
```

## 📝 说明文档

### 🌟 核心数据文件
- **[联合国WHO营养标准数据说明](./联合国WHO营养标准数据说明.md)** ⭐ **重要**
  - 详细解释 `un_nutrition_standards.json` 文件
  - WHO营养标准的科学依据和应用方法
  - 4类人群（成人/青少年/儿童/老年人）的营养需求

### 快速开始
- [快速启动指南](./快速启动指南.md)
- [完整测试指南](./完整测试指南.md)
- [快速测试清单](./快速测试清单.md)

### 功能文档
- [功能完整性报告](./功能完整性报告.md)
- [功能对比详细检查报告](./功能对比详细检查报告.md)
- [功能完整性验证报告_v2](./功能完整性验证报告_v2.md)
- [功能完整性验证报告_v3](./功能完整性验证报告_v3.md)

### 优化与修复
- [UI优化报告](./UI优化报告.md)
- [修复说明](./修复说明.md)
- [优化对比](./优化对比.md)
- [AI对话与输出格式优化说明](./AI对话与输出格式优化说明.md)

### 技术文档
- [Web版功能完整复刻报告](./Web版功能完整复刻报告.md)
- [Python版vsWeb版完整对比报告](./Python版vsWeb版完整对比报告_最终版.md)
- [Python版vsWeb版完整逻辑对比报告](./Python版vsWeb版完整逻辑对比报告_最终完整版.md)
- [Web版与Python版逻辑对比及修复报告](./Web版与Python版逻辑对比及修复报告.md)

### 其他
- [国际化实施报告](./国际化实施报告.md)
- [食材重量智能估算系统说明](./食材重量智能估算系统说明.md)
- [食谱生成计数器功能说明](./食谱生成计数器功能说明.md)
- [测试指南-自动化功能](./测试指南-自动化功能.md)

## 🛠️ 技术栈

- **后端**: Python + Flask
- **AI**: GLM-4 API
- **前端**: HTML/CSS/JavaScript
- **国际化**: i18n

## 📄 许可证

本项目仅供学习和研究使用。

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者！
