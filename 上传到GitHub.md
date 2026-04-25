# 上传到 GitHub 快速指南

## 前置准备

✅ 已创建以下文件：
- `.gitignore` - Git 忽略配置
- `README.md` - 项目说明文档
- `requirements.txt` - Python 依赖列表

## 方法一：使用 GitHub Desktop（最简单）

### 1. 下载安装
访问 https://desktop.github.com/ 下载并安装

### 2. 添加项目
- 打开 GitHub Desktop
- 点击 `File` → `Add Local Repository...`
- 选择 `d:\MyDesktop\Food AI` 文件夹
- 如果提示不是 Git 仓库，点击 `create a repository`
- 填写名称 "Food-AI"，点击 `Create Repository`

### 3. 发布到 GitHub
- 点击顶部 `Publish repository` 按钮
- 设置仓库名称和可见性
- 点击 `Publish Repository`

完成！✅

## 方法二：网页直接上传（无需安装）

### 1. 创建仓库
- 登录 GitHub
- 点击右上角 "+" → "New repository"
- 仓库名：Food-AI
- 选择公开/私有
- **不要**勾选 "Initialize with README"
- 点击 "Create repository"

### 2. 上传文件
- 在新仓库页面点击 "uploading an existing file"
- 将整个 `Food AI` 文件夹拖拽到上传区域
- 等待上传完成
- 输入提交信息 "Initial commit"
- 点击 "Commit changes"

## 后续更新

### GitHub Desktop 方式
1. 修改代码后打开 GitHub Desktop
2. 左侧显示更改的文件
3. 输入提交信息
4. 点击 `Commit to main`
5. 点击 `Push origin`

### 网页上传方式
- 在仓库页面点击 "Add file" → "Upload files"
- 拖拽修改的文件
- 提交更改

## 注意事项

⚠️ 敏感信息检查：
- 确保没有 API 密钥、密码等敏感信息
- `.gitignore` 已配置忽略以下文件：
  - Python 缓存文件
  - 虚拟环境
  - IDE 配置
  - Lingma AI 配置
  - 临时文件
