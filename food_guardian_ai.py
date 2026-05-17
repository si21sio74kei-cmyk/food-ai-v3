# -*- coding: utf-8 -*-
# food_guardian_ai.py
"""
FoodGuardian AI - 智能食谱助手
Smart Anti-Food-Waste Assistant for Families (CustomTkinter Version)

这是一个完整的单文件 Python 桌面应用，使用 CustomTkinter 框架实现现代化界面。
This is a complete single file Python desktop application using CustomTkinter framework with modern style.

依赖包 / Dependencies:
- customtkinter
- CTkMessagebox (可选，用于美化消息框)

Install dependencies / 安装依赖:
pip install customtkinter

Run app / 运行应用:
python food_guardian_ai.py
"""

import customtkinter as ctk
from tkinter import messagebox, scrolledtext, ttk
import tkinter as tk
import json
import os
import random
from datetime import datetime
import requests
import time
import threading

# ====================== AI API 全局配置 开始 ======================

# 多 API 容错配置（适配澳门地区）
# 优先级：智谱 AI

# 方案 1: 智谱 AI GLM-4 (推荐，港澳支持良好)
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_API_KEY = "96c2f3dc023441738ea4ab27dc288dba.74edfBTCaWL5bhhj"  # 第二条 API（用于图像识别）
ZHIPU_API_KEY_TEXT = "022ac847f3384c28be276fcdf04c9892.lVw8PyzurjGIXhm2"  # 第一条 API（用于文本问答）



# API 调用超时设置（秒）
# 注意：AI生成需要较长时间，特别是长文本生成
# 建议设置：60-120 秒（避免频繁超时）
API_TIMEOUT = 90
# API 最大重试次数（增加重试次数提高成功率）
API_MAX_RETRIES = 3
# 是否启用智能 API 切换
ENABLE_SMART_FAILOVER = True

# ====================== AI API 全局配置 结束 ======================

# =============================================================================
# 各平台 API 调用实现
# =============================================================================



def _call_zhipu_api(url, api_key, prompt, max_retries):
    """智谱 AI GLM-4 API 调用（智能降级策略）"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 智能降级策略：先尝试更好的模型，失败后回退到 Flash
    model_priority = [
        {"name": "glm-4-air", "desc": "GLM-4-Air（平衡版，性价比高）"},
        {"name": "glm-4-flash", "desc": "GLM-4-Flash（轻量版，快速响应）"}
    ]
    
    last_error = None
    
    # 遍历模型优先级列表
    for model_info in model_priority:
        model_name = model_info["name"]
        model_desc = model_info["desc"]
        
        print(f"\n【智谱 AI】🚀 尝试使用 {model_desc}...")
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        for attempt in range(max_retries + 1):
            try:
                print(f"【智谱 AI】第 {attempt + 1}/{max_retries + 1} 次尝试 ({model_name})...")
                response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
                response.raise_for_status()
                
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    print(f"【智谱 AI】✅ 成功使用 {model_desc} 生成回复")
                    return {
                        'success': True,
                        'content': content,
                        'error': None,
                        'model_used': model_name
                    }
                else:
                    last_error = '智谱 AI 返回格式异常'
                    print(f"【智谱 AI】⚠️ {model_desc} 返回格式异常")
                    break  # 格式异常，尝试下一个模型
                    
            except requests.exceptions.Timeout:
                last_error = f"{model_name} 请求超时"
                print(f"【智谱 AI】⚠️ {model_desc} 超时")
                break  # 超时，尝试下一个模型
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 'Unknown'
                last_error = f"HTTP 错误 {status_code}"
                print(f"【智谱 AI】❌ {model_desc} HTTP 错误：{status_code}")
                
                # 如果是 401/403（认证错误）或 429（配额用尽），直接降级
                if status_code in [401, 403, 429]:
                    print(f"【智谱 AI】⚠️ {model_desc} 不可用，尝试降级...")
                    break
                # 其他错误继续重试
                if attempt < max_retries:
                    time.sleep(1)
                continue
                
            except Exception as e:
                last_error = str(e)
                print(f"【智谱 AI】❌ {model_desc} 异常：{e}")
                if attempt < max_retries:
                    time.sleep(1)
                continue
        
        # 当前模型失败，打印降级信息
        print(f"【智谱 AI】⚠️ {model_desc} 未能成功，准备尝试下一个模型...")
    
    # 所有模型都失败
    print(f"\n【智谱 AI】❌ 所有模型尝试失败")
    return {
        'success': False,
        'content': None,
        'error': last_error or '智谱 AI 调用失败',
        'model_used': 'none'
    }




# =============================================================================
# AI API 调用工具函数 / AI API Call Utility Functions
# =============================================================================

def call_ai_api(prompt, api_url=None, token=None, max_retries=None, api_type="auto"):
    """
    智能 AI API 调用函数（支持多 API 自动切换）
    
    Args:
        prompt: 用户提示词
        api_url: API URL（可选，默认使用全局配置）
        token: API Token/Key（可选，默认使用全局配置）
        max_retries: 最大重试次数（可选，默认使用全局配置）
        api_type: API 类型 ("auto"|"zhipu")
    
    Returns:
        dict: {'success': bool, 'content': str, 'error': str, 'api_used': str}
    """
    import json
    
    # 使用全局配置作为默认值
    max_retries = max_retries if max_retries is not None else API_MAX_RETRIES
    
    # 智能 API 列表（按优先级排序）
    api_list = []
    
    if api_type == "auto":
        # 自动模式：尝试所有可用的 API（按优先级排序）
        if ZHIPU_API_KEY:
            api_list.append({"type": "zhipu", "url": ZHIPU_API_URL, "key": ZHIPU_API_KEY})
    else:
        # 指定 API 模式
        if api_type == "zhipu" and ZHIPU_API_KEY:
            api_list.append({"type": "zhipu", "url": ZHIPU_API_URL, "key": ZHIPU_API_KEY})
    
    # 如果没有可用的 API，直接使用保底方案
    if not api_list:
        print("【API 调用】⚠️ 未配置任何 API Key，将使用保底方案")
        return {
            'success': False,
            'content': None,
            'error': '未配置 API Key',
            'api_used': 'none'
        }
    
    print(f"【API 调用】📡 准备尝试 {len(api_list)} 个 API 服务...")
    
    # 遍历所有 API 尝试
    for api_info in api_list:
        api_name = api_info["type"]
        current_url = api_info["url"]
        current_key = api_info["key"]
        
        print(f"\n【API 调用】正在尝试 {api_name.upper()} API...")
        
        try:
            if api_name == "zhipu":
                result = _call_zhipu_api(current_url, current_key, prompt, max_retries)
            else:
                continue
            
            # 如果成功，直接返回
            if result['success']:
                result['api_used'] = api_name
                print(f"【API 调用】✅ 使用 {api_name.upper()} API 成功获取 AI 回复")
                return result
            else:
                print(f"【API 调用】❌ {api_name.upper()} API 失败：{result.get('error', '未知错误')}")
        
        except Exception as e:
            print(f"【API 调用】❌ {api_name.upper()} API 异常：{e}")
            continue
    
    # 所有 API 都失败
    print(f"\n【API 调用】❌ 所有 API 尝试失败，将使用保底方案")
    return {
        'success': False,
        'content': None,
        'error': '所有 API 调用失败',
        'api_used': 'none'
    }


def parse_ai_recipe(ai_content, ingredients_list, people_num, appetite_coefficient):
    """
    解析 AI 生成的食谱内容，提取结构化数据
    
    Args:
        ai_content: AI 返回的文本内容
        ingredients_list: 食材列表
        people_num: 人数
        appetite_coefficient: 饭量系数
    
    Returns:
        dict: 结构化的食谱数据
    """
    # 简单的文本解析，可以根据 AI 返回格式优化
    # 假设 AI 按照特定格式返回：菜名、用料清单、制作步骤
    
    recipe_data = {
        'dish_name': '',
        'ingredients': [],
        'steps': []
    }
    
    lines = ai_content.strip().split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 识别段落
        if '菜名' in line or '菜品' in line:
            current_section = 'name'
            recipe_data['dish_name'] = line.split(':')[-1] if ':' in line else line
        elif '用料' in line or '食材' in line:
            current_section = 'ingredients'
        elif '步骤' in line or '做法' in line:
            current_section = 'steps'
        elif current_section == 'ingredients' and line.startswith('-'):
            recipe_data['ingredients'].append(line)
        elif current_section == 'steps' and (line[0].isdigit() or line.startswith('步骤')):
            recipe_data['steps'].append(line)
    
    return recipe_data

# =============================================================================
# 常量定义 / Constants Definition
# =============================================================================

# 配色方案 / Color Scheme
COLORS = {
    'primary': '#FF8C42',      # 温暖橙色（主色调）
    'secondary': '#FFB347',    # 浅橙色
    'tertiary': '#FFD93D',     # 暖黄色
    'background': '#FFF9F0',   # 淡黄色背景（治愈、温暖）
    'card_bg': '#FFFFFF',      # 卡片白色
    'text_primary': '#2C2C2C', # 深灰色文字（接近黑色）
    'text_secondary': '#5A5A5A', # 中灰色文字
    'danger': '#FF6B6B',       # 柔和红色
    'separator': '#E0E0E0'     # 浅灰分隔线
}

# 中文文本 / Chinese Texts
TEXTS = {
    'nav_home': '首页',
    'nav_recipes': '智能食谱',
    'nav_nutrition': '营养分析',  # 【新增】C
    'nav_chat': 'AI 助手',  # 【新增】F
    'nav_shopping': '采购清单',  # 【新增】D
    'nav_about': '关于项目',
    'nav_subtitle': '智能食谱助手',
    'slogan_main': '让每一口都不被浪费',
    'slogan_sub': '智能食谱 + 环保量化，让家庭用餐更绿色。',
    'tag_realtime': '实时环保 impact',
    'tag_antiwaste': '环保优先',
    'tag_family': '适合家庭与课堂演示',
    'tag_local': '纯前端 · 本地数据存储',
    'profile_title': '你的绿色档案',
    'nickname_hint': '设置一个昵称，我们会在本机悄悄为你记录每一次节约。',
    'nickname_label': '环保昵称（仅保存在本机）',
    'save_nickname': '保存昵称',
    'saved_local': '已保存到本机浏览器。',
    'empty_nickname': '请输入一个昵称。',
    'welcome': '欢迎回来，{}！今天也一起为地球省下一点点资源吧。',
    'start_menu': '开始生成今天的零浪费菜单',
    'cumulative_title': '你的累计环保贡献',
    'cumulative_tag': '仅在本机统计 · 可随时清零',
    'waste_reduced': '减少食物浪费',
    'water_saved': '节约水资源',
    'co2_reduced': '减少碳排放',
    'total': '累计',
    'unit_g': '克',
    'unit_l': '升',
    'tip_achievement': '小提示：每次你使用智能食谱生成器并采纳建议，系统都会为你叠加一次“绿色成就”。',
    'reset_stats': '清零本机统计',
    'reset_confirm': '确定要清零本机的所有环保统计吗？此操作不可恢复。',
    'generator_title': '智能食谱生成器',
    'generator_sub': '选择就餐人数和食材，我们将为你推荐刚刚好的份量。',
    'tag_people': '1-20 人',
    'setup_title': '基础设定',
    'people_label': '就餐人数',
    'meal_type_label': '用餐类型',
    'meal_home': '家常菜',
    'meal_healthy': '健康餐',
    'meal_vegetarian': '素食',
    'meal_banquet': '宴客菜',
    'ingredients_label': '主要食材（可多选）',
    'ing_tomato': '番茄',
    'ing_chicken': '鸡肉',
    'ing_potato': '土豆',
    'ing_egg': '鸡蛋',
    'ing_beef': '牛肉',
    'ing_fish': '鱼类',
    'fine_tune': '动态份量调整',
    'fine_hint': '如果你家人饭量偏大/偏小，可以微调基础份量系数。',
    'appetite_label': '个人饭量系数',
    'generate_menu': '生成环保菜单',
    'no_ingredient': '请至少选择一种主要食材。',
    'impact_title': '本次环保影响量化',
    'impact_note': '以下数据基于 FAO 和 Water Footprint Network 公开研究中的平均换算系数，仅用于科普与课堂演示。',
    'waste_this': '本次减少食物浪费',
    'water_this': '本次节约水资源',
    'co2_this': '本次减少碳排放',
    'goal': '小目标：累计减少 1000 克食物浪费 ≈ 为地球省下一整天家庭厨房的隐形损失。',
    'menu_title': '推荐菜单与份量',
    'menu_placeholder': '请先选择人数、用餐类型和主要食材，然后点击"生成环保菜单"。',
    'menu_info': '为 {} 人准备的 {}，主要食材：{}。',
    'portion': '{}：约 {} 克（含预留少量机动空间）。',
    'dishes': '可能的菜品',
    'steps': '制作步骤',
    'step_prefix': '步骤',
    'tip_reduce': '小建议：菜品已经比较丰富，可以适当减少一道菜，继续为地球减负。',
    'tip_add': '小建议：如果还有特别能吃的家人，可以酌情增加一道蔬菜类菜品。',
    'about_title': '关于 FoodGuardian AI',
    'about_sub': '本项目专注“技术 + 教育 + 环保”的结合。',
    'footer_title': '智能食谱与环保教育平台',
    'footer_copyright': '© 2026 保留所有权利 · 内容仅用于教育与科普目的。'
}

# 食材基准份量 / Ingredient Base Portions (g per person per dish)
BASE_PORTIONS = {
    'tomato': 80,
    'chicken': 120,
    'potato': 90,
    'egg': 60,
    'beef': 130,
    'fish': 110
}

# 用餐类型系数 / Meal Type Multipliers
MEAL_MULTIPLIERS = {
    'home': 1.0,
    'healthy': 0.9,
    'vegetarian': 0.85,
    'banquet': 1.15
}

# 环保换算系数 / Environmental Conversion Factors
# 数据来源：
# - Water Footprint Network (Mekonnen & Hoekstra, 2010)
# - FAO "Tackling Climate Change Through Livestock" (2013)
# - Our World in Data "Environmental impacts of food production" (Ritchie, 2020)
# 注：以下系数基于中国居民膳食结构的加权平均值，适合教育科普演示
# 实际数值因食材种类、产地、生产方式差异巨大
ENV_FACTORS = {
    'water_per_g': 0.5,      # L/g → 500L/kg (中国膳食加权平均，含虚拟水)
    'co2_per_g': 0.003       # g/g → 3g CO2e/g食物 (中国膳食混合平均值)
}

WASTE_RATIO = 0.25  # 浪费减少比例 / Waste reduction ratio

# 中英文食材名称映射 / Chinese-English Ingredient Name Mapping
INGREDIENT_MAP = {
    '番茄': 'tomato',
    '西红柿': 'tomato',
    '鸡肉': 'chicken',
    '鸡胸肉': 'chicken',
    '土豆': 'potato',
    '马铃薯': 'potato',
    '鸡蛋': 'egg',
    '蛋': 'egg',
    '牛肉': 'beef',
    '猪肉': 'beef',
    '鱼': 'fish',
    '鱼类': 'fish',
    '虾': 'fish',
    '青菜': 'tomato',
    '菜': 'tomato',
    '白菜': 'tomato',
    '生菜': 'tomato',
    '菠菜': 'tomato',
    '萝卜': 'potato',
    '红薯': 'potato',
    '山药': 'potato',
    '芋头': 'potato',
    '莲藕': 'potato',
    '莴笋': 'potato',
    '黄瓜': 'tomato',
    '冬瓜': 'tomato',
    '南瓜': 'tomato',
    '丝瓜': 'tomato',
    '苦瓜': 'tomato',
    '菇': 'tomato',
    '菌': 'tomato',
    '香菇': 'tomato',
    '金针菇': 'tomato',
    '豆腐': 'egg',
    '豆干': 'egg',
    '豆芽': 'egg',
    '腐竹': 'egg'
}

# =============================================================================
# 工具函数 / Utility Functions
# =============================================================================

def get_text(key):
    """获取文本 / Get text"""
    return TEXTS[key]

def load_data():
    """加载本地数据 / Load local data"""
    if os.path.exists('fgai_local_data.json'):
        try:
            with open('fgai_local_data.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'nickname': '', 'waste_reduced': 0, 'water_saved': 0, 'co2_reduced': 0}

def save_data(data):
    """保存本地数据 / Save local data"""
    with open('fgai_local_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =============================================================================
# 营养评估与个性化方案生成核心函数
# =============================================================================

def load_nutrition_standards():
    """加载联合国营养标准"""
    try:
        # 使用脚本所在目录作为基准路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, 'un_nutrition_standards.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            standards = json.load(f)
        # 转换为字典格式，方便查询
        standards_dict = {s['population_group']: s for s in standards}
        return standards_dict
    except Exception as e:
        print(f"❌ 加载营养标准失败：{e}")
        return {}

def get_nutrition_standard(population_group):
    """获取指定人群的营养标准"""
    standards = load_nutrition_standards()
    return standards.get(population_group, standards.get('adults', None))

def nutrition_assessment(user_intake, population_group):
    """
    全维度营养健康评估引擎
    
    Args:
        user_intake: dict, 用户摄入量数据 {'vegetables': 200, 'fruits': 150, ...}
        population_group: str, 人群标签 'adults'/'children'/'elderly'
    
    Returns:
        dict: 评估结果，包含每个食材类别的摄入状态和建议
    """
    standard = get_nutrition_standard(population_group)
    if not standard:
        return {'error': f'未找到人群 {population_group} 的营养标准'}
    
    intake_to_chinese = {
        'vegetables': '蔬菜',
        'fruits': '水果',
        'meat': '肉类',
        'eggs': '蛋类'
    }
    
    # 检查是否为部分录入（只录入了部分食材）
    # 注意：只检查 4 种食材字段，排除 date、time 等其他字段
    food_types = ['vegetables', 'fruits', 'meat', 'eggs']
    recorded_foods = []
    for food_type in food_types:
        v = user_intake.get(food_type, 0)
        try:
            if int(v) > 0:
                recorded_foods.append(food_type)
        except (ValueError, TypeError):
            # 如果无法转换为整数，跳过该字段
            pass
    is_partial_entry = len(recorded_foods) < 4  # 只录入了不到 4 种食材
    
    assessment = {}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        intake = user_intake.get(food_type, 0)
        recommendations = standard['daily_recommendations'].get(food_type, {})
        min_rec = recommendations.get('min', 0)
        max_rec = recommendations.get('max', 0)
        
        # 如果是部分录入，且该食材未录入（为 0），则不评估为"不足"
        if is_partial_entry and intake == 0:
            # 未录入的食材，显示"未录入"而不是"不足"
            assessment[food_type] = {
                'intake': intake,
                'status': '未录入',
                'gap': 0,
                'chinese_name': intake_to_chinese[food_type],
                'suggestion': f"暂未录入{intake_to_chinese[food_type]}，如已摄入请补充录入"
            }
        elif intake < min_rec:
            status = "不足"
            gap = min_rec - intake
            suggestion = f"建议增加{intake_to_chinese[food_type]}摄入，当前{intake}g，距离推荐最小值还差{gap}g"
            
            # 如果是部分录入，语气更温和
            if is_partial_entry:
                suggestion = f"{intake_to_chinese[food_type]}摄入较少（{intake}g），建议适当增加"
        elif intake > max_rec:
            status = "超标"
            gap = intake - max_rec
            suggestion = f"建议减少{intake_to_chinese[food_type]}摄入，当前{intake}g，已超过推荐最大值{gap}g"
            
            # 如果是部分录入，语气更温和
            if is_partial_entry:
                suggestion = f"{intake_to_chinese[food_type]}摄入略多（{intake}g），建议后续餐次适当控制"
        else:
            status = "达标"
            gap = 0
            suggestion = f"{intake_to_chinese[food_type]}摄入充足（{intake}g），请继续保持"
        
        assessment[food_type] = {
            'intake': intake,
            'status': status,
            'gap': gap,
            'chinese_name': intake_to_chinese[food_type],
            'suggestion': suggestion
        }
    
    return assessment

def check_and_alert(food_type, amount, population_group, current_daily_total=0):
    """
    实时摄入量达标预警系统
    
    Args:
        food_type: str, 食材类型 'vegetables'/'fruits'/'meat'/'eggs'
        amount: int, 本次摄入量（克）
        population_group: str, 人群标签
        current_daily_total: int, 当日已累计摄入量
    
    Returns:
        tuple: (is_alert, alert_message) 是否需要预警和预警信息
    """
    standard = get_nutrition_standard(population_group)
    if not standard:
        return False, ""
    
    intake_to_chinese = {
        'vegetables': '蔬菜',
        'fruits': '水果',
        'meat': '肉类',
        'eggs': '蛋类'
    }
    
    recommendations = standard['daily_recommendations'].get(food_type, {})
    max_rec = recommendations.get('max', 0)
    
    new_total = current_daily_total + amount
    
    if new_total >= max_rec * 0.9:  # 达到 90% 就预警
        alert_msg = f"⚠️ {intake_to_chinese.get(food_type, food_type)}今日摄入量已接近达标！\n\n"
        alert_msg += f"📊 当前：{new_total}g | 推荐上限：{max_rec}g\n\n"
        alert_msg += f"💡 建议：停止额外摄入{intake_to_chinese.get(food_type, food_type)}，可搭配其他未达标品类食材，优化饮食均衡性"
        return True, alert_msg
    
    return False, ""

def generate_personalized_plan(user_intake, population_group, fridge_items=None):
    """
    分人群差异化饮食方案生成
    
    Args:
        user_intake: dict, 用户摄入量数据
        population_group: str, 人群标签
        fridge_items: list, 冰箱现有食材清单
    
    Returns:
        str: AI 生成的个性化饮食方案
    """
    # 1. 先进行营养评估
    assessment = nutrition_assessment(user_intake, population_group)
    
    # 2. 构建 AI Prompt
    population_info = {
        'adults': '成年人，需要均衡营养以维持身体机能',
        'children': '儿童，处于生长发育期，需要充足的蛋白质和钙质',
        'elderly': '老年人，消化吸收能力下降，需要易消化、高钙的食物'
    }
    
    # 找出不足和超标的项
    insufficient = [k for k, v in assessment.items() if v['status'] == '不足']
    excessive = [k for k, v in assessment.items() if v['status'] == '超标']
    
    prompt = f"""你是一位专业营养师，请根据以下信息生成个性化饮食方案：

【用户信息】
- 人群标签：{population_group}（{population_info.get(population_group, '')}）
- 今日摄入：蔬菜{user_intake.get('vegetables', 0)}g、水果{user_intake.get('fruits', 0)}g、肉类{user_intake.get('meat', 0)}g、蛋类{user_intake.get('eggs', 0)}g

【营养评估结果】
- 摄入不足：{', '.join(insufficient) if insufficient else '无'}
- 摄入超标：{', '.join(excessive) if excessive else '无'}

【任务要求】
1. 分析该人群的特殊营养需求
2. 针对摄入不足项给出补充建议
3. 针对摄入超标项给出控制建议
4. 生成明日饮食建议（具体菜品 + 食材用量）
5. 考虑该人群的消化特点（老年人软烂、儿童趣味、成年人均衡）

【输出格式】
## 营养评估总结
## 改善建议（至少 3 条）
## 明日食谱推荐（2-3 道菜）
"""
    
    # 3. 调用智谱 AI 生成方案（使用智能降级策略）
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败：{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成方案时出错：{str(e)}"

def generate_daily_recommendation(user_intake, population_group, fridge_items):
    """
    基于现有食材 + 营养数据的每日饮食推荐
    
    Args:
        user_intake: dict, 用户摄入数据
        population_group: str, 人群标签
        fridge_items: list, 冰箱食材清单 [{'name': '牛肉', 'quantity': 500, ...}, ...]
    
    Returns:
        str: AI 生成的饮食推荐
    """
    # 1. 营养评估
    assessment = nutrition_assessment(user_intake, population_group)
    
    # 2. 筛选食材（优先使用不足的品类）
    recommended_ingredients = []
    for food_type, data in assessment.items():
        if data['status'] == '不足':
            # TODO: 实现食材分类匹配逻辑
            # 这里简化处理，假设冰箱中所有食材都可用
            recommended_ingredients.extend(fridge_items[:3])  # 最多取 3 种
    
    if not recommended_ingredients and fridge_items:
        # 如果都达标，随机使用现有食材
        recommended_ingredients = fridge_items[:3]
    
    ingredients_str = ", ".join([f"{item['name']}{item.get('quantity', '')}g" for item in recommended_ingredients])
    
    prompt = f"""请根据以下食材生成今晚食谱：

【可用食材】{ingredients_str if ingredients_str else '家常食材'}
【用户人群】{population_group}
【营养缺口】需要重点补充：{', '.join([assessment[k]['chinese_name'] for k, v in assessment.items() if v['status'] == '不足']) if any(v['status']=='不足' for v in assessment.values()) else '营养均衡'}

【要求】
1. 必须完全使用上述食材
2. 考虑{population_group}的消化特点
3. 输出 2-3 道菜品
4. 标注每道菜的营养补充方向

【输出格式】
## 推荐菜品（2-3 道）
## 所需食材
## 简要步骤
## 营养功效
"""
    
    # 3. 调用智谱 AI（使用智能降级策略）
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败：{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成推荐时出错：{str(e)}"

def generate_menu(ingredients):
    """生成菜单 / Generate menu"""
    # 生成菜单现在完全依赖AI
    return {}




class ScrollableFrame(ctk.CTkFrame):
    """可滚动框架 / Scrollable Frame"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # 设置透明背景
        self.configure(fg_color="transparent")
        
        # 创建 Canvas 和 Scrollbar
        self.canvas = ctk.CTkCanvas(self, bg=COLORS['card_bg'], highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")

        # 配置滚动区域
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        # 在 Canvas 中创建窗口
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # 修复 focus_set() 回调报错
        self.bind("<Enter>", lambda e: self.focus_set())
        self.canvas.bind("<Enter>", lambda e: self.focus_set())
        scrollbar.bind("<Enter>", lambda e: self.focus_set())
        
        # 响应式调整 Canvas 窗口宽度
        def _configure_canvas_width(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        self.canvas.bind("<Configure>", _configure_canvas_width)


class FoodGuardianAI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FoodGuardian AI")
        self.geometry("1200x800")
        self.configure(fg_color=COLORS['background'])
        
        # 设置 CustomTkinter 外观模式
        ctk.set_appearance_mode("light")  # 浅色模式
        ctk.set_default_color_theme("blue")  # 蓝色主题
        
        # 自定义样式 / Custom Styles
        self.setup_styles()
        
        # 数据 / Data
        self.data = load_data()
        self.current_page = 'home'
        self.generated_menu = None
        self.current_impact = None
        self.generation_count = 0  # 食谱生成计数器（首页）
        self.recipe_generation_count = 0  # 智能食谱页面生成计数器
        
        # 创建主容器 / Main Container
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # 主框架 / Main Frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 导航栏 / Navigation Bar
        self.create_nav_bar(main_frame)
        
        # 页面框架 / Page Frames
        self.page_frames = {}
        self.create_frames(main_frame)
        
        # 显示首页 / Show Home Page
        self.show_page('home')

    def setup_styles(self):
        """设置样式 (CustomTkinter 样式配置) / Setup Styles"""
        # CustomTkinter 的样式通过 configure 方法设置
        # 按钮悬浮效果通过 CustomTkinter 自动处理
        pass

    def calculate_impact(self, ingredients, people_num=3, portion_coefficient=1.0):
        """
        计算环保影响（采用国际通用公式）
        
        基于 FAO 和 Water Footprint Network 权威数据源
        Calculate environmental impact using international standard formulas
        
        Args:
            ingredients: 食材列表
            people_num: 人数
            portion_coefficient: 饭量系数
        
        Returns:
            dict: {'food_waste': float, 'water': float, 'carbon': float}
        """
        # 计算总份量（考虑人数和饭量系数）
        total_portion = 0
        for ing in ingredients:
            # 中文转英文映射
            ing_en = INGREDIENT_MAP.get(ing, ing.lower())
            
            # 如果食材在基准份量表中，使用对应值；否则使用默认值 100g
            if ing_en in BASE_PORTIONS:
                base = BASE_PORTIONS[ing_en]
                multiplier = MEAL_MULTIPLIERS['home'] * portion_coefficient
                total_portion += base * people_num * multiplier
            else:
                # 未知食材使用默认值 100g/人
                total_portion += 100 * people_num * portion_coefficient

        # 计算减少的食物浪费
        # 依据：FAO 报告显示全球约 1/3 食物被浪费，家庭端浪费率约 20-30%
        # 中国餐饮浪费率约为 20-35%（中科院地理所研究）
        traditional_portion = total_portion * (1 + WASTE_RATIO)  # 传统做法多准备 25%
        waste_reduced = traditional_portion - total_portion  # 精准备餐减少的浪费量

        # 计算节约的水资源（基于水足迹理论）
        # 公式：节水量 = 减少浪费量 × 单位食材水足迹
        # 中国膳食结构加权平均：约 500 L/kg（植物性食物为主）
        water_saved = waste_reduced * ENV_FACTORS['water_per_g']

        # 计算减少的碳排放（基于生命周期评估 LCA）
        # 公式：碳减排 = 减少浪费量 × 单位食材碳排放因子
        # 中国膳食混合平均：约 3 kg CO2e/kg食物
        co2_reduced = waste_reduced * ENV_FACTORS['co2_per_g']

        return {
            'food_waste': round(waste_reduced, 2),
            'water': round(water_saved, 2),
            'carbon': round(co2_reduced, 2)
        }

    def create_frames(self, parent):
        """创建页面框架 / Create Page Frames"""
        # 配置主框架的网格权重
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        for page in ['home', 'recipes', 'nutrition', 'chat', 'fridge', 'shopping', 'about']:  # 新增功能页面
            # 为每个页面创建滚动框架
            scrollable_frame = ScrollableFrame(parent)
            scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
            scrollable_frame.grid_remove()  # 先隐藏，只在需要时显示
            self.page_frames[page] = scrollable_frame
            
            # 创建页面内容
            self.create_page_content(scrollable_frame.scrollable_frame, page)

    def create_nav_bar(self, parent):
        """创建导航栏 / Create Navigation Bar（下拉菜单优化版）"""
        nav_frame = ctk.CTkFrame(parent, fg_color="transparent")
        nav_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        parent.grid_columnconfigure(0, weight=1)
        
        # 标题 / Title
        title_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        title_frame.pack(side=tk.LEFT)
        ctk.CTkLabel(title_frame, text="FoodGuardian AI", 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(side=tk.TOP)
        ctk.CTkLabel(title_frame, text=TEXTS['nav_subtitle'], 
                    text_color=COLORS['text_secondary']).pack(side=tk.TOP)
        
        # 右侧功能区
        right_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
        right_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        # 【新增】图像识别按钮
        image_btn = ctk.CTkButton(right_frame, text="📸 拍照识菜",
                                 command=self.open_image_recognition,
                                 fg_color=COLORS['secondary'],
                                 hover_color=COLORS['primary'],
                                 text_color="white",
                                 corner_radius=20,  # 统一圆角
                                 height=40,  # 缩小 20%: 50*0.8=40
                                 width=128,  # 缩小 20%: 160*0.8=128
                                 font=("Arial", 16, "bold"))  # 字体略小
        image_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 【新增】语音交互按钮
        voice_btn = ctk.CTkButton(right_frame, text="🎤 语音交互",
                                 command=self.open_voice_interaction,
                                 fg_color=COLORS['primary'],
                                 hover_color=COLORS['secondary'],
                                 text_color="white",
                                 corner_radius=20,  # 统一圆角
                                 height=40,  # 缩小 20%: 50*0.8=40
                                 width=128,  # 缩小 20%: 160*0.8=128
                                 font=("Arial", 16, "bold"))  # 字体略小
        voice_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 下拉菜单导航按钮
        self.menu_btn = ctk.CTkButton(right_frame, text="☰ 菜单",
                                command=self.show_page_menu,
                                fg_color=COLORS['primary'],  # 改成橙色背景
                                hover_color=COLORS['secondary'],
                                text_color="white",
                                corner_radius=20,  # 统一圆角
                                height=40,  # 缩小 20%: 50*0.8=40
                                width=128,  # 缩小 20%: 160*0.8=128
                                font=("Arial", 16, "bold"))  # 字体略小
        self.menu_btn.pack(side=tk.LEFT)
    
    def show_page_menu(self):
        """显示页面选择菜单 / Show Page Selection Menu（放大圆角版）"""
        # 创建顶部菜单（放大字体和宽度，圆角风格）
        menu = tk.Menu(self, tearoff=0, bg=COLORS['card_bg'],
                      fg=COLORS['text_primary'], 
                      font=("Arial", 22, "bold"),  # 放大 20%: 18*1.2≈22
                      borderwidth=3)  # 加粗边框
        
        # 配置菜单样式
        try:
            # 设置菜单项的背景和字体
            menu.configure(bg=COLORS['card_bg'])  # 背景色
        except:
            pass
        
        # 添加菜单项
        pages = [
            ('首页', 'home'),
            ('智能食谱', 'recipes'),
            ('营养分析', 'nutrition'),
            ('AI 助手', 'chat'),
            ('智能冰箱', 'fridge'),  # 新增：智能冰箱管理
            ('采购清单', 'shopping'),
            ('关于项目', 'about')
        ]
        
        for label, page_key in pages:
            menu.add_command(label=label, 
                           font=("Arial", 22),  # 放大 20%: 18*1.2≈22
                           command=lambda p=page_key: self.show_page(p))
        
        # 显示菜单在按钮位置（精确计算菜单位置，居中对齐）
        try:
            # 获取按钮的位置
            btn_x = self.menu_btn.winfo_rootx()
            btn_width = self.menu_btn.winfo_width()
            btn_y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height()
            
            # 计算居中位置：按钮左侧 - (菜单宽度 - 按钮宽度) / 2
            # 让菜单以按钮为中心对齐
            menu_width = 240  # 放大 20%: 200*1.2=240
            centered_x = btn_x + (btn_width - menu_width) // 2
            
            menu.post(centered_x, btn_y)
        except:
            # 如果获取位置失败，使用默认位置
            menu.post(self.winfo_rootx() + 800, self.winfo_rooty() + 50)
    
    def open_image_recognition(self):
        """打开图像识别弹窗 / Open Image Recognition Dialog"""
        # 创建弹窗
        dialog = ctk.CTkToplevel(self)
        dialog.title("📸 拍照识菜 - 上传食材图片")
        dialog.geometry("1200x800")  # 改大，和主视窗一样大
        dialog.transient(self)
        dialog.grab_set()
        
        # 标题
        title_label = ctk.CTkLabel(dialog, text="📸 拍照识菜",
                                  font=("Arial", 24, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(dialog, text="上传图片或拍照，AI 自动识别食材",
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 图片显示区域
        image_frame = ctk.CTkFrame(dialog, fg_color=COLORS['card_bg'],
                                  corner_radius=15, width=800, height=500)  # 改大
        image_frame.pack(pady=10)
        image_frame.pack_propagate(False)
        
        image_label = ctk.CTkLabel(image_frame, text="📷 点击上传或拖拽图片到此处",
                                  text_color=COLORS['text_secondary'],
                                  font=("Arial", 20))  # 改大字体
        image_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # 按钮区
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        def upload_image():
            """上传图片并识别"""
            try:
                from tkinter import filedialog
                file_path = filedialog.askopenfilename(
                    title="选择图片",
                    filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp")]
                )
                if file_path:
                    image_label.configure(text=f"✅ 已选择：{file_path.split('/')[-1]}")
                    # 存储图片路径
                    dialog.image_path = file_path
                    # 显示图片预览
                    try:
                        from PIL import Image
                        img = Image.open(file_path)
                        img.thumbnail((380, 280))
                        # 显示在 label 上（简化处理）
                        image_label.configure(text=f"✅ 已加载：{file_path.split('/')[-1]}\n尺寸：{img.size[0]}x{img.size[1]}")
                    except:
                        pass
            except Exception as e:
                messagebox.showerror("错误", f"图片加载失败：{e}")
        
        def take_photo():
            """调用摄像头拍照"""
            try:
                import cv2
                from PIL import Image
                import numpy as np
                
                # 打开摄像头
                cap = cv2.VideoCapture(0)
                
                if not cap.isOpened():
                    # 尝试更详细的错误提示
                    messagebox.showerror(
                        "错误", 
                        "无法打开摄像头\n\n"
                        "可能的原因：\n"
                        "1. 摄像头被其他程序占用（如 Zoom、Skype 等）\n"
                        "2. 摄像头驱动未安装或损坏\n"
                        "3. 摄像头硬件开关未打开\n"
                        "4. 隐私设置禁止访问摄像头\n\n"
                        "解决方案：\n"
                        "1. 关闭其他使用摄像头的程序\n"
                        "2. 检查设备管理器中的摄像头驱动\n"
                        "3. 检查摄像头的物理开关\n"
                        "4. 在 Windows 设置中允许应用访问摄像头\n\n"
                        "提示：可以尝试重启电脑后再试"
                    )
                    return
                
                # 创建拍照窗口
                photo_dialog = ctk.CTkToplevel(dialog)
                photo_dialog.title("📸 拍照")
                photo_dialog.geometry("1400x900")  # 加大尺寸
                
                # 视频显示区域（加大）
                video_label = ctk.CTkLabel(photo_dialog, text="摄像头画面\n\n请对准食材", 
                                          font=("Arial", 18),
                                          text_color=COLORS['text_secondary'])
                video_label.pack(pady=10)
                
                # 拍照按钮（并排对齐）
                photo_btn_frame = ctk.CTkFrame(photo_dialog, fg_color="transparent")
                photo_btn_frame.pack(pady=15)
                
                is_capturing = [True]  # 使用列表以便在嵌套函数中修改
                
                def show_frame():
                    """显示视频帧"""
                    if is_capturing[0]:
                        ret, frame = cap.read()
                        if ret:
                            # 转换颜色空间（BGR -> RGB）
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            # 转换为 PIL Image
                            img = Image.fromarray(frame)
                            # 调整大小（加大显示）
                            img = img.resize((800, 600))
                            # 转换为 CTkPhotoImage
                            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(800, 600))
                            video_label.configure(image=photo)
                            video_label.image = photo
                            # 10ms 后更新
                            photo_dialog.after(10, show_frame)
                        else:
                            # 读取失败，停止更新
                            is_capturing[0] = False
                            cap.release()
                    else:
                        # 已停止，释放资源
                        try:
                            if cap.isOpened():
                                cap.release()
                        except:
                            pass
                
                def capture():
                    """拍照"""
                    try:
                        ret, frame = cap.read()
                        if ret:
                            # 保存图片
                            import os
                            from datetime import datetime
                            filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            cv2.imwrite(filename, frame)
                            
                            # 关闭拍照窗口
                            is_capturing[0] = False
                            cap.release()
                            photo_dialog.destroy()
                            
                            # 设置图片路径
                            dialog.image_path = os.path.abspath(filename)
                            image_label.configure(text=f"✅ 已拍照：{filename}\n尺寸：640x480")
                            
                            messagebox.showinfo("成功", f"✅ 照片已保存\n\n文件：{filename}\n\n点击'开始识别'按钮识别食材")
                    except Exception as e:
                        messagebox.showerror("错误", f"拍照失败：{e}")
                
                capture_btn = ctk.CTkButton(photo_btn_frame, text="📸 拍照",
                                          command=capture,
                                          fg_color=COLORS['primary'],
                                          hover_color=COLORS['secondary'],
                                          text_color="white",
                                          corner_radius=20,
                                          height=50,
                                          width=200,
                                          font=("Arial", 16, "bold"))
                capture_btn.pack(side=tk.LEFT, padx=10)
                
                def cancel_photo():
                    """取消拍照"""
                    is_capturing[0] = False
                    try:
                        if cap.isOpened():
                            cap.release()
                    except:
                        pass
                    photo_dialog.destroy()
                
                def on_closing():
                    """窗口关闭时清理资源"""
                    is_capturing[0] = False
                    try:
                        if cap.isOpened():
                            cap.release()
                    except:
                        pass
                    photo_dialog.destroy()
                
                # 绑定窗口关闭事件
                photo_dialog.protocol("WM_DELETE_WINDOW", on_closing)
                
                cancel_btn = ctk.CTkButton(photo_btn_frame, text="❌ 取消",
                                          command=cancel_photo,
                                          fg_color="transparent",
                                          border_width=2,
                                          border_color=COLORS['text_secondary'],
                                          text_color=COLORS['text_secondary'],
                                          hover_color=COLORS['card_bg'],
                                          corner_radius=20,
                                          height=50,
                                          width=100)
                cancel_btn.pack(side=tk.LEFT, padx=10)
                
                # 开始显示视频
                show_frame()
                
            except ImportError:
                messagebox.showerror("错误", "未安装 opencv-python 库\n\n请运行：pip install opencv-python")
            except Exception as e:
                messagebox.showerror("错误", f"拍照失败：{e}")
        
        upload_btn = ctk.CTkButton(btn_frame, text="📤 选择图片",
                                  command=upload_image,
                                  fg_color=COLORS['primary'],
                                  hover_color=COLORS['secondary'],
                                  text_color="white",
                                  corner_radius=8,
                                  height=40,
                                  width=150)
        upload_btn.pack(side=tk.LEFT, padx=10)
        
        photo_btn = ctk.CTkButton(btn_frame, text="📷 拍照",
                                 command=take_photo,
                                 fg_color=COLORS['secondary'],
                                 hover_color=COLORS['primary'],
                                 text_color="white",
                                 corner_radius=8,
                                 height=40,
                                 width=100)
        photo_btn.pack(side=tk.LEFT, padx=10)
        
        def recognize():
            """异步识别图片中的食材"""
            if not hasattr(dialog, 'image_path') or not dialog.image_path:
                messagebox.showwarning("提示", "请先选择图片")
                return
            
            # 显示识别中提示
            recognize_btn.configure(text="🤖 AI 识别中...", state='disabled')
            
            def do_recognition():
                try:
                    # 使用智谱 AI 视觉模型（更稳定）
                    import requests
                    import base64
                    
                    # 读取图片并转换为 base64
                    from PIL import Image
                    image = Image.open(dialog.image_path)
                    
                    # 压缩图片（减少网络传输）
                    max_size = 800  # 最大边长
                    if max(image.size) > max_size:
                        ratio = max_size / max(image.size)
                        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # 转换为 JPEG 并压缩
                    import io
                    image_bytes = io.BytesIO()
                    image.save(image_bytes, format='JPEG', quality=85, optimize=True)
                    image_bytes.seek(0)
                    
                    # 转换为 base64
                    base64_image = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
                    
                    # 使用智谱 AI GLM-4V-Flash 视觉模型（免费）
                    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {ZHIPU_API_KEY}",  # 使用第二条 API
                        "Content-Type": "application/json"
                    }
                    
                    # 构建请求体
                    payload = {
                        "model": "glm-4v-flash",  # 免费的图像识别模型
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": "请识别这张图片中的食材。要求：\n1. 只列出具体的食材名称（如：西红柿、鸡蛋、青椒）\n2. 用逗号分隔\n3. 不要描述性语言\n4. 如果是菜品，列出主要食材\n5. 不确定时给出最可能的食材名称"
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 200,
                        "temperature": 0.3
                    }
                    
                    # 发送请求（增加超时设置）
                    response = requests.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=30  # 30 秒超时
                    )
                    
                    # 解析结果
                    if response.status_code == 200:
                        result = response.json()
                        ingredients_text = result['choices'][0]['message']['content']
                        
                        # 使用 after 在主线程更新 UI
                        def update_ui():
                            messagebox.showinfo(
                                "识别成功",
                                f"✅ 图片识别完成！\n\n识别结果：{ingredients_text}\n\n已自动填入食材"
                            )
                            
                            # 自动填入食材输入框
                            if hasattr(self, 'custom_food_entry'):
                                self.custom_food_entry.delete(0, tk.END)
                                self.custom_food_entry.insert(0, ingredients_text)
                            
                            # 恢复按钮状态
                            recognize_btn.configure(text="📷 识别图片", state='normal')
                        
                        self.after(0, update_ui)
                    else:
                        error_msg = f"API 调用失败：{response.status_code}"
                        if response.status_code == 401:
                            error_msg += "\n\n智谱 AI API 密钥无效或已过期"
                        elif response.status_code == 429:
                            error_msg += "\n\n请求过于频繁，请稍后再试"
                        elif response.status_code >= 500:
                            error_msg += "\n\n服务器错误，请稍后再试"
                        
                        def show_error():
                            messagebox.showerror("识别失败", f"{error_msg}\n\n请使用手动输入方式")
                            recognize_btn.configure(text="📷 识别图片", state='normal')
                        
                        self.after(0, show_error)
                        
                except requests.exceptions.Timeout:
                    def show_timeout():
                        messagebox.showerror(
                            "错误", 
                            "⏱️ 网络超时\n\n"
                            "图片上传超时，请检查网络连接\n\n"
                            "建议：\n"
                            "1. 检查网络是否畅通\n"
                            "2. 尝试较小的图片\n"
                            "3. 使用手动输入方式"
                        )
                        recognize_btn.configure(text="📷 识别图片", state='normal')
                    
                    self.after(0, show_timeout)
                    
                except requests.exceptions.RequestException as e:
                    def show_network_error():
                        messagebox.showerror(
                            "错误", 
                            f"🌐 网络错误\n\n"
                            f"无法连接 AI 服务：{e}\n\n"
                            "请检查网络连接后重试"
                        )
                        recognize_btn.configure(text="📷 识别图片", state='normal')
                    
                    self.after(0, show_network_error)
                    
                except Exception as e:
                    error_type = type(e).__name__
                    def show_general_error():
                        if "IncompleteRead" in str(e) or "Connection" in str(e):
                            messagebox.showerror(
                                "错误", 
                                "🌐 连接中断\n\n"
                                "图片上传过程中网络中断\n\n"
                                "可能的原因：\n"
                                "1. 网络不稳定\n"
                                "2. 图片太大\n"
                                "3. 服务器响应超时\n\n"
                                "解决方案：\n"
                                "1. 检查网络连接\n"
                                "2. 尝试更小的图片\n"
                                "3. 使用手动输入方式"
                            )
                        else:
                            messagebox.showerror(
                                "错误", 
                                f"❌ 识别失败：{error_type}\n\n"
                                f"错误信息：{e}\n\n"
                                "请使用手动输入方式"
                            )
                        recognize_btn.configure(text="📷 识别图片", state='normal')
                    
                    self.after(0, show_general_error)
            
            # 启动异步线程
            thread = threading.Thread(target=do_recognition)
            thread.daemon = True
            thread.start()
        
        recognize_btn = ctk.CTkButton(btn_frame, text="🔍 开始识别",
                                     command=recognize,
                                     fg_color=COLORS['secondary'],
                                     hover_color=COLORS['primary'],
                                     text_color="white",
                                     corner_radius=8,
                                     height=40,
                                     width=150)
        recognize_btn.pack(side=tk.LEFT, padx=10)
        
        close_btn = ctk.CTkButton(btn_frame, text="❌ 关闭",
                                 command=dialog.destroy,
                                 fg_color="transparent",
                                 border_width=2,
                                 border_color=COLORS['text_secondary'],
                                 text_color=COLORS['text_secondary'],
                                 hover_color=COLORS['card_bg'],
                                 corner_radius=8,
                                 height=40,
                                 width=100)
        close_btn.pack(side=tk.LEFT, padx=10)
    
    def open_voice_interaction(self):
        """打开语音交互弹窗 / Open Voice Interaction Dialog"""
        # 创建弹窗
        dialog = ctk.CTkToplevel(self)
        dialog.title("🎤 语音交互 - 说话就能输入")
        dialog.geometry("1200x800")  # 改大，和主视窗一样大
        dialog.transient(self)
        dialog.grab_set()
        
        # 标题
        title_label = ctk.CTkLabel(dialog, text="🎤 语音交互 - 说话问 AI",
                                  font=("Arial", 24, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(dialog, text="语音转文字 · 一键问 AI",
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 语音输入区
        input_frame = ctk.CTkFrame(dialog, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(input_frame, text="📢 语音输入",
                    text_color=COLORS['text_primary'],
                    font=("Arial", 20, "bold")).pack(pady=(15, 10))
        
        voice_input_display = ctk.CTkTextbox(input_frame, height=200,  # 减小高度
                                            font=("Arial", 18))  # 改大字体
        voice_input_display.pack(padx=15, pady=(0, 15), fill=tk.X)  # 横向填充
        voice_input_display.insert(tk.END, "正在初始化，请稍候...")
        
        # 录音进度条
        recording_progress_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        recording_progress_frame.pack(padx=15, pady=(0, 10), fill=tk.X)
        
        recording_progress_label = ctk.CTkLabel(recording_progress_frame, 
                                               text="",
                                               font=("Arial", 14, "bold"),
                                               text_color=COLORS['primary'])
        recording_progress_label.pack(side=tk.LEFT, padx=(0, 10))
        
        recording_progress_bar = ctk.CTkProgressBar(recording_progress_frame, 
                                                     width=300, 
                                                     height=8,
                                                     mode='determinate')
        recording_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        recording_progress_bar.set(0)
        recording_progress_frame.pack_forget()  # 初始隐藏
        
        # 按钮区
        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 15))
        
        # 存储识别结果和状态
        recognized_text = [""]
        is_recording = [False]
        stop_early = [False]  # 是否提前停止
        
        # 提前确定按钮（录音时显示）
        early_confirm_btn = ctk.CTkButton(btn_frame, text="✅ 确定（提前结束）",
                                         command=lambda: stop_recording_early(stop_early, early_confirm_btn),
                                         fg_color=COLORS['secondary'],
                                         hover_color=COLORS['primary'],
                                         text_color="white",
                                         corner_radius=8,
                                         height=40,
                                         width=180,
                                         font=("Arial", 12, "bold"))
        
        def stop_recording_early(stop_flag, btn):
            """提前停止录音"""
            stop_flag[0] = True
            btn.configure(text="⏹️ 正在停止...", state='disabled')
            print("[语音识别] 用户点击提前停止")
                
        def start_listening():
            """开始语音识别（自动开始）"""
            try:
                # 导入语音识别库
                import speech_recognition as sr
                
                # 显示录音中
                record_btn.configure(text="🎤 录音中...", fg_color='red', state='disabled')
                stop_early[0] = False  # 重置提前停止标志
                early_confirm_btn.pack(pady=5)  # 显示提前确定按钮
                
                # 显示录音进度条
                recording_progress_frame.pack(padx=15, pady=(0, 10), fill=tk.X)
                recording_progress_bar.set(0)
                recording_progress_label.configure(text="🎙️ 正在录音...")
                
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, "🔴 正在录音，请说话...（最长 30 秒）\n\n说完可点击【✅ 确定】提前结束")
                is_recording[0] = True
                
                # 使用 SpeechRecognition 进行语音识别
                recognizer = sr.Recognizer()
                
                # 使用麦克风
                with sr.Microphone() as source:
                    print("[语音识别] 开始使用麦克风...")
                    # 调整环境噪音（优化：时间 0.5 秒，更准确）
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # 设置灵敏度（优化阈值，更灵敏）
                    recognizer.energy_threshold = 300  # 降低阈值，更灵敏
                    recognizer.dynamic_energy_threshold = True
                    recognizer.phrase_threshold = 0.5  # 短语阈值
                    
                    # 录音（30 秒限制，支持提前停止）
                    print("[语音识别] 正在录音...（最长 30 秒）")
                    
                    # 使用线程实现可中断的录音
                    import threading
                    import time
                    
                    audio_container = [None]  # 存储录音数据
                    error_container = [None]  # 存储错误信息
                    
                    def listen_thread():
                        """录音线程"""
                        try:
                            audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
                            audio_container[0] = audio
                        except Exception as e:
                            error_container[0] = e
                    
                    # 启动录音线程
                    thread = threading.Thread(target=listen_thread)
                    thread.daemon = True
                    thread.start()
                    
                    # 等待录音完成（带动态进度条）
                    start_time = time.time()
                    max_duration = 30  # 最大录音时长（秒）
                    
                    while audio_container[0] is None and error_container[0] is None:
                        if stop_early[0]:
                            print("[语音识别] 用户选择提前停止")
                            break
                        
                        elapsed = time.time() - start_time
                        if elapsed > max_duration:
                            print("[语音识别] 达到 30 秒限制")
                            break
                        
                        # 更新进度条并刷新UI
                        progress = min(elapsed / max_duration, 1.0)
                        recording_progress_bar.set(progress)
                        remaining = int(max_duration - elapsed)
                        recording_progress_label.configure(text=f"🎙️ 正在录音... {remaining}秒")
                        dialog.update_idletasks()  # 关键：刷新UI
                        
                        time.sleep(0.1)  # 等待 100ms
                    
                    # 检查是否有错误
                    if error_container[0]:
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"❌ 录音错误：{error_container[0]}")
                        messagebox.showerror("错误", f"录音失败：{error_container[0]}")
                        record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                        early_confirm_btn.pack_forget()
                        recording_progress_frame.pack_forget()
                        return
                    
                    # 检查是否有录音数据
                    if audio_container[0] is None:
                        if stop_early[0]:
                            voice_input_display.delete(1.0, tk.END)
                            voice_input_display.insert(tk.END, "⏹️ 已提前停止录音，请重新录音")
                            record_btn.configure(text="🎤 重新录音", fg_color=COLORS['primary'], state='normal')
                            early_confirm_btn.pack_forget()
                            recording_progress_frame.pack_forget()
                            return
                        else:
                            # 录音超时
                            voice_input_display.delete(1.0, tk.END)
                            voice_input_display.insert(tk.END, "❌ 未检测到声音，请重试")
                            messagebox.showwarning(
                                "提示", 
                                "⏱️ 超时！\n\n未检测到您说话\n\n"
                                "可能的原因：\n"
                                "1. 麦克风未连接或损坏\n"
                                "2. 麦克风音量太小\n"
                                "3. 环境太嘈杂\n\n"
                                "请检查麦克风后重试"
                            )
                            record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                            early_confirm_btn.pack_forget()
                            recording_progress_frame.pack_forget()
                            return
                    
                    # 录音成功
                    audio = audio_container[0]
                    print("[语音识别] 录音完成")
                    
                    # 隐藏进度条
                    recording_progress_frame.pack_forget()
                    
                    # 显示“正在识别...”
                    voice_input_display.delete(1.0, tk.END)
                    voice_input_display.insert(tk.END, "🔍 正在识别...")
                    dialog.update_idletasks()
                                        
                    # 使用 Google 语音识别
                    try:
                        print("[语音识别] 正在使用 Google 语音识别引擎...")
                        text = recognizer.recognize_google(audio, language='zh-CN')
                        recognized_text[0] = text
                        print(f"[语音识别] 识别成功：{text}")
                                            
                        # 显示识别结果和确认按钮
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"🎤 识别结果：\n{text}\n\n点击下方【确定】按钮使用 AI 解答")
                                            
                        # 隐藏录音按钮
                        record_btn.pack_forget()
                                            
                        # 显示确认按钮框架
                        confirm_frame.pack(pady=10)
                                            
                        # 并排显示三个按钮
                        confirm_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                        edit_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                        cancel_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                                            
                        # 显示“重新录音”按钮
                        record_btn.configure(text="🎤 重新录音", fg_color=COLORS['primary'], state='normal')
                        record_btn.pack(pady=10)
                        early_confirm_btn.pack_forget()
                                            
                    except Exception as e:
                        error_detail = str(e)
                        print(f"[语音识别] 识别失败：{error_detail}")
                                            
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"❌ 识别错误：{error_detail}")
                        messagebox.showerror(
                            "错误",
                            f"❌ 识别失败\n\n"
                            f"错误信息：{error_detail}\n\n"
                            "请检查麦克风或网络连接后重试"
                        )
                        recording_progress_frame.pack_forget()  # 隐藏进度条
                        record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                        early_confirm_btn.pack_forget()
                        return
                        
            except ImportError as e:
                error_msg = str(e)
                if "PyAudio" in error_msg:
                    messagebox.showerror(
                        "错误", 
                        "未安装 PyAudio 音频处理库\n\n"
                        "这是语音识别必需的库\n\n"
                        "解决方案：\n"
                        "1. 双击运行 '安装 PyAudio.bat'\n"
                        "2. 重新运行程序测试语音功能"
                    )
                elif "speech_recognition" in error_msg.lower():
                    messagebox.showerror(
                        "错误", 
                        "未安装 SpeechRecognition 库\n\n"
                        "请运行：pip install SpeechRecognition"
                    )
                else:
                    messagebox.showerror(
                        "错误", 
                        f"语音识别失败：缺少必要的库\n\n"
                        f"错误信息：{error_msg}\n\n"
                        "请检查是否已安装所有依赖库"
                    )
            except OSError as e:
                # 麦克风访问错误
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, f"❌ 麦克风错误：{e}")
                messagebox.showerror(
                    "错误", 
                    f"🎤 麦克风错误\n\n"
                    f"无法访问麦克风：{e}\n\n"
                    "可能的原因：\n"
                    "1. 麦克风未连接\n"
                    "2. 麦克风被其他程序占用\n"
                    "3. 权限设置禁止访问麦克风\n\n"
                    "请检查麦克风连接和权限设置"
                )
            except Exception as e:
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, f"❌ 错误：{e}")
                messagebox.showerror(
                    "错误", 
                    f"🎤 语音识别失败\n\n"
                    f"发生错误：{e}\n\n"
                    "请检查设备后重试"
                )
            finally:
                # 恢复按钮状态（如果有确认按钮则不恢复）
                if not confirm_btn.winfo_ismapped():
                    record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                    early_confirm_btn.pack_forget()  # 隐藏提前确定按钮
        
        # 录音按钮
        record_btn = ctk.CTkButton(btn_frame, text="🎤 按住说话",
                                  command=start_listening,
                                  fg_color=COLORS['primary'],
                                  hover_color=COLORS['secondary'],
                                  text_color="white",
                                  corner_radius=25,
                                  height=80,  # 改大
                                  width=300,  # 改大
                                  font=("Arial", 20, "bold"))  # 改大字体
        record_btn.pack(pady=10)
        
        # 确认按钮框架（识别成功后显示，用于并排显示三个按钮）
        confirm_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        
        # 确认按钮（创建但不 pack）
        confirm_btn = ctk.CTkButton(confirm_frame, text="✅ 确定（向 AI 提问）",
                                   command=lambda: confirm_and_ask_ai(voice_input_display, recognized_text, confirm_btn, edit_btn, cancel_btn, record_btn),
                                   fg_color=COLORS['secondary'],
                                   hover_color=COLORS['primary'],
                                   text_color="white",
                                   corner_radius=8,
                                   height=60,  # 改大
                                   width=200,  # 改大
                                   font=("Arial", 16, "bold"))  # 改大字体
        
        # 编辑按钮（创建但不 pack）
        edit_btn = ctk.CTkButton(confirm_frame, text="✏️ 修改文字",
                                command=lambda: edit_text(dialog, recognized_text, voice_input_display, confirm_btn, edit_btn, cancel_btn),
                                fg_color=COLORS['tertiary'],
                                hover_color=COLORS['secondary'],
                                text_color="white",
                                corner_radius=8,
                                height=60,  # 改大
                                width=160,  # 改大
                                font=("Arial", 16))  # 改大字体
        
        # 取消按钮（创建但不 pack）
        cancel_btn = ctk.CTkButton(confirm_frame, text="❌ 取消",
                                  command=lambda: cancel_and_retry(voice_input_display, confirm_btn, edit_btn, cancel_btn, record_btn),
                                  fg_color="transparent",
                                  border_width=2,
                                  border_color=COLORS['text_secondary'],
                                  text_color=COLORS['text_secondary'],
                                  hover_color=COLORS['card_bg'],
                                  corner_radius=8,
                                  height=60,  # 改大
                                  width=120,  # 改大
                                  font=("Arial", 16))  # 改大字体
        
        # 提示信息
        hint_label = ctk.CTkLabel(input_frame, 
                                 text="💡 使用指南：\n"
                                      "1. 点击【按住说话】按钮\n"
                                      "2. 对着麦克风说话\n"
                                      "3. 识别完成后可以修改文字\n"
                                      "4. 点击【确定】向 AI 提问",
                                 text_color=COLORS['text_secondary'],
                                 justify=tk.LEFT)
        hint_label.pack(pady=(10, 5))
        
        def stop_recording_early(stop_flag, btn):
            """提前停止录音"""
            stop_flag[0] = True
            btn.configure(text="⏹️ 正在停止...", state='disabled')
            print("[语音识别] 用户点击提前停止")
                
        def start_listening():
            """开始语音识别（自动开始）"""
            try:
                # 导入语音识别库
                import speech_recognition as sr
                
                # 显示录音中
                record_btn.configure(text="🎤 录音中...", fg_color='red', state='disabled')
                stop_early[0] = False  # 重置提前停止标志
                early_confirm_btn.pack(pady=5)  # 显示提前确定按钮
                
                # 显示录音进度条
                recording_progress_frame.pack(padx=15, pady=(0, 10), fill=tk.X)
                recording_progress_bar.set(0)
                recording_progress_label.configure(text="🎙️ 正在录音...")
                
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, "🔴 正在录音，请说话...（最长 30 秒）\n\n说完可点击【✅ 确定】提前结束")
                is_recording[0] = True
                
                # 使用 SpeechRecognition 进行语音识别
                recognizer = sr.Recognizer()
                
                # 使用麦克风
                with sr.Microphone() as source:
                    print("[语音识别] 开始使用麦克风...")
                    # 调整环境噪音（优化：时间 0.5 秒，更准确）
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # 设置灵敏度（优化阈值，更灵敏）
                    recognizer.energy_threshold = 300  # 降低阈值，更灵敏
                    recognizer.dynamic_energy_threshold = True
                    recognizer.phrase_threshold = 0.5  # 短语阈值
                    
                    # 录音（30 秒限制，支持提前停止）
                    print("[语音识别] 正在录音...（最长 30 秒）")
                    
                    # 使用线程实现可中断的录音
                    import threading
                    import time
                    
                    audio_container = [None]  # 存储录音数据
                    error_container = [None]  # 存储错误信息
                    
                    def listen_thread():
                        """录音线程"""
                        try:
                            audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
                            audio_container[0] = audio
                        except Exception as e:
                            error_container[0] = e
                    
                    # 启动录音线程
                    thread = threading.Thread(target=listen_thread)
                    thread.daemon = True
                    thread.start()
                    
                    # 等待录音完成（带动态进度条）
                    start_time = time.time()
                    max_duration = 30  # 最大录音时长（秒）
                    
                    while audio_container[0] is None and error_container[0] is None:
                        if stop_early[0]:
                            print("[语音识别] 用户选择提前停止")
                            break
                        
                        elapsed = time.time() - start_time
                        if elapsed > max_duration:
                            print("[语音识别] 达到 30 秒限制")
                            break
                        
                        # 更新进度条并刷新UI
                        progress = min(elapsed / max_duration, 1.0)
                        recording_progress_bar.set(progress)
                        remaining = int(max_duration - elapsed)
                        recording_progress_label.configure(text=f"🎙️ 正在录音... {remaining}秒")
                        dialog.update_idletasks()  # 关键：刷新UI
                        
                        time.sleep(0.1)  # 等待 100ms
                    
                    # 检查是否有错误
                    if error_container[0]:
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"❌ 录音错误：{error_container[0]}")
                        messagebox.showerror("错误", f"录音失败：{error_container[0]}")
                        record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                        early_confirm_btn.pack_forget()
                        recording_progress_frame.pack_forget()
                        return
                    
                    # 检查是否有录音数据
                    if audio_container[0] is None:
                        if stop_early[0]:
                            voice_input_display.delete(1.0, tk.END)
                            voice_input_display.insert(tk.END, "⏹️ 已提前停止录音，请重新录音")
                            record_btn.configure(text="🎤 重新录音", fg_color=COLORS['primary'], state='normal')
                            early_confirm_btn.pack_forget()
                            recording_progress_frame.pack_forget()
                            return
                        else:
                            # 录音超时
                            voice_input_display.delete(1.0, tk.END)
                            voice_input_display.insert(tk.END, "❌ 未检测到声音，请重试")
                            messagebox.showwarning(
                                "提示", 
                                "⏱️ 超时！\n\n未检测到您说话\n\n"
                                "可能的原因：\n"
                                "1. 麦克风未连接或损坏\n"
                                "2. 麦克风音量太小\n"
                                "3. 环境太嘈杂\n\n"
                                "请检查麦克风后重试"
                            )
                            record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                            early_confirm_btn.pack_forget()
                            recording_progress_frame.pack_forget()
                            return
                    
                    # 录音成功
                    audio = audio_container[0]
                    print("[语音识别] 录音完成")
                    
                    # 隐藏进度条
                    recording_progress_frame.pack_forget()
                    
                    # 显示“正在识别...”
                    voice_input_display.delete(1.0, tk.END)
                    voice_input_display.insert(tk.END, "🔍 正在识别...")
                    dialog.update_idletasks()
                                        
                    # 使用 Google 语音识别
                    try:
                        print("[语音识别] 正在使用 Google 语音识别引擎...")
                        text = recognizer.recognize_google(audio, language='zh-CN')
                        recognized_text[0] = text
                        print(f"[语音识别] 识别成功：{text}")
                                            
                        # 显示识别结果和确认按钮
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"🎤 识别结果：\n{text}\n\n点击下方【确定】按钮使用 AI 解答")
                                            
                        # 隐藏录音按钮
                        record_btn.pack_forget()
                                            
                        # 显示确认按钮框架
                        confirm_frame.pack(pady=10)
                                            
                        # 并排显示三个按钮
                        confirm_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                        edit_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                        cancel_btn.pack(in_=confirm_frame, side=tk.LEFT, padx=5)
                                            
                        # 显示“重新录音”按钮
                        record_btn.configure(text="🎤 重新录音", fg_color=COLORS['primary'], state='normal')
                        record_btn.pack(pady=10)
                        early_confirm_btn.pack_forget()
                                            
                    except Exception as e:
                        error_detail = str(e)
                        print(f"[语音识别] 识别失败：{error_detail}")
                                            
                        voice_input_display.delete(1.0, tk.END)
                        voice_input_display.insert(tk.END, f"❌ 识别错误：{error_detail}")
                        messagebox.showerror(
                            "错误",
                            f"❌ 识别失败\n\n"
                            f"错误信息：{error_detail}\n\n"
                            "请检查麦克风或网络连接后重试"
                        )
                        recording_progress_frame.pack_forget()  # 隐藏进度条
                        record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                        early_confirm_btn.pack_forget()
                        return
                        
            except ImportError as e:
                error_msg = str(e)
                if "PyAudio" in error_msg:
                    messagebox.showerror(
                        "错误", 
                        "未安装 PyAudio 音频处理库\n\n"
                        "这是语音识别必需的库\n\n"
                        "解决方案：\n"
                        "1. 双击运行 '安装 PyAudio.bat'\n"
                        "2. 重新运行程序测试语音功能"
                    )
                elif "speech_recognition" in error_msg.lower():
                    messagebox.showerror(
                        "错误", 
                        "未安装 SpeechRecognition 库\n\n"
                        "请运行：pip install SpeechRecognition"
                    )
                else:
                    messagebox.showerror(
                        "错误", 
                        f"语音识别失败：缺少必要的库\n\n"
                        f"错误信息：{error_msg}\n\n"
                        "请检查是否已安装所有依赖库"
                    )
            except OSError as e:
                # 麦克风访问错误
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, f"❌ 麦克风错误：{e}")
                messagebox.showerror(
                    "错误", 
                    f"🎤 麦克风错误\n\n"
                    f"无法访问麦克风：{e}\n\n"
                    "可能的原因：\n"
                    "1. 麦克风未连接\n"
                    "2. 麦克风被其他程序占用\n"
                    "3. 权限设置禁止访问麦克风\n\n"
                    "请检查麦克风连接和权限设置"
                )
            except Exception as e:
                voice_input_display.delete(1.0, tk.END)
                voice_input_display.insert(tk.END, f"❌ 错误：{e}")
                messagebox.showerror(
                    "错误", 
                    f"🎤 语音识别失败\n\n"
                    f"发生错误：{e}\n\n"
                    "请检查设备后重试"
                )
            finally:
                # 恢复按钮状态（如果有确认按钮则不恢复）
                if not confirm_btn.winfo_ismapped():
                    record_btn.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
                    early_confirm_btn.pack_forget()  # 隐藏提前确定按钮
        
        def start_listening():
            """异步确认并向 AI 提问"""
            if not recognized_text[0]:
                messagebox.showwarning("提示", "请先录音")
                return
            
            # 禁用按钮
            confirm_b.configure(state='disabled')
            edit_b.configure(state='disabled')
            cancel_b.configure(state='disabled')
            
            # 显示 AI 正在回复中
            display.delete(1.0, tk.END)
            display.insert(tk.END, "🤖 AI 正在思考您的问题，请稍候...\n\n")
            
            def call_ai_async():
                try:
                    # 调用 AI API（使用智能降级策略）
                    ai_prompt = f"用户通过语音输入了以下内容，请用友好、专业的语气回答（食品安全和营养咨询）：\n\n{recognized_text[0]}"
                    
                    api_result = call_ai_api(ai_prompt, api_type="auto")
                    
                    if api_result['success']:
                        ai_answer = api_result['content']
                        
                        # 使用 after 在主线程更新 UI
                        def update_ui():
                            # 显示 AI 回答
                            display.delete(1.0, tk.END)
                            display.insert(tk.END, f"✅ AI 回答：\n\n{ai_answer}")
                            
                            messagebox.showinfo(
                                "成功",
                                f"✅ AI 已回答\n\n问题：{recognized_text[0]}\n\n请查看上方回答"
                            )
                            
                            # 恢复按钮
                            confirm_b.configure(state='normal')
                            edit_b.configure(state='normal')
                            cancel_b.configure(state='normal')
                        
                        self.after(0, update_ui)
                    else:
                        error_msg = f"AI 调用失败：{api_result.get('error', '未知错误')}"
                        
                        def show_error():
                            display.delete(1.0, tk.END)
                            display.insert(tk.END, f"❌ {error_msg}")
                            messagebox.showerror("错误", error_msg)
                            
                            # 恢复按钮
                            confirm_b.configure(state='normal')
                            edit_b.configure(state='normal')
                            cancel_b.configure(state='normal')
                        
                        self.after(0, show_error)
                        edit_b.configure(state='normal')
                        cancel_b.configure(state='normal')
                    
                    self.after(0, show_timeout)
                    
                except requests.exceptions.RequestException as e:
                    def show_network_error():
                        display.delete(1.0, tk.END)
                        display.insert(tk.END, f"❌ 网络错误：{e}")
                        messagebox.showerror(
                            "错误",
                            f"🌐 网络错误\n\n无法连接 AI 服务：{e}\n\n请检查网络连接"
                        )
                        
                        # 恢复按钮
                        confirm_b.configure(state='normal')
                        edit_b.configure(state='normal')
                        cancel_b.configure(state='normal')
                    
                    self.after(0, show_network_error)
                    
                except Exception as e:
                    def show_general_error():
                        display.delete(1.0, tk.END)
                        display.insert(tk.END, f"❌ 错误：{e}")
                        messagebox.showerror(
                            "错误",
                            f"❌ AI 提问失败\n\n发生错误：{e}\n\n请重试"
                        )
                        
                        # 恢复按钮
                        confirm_b.configure(state='normal')
                        edit_b.configure(state='normal')
                        cancel_b.configure(state='normal')
                    
                    self.after(0, show_general_error)
            
            # 启动异步线程
            thread = threading.Thread(target=call_ai_async)
            thread.daemon = True
            thread.start()
        
        def edit_text(edit_dlg, rec_text, display, confirm_b, edit_b, cancel_b):
            """编辑识别的文字"""
            if not rec_text[0]:
                messagebox.showwarning("提示", "请先录音")
                return
            
            # 创建编辑窗口
            edit_dialog = ctk.CTkToplevel(edit_dlg)
            edit_dialog.title("✏️ 编辑识别结果")
            edit_dialog.geometry("500x400")
            edit_dialog.transient(edit_dlg)
            edit_dialog.grab_set()
            
            ctk.CTkLabel(edit_dialog, text="✏️ 编辑识别结果",
                        font=("Arial", 18, "bold")).pack(pady=15)
            
            edit_textbox = ctk.CTkTextbox(edit_dialog, height=200)
            edit_textbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
            edit_textbox.insert(tk.END, rec_text[0])
            
            def save_edit():
                """保存编辑"""
                new_text = edit_textbox.get("1.0", tk.END).strip()
                if new_text:
                    rec_text[0] = new_text
                    display.delete(1.0, tk.END)
                    display.insert(tk.END, f"🎤 识别结果（已编辑）：\n{new_text}\n\n点击下方【确定】按钮向 AI 提问")
                    messagebox.showinfo("成功", "✅ 编辑已保存")
                    edit_dialog.destroy()
                else:
                    messagebox.showwarning("提示", "内容不能为空")
            
            btn_frame_edit = ctk.CTkFrame(edit_dialog, fg_color="transparent")
            btn_frame_edit.pack(pady=15)
            
            ctk.CTkButton(btn_frame_edit, text="💾 保存", command=save_edit,
                         fg_color=COLORS['primary']).pack(side=tk.LEFT, padx=5)
            ctk.CTkButton(btn_frame_edit, text="❌ 取消", command=edit_dialog.destroy,
                         fg_color="transparent", border_width=2).pack(side=tk.LEFT, padx=5)
        
        def cancel_and_retry(display, confirm_b, edit_b, cancel_b, record_b):
            """取消并重试"""
            recognized_text[0] = ""
            display.delete(1.0, tk.END)
            display.insert(tk.END, "点击麦克风按钮开始说话...")
            
            # 隐藏确认按钮框架
            confirm_frame.pack_forget()
            
            # 显示录音按钮
            record_b.configure(text="🎤 按住说话", fg_color=COLORS['primary'], state='normal')
            record_b.pack(pady=10)
        
        def confirm_and_ask_ai(display, rec_text, confirm_b, edit_b, cancel_b, record_b):
            """异步确认并向 AI 提问"""
            if not rec_text[0]:
                messagebox.showwarning("提示", "请先录音")
                return
            
            # 禁用按钮
            confirm_b.configure(state='disabled')
            edit_b.configure(state='disabled')
            cancel_b.configure(state='disabled')
            
            # 显示 AI 正在回复中
            display.delete(1.0, tk.END)
            display.insert(tk.END, "🤖 AI 正在思考您的问题，请稍候...\n\n")
            
            def call_ai_async():
                try:
                    # 调用 AI API（使用智能降级策略）
                    print(f"[AI 调用] 准备调用智谱 AI，问题：{rec_text[0]}")
                    
                    # 构建带系统提示的完整 prompt
                    ai_prompt = f"""你是一个专业的智能食谱助手，擅长根据用户提供的食材、口味偏好、饮食限制等信息，提供详细、实用、美味的食谱建议。

用户问题：{rec_text[0]}"""
                    
                    api_result = call_ai_api(ai_prompt, api_type="auto")
                    
                    if api_result['success']:
                        ai_answer = api_result['content']
                        
                        # 使用 after 在主线程更新 UI
                        def update_ui():
                            # 显示 AI 回答
                            display.delete(1.0, tk.END)
                            display.insert(tk.END, f"✅ AI 回答：\n\n{ai_answer}")
                            
                            messagebox.showinfo(
                                "成功",
                                f"✅ AI 已回答\n\n问题：{rec_text[0]}\n\n请查看上方回答"
                            )
                            
                            # 恢复按钮状态
                            confirm_b.configure(state='normal')
                            edit_b.configure(state='normal')
                            cancel_b.configure(state='normal')
                        
                        self.after(0, update_ui)
                    else:
                        error_msg = f"AI 调用失败：{api_result.get('error', '未知错误')}"
                        
                        def show_error():
                            display.delete(1.0, tk.END)
                            display.insert(tk.END, f"❌ {error_msg}")
                            messagebox.showerror("错误", error_msg)
                            
                            # 恢复按钮状态
                            confirm_b.configure(state='normal')
                            edit_b.configure(state='normal')
                            cancel_b.configure(state='normal')
                        
                        self.after(0, show_error)
                        
                except Exception as e:
                    def show_general_error():
                        error_msg = f"❌ 发生错误：{e}"
                        display.delete(1.0, tk.END)
                        display.insert(tk.END, error_msg)
                        messagebox.showerror("错误", error_msg)
                        
                        # 恢复按钮状态
                        confirm_b.configure(state='normal')
                        edit_b.configure(state='normal')
                        cancel_b.configure(state='normal')
                    
                    self.after(0, show_general_error)
            
            # 启动异步线程
            thread = threading.Thread(target=call_ai_async)
            thread.daemon = True
            thread.start()
        
        # 语音播报区
        output_frame = ctk.CTkFrame(dialog, fg_color=COLORS['card_bg'],
                                   corner_radius=15)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(output_frame, text="🔊 语音播报",
                    text_color=COLORS['text_primary'],
                    font=("Arial", 16, "bold")).pack(pady=(15, 10))
        
        def speak_recipe():
            """语音播报食谱"""
            try:
                # 获取当前食谱内容
                if hasattr(self, 'recipe_output'):
                    recipe_text = self.recipe_output.get(1.0, tk.END).strip()
                    if not recipe_text:
                        messagebox.showwarning("提示", "请先生成智能食谱")
                        return
                else:
                    messagebox.showwarning("提示", "未找到食谱内容")
                    return
                
                # 使用 pyttsx3 进行语音合成（离线）
                import pyttsx3
                
                engine = pyttsx3.init()
                
                # 设置语音参数
                voices = engine.getProperty('voices')
                engine.setProperty('voice', 'zh')  # 中文
                engine.setProperty('rate', 150)  # 语速
                engine.setProperty('volume', 1.0)  # 音量
                
                # 播报食谱
                messagebox.showinfo("提示", "🔊 正在播报食谱...\n\n请安静聆听")
                engine.say(recipe_text)
                engine.runAndWait()
                
            except ImportError:
                messagebox.showerror("错误", "未安装 pyttsx3 库\n\n请运行：pip install pyttsx3")
            except Exception as e:
                messagebox.showerror("错误", f"语音播报失败：{e}")
        
        speak_btn = ctk.CTkButton(output_frame, text="🔊 播报当前食谱",
                                 command=speak_recipe,
                                 fg_color=COLORS['secondary'],
                                 hover_color=COLORS['primary'],
                                 text_color="white",
                                 corner_radius=8,
                                 height=40)
        speak_btn.pack(pady=15)
        
        # 关闭按钮
        close_btn = ctk.CTkButton(dialog, text="❌ 关闭",
                                 command=dialog.destroy,
                                 fg_color="transparent",
                                 border_width=2,
                                 border_color=COLORS['text_secondary'],
                                 text_color=COLORS['text_secondary'],
                                 hover_color=COLORS['card_bg'],
                                 corner_radius=8,
                                 height=40)
        close_btn.pack(pady=(0, 20))
        
        # 弹窗打开后自动开始录音
        dialog.after(500, start_listening)  # 延迟 500ms 自动开始
    
    def create_page_content(self, parent, page):
        """创建页面内容 / Create Page Content"""
        if page == 'home':
            self.create_home_page(parent)
        elif page == 'recipes':
            self.create_recipes_page(parent)
        elif page == 'nutrition':
            self.create_nutrition_page(parent)  # 【新增】C.智能营养分析
        elif page == 'chat':
            self.create_chat_page(parent)  # 【新增】F.AI 对话助手
        elif page == 'fridge':
            self.create_fridge_page(parent)  # 【新增】智能冰箱管理
        elif page == 'shopping':
            self.create_shopping_page(parent)  # 【新增】D.智能采购清单
        elif page == 'about':
            self.create_about_page(parent)
    
    def create_home_page(self, parent):
        """创建首页 / Create Home Page"""
        # 介绍区 / Introduction Section
        intro_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        intro_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ctk.CTkLabel(intro_frame, text=TEXTS['slogan_main'], 
                                  font=("Arial", 28, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(intro_frame, text=TEXTS['slogan_sub'], 
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 标签 / Tags
        tags_frame = ctk.CTkFrame(intro_frame, fg_color="transparent")
        tags_frame.pack(pady=(0, 20))
        tags = [TEXTS['tag_realtime'], TEXTS['tag_antiwaste'], 
                TEXTS['tag_family'], TEXTS['tag_local']]
        for tag in tags:
            tag_label = ctk.CTkLabel(tags_frame, text=tag, 
                                    fg_color=COLORS['primary'],
                                    text_color="white",
                                    corner_radius=8,
                                    padx=10,
                                    pady=5,
                                    font=("Arial", 10, "bold"))
            tag_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 绿色档案 / Green Profile
        profile_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                    corner_radius=15)
        profile_frame.pack(fill=tk.X, pady=(0, 20))
        
        profile_title = ctk.CTkLabel(profile_frame, text=TEXTS['profile_title'], 
                                    font=("Arial", 20, "bold"),
                                    text_color=COLORS['text_primary'])
        profile_title.pack(pady=(20, 10))
        
        hint_label = ctk.CTkLabel(profile_frame, text=TEXTS['nickname_hint'], 
                                 text_color=COLORS['text_secondary'])
        hint_label.pack(pady=(0, 10))
        
        # 昵称输入 / Nickname Input
        input_frame = ctk.CTkFrame(profile_frame, fg_color="transparent")
        input_frame.pack(pady=(0, 10))
        ctk.CTkLabel(input_frame, text=TEXTS['nickname_label'],
                    text_color=COLORS['text_primary']).pack(side=tk.LEFT)
        self.nickname_entry = ctk.CTkEntry(input_frame, width=200,
                                          fg_color=COLORS['card_bg'],
                                          border_color=COLORS['primary'],
                                          border_width=2,
                                          text_color=COLORS['text_primary'])
        self.nickname_entry.pack(side=tk.LEFT, padx=(10, 0))
        self.nickname_entry.insert(0, self.data['nickname'])
        
        save_btn = ctk.CTkButton(input_frame, text=TEXTS['save_nickname'], 
                                command=self.save_nickname,
                                fg_color=COLORS['primary'],
                                hover_color=COLORS['secondary'],
                                text_color="white",
                                corner_radius=8,
                                height=32)
        save_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        self.welcome_label = ctk.CTkLabel(profile_frame, text="", 
                                         text_color=COLORS['text_secondary'])
        self.welcome_label.pack(pady=(10, 0))
        self.update_welcome()
        
        # 人群选择 / Population Group Selector
        population_frame = ctk.CTkFrame(profile_frame, fg_color="transparent")
        population_frame.pack(pady=(15, 10))
        
        ctk.CTkLabel(population_frame, text="🏷️ 选择您的人群标签（用于营养评估）", 
                    font=("Arial", 14, "bold"),
                    text_color=COLORS['text_primary']).pack(anchor=tk.W)
        
        ctk.CTkLabel(population_frame, text="不同人群有不同的营养摄入标准", 
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 12)).pack(anchor=tk.W, pady=(5, 10))
        
        # 三选一单选按钮组
        self.population_var = tk.StringVar(value=self.data.get('population_group', 'adults'))
        
        groups_frame = ctk.CTkFrame(population_frame, fg_color="transparent")
        groups_frame.pack(fill=tk.X)
        
        # 成年人
        adults_rb = ctk.CTkRadioButton(groups_frame, text="成年人 (18-60 岁) - 均衡营养", 
                                       variable=self.population_var, value='adults',
                                       text_color=COLORS['text_primary'],
                                       hover_color=COLORS['secondary'],
                                       command=self.save_population_group)
        adults_rb.pack(anchor=tk.W, pady=(5, 0))
        
        # 青少年（新增）
        teens_rb = ctk.CTkRadioButton(groups_frame, text="青少年 (13-17 岁) - 生长发育关键期", 
                                      variable=self.population_var, value='teens',
                                      text_color=COLORS['text_primary'],
                                      hover_color=COLORS['secondary'],
                                      command=self.save_population_group)
        teens_rb.pack(anchor=tk.W, pady=(5, 0))
        
        # 儿童
        children_rb = ctk.CTkRadioButton(groups_frame, text="儿童 (6-12 岁) - 生长发育", 
                                        variable=self.population_var, value='children',
                                        text_color=COLORS['text_primary'],
                                        hover_color=COLORS['secondary'],
                                        command=self.save_population_group)
        children_rb.pack(anchor=tk.W, pady=(5, 0))
        
        # 老年人
        elderly_rb = ctk.CTkRadioButton(groups_frame, text="老年人 (60 岁以上) - 易消化高钙", 
                                       variable=self.population_var, value='elderly',
                                       text_color=COLORS['text_primary'],
                                       hover_color=COLORS['secondary'],
                                       command=self.save_population_group)
        elderly_rb.pack(anchor=tk.W, pady=(5, 0))
        
        # 以上皆是（新增）
        all_rb = ctk.CTkRadioButton(groups_frame, text="以上皆是 - 为所有人群生成适配方案", 
                                   variable=self.population_var, value='all',
                                   text_color=COLORS['text_primary'],
                                   hover_color=COLORS['secondary'],
                                   command=self.save_population_group)
        all_rb.pack(anchor=tk.W, pady=(5, 0))
        
        # 开始按钮 / Start Button
        start_btn = ctk.CTkButton(profile_frame, text=TEXTS['start_menu'], 
                                 command=lambda: self.show_page('recipes'),
                                 fg_color=COLORS['primary'],
                                 hover_color=COLORS['secondary'],
                                 text_color="white",
                                 corner_radius=8,
                                 height=45)
        start_btn.pack(pady=(20, 20))
        
        # 累计环保贡献 / Cumulative Impact
        self.cumulative_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                            corner_radius=15)
        self.cumulative_frame.pack(fill=tk.X, pady=(0, 20))
        self.update_cumulative_impact()
        
        # 今日饮食推荐 / Daily Recommendation (新增)
        recommendation_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                          corner_radius=15)
        recommendation_frame.pack(fill=tk.X, pady=(0, 20))
        
        rec_title_label = ctk.CTkLabel(recommendation_frame, text="🍽️ 今日饮食推荐",
                                      font=("Arial", 20, "bold"),
                                      text_color=COLORS['text_primary'])
        rec_title_label.pack(pady=(20, 10))
        
        rec_desc_label = ctk.CTkLabel(recommendation_frame, 
                                     text="基于您的营养状况和冰箱食材，AI 为您生成专属饮食建议",
                                     text_color=COLORS['text_secondary'],
                                     font=("Arial", 14))
        rec_desc_label.pack(pady=(0, 15))
        
        generate_rec_btn = ctk.CTkButton(recommendation_frame, text="🤖 AI 生成今日推荐",
                                        command=self.generate_today_recommendation,
                                        fg_color=COLORS['primary'],
                                        hover_color=COLORS['secondary'],
                                        text_color="white",
                                        corner_radius=8,
                                        height=45)
        generate_rec_btn.pack(pady=(0, 20))
        
        # 推荐结果展示区
        self.recommendation_output = ctk.CTkTextbox(recommendation_frame, wrap=tk.WORD,
                                                   font=("Arial", 14),
                                                   height=300)
        self.recommendation_output.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 计数器：记录生成次数
        self.generation_count = 0
        
        # 今日摄入记录录入区域（新增核心功能）
        intake_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                   corner_radius=15)
        intake_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(intake_frame, text="📝 今日饮食摄入记录", 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 10))
        
        ctk.CTkLabel(intake_frame, text="请录入您今日已摄入的各类食材重量（克）",
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 14)).pack(pady=(0, 15))
        
        # 输入框网格布局
        input_grid = ctk.CTkFrame(intake_frame, fg_color="transparent")
        input_grid.pack(pady=10)
        
        # 蔬菜
        ctk.CTkLabel(input_grid, text="🥬 蔬菜 (g):", 
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).grid(row=0, column=0, padx=10, pady=5)
        self.vegetables_entry = ctk.CTkEntry(input_grid, width=120,
                                            fg_color=COLORS['card_bg'],
                                            border_color=COLORS['primary'],
                                            text_color=COLORS['text_primary'])
        self.vegetables_entry.grid(row=0, column=1, padx=10, pady=5)
        self.vegetables_entry.insert(0, "0")  # 默认值
        
        # 水果
        ctk.CTkLabel(input_grid, text="🍎 水果 (g):", 
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).grid(row=0, column=2, padx=10, pady=5)
        self.fruits_entry = ctk.CTkEntry(input_grid, width=120,
                                        fg_color=COLORS['card_bg'],
                                        border_color=COLORS['primary'],
                                        text_color=COLORS['text_primary'])
        self.fruits_entry.grid(row=0, column=3, padx=10, pady=5)
        self.fruits_entry.insert(0, "0")
        
        # 肉类
        ctk.CTkLabel(input_grid, text="🥩 肉类 (g):", 
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).grid(row=0, column=4, padx=10, pady=5)
        self.meat_entry = ctk.CTkEntry(input_grid, width=120,
                                      fg_color=COLORS['card_bg'],
                                      border_color=COLORS['primary'],
                                      text_color=COLORS['text_primary'])
        self.meat_entry.grid(row=0, column=5, padx=10, pady=5)
        self.meat_entry.insert(0, "0")
        
        # 蛋类
        ctk.CTkLabel(input_grid, text="🥚 蛋类 (g):", 
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).grid(row=0, column=6, padx=10, pady=5)
        self.eggs_entry = ctk.CTkEntry(input_grid, width=120,
                                      fg_color=COLORS['card_bg'],
                                      border_color=COLORS['primary'],
                                      text_color=COLORS['text_primary'])
        self.eggs_entry.grid(row=0, column=7, padx=10, pady=5)
        self.eggs_entry.insert(0, "0")
        
        # 按钮区域
        btn_frame = ctk.CTkFrame(intake_frame, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        save_intake_btn = ctk.CTkButton(btn_frame, text="💾 保存记录",
                                       command=self.save_daily_intake,
                                       fg_color=COLORS['primary'],
                                       hover_color=COLORS['secondary'],
                                       text_color="white",
                                       height=40,
                                       width=150)
        save_intake_btn.pack(side=tk.LEFT, padx=10)
        
        assess_btn = ctk.CTkButton(btn_frame, text="🔍 立即评估",
                                  command=self.show_nutrition_report,
                                  fg_color=COLORS['secondary'],
                                  hover_color=COLORS['primary'],
                                  text_color="white",
                                  height=40,
                                  width=150)
        assess_btn.pack(side=tk.LEFT, padx=10)
        
        # 评估报告展示区
        self.assessment_output = ctk.CTkTextbox(intake_frame, wrap=tk.WORD,
                                               font=("Arial", 14),
                                               height=350)
        self.assessment_output.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 历史记录表格区域（显示当天最多 5 条记录，支持手动编辑）
        history_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                    corner_radius=15)
        history_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(history_frame, text="📊 今日摄入概览", 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 10))
        
        ctk.CTkLabel(history_frame, text="💡 提示：可直接在表格中修改摄入数据，录入 3 次后自动评估营养状况", 
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 12)).pack(pady=(0, 10))
        
        # 创建表格容器
        table_container = ctk.CTkFrame(history_frame, fg_color="transparent")
        table_container.pack(fill=tk.X, padx=20, pady=10)
        
        # 保存容器引用以便刷新
        self.history_table_container = table_container
        
        # 表格标题行
        header_frame = ctk.CTkFrame(table_container, fg_color=COLORS['primary'])
        header_frame.pack(fill=tk.X)
        
        # 删除"营养状况"列，因为单顿饭的评估没有意义
        headers = ["序号", "时间", "蔬菜 (g)", "水果 (g)", "肉类 (g)", "蛋类 (g)", "操作"]
        widths = [50, 120, 80, 80, 80, 80, 80]
        
        for i, header in enumerate(headers):
            lbl = ctk.CTkLabel(header_frame, text=header, 
                             font=("Arial", 13, "bold"),
                             text_color="white",
                             width=widths[i])
            lbl.pack(side=tk.LEFT, padx=1, pady=2)
        
        # 获取今日数据
        today = datetime.now().strftime('%Y-%m-%d')
        records = self.data.get('daily_intake_records', [])
        
        # 筛选今日记录，按时间倒序排列，最多显示 5 条
        today_records = []
        for record in records:
            if record.get('date') == today:
                today_records.append(record)
        
        # 按时间倒序排序（假设最新的在后面）
        today_records = today_records[-5:]  # 只保留最后 5 条
        
        # 存储可编辑的 Entry 引用
        self.editable_entries = {}  # {record_index: {'vegetables': entry, 'fruits': entry, ...}}
        
        # 显示表格内容
        if today_records:
            for idx, record in enumerate(today_records, 1):
                row_frame = ctk.CTkFrame(table_container, fg_color=COLORS['card_bg'])
                row_frame.pack(fill=tk.X, pady=1)
                
                # 序号
                ctk.CTkLabel(row_frame, text=str(idx), 
                           text_color=COLORS['text_primary'],
                           width=widths[0]).pack(side=tk.LEFT, padx=1, pady=5)
                
                # 时间（带日期）
                time_str = record.get('time', 'N/A')
                date_str = record.get('date', today)
                # 显示完整日期时间
                full_time = f"{date_str} {time_str}"
                ctk.CTkLabel(row_frame, text=full_time, 
                           text_color=COLORS['text_primary'],
                           width=widths[1],
                           justify=tk.LEFT).pack(side=tk.LEFT, padx=1, pady=5)
                
                # 可编辑的摄入数据容器
                edit_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                edit_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                # 蔬菜
                veg_entry = ctk.CTkEntry(edit_frame, width=70,
                                       fg_color=COLORS['card_bg'],
                                       border_color=COLORS['primary'],
                                       text_color=COLORS['text_primary'])
                veg_entry.insert(0, str(record.get('vegetables', 0)))
                veg_entry.pack(side=tk.LEFT, padx=2)
                
                # 水果
                fruit_entry = ctk.CTkEntry(edit_frame, width=70,
                                         fg_color=COLORS['card_bg'],
                                         border_color=COLORS['primary'],
                                         text_color=COLORS['text_primary'])
                fruit_entry.insert(0, str(record.get('fruits', 0)))
                fruit_entry.pack(side=tk.LEFT, padx=2)
                
                # 肉类
                meat_entry = ctk.CTkEntry(edit_frame, width=70,
                                        fg_color=COLORS['card_bg'],
                                        border_color=COLORS['primary'],
                                        text_color=COLORS['text_primary'])
                meat_entry.insert(0, str(record.get('meat', 0)))
                meat_entry.pack(side=tk.LEFT, padx=2)
                
                # 蛋类
                egg_entry = ctk.CTkEntry(edit_frame, width=70,
                                       fg_color=COLORS['card_bg'],
                                       border_color=COLORS['primary'],
                                       text_color=COLORS['text_primary'])
                egg_entry.insert(0, str(record.get('eggs', 0)))
                egg_entry.pack(side=tk.LEFT, padx=2)
                
                # 确定按钮
                confirm_btn = ctk.CTkButton(edit_frame, text="✓ 确定",
                                           width=60, height=28,
                                           fg_color=COLORS['primary'],
                                           hover_color=COLORS['secondary'],
                                           text_color="white",
                                           font=("Arial", 12, "bold"),
                                           command=lambda r=idx-1: self.on_confirm_edit(r))
                confirm_btn.pack(side=tk.LEFT, padx=5)
                
                # 删除按钮（新增）
                delete_btn = ctk.CTkButton(edit_frame, text="🗑️ 删除",
                                          width=70, height=28,
                                          fg_color="#dc3545",
                                          hover_color="#c82333",
                                          text_color="white",
                                          font=("Arial", 12, "bold"),
                                          command=lambda r=idx-1: self.on_delete_record(r))
                delete_btn.pack(side=tk.LEFT, padx=2)
                
                # 存储引用（使用正序索引，与删除按钮一致）
                rec_idx = idx - 1  # 计算在 today_records 中的索引（从 0 开始）
                self.editable_entries[rec_idx] = {
                    'vegetables': veg_entry,
                    'fruits': fruit_entry,
                    'meat': meat_entry,
                    'eggs': egg_entry,
                    'status_label': None  # 不再需要状态标签
                }
        else:
            # 无数据时显示提示
            no_data_label = ctk.CTkLabel(table_container, 
                                       text="📭 今日暂无摄入记录\n请先保存摄入数据",
                                       text_color=COLORS['text_secondary'],
                                       font=("Arial", 14))
            no_data_label.pack(pady=30)
        
        # 查看 7 天记录的按钮
        view_7days_btn = ctk.CTkButton(history_frame, 
                                       text="📅 查看近 7 天记录",
                                       command=self.show_7days_history,
                                       fg_color=COLORS['secondary'],
                                       hover_color=COLORS['primary'],
                                       text_color="white",
                                       height=40,
                                       width=200)
        view_7days_btn.pack(pady=10)
        
        # 食材重量查询功能（新增）
        query_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        query_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(query_frame, text="⚖️ 食材重量查询", 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 10))
        
        ctk.CTkLabel(query_frame, text="💡 输入食材名称，查询常见食物的近似重量（帮助您估算摄入量）", 
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 12)).pack(pady=(0, 15))
        
        # 查询输入框
        query_input_frame = ctk.CTkFrame(query_frame, fg_color="transparent")
        query_input_frame.pack(pady=10)
        
        ctk.CTkLabel(query_input_frame, text="🍎 食材名称:", 
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        
        self.food_query_entry = ctk.CTkEntry(query_input_frame, width=200,
                                            fg_color=COLORS['card_bg'],
                                            border_color=COLORS['primary'],
                                            text_color=COLORS['text_primary'],
                                            placeholder_text="例如：苹果、米饭、鸡蛋...")
        self.food_query_entry.pack(side=tk.LEFT, padx=10)
        
        query_btn = ctk.CTkButton(query_input_frame, text="🔍 查询",
                                 command=self.query_food_weight,
                                 fg_color=COLORS['primary'],
                                 hover_color=COLORS['secondary'],
                                 text_color="white",
                                 height=35,
                                 width=100)
        query_btn.pack(side=tk.LEFT, padx=10)
        
        # 查询结果展示
        self.query_result_label = ctk.CTkLabel(query_frame, text="",
                                              text_color=COLORS['text_secondary'],
                                              font=("Arial", 14),
                                              justify=tk.LEFT)
        self.query_result_label.pack(pady=(10, 20), padx=20, anchor=tk.W)
    
    def create_recipes_page(self, parent):
        """创建食谱页面 / Create Recipes Page"""
        # 主要内容 / Main Content - 使用 grid 布局实现左右分栏
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 配置网格权重，实现自动拉伸 (4:6 比例)
        content_frame.grid_columnconfigure(0, weight=4)  # 左侧占 40%
        content_frame.grid_columnconfigure(1, weight=6)  # 右侧占 60%
        content_frame.grid_rowconfigure(0, weight=1)
        
        # 左侧容器框 - 参数设置区（40%）
        left_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                 corner_radius=15)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        # 左侧标题
        setup_title = ctk.CTkLabel(left_frame, text=TEXTS['setup_title'], 
                                  font=("Arial", 20, "bold"),
                                  text_color=COLORS['text_primary'])
        setup_title.pack(pady=(15, 10))
        
        # 左侧内容框架
        left_content_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 就餐人数 / Number of People
        people_frame = ctk.CTkFrame(left_content_frame, fg_color="transparent")
        people_frame.pack(fill=tk.X, pady=(0, 10))
        ctk.CTkLabel(people_frame, text=TEXTS['people_label'],
                    text_color=COLORS['text_primary']).pack(anchor=tk.W)
        self.people_var = tk.IntVar(value=3)
        self.people_scale = ctk.CTkSlider(people_frame, from_=1, to=20, 
                                         variable=self.people_var,
                                         command=self.update_people_label,
                                         button_color=COLORS['primary'],
                                         button_hover_color=COLORS['secondary'],
                                         progress_color=COLORS['secondary'])
        self.people_scale.pack(fill=tk.X, pady=(5, 0))
        self.people_label = ctk.CTkLabel(people_frame, text="3 人", 
                                        text_color=COLORS['text_secondary'])
        self.people_label.pack(anchor=tk.W)
        
        # 用餐类型 / Meal Type
        meal_frame = ctk.CTkFrame(left_content_frame, fg_color="transparent")
        meal_frame.pack(fill=tk.X, pady=(10, 10))
        ctk.CTkLabel(meal_frame, text=TEXTS['meal_type_label'],
                    text_color=COLORS['text_primary']).pack(anchor=tk.W)
        self.meal_var = tk.StringVar(value='home')
        meal_options = ['home', 'healthy', 'vegetarian', 'banquet']
        meal_labels = [TEXTS[f'meal_{opt}'] for opt in meal_options]
        for i, (opt, label) in enumerate(zip(meal_options, meal_labels)):
            rb = ctk.CTkRadioButton(meal_frame, text=label, 
                                   variable=self.meal_var, 
                                   value=opt,
                                   text_color=COLORS['text_primary'],
                                   hover_color=COLORS['secondary'])
            rb.pack(anchor=tk.W, pady=(2, 0))
        
        # 自定义食材输入 / Custom Ingredients Input - 替换为 AI 生成组件
        ing_frame = ctk.CTkFrame(left_content_frame, fg_color="transparent")
        ing_frame.pack(fill=tk.X, pady=(10, 10))
        # 标签文本
        ctk.CTkLabel(ing_frame, 
                    text="【智能食谱生成】自定义食材（多种食材用英文逗号分隔）", 
                    text_color=COLORS['text_secondary']).pack(anchor=tk.W)
        # 文本输入框
        self.custom_food_entry = ctk.CTkEntry(ing_frame, width=400,
                                             fg_color=COLORS['card_bg'],
                                             border_color=COLORS['primary'],
                                             border_width=2,
                                             text_color=COLORS['text_primary'])
        self.custom_food_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 添加选项：是否使用冰箱食材
        self.use_fridge_var = tk.BooleanVar(value=False)
        fridge_option_frame = ctk.CTkFrame(ing_frame, fg_color="transparent")
        fridge_option_frame.pack(fill=tk.X, pady=(10, 0))
        
        ctk.CTkCheckBox(fridge_option_frame, 
                       text="✅ 同时使用冰箱现有食材",
                       variable=self.use_fridge_var,
                       font=("Arial", 14)).pack(anchor=tk.W)
        
        # 按钮
        ai_gen_btn = ctk.CTkButton(ing_frame, text="AI 生成环保食谱",
                                  command=self.ai_generate_menu,
                                  fg_color=COLORS['primary'],
                                  hover_color=COLORS['secondary'],
                                  text_color="white",
                                  corner_radius=8,
                                  height=40)
        ai_gen_btn.pack(pady=(10, 0))
        
        # 饭量系数 / Appetite Multiplier
        appetite_frame = ctk.CTkFrame(left_content_frame, fg_color="transparent")
        appetite_frame.pack(fill=tk.X, pady=(10, 10))
        ctk.CTkLabel(appetite_frame, text=TEXTS['fine_tune'], 
                    font=("Arial", 12, "bold"),
                    text_color=COLORS['text_primary']).pack(anchor=tk.W)
        ctk.CTkLabel(appetite_frame, text=TEXTS['fine_hint'], 
                    text_color=COLORS['text_secondary']).pack(anchor=tk.W)
        ctk.CTkLabel(appetite_frame, text=TEXTS['appetite_label'],
                    text_color=COLORS['text_primary']).pack(anchor=tk.W)
        self.appetite_var = tk.DoubleVar(value=1.0)
        self.appetite_scale = ctk.CTkSlider(appetite_frame, from_=0.7, to=1.4, 
                                           variable=self.appetite_var,
                                           command=self.update_appetite_label,
                                           button_color=COLORS['primary'],
                                           button_hover_color=COLORS['secondary'],
                                           progress_color=COLORS['secondary'])
        self.appetite_scale.pack(fill=tk.X, pady=(5, 0))
        self.appetite_label = ctk.CTkLabel(appetite_frame, text="1.0", 
                                          text_color=COLORS['text_secondary'])
        self.appetite_label.pack(anchor=tk.W)
        
        # 右侧容器框 - 结果展示区（60%）
        right_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        # 配置右侧框架的网格，让内容区域占据所有剩余空间
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # 右侧标题（放在 grid 的第 0 行）
        menu_title = ctk.CTkLabel(right_frame, text=TEXTS['menu_title'], 
                                 font=("Arial", 20, "bold"),
                                 text_color=COLORS['text_primary'])
        menu_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(15, 10))
        
        # 创建右侧内容的滚动框架（放在 grid 的第 1 行，占据所有剩余空间）
        right_scroll_frame = ScrollableFrame(right_frame)
        right_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        right_content_frame = right_scroll_frame.scrollable_frame
        
        # 本次影响 / Current Impact（紧凑显示）- 初始时隐藏，有数据时才显示
        self.impact_frame = ctk.CTkFrame(right_content_frame, 
                                        fg_color="transparent",
                                        corner_radius=10)
        # 初始时不 pack，避免占用空间
        
        # 菜单输出 / Menu Output
        self.menu_frame = ctk.CTkFrame(right_content_frame, fg_color="transparent")
        self.menu_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 为右侧滚动框架添加事件监听，确保滚轮事件在内容区域内也能触发
        def bind_mouse_wheel_recursive(widget):
            widget.bind("<Enter>", lambda e: e.widget.nametowidget(e.widget.winfo_parent()).focus_set())
            widget.bind("<Leave>", lambda e: None)
            for child in widget.winfo_children():
                bind_mouse_wheel_recursive(child)
                
        bind_mouse_wheel_recursive(right_content_frame)
    

    
    def create_about_page(self, parent):
        """创建关于页面 / Create About Page"""
        # 标题 / Title
        title_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ctk.CTkLabel(title_frame, text=TEXTS['about_title'], 
                                  font=("Arial", 28, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(title_frame, text=TEXTS['about_sub'], 
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 页脚 / Footer
        footer_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                   corner_radius=15)
        footer_frame.pack(fill=tk.X, pady=(0, 20))
        
        footer_text = f"{TEXTS['footer_title']}\n{TEXTS['footer_copyright']}"
        ctk.CTkLabel(footer_frame, text=footer_text, 
                    text_color=COLORS['text_secondary'],
                    justify=tk.CENTER).pack(pady=20)
    
    def show_page(self, page):
        """显示页面 / Show Page"""
        # 隐藏所有页面
        for p in self.page_frames:
            self.page_frames[p].grid_remove()
        
        # 显示当前页面
        self.page_frames[page].grid()
        self.current_page = page
        
        # 【已删除】不再需要更新导航按钮状态（改为下拉菜单）
    
    # 删除了switch_language和update_texts函数
    
    def update_texts(self):
        """更新所有文本 / Update All Texts"""
        # 导航栏 / Navigation Bar
        for page, btn in self.nav_buttons.items():
            btn.configure(text=TEXTS[f'nav_{page}'])
        
        # 重新创建页面内容 / Recreate Page Content
        for page in self.page_frames:
            # 获取滚动框架
            scroll_frame = self.page_frames[page]
            # 清除内容框架内的所有内容
            for widget in scroll_frame.scrollable_frame.winfo_children():
                widget.destroy()
            # 重新创建页面内容
            self.create_page_content(scroll_frame.scrollable_frame, page)
        
        # 显示当前页面 / Show Current Page
        self.show_page(self.current_page)
    
    def save_nickname(self):
        """保存昵称 / Save Nickname"""
        nickname = self.nickname_entry.get().strip()
        if nickname:
            self.data['nickname'] = nickname
            save_data(self.data)
            messagebox.showinfo("成功", TEXTS['saved_local'])
            self.update_welcome()
        else:
            messagebox.showerror("错误", TEXTS['empty_nickname'])
    
    def save_population_group(self):
        """保存人群标签 / Save Population Group"""
        population_group = self.population_var.get()
        self.data['population_group'] = population_group
        save_data(self.data)
        print(f"✅ 人群标签已保存：{population_group}")
    
    def update_welcome(self):
        """更新欢迎信息 / Update Welcome Message"""
        if self.data['nickname']:
            self.welcome_label.configure(text=TEXTS['welcome'].format(self.data['nickname']))
        else:
            self.welcome_label.configure(text="")
    
    def update_cumulative_impact(self):
        """更新累计环保贡献 / Update Cumulative Impact"""
        # 清空现有内容 / Clear Existing Content
        for widget in self.cumulative_frame.winfo_children():
            widget.destroy()
            
        parent = self.cumulative_frame  # 移除了 dashboard 相关判断
            
        ctk.CTkLabel(parent, text=TEXTS['cumulative_title'], 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(20, 10))
        ctk.CTkLabel(parent, text=TEXTS['cumulative_tag'], 
                    text_color=COLORS['text_secondary']).pack(pady=(0, 20))
            
        # 指标卡片 / Metric Cards - 橙色背景，白色文字
        metrics_frame = ctk.CTkFrame(parent, fg_color="transparent")
        metrics_frame.pack(fill=tk.X, expand=True, padx=20, pady=20)
            
        metrics = [
            (TEXTS['waste_reduced'], self.data['waste_reduced'], TEXTS['unit_g']),
            (TEXTS['water_saved'], self.data['water_saved'], TEXTS['unit_l']),
            (TEXTS['co2_reduced'], self.data['co2_reduced'], TEXTS['unit_g'])
        ]
            
        # 创建三个卡片的容器（使用 pack 布局）
        cards_container = ctk.CTkFrame(metrics_frame, fg_color="transparent")
        cards_container.pack(fill=tk.BOTH, expand=True)
        
        for i, (name, value, unit) in enumerate(metrics):
            # 橙色卡片，白色文字
            card_frame = ctk.CTkFrame(cards_container, 
                                     fg_color=COLORS['primary'],
                                     bg_color=COLORS['primary'],
                                     corner_radius=15,
                                     width=250,
                                     height=150)
            card_frame.pack(side=tk.LEFT, padx=15, pady=20, expand=True, fill=tk.BOTH)
            card_frame.pack_propagate(False)  # 防止子组件改变卡片大小
                
            # 数值标签（大字体）
            value_label = ctk.CTkLabel(card_frame, 
                        text=f"{value} {unit}",
                        font=("Arial", 32, "bold"),
                        text_color="white")
            value_label.pack(pady=(30, 10), anchor=tk.CENTER)
            
            # 名称标签（小字体）
            name_label = ctk.CTkLabel(card_frame, 
                        text=name,
                        text_color="white",
                        font=("Arial", 13, "bold"))
            name_label.pack(pady=(0, 20), anchor=tk.CENTER)
            
        ctk.CTkLabel(parent, text=TEXTS['tip_achievement'], 
                    text_color=COLORS['text_secondary']).pack(pady=(0, 10))
            
        # 重置按钮 / Reset Button
        reset_frame = ctk.CTkFrame(parent, fg_color="transparent")
        reset_frame.pack(pady=(10, 20))
            
        reset_btn = ctk.CTkButton(reset_frame, text=TEXTS['reset_stats'], 
                                 command=self.reset_stats,
                                 fg_color="transparent",
                                 border_width=2,
                                 border_color=COLORS['danger'],
                                 text_color=COLORS['text_primary'],
                                 hover_color=COLORS['danger'],
                                 height=36)
        reset_btn.pack()
            
        self.reset_var = tk.BooleanVar()
        ctk.CTkCheckBox(reset_frame, text=TEXTS['reset_confirm'], 
                       variable=self.reset_var,
                       text_color=COLORS['text_primary']).pack(pady=(10, 0))
    
    def reset_stats(self):
        """重置统计 / Reset Stats"""
        if self.reset_var.get():
            self.data = {'nickname': self.data['nickname'], 'waste_reduced': 0, 'water_saved': 0, 
                        'co2_reduced': 0}
            save_data(self.data)
            messagebox.showinfo("成功", "统计已重置 / Stats reset")
            self.update_cumulative_impact()
        else:
            messagebox.showwarning("警告", "请先勾选确认选项 / Please check the confirmation first")
    
    def generate_today_recommendation(self):
        """生成今日饮食推荐 / Generate Today's Diet Recommendation"""
        # 计数器 +1
        self.generation_count += 1
        
        # 清空输出
        self.recommendation_output.delete(1.0, tk.END)
        self.recommendation_output.insert(tk.END, f"🤖 AI 正在分析您的营养状况和冰箱食材... (第{self.generation_count}次生成)\n\n")
        
        # 获取用户数据
        population_group = self.data.get('population_group', 'adults')
        fridge_items = self.data.get('fridge_inventory', [])
        
        # 获取用户今日总摄入数据（整合所有记录）
        if self.data.get('daily_intake_records'):
            today = datetime.now().strftime('%Y-%m-%d')
            all_records = self.data.get('daily_intake_records', [])
            today_records = [r for r in all_records if r.get('date') == today]
            
            if today_records:
                # 整合今日所有数据
                user_intake = {
                    'vegetables': sum(r.get('vegetables', 0) for r in today_records),
                    'fruits': sum(r.get('fruits', 0) for r in today_records),
                    'meat': sum(r.get('meat', 0) for r in today_records),
                    'eggs': sum(r.get('eggs', 0) for r in today_records)
                }
                print(f"📊 生成今日推荐：整合了{len(today_records)}条记录，总摄入：蔬菜{user_intake['vegetables']}g, 水果{user_intake['fruits']}g, 肉类{user_intake['meat']}g, 蛋类{user_intake['eggs']}g")
            else:
                # 如果今日无记录，使用默认值
                user_intake = {
                    'vegetables': 0,
                    'fruits': 0,
                    'meat': 0,
                    'eggs': 0
                }
                self.recommendation_output.insert(tk.END, "⚠️ 提示：今日暂无摄入记录，将基于 0 摄入进行推荐。\n\n")
        else:
            # 如果用户未录入，使用默认值并提示
            user_intake = {
                'vegetables': 0,
                'fruits': 0,
                'meat': 0,
                'eggs': 0
            }
            self.recommendation_output.insert(tk.END, "⚠️ 提示：您还未录入今日摄入数据，将基于 0 摄入进行推荐。建议先录入实际摄入量以获得更精准的推荐。\n\n")
        
        # ========== 检查是否为"以上皆是"模式 ==========
        if population_group == 'all':
            # 显示所有人群的营养标准对比
            self._show_multi_group_nutrition_comparison(user_intake)
            # 为所有人群生成推荐
            self._generate_multi_group_recommendation(user_intake, fridge_items)
        else:
            # 检查是否需要自动评估（生成 3 次以上）
            if self.generation_count >= 3:
                self.recommendation_output.insert(tk.END, "🔍 检测到您已生成 3 次以上食谱，系统自动执行营养评估...\n\n")
                self.after(500, self.auto_assessment_and_recommend)  # 延迟执行评估
            else:
                # 正常推荐流程
                self._do_recommend(user_intake, population_group, fridge_items)
    
    def auto_assessment_and_recommend(self):
        """自动评估并推荐（整合全天数据）"""
        # 获取今日所有记录
        today = datetime.now().strftime('%Y-%m-%d')
        all_records = self.data.get('daily_intake_records', [])
        today_records = [r for r in all_records if r.get('date') == today]
        
        if not today_records:
            self.recommendation_output.insert(tk.END, "⚠️ 今日暂无摄入记录\n\n")
            return
        
        # 整合今日总摄入数据
        total_intake = {
            'date': today,
            'vegetables': sum(r.get('vegetables', 0) for r in today_records),
            'fruits': sum(r.get('fruits', 0) for r in today_records),
            'meat': sum(r.get('meat', 0) for r in today_records),
            'eggs': sum(r.get('eggs', 0) for r in today_records)
        }
        
        population_group = self.data.get('population_group', 'adults')
        
        # ========== 检查是否为"以上皆是"模式 ==========
        if population_group == 'all':
            # 为所有人群生成评估和推荐
            self._show_multi_group_nutrition_report(total_intake)
            fridge_items = self.data.get('fridge_inventory', [])
            self._generate_multi_group_recommendation(total_intake, fridge_items)
        else:
            # 单一人群模式：正常评估并推荐
            # 调用评估函数（使用总量）
            assessment = nutrition_assessment(total_intake, population_group)
            
            # 显示评估摘要
            self.recommendation_output.insert(tk.END, f"📊 自动评估结果（整合{len(today_records)}条记录）:\n")
            for food_type, result in assessment.items():
                status_icon = {"达标": "✅", "不足": "⬇️", "超标": "⬆️", "未录入": "⏸️"}.get(result['status'], '❓')
                self.recommendation_output.insert(tk.END, f"   {status_icon} {result['chinese_name']}：{result['status']}\n")
            self.recommendation_output.insert(tk.END, "\n")
            
            # 继续推荐（使用总量）
            fridge_items = self.data.get('fridge_inventory', [])
            self._do_recommend(total_intake, population_group, fridge_items)
    
    def _do_recommend(self, user_intake, population_group, fridge_items):
        """执行实际的推荐逻辑（异步非阻塞）"""
        # 显示加载提示
        self.recommendation_output.delete(1.0, tk.END)
        self.recommendation_output.insert(tk.END, "🤖 AI 正在生成饮食推荐，请稍候...\n\n")
        
        # 禁用生成按钮，防止重复点击
        if hasattr(self, 'generate_rec_btn'):
            self.generate_rec_btn.configure(state='disabled', text="⏳ 生成中...")
        
        # 异步调用 AI
        def call_ai_async():
            try:
                # 调用智能推荐函数
                recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items)
                
                # 使用 after 方法在主线程更新 UI
                def update_ui():
                    self.recommendation_output.delete(1.0, tk.END)
                    if population_group == 'all':
                        # 多人群模式：调用多人群推荐函数
                        self._generate_multi_group_recommendation(user_intake, fridge_items)
                    else:
                        self.recommendation_output.insert(tk.END, f"✅ 今日饮食推荐（适配人群：{population_group}）\n\n")
                        self.recommendation_output.insert(tk.END, recommendation)
                    
                    # 恢复按钮状态
                    if hasattr(self, 'generate_rec_btn'):
                        self.generate_rec_btn.configure(state='normal', text="🍽️ 生成推荐")
                
                self.after(0, update_ui)
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    self.recommendation_output.delete(1.0, tk.END)
                    self.recommendation_output.insert(tk.END, f"❌ 生成推荐失败：{error_msg}\n\n请检查网络连接或稍后重试。")
                    if hasattr(self, 'generate_rec_btn'):
                        self.generate_rec_btn.configure(state='normal', text="🍽️ 生成推荐")
                
                self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()
    
    def on_data_edit(self, record_index):
        """处理表格数据编辑，实时更新营养状况 / Handle data editing and update nutrition status in real-time"""
        try:
            # 获取编辑后的数据
            if not hasattr(self, 'editable_entries') or record_index not in self.editable_entries:
                return
            
            entry_data = self.editable_entries[record_index]
            
            # 从 Entry 获取新值
            vegetables = int(entry_data['vegetables'].get())
            fruits = int(entry_data['fruits'].get())
            meat = int(entry_data['meat'].get())
            eggs = int(entry_data['eggs'].get())
            
            # 验证合理性
            for name, value in [("蔬菜", vegetables), ("水果", fruits), ("肉类", meat), ("蛋类", eggs)]:
                if value < 0 or value > 5000:
                    messagebox.showerror("错误", f"{name}摄入量 {value}g 不合理，请输入 0-5000 之间的数字")
                    return
            
            # 更新数据文件中的记录
            today = datetime.now().strftime('%Y-%m-%d')
            records = self.data.get('daily_intake_records', [])
            
            # 找到对应的记录并更新
            today_records = [r for r in records if r.get('date') == today]
            if record_index < len(today_records):
                target_record = today_records[record_index]
                target_record['vegetables'] = vegetables
                target_record['fruits'] = fruits
                target_record['meat'] = meat
                target_record['eggs'] = eggs
                
                # 保存更新
                save_data(self.data)
                
                # 重新计算营养状况
                intake = {
                    'vegetables': vegetables,
                    'fruits': fruits,
                    'meat': meat,
                    'eggs': eggs
                }
                population_group = self.data.get('population_group', 'adults')
                assessment = nutrition_assessment(intake, population_group)
                
                status_list = [result['status'] for result in assessment.values() if result['status'] != '未录入']
                adequate_count = status_list.count('达标')
                recorded_count = len(status_list)  # 已录入的食材数
                
                # 根据已录入的食材数判断
                if recorded_count == 0:
                    status_str = "⏸️ 未录入"
                elif adequate_count == recorded_count:
                    status_str = "✅ 全部达标"
                elif adequate_count >= recorded_count / 2:
                    status_str = "⚠️ 部分达标"
                else:
                    status_str = "❌ 需要改善"
                
                # 更新状态标签
                if entry_data['status_label']:
                    entry_data['status_label'].configure(text=status_str)
                
                print(f"✓ 记录 {record_index + 1} 已更新：蔬菜={vegetables}g, 水果={fruits}g, 肉类={meat}g, 蛋类={eggs}g")
                print(f"  营养状况：{status_str}")
                
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数")
        except Exception as e:
            print(f"✗ 更新数据时出错：{e}")
    
    def on_confirm_edit(self, record_index):
        """处理表格数据编辑确认，实时更新营养状况 / Handle data editing confirmation and update nutrition status in real-time"""
        try:
            # 获取编辑后的数据
            if not hasattr(self, 'editable_entries') or record_index < 0:
                return
            
            entry_data = self.editable_entries.get(record_index)
            if not entry_data:
                return
            
            # 从 Entry 获取新值
            vegetables = int(entry_data['vegetables'].get())
            fruits = int(entry_data['fruits'].get())
            meat = int(entry_data['meat'].get())
            eggs = int(entry_data['eggs'].get())
            
            # 验证合理性
            for name, value in [("蔬菜", vegetables), ("水果", fruits), ("肉类", meat), ("蛋类", eggs)]:
                if value < 0 or value > 5000:
                    messagebox.showerror("错误", f"{name}摄入量 {value}g 不合理，请输入 0-5000 之间的数字")
                    return
            
            # 更新数据文件中的记录
            today = datetime.now().strftime('%Y-%m-%d')
            records = self.data.get('daily_intake_records', [])
            
            # 找到对应的记录并更新
            today_records = [r for r in records if r.get('date') == today]
            if record_index < len(today_records):
                target_record = today_records[record_index]
                target_record['vegetables'] = vegetables
                target_record['fruits'] = fruits
                target_record['meat'] = meat
                target_record['eggs'] = eggs
                
                # 保存更新
                save_data(self.data)
                
                # 重新计算营养状况
                intake = {
                    'vegetables': vegetables,
                    'fruits': fruits,
                    'meat': meat,
                    'eggs': eggs
                }
                population_group = self.data.get('population_group', 'adults')
                assessment = nutrition_assessment(intake, population_group)
                
                status_list = [result['status'] for result in assessment.values() if result['status'] != '未录入']
                adequate_count = status_list.count('达标')
                recorded_count = len(status_list)  # 已录入的食材数
                
                # 根据已录入的食材数判断
                if recorded_count == 0:
                    status_str = "⏸️ 未录入"
                    detail_msg = "💡 请至少录入一种食材"
                elif adequate_count == recorded_count:
                    status_str = "✅ 全部达标"
                    detail_msg = "🎉 已录入食材营养均衡！"
                elif adequate_count >= recorded_count / 2:
                    status_str = "⚠️ 部分达标"
                    insufficient = [v['chinese_name'] for k, v in assessment.items() if v['status'] == '不足']
                    excessive = [v['chinese_name'] for k, v in assessment.items() if v['status'] == '超标']
                    detail_msg = f"💡 建议："
                    if insufficient:
                        detail_msg += f"增加{','.join(insufficient)}摄入；"
                    if excessive:
                        detail_msg += f"减少{','.join(excessive)}摄入。"
                else:
                    status_str = "❌ 需要改善"
                    insufficient = [v['chinese_name'] for k, v in assessment.items() if v['status'] == '不足']
                    excessive = [v['chinese_name'] for k, v in assessment.items() if v['status'] == '超标']
                    detail_msg = f"⚠️ 需要调整："
                    if insufficient:
                        detail_msg += f"增加{','.join(insufficient)}；"
                    if excessive:
                        detail_msg += f"减少{','.join(excessive)}。"
                
                # 更新状态标签
                if entry_data['status_label']:
                    entry_data['status_label'].configure(text=status_str)
                
                # 显示成功提示和详细分析
                messagebox.showinfo("✅ 更新成功", 
                                   f"数据已确认并保存！\n\n"
                                   f"📊 营养状况：{status_str}\n\n"
                                   f"{detail_msg}")
                
                print(f"✓ 记录 {record_index + 1} 已确认：蔬菜={vegetables}g, 水果={fruits}g, 肉类={meat}g, 蛋类={eggs}g")
                print(f"  营养状况：{status_str}")
                
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数")
        except Exception as e:
            print(f"✗ 确认数据时出错：{e}")
    
    def on_delete_record(self, record_index):
        """处理表格数据删除 / Handle record deletion"""
        try:
            # 确认删除
            confirm = messagebox.askyesno("🗑️ 确认删除", "确定要删除这条记录吗？\n\n删除后将无法恢复！")
            if not confirm:
                return
            
            # 获取今日所有记录
            today = datetime.now().strftime('%Y-%m-%d')
            records = self.data.get('daily_intake_records', [])
            today_records = [r for r in records if r.get('date') == today]
            
            if record_index >= len(today_records):
                return
            
            # 删除指定记录
            deleted_record = today_records.pop(record_index)
            
            # 更新主数据列表（移除旧记录，添加剩余记录）
            all_records = [r for r in records if r.get('date') != today]
            all_records.extend(today_records)
            self.data['daily_intake_records'] = all_records
            
            # 保存到文件
            save_data(self.data)
            
            # 清空编辑缓存（重要：删除后必须清空，因为索引已失效）
            if hasattr(self, 'editable_entries'):
                self.editable_entries.clear()
            
            # 刷新表格（会重新建立 editable_entries）
            self.refresh_history_table()
            
            print(f"✅ 已删除记录：{deleted_record}")
            messagebox.showinfo("✅ 删除成功", f"已删除该条记录")
            
        except Exception as e:
            print(f"✗ 删除失败：{e}")
            messagebox.showerror("错误", f"删除失败：{e}")
    
    def query_food_weight(self):
        """查询食材重量 / Query food weight"""
        food_name = self.food_query_entry.get().strip()
        
        if not food_name:
            self.query_result_label.configure(text="❌ 请输入食材名称")
            return
        
        # 常见食材重量数据库（每 100g 可食部）
        food_weight_db = {
            # 蔬菜类
            '白菜': {'weight': 100, 'unit': '克/片', 'desc': '大白菜，中等大小叶片'},
            '青菜': {'weight': 50, 'unit': '克/棵', 'desc': '小油菜，中等大小'},
            '菠菜': {'weight': 80, 'unit': '克/把', 'desc': '新鲜菠菜，一小把'},
            '生菜': {'weight': 60, 'unit': '克/片', 'desc': '球生菜，大片'},
            '西红柿': {'weight': 150, 'unit': '克/个', 'desc': '中等大小番茄'},
            '黄瓜': {'weight': 180, 'unit': '克/根', 'desc': '中等大小黄瓜'},
            '土豆': {'weight': 150, 'unit': '克/个', 'desc': '中等大小马铃薯'},
            '胡萝卜': {'weight': 100, 'unit': '克/根', 'desc': '中等大小胡萝卜'},
            '茄子': {'weight': 200, 'unit': '克/个', 'desc': '长茄子，一根'},
            '青椒': {'weight': 80, 'unit': '克/个', 'desc': '大青椒，一个'},
            '菜花': {'weight': 150, 'unit': '克/朵', 'desc': '西兰花或花椰菜，一小朵'},
            
            # 水果类
            '苹果': {'weight': 200, 'unit': '克/个', 'desc': '中等大小苹果'},
            '香蕉': {'weight': 120, 'unit': '克/根', 'desc': '中等大小香蕉'},
            '橙子': {'weight': 150, 'unit': '克/个', 'desc': '中等大小橙子'},
            '梨': {'weight': 180, 'unit': '克/个', 'desc': '中等大小梨'},
            '葡萄': {'weight': 10, 'unit': '克/粒', 'desc': '中等大小葡萄粒'},
            '西瓜': {'weight': 300, 'unit': '克/片', 'desc': '一片西瓜（三角块）'},
            '草莓': {'weight': 15, 'unit': '克/个', 'desc': '中等大小草莓'},
            '桃子': {'weight': 150, 'unit': '克/个', 'desc': '中等大小桃子'},
            '橘子': {'weight': 80, 'unit': '克/个', 'desc': '中等大小橘子'},
            
            # 肉类
            '猪肉': {'weight': 50, 'unit': '克/片', 'desc': '猪肉片，中等大小'},
            '牛肉': {'weight': 60, 'unit': '克/片', 'desc': '牛肉片，中等大小'},
            '鸡肉': {'weight': 80, 'unit': '克/块', 'desc': '鸡胸肉，一块'},
            '羊肉': {'weight': 50, 'unit': '克/片', 'desc': '羊肉片，中等大小'},
            '鱼': {'weight': 150, 'unit': '克/块', 'desc': '鱼排，一块'},
            '虾': {'weight': 20, 'unit': '克/只', 'desc': '中等大小虾'},
            
            # 蛋类
            '鸡蛋': {'weight': 50, 'unit': '克/个', 'desc': '中等大小鸡蛋'},
            '鸭蛋': {'weight': 60, 'unit': '克/个', 'desc': '中等大小鸭蛋'},
            '鹌鹑蛋': {'weight': 10, 'unit': '克/个', 'desc': '鹌鹑蛋，一个'},
            
            # 主食类
            '米饭': {'weight': 150, 'unit': '克/碗', 'desc': '一碗米饭（普通饭碗）'},
            '馒头': {'weight': 100, 'unit': '克/个', 'desc': '中等大小馒头'},
            '面条': {'weight': 200, 'unit': '克/碗', 'desc': '一碗面条（连汤带水）'},
            '面包': {'weight': 50, 'unit': '克/片', 'desc': '切片面包，一片'},
            '饺子': {'weight': 20, 'unit': '克/个', 'desc': '中等大小水饺'},
            '包子': {'weight': 100, 'unit': '克/个', 'desc': '中等大小包子'},
            
            # 豆制品
            '豆腐': {'weight': 100, 'unit': '克/块', 'desc': '北豆腐，一块'},
            '豆浆': {'weight': 250, 'unit': '克/杯', 'desc': '一杯豆浆（普通杯子）'},
            
            # 坚果类
            '花生': {'weight': 10, 'unit': '克/勺', 'desc': '一勺花生米'},
            '核桃': {'weight': 10, 'unit': '克/个', 'desc': '一个核桃仁'},
            '杏仁': {'weight': 3, 'unit': '克/粒', 'desc': '一粒杏仁'},
        }
        
        # 模糊匹配
        matched_foods = []
        for name, info in food_weight_db.items():
            if name in food_name or food_name in name:
                matched_foods.append((name, info))
        
        if matched_foods:
            result_text = f"🔍 查询结果（匹配到 {len(matched_foods)} 项）:\n\n"
            for i, (name, info) in enumerate(matched_foods[:5], 1):  # 最多显示 5 个
                result_text += f"{i}. {name}: 约{info['weight']} {info['unit']}\n"
                result_text += f"   📝 {info['desc']}\n\n"
            
            if len(matched_foods) > 5:
                result_text += f"... 还有{len(matched_foods)-5}项，请具体描述\n"
            
            self.query_result_label.configure(text=result_text)
        else:
            # 如果没找到，给出一些通用建议
            self.query_result_label.configure(
                text=f"❌ 未找到'{food_name}'的准确数据\n\n"
                     f"💡 参考建议：\n"
                     f"• 蔬菜类：一般叶片菜 50-100g/份\n"
                     f"• 水果类：中等大小水果 150-200g/个\n"
                     f"• 肉类：手掌心大小约 80-100g\n"
                     f"• 主食类：一碗米饭约 150-200g\n\n"
                     f"您可以尝试输入更具体的名称，如'苹果'、'白菜'等"
            )
    
    def check_and_auto_evaluate(self):
        """检查录入次数，自动触发营养评估 / Check intake count and auto-evaluate"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            records = self.data.get('daily_intake_records', [])
            
            # 统计今日录入次数
            today_records = [r for r in records if r.get('date') == today]
            record_count = len(today_records)
            
            # 如果录入次数>=3，自动触发评估
            if record_count >= 3:
                print(f"📊 今日已录入{record_count}次，达到 3 次，自动触发营养评估")
                
                # 计算今日总摄入量
                total_vegetables = sum(r.get('vegetables', 0) for r in today_records)
                total_fruits = sum(r.get('fruits', 0) for r in today_records)
                total_meat = sum(r.get('meat', 0) for r in today_records)
                total_eggs = sum(r.get('eggs', 0) for r in today_records)
                
                # 更新输入框为总量
                self.vegetables_entry.delete(0, tk.END)
                self.vegetables_entry.insert(0, str(total_vegetables))
                
                self.fruits_entry.delete(0, tk.END)
                self.fruits_entry.insert(0, str(total_fruits))
                
                self.meat_entry.delete(0, tk.END)
                self.meat_entry.insert(0, str(total_meat))
                
                self.eggs_entry.delete(0, tk.END)
                self.eggs_entry.insert(0, str(total_eggs))
                
                # 自动触发评估
                self.show_nutrition_report()
                
                # 显示提示
                messagebox.showinfo("🔔 自动评估提醒", 
                                   f"今日已录入{record_count}次饮食\n\n"
                                   f"📊 已自动汇总并评估营养状况\n"
                                   f"📈 总摄入：蔬菜{total_vegetables}g, 水果{total_fruits}g, "
                                   f"肉类{total_meat}g, 蛋类{total_eggs}g\n\n"
                                   f"💡 您可以查看下方的评估报告")
            else:
                print(f"📝 今日已录入{record_count}次，未达到 3 次，暂不自动评估")
                
        except Exception as e:
            print(f"✗ 自动评估检查出错：{e}")
    
    def save_daily_intake(self):
        """保存用户今日摄入数据 / Save Daily Intake Data"""
        try:
            # 获取输入值
            vegetables = int(self.vegetables_entry.get())
            fruits = int(self.fruits_entry.get())
            meat = int(self.meat_entry.get())
            eggs = int(self.eggs_entry.get())
            
            # 验证合理性（0-5000g 范围）
            for name, value in [("蔬菜", vegetables), ("水果", fruits), ("肉类", meat), ("蛋类", eggs)]:
                if value < 0 or value > 5000:
                    messagebox.showerror("错误", f"{name}摄入量 {value}g 不合理，请输入 0-5000 之间的数字")
                    return
            
            # 保存到数据文件
            today = datetime.now().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M')
            intake_record = {
                'date': today,
                'time': now_time,
                'vegetables': vegetables,
                'fruits': fruits,
                'meat': meat,
                'eggs': eggs
            }
            
            if 'daily_intake_records' not in self.data:
                self.data['daily_intake_records'] = []
            
            # 直接追加记录（不删除历史记录）
            self.data['daily_intake_records'].append(intake_record)
            
            save_data(self.data)
            
            # 提示成功
            messagebox.showinfo("成功", f"✅ {today} 摄入数据已保存\n\n蔬菜：{vegetables}g\n水果：{fruits}g\n肉类：{meat}g\n蛋类：{eggs}g")
            
            # 自动触发实时预警检查
            population_group = self.data.get('population_group', 'adults')
            for food_type, amount in [('vegetables', vegetables), ('fruits', fruits), ('meat', meat), ('eggs', eggs)]:
                is_alert, message = check_and_alert(food_type, amount, population_group, 0)
                if is_alert:
                    messagebox.showwarning("⚠️ 摄入预警", message)
            
            # 自动刷新历史记录表格
            self.after(500, self.refresh_history_table)
            
            # 检查录入次数，自动触发评估
            self.after(1000, lambda: self.check_and_auto_evaluate())
            
            # 检查是否有不达标项目，自动生成解决方案
            self.after(1500, lambda: self.check_and_auto_recommend())
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数")
    
    def show_nutrition_report(self):
        """显示营养评估报告（整合全天数据） / Show Nutrition Assessment Report"""
        # 清空输出区
        self.assessment_output.delete(1.0, tk.END)
        
        # 首先尝试从输入框获取实时数据
        try:
            vegetables = int(self.vegetables_entry.get())
            fruits = int(self.fruits_entry.get())
            meat = int(self.meat_entry.get())
            eggs = int(self.eggs_entry.get())
            
            # 如果输入框中有数据（非 0），优先使用输入框数据
            if vegetables > 0 or fruits > 0 or meat > 0 or eggs > 0:
                latest_intake = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'vegetables': vegetables,
                    'fruits': fruits,
                    'meat': meat,
                    'eggs': eggs
                }
                print(f" 使用输入框实时数据进行评估：蔬菜={vegetables}g, 水果={fruits}g, 肉类={meat}g, 蛋类={eggs}g")
            else:
                # 如果输入框都是 0，则使用今日总摄入数据
                if not self.data.get('daily_intake_records'):
                    self.assessment_output.insert(tk.END, "❌ 您还未录入任何摄入数据，请先点击【💾 保存记录】录入今日饮食。")
                    return
                
                # 整合今日所有数据
                today = datetime.now().strftime('%Y-%m-%d')
                all_records = self.data.get('daily_intake_records', [])
                today_records = [r for r in all_records if r.get('date') == today]
                
                if today_records:
                    total_intake = {
                        'date': today,
                        'vegetables': sum(r.get('vegetables', 0) for r in today_records),
                        'fruits': sum(r.get('fruits', 0) for r in today_records),
                        'meat': sum(r.get('meat', 0) for r in today_records),
                        'eggs': sum(r.get('eggs', 0) for r in today_records)
                    }
                    latest_intake = total_intake
                    print(f"🔍 使用今日总摄入数据进行评估：整合了{len(today_records)}条记录")
                else:
                    self.assessment_output.insert(tk.END, "❌ 今日暂无摄入数据")
                    return
        except ValueError:
            self.assessment_output.insert(tk.END, "❌ 输入数据无效，请输入整数")
            return
        
        # 获取人群分类
        population_group = self.data.get('population_group', 'adults')
        
        # ========== 检查是否为"以上皆是"模式 ==========
        if population_group == 'all':
            # 为所有人群分别生成评估报告
            self._show_multi_group_nutrition_report(latest_intake)
            return
        
        # ========== 单一人群模式：生成完整的本地营养评估报告 ==========
        print("\n🔍 开始本地营养评估（基于联合国 WHO 标准）...")
        
        # 调用评估函数
        assessment = nutrition_assessment(latest_intake, population_group)
        
        # 获取营养标准
        standard = get_nutrition_standard(population_group)
        
        # 构建完整的本地评估报告
        report = self._generate_complete_local_report(latest_intake, population_group, assessment, standard)
        
        # 显示报告
        self.assessment_output.insert(tk.END, report)
        print("✅ 本地营养评估报告生成完成")
    
    def _show_multi_group_nutrition_report(self, latest_intake):
        """为所有人群生成营养评估报告（"以上皆是"模式 - 纯本地版） / Show Multi-Group Nutrition Report"""
        print("\n📊 开始为所有人群生成营养评估报告...")
        
        # 人群映射表
        group_info = {
            'adults': {'name': '成年人', 'age': '18-60 岁', 'icon': '👥'},
            'teens': {'name': '青少年', 'age': '13-17 岁', 'icon': '👦'},
            'children': {'name': '儿童', 'age': '6-12 岁', 'icon': '👶'},
            'elderly': {'name': '老年人', 'age': '60 岁以上', 'icon': '👴'}
        }
        
        # 为每个群体生成报告
        for group_key in ['adults', 'teens', 'children', 'elderly']:
            info = group_info[group_key]
            
            # 分隔线
            separator = "\n" + "="*60 + "\n"
            header = f"{info['icon']}【{info['name']} ({info['age']})】营养评估报告\n"
            
            self.assessment_output.insert(tk.END, separator)
            self.assessment_output.insert(tk.END, header)
            self.assessment_output.insert(tk.END, "="*60 + "\n\n")
            
            # 本地快速评估
            assessment = nutrition_assessment(latest_intake, group_key)
            standard = get_nutrition_standard(group_key)
            
            # 生成完整的本地报告
            report = self._generate_complete_local_report(latest_intake, group_key, assessment, standard)
            
            # 显示报告
            self.assessment_output.insert(tk.END, report)
            self.assessment_output.insert(tk.END, "\n")
        
        # 最后总结
        final_summary = "\n" + "="*60 + "\n"
        final_summary += "📋 总体总结\n"
        final_summary += "="*60 + "\n\n"
        final_summary += "💡 已为所有人群生成营养评估报告，请向上滚动查看各群体的详细分析。\n\n"
        final_summary += "📊 关键发现：\n"
        final_summary += "• 不同年龄段对营养的需求不同\n"
        final_summary += "• 请根据家庭成员的实际情况，参考对应人群的评估结果\n"
        final_summary += "• 如有不达标项目，建议针对性调整饮食结构\n\n"
        
        self.assessment_output.insert(tk.END, final_summary)
        print("✅ 所有人群营养评估报告生成完成")
    
    def _show_multi_group_nutrition_comparison(self, user_intake):
        """显示所有人群的营养标准对比（"以上皆是"模式） / Show Multi-Group Nutrition Comparison"""
        print("\n📊 显示所有人群营养标准对比...")
        
        # 人群映射表
        group_info = {
            'adults': {'name': '成年人', 'age': '18-60 岁', 'icon': '👥'},
            'teens': {'name': '青少年', 'age': '13-17 岁', 'icon': '👦'},
            'children': {'name': '儿童', 'age': '6-12 岁', 'icon': '👶'},
            'elderly': {'name': '老年人', 'age': '60 岁以上', 'icon': '👴'}
        }
        
        # 分隔线
        separator = "\n" + "="*70 + "\n"
        header = "📊 各年龄段营养需求标准对比（基于联合国 WHO 标准）\n"
        
        self.recommendation_output.insert(tk.END, separator)
        self.recommendation_output.insert(tk.END, header)
        self.recommendation_output.insert(tk.END, "="*70 + "\n\n")
        
        # 显示用户当前摄入
        self.recommendation_output.insert(tk.END, "【您当前摄入】\n")
        self.recommendation_output.insert(tk.END, f"  蔬菜：{user_intake.get('vegetables', 0)}g\n")
        self.recommendation_output.insert(tk.END, f"  水果：{user_intake.get('fruits', 0)}g\n")
        self.recommendation_output.insert(tk.END, f"  肉类：{user_intake.get('meat', 0)}g\n")
        self.recommendation_output.insert(tk.END, f"  蛋类：{user_intake.get('eggs', 0)}g\n\n")
        
        # 为每个群体显示营养标准
        for group_key in ['adults', 'teens', 'children', 'elderly']:
            info = group_info[group_key]
            standard = get_nutrition_standard(group_key)
            
            if not standard:
                continue
            
            # 群体标题
            group_header = f"{info['icon']} {info['name']} ({info['age']}) 营养标准:\n"
            self.recommendation_output.insert(tk.END, group_header)
            self.recommendation_output.insert(tk.END, "-" * 50 + "\n")
            
            # 显示该群体的营养标准
            recommendations = standard.get('daily_recommendations', {})
            
            # 只显示 4 类主要食材
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                unit = rec.get('unit', 'g')
                
                chinese_name = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}[food_type]
                
                # 检查用户摄入是否达标
                intake_amount = user_intake.get(food_type, 0)
                if intake_amount < min_val:
                    status = "⬇️ 不足"
                    gap = min_val - intake_amount
                    status_text = f"{status} (还差 {gap}g)"
                elif intake_amount > max_val:
                    status = "⬆️ 超标"
                    gap = intake_amount - max_val
                    status_text = f"{status} (超出 {gap}g)"
                else:
                    status = "✅ 达标"
                    status_text = status
                
                self.recommendation_output.insert(tk.END, f"  {chinese_name}: {min_val}-{max_val}{unit} → 您的摄入：{intake_amount}g {status_text}\n")
            
            # 显示该群体的特征描述
            characteristics = standard.get('characteristics', '')
            if characteristics:
                self.recommendation_output.insert(tk.END, f"\n  💡 群体特点：{characteristics}\n")
            
            self.recommendation_output.insert(tk.END, "\n")
        
        # 总结
        summary = "\n" + "="*70 + "\n"
        summary += "📋 关键发现：\n"
        summary += "• 不同年龄段对营养的需求不同，请根据家庭成员情况参考对应标准\n"
        summary += "• 系统将基于各年龄段的需求，生成适配所有人的饮食方案\n"
        summary += "• 如有不达标项目，推荐中会提供针对性的改善建议\n\n"
        
        self.recommendation_output.insert(tk.END, summary)
    
    def _generate_multi_group_recommendation(self, user_intake, fridge_items):
        """为所有人群生成饮食推荐（"以上皆是"模式 - 异步非阻塞） / Generate Multi-Group Recommendation"""
        print("\n🍽️ 开始为所有人群生成饮食推荐...")
        
        # 显示加载提示
        self.recommendation_output.delete(1.0, tk.END)
        self.recommendation_output.insert(tk.END, "🤖 AI 正在为所有年龄段生成饮食推荐，请稍候...\n\n")
        
        # 禁用生成按钮
        if hasattr(self, 'generate_rec_btn'):
            self.generate_rec_btn.configure(state='disabled', text="⏳ 生成中...")
        
        # 人群映射表
        group_info = {
            'adults': {'name': '成年人', 'age': '18-60 岁', 'icon': '👥'},
            'teens': {'name': '青少年', 'age': '13-17 岁', 'icon': '👦'},
            'children': {'name': '儿童', 'age': '6-12 岁', 'icon': '👶'},
            'elderly': {'name': '老年人', 'age': '60 岁以上', 'icon': '👴'}
        }
        
        # 异步调用 AI
        def call_ai_async():
            try:
                results = []
                # 为每个群体生成推荐
                for group_key in ['adults', 'teens', 'children', 'elderly']:
                    info = group_info[group_key]
                    group_header = f"{info['icon']}【{info['name']} ({info['age']})】\n"
                    
                    # 调用推荐函数
                    rec = generate_daily_recommendation(user_intake, group_key, fridge_items)
                    results.append((group_header, rec))
                
                # 使用 after 方法在主线程更新 UI
                def update_ui():
                    # 显示分隔线
                    separator = "\n" + "="*70 + "\n"
                    header = "🍽️ 分年龄段饮食推荐方案\n"
                    self.recommendation_output.delete(1.0, tk.END)
                    self.recommendation_output.insert(tk.END, separator)
                    self.recommendation_output.insert(tk.END, header)
                    self.recommendation_output.insert(tk.END, "="*70 + "\n\n")
                    
                    # 显示每个群体的推荐
                    for group_header, rec in results:
                        self.recommendation_output.insert(tk.END, group_header)
                        self.recommendation_output.insert(tk.END, "-" * 50 + "\n\n")
                        self.recommendation_output.insert(tk.END, rec)
                        self.recommendation_output.insert(tk.END, "\n\n" + "="*70 + "\n\n")
                    
                    # 最后总结
                    final_summary = "📋 总体建议：\n"
                    final_summary += "• 已为所有人群生成适配的饮食方案\n"
                    final_summary += "• 请根据家庭成员的实际情况，参考对应人群的推荐\n"
                    final_summary += "• 如有特殊饮食需求（如过敏、慢性病），请适当调整\n\n"
                    self.recommendation_output.insert(tk.END, final_summary)
                    
                    # 恢复按钮状态
                    if hasattr(self, 'generate_rec_btn'):
                        self.generate_rec_btn.configure(state='normal', text="🍽️ 生成推荐")
                
                self.after(0, update_ui)
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    self.recommendation_output.delete(1.0, tk.END)
                    self.recommendation_output.insert(tk.END, f"❌ 生成推荐失败：{error_msg}\n\n请检查网络连接或稍后重试。")
                    if hasattr(self, 'generate_rec_btn'):
                        self.generate_rec_btn.configure(state='normal', text="🍽️ 生成推荐")
                
                self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()
    
    def _format_standard_for_ai(self, standard, population_group):
        """格式化营养标准为 AI 可读文本 / Format Nutrition Standard for AI"""
        if not standard:
            return "无标准数据"
        
        text = f"人群：{population_group}（{standard.get('age_range', '未知')}）\n"
        text += f"标准来源：{standard.get('standard_source', 'WHO')}\n"
        text += f"特征描述：{standard.get('characteristics', '无')}\n\n"
        text += "每日营养推荐：\n"
        
        recommendations = standard.get('daily_recommendations', {})
        food_names = {
            'vegetables': '蔬菜',
            'fruits': '水果',
            'meat': '肉类',
            'eggs': '蛋类',
            'calories': '热量',
            'protein': '蛋白质',
            'calcium': '钙'
        }
        
        for food_type, rec in recommendations.items():
            chinese_name = food_names.get(food_type, food_type)
            unit = rec.get('unit', '')
            min_val = rec.get('min', 0)
            max_val = rec.get('max', 0)
            text += f"  - {chinese_name}: {min_val}-{max_val}{unit}\n"
        
        return text
    
    def _format_local_assessment(self, assessment, intake):
        """格式化本地评估结果为 AI 可读文本 / Format Local Assessment for AI"""
        text = "本地初步评估结果：\n"
        
        for food_type, result in assessment.items():
            chinese_name = result['chinese_name']
            status = result['status']
            intake_amount = result['intake']
            gap = result.get('gap', 0)
            suggestion = result.get('suggestion', '')
            
            text += f"  - {chinese_name}: {intake_amount}g → {status}"
            if status == "不足":
                text += f"（还差{gap}g）"
            elif status == "超标":
                text += f"（超出{gap}g）"
            text += f"\n    建议：{suggestion}\n"
        
        return text
    
    def _generate_full_local_report(self, local_report):
        """生成完整的本地评估报告（作为 AI 失败的备选） / Generate Full Local Report"""
        report = "📊 本地营养评估完整报告\n"
        report += "="*50 + "\n\n"
        
        report += f"评估日期：{local_report['date']}\n"
        report += f"人群标签：{local_report['population_group']}\n\n"
        
        # 逐项详细分析
        for food_type, result in local_report['assessment'].items():
            status_icon = {"达标": "✅", "不足": "⬇️", "超标": "⬆️"}[result['status']]
            report += f"{status_icon} {result['chinese_name']}：{result['status']}\n"
            report += f"   📊 当前摄入：{result['intake']}g\n"
            
            # 获取标准范围
            standard = local_report['standard']
            if standard:
                min_rec = standard['daily_recommendations'][food_type]['min']
                max_rec = standard['daily_recommendations'][food_type]['max']
                report += f"   📏 推荐范围：{min_rec}-{max_rec}g\n"
            
            # 计算差距
            if result['status'] == "不足":
                gap = min_rec - result['intake']
                report += f"   📉 还差：{gap}g\n"
            elif result['status'] == "超标":
                gap = result['intake'] - max_rec
                report += f"   📈 超出：{gap}g\n"
            
            report += f"   💡 {result['suggestion']}\n\n"
        
        report += "\n" + "="*50 + "\n"
        report += "注：这是本地评估报告，如需更专业的 AI 评估，请检查网络连接后重试。\n"
        
        return report
    
    def _generate_complete_local_report(self, intake, population_group, assessment, standard):
        """生成完整的本地营养评估报告（纯本地版） / Generate Complete Local Nutrition Report"""
        # 人群名称映射
        group_names = {
            'adults': '成年人 (18-60 岁)',
            'teens': '青少年 (13-17 岁)',
            'children': '儿童 (6-12 岁)',
            'elderly': '老年人 (60 岁以上)'
        }
        group_name = group_names.get(population_group, population_group)
        
        # 报告标题
        report = "\n" + "="*60 + "\n"
        report += "📊 营养评估报告（基于联合国 WHO 标准）\n"
        report += "="*60 + "\n\n"
        
        # 基本信息
        report += "【基本信息】\n"
        report += f"评估日期：{intake.get('date', '未知')}\n"
        report += f"人群分类：{group_name}\n"
        if standard:
            report += f"标准来源：{standard.get('standard_source', 'WHO')}\n"
            report += f"年龄范围：{standard.get('age_range', '未知')}\n"
        report += "\n"
        
        # 摄入数据对比
        report += "【摄入数据对比】\n"
        report += "-"*50 + "\n"
        
        food_names = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}
        icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️', '未录入': '⏸️'}
        
        for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
            intake_amount = intake.get(food_type, 0)
            if standard:
                min_rec = standard['daily_recommendations'][food_type]['min']
                max_rec = standard['daily_recommendations'][food_type]['max']
                chinese_name = food_names[food_type]
                status = assessment[food_type]['status']
                icon = icons[status]
                
                report += f"{icon} {chinese_name}：{intake_amount}g（标准：{min_rec}-{max_rec}g）→ {status}\n"
        
        report += "\n"
        
        # 详细分析
        report += "【详细分析】\n"
        report += "-"*50 + "\n\n"
        
        # 总体评价
        sufficient_count = sum(1 for r in assessment.values() if r['status'] == '达标')
        recorded_count = sum(1 for r in assessment.values() if r['status'] != '未录入')
        total_count = recorded_count  # 只计算已录入的
        
        if total_count == 0:
            report += " 总体评价：暂未录入任何食材数据，请先录入饮食。\n\n"
        elif sufficient_count == total_count:
            report += " 总体评价：已录入食材营养均衡，所有指标均达标！\n\n"
        elif sufficient_count >= total_count / 2:
            report += "👍 总体评价：已录入食材基本合理，部分项目需要改进。\n\n"
        else:
            report += "⚠️ 总体评价：已录入食材存在不足，建议调整饮食结构。\n\n"
        
        # 逐项分析
        for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
            chinese_name = food_names[food_type]
            result = assessment[food_type]
            status = result['status']
            intake_amount = intake.get(food_type, 0)
            
            if standard:
                min_rec = standard['daily_recommendations'][food_type]['min']
                max_rec = standard['daily_recommendations'][food_type]['max']
                
                if status == '达标':
                    report += f"✅ {chinese_name}：达标\n"
                    report += f"   摄入量：{intake_amount}g（标准范围：{min_rec}-{max_rec}g）\n"
                    report += f"   评价：{self._get_positive_comment(food_type, intake_amount, standard)}\n\n"
                elif status == '不足':
                    gap = min_rec - intake_amount
                    report += f"⬇️ {chinese_name}：不足\n"
                    report += f"   摄入量：{intake_amount}g（标准范围：{min_rec}-{max_rec}g）\n"
                    report += f"   差距：还差 {gap}g\n"
                    report += f"   建议：{self._get_improvement_suggestion(food_type, gap, standard)}\n\n"
                elif status == '超标':
                    gap = intake_amount - max_rec
                    report += f"⬆️ {chinese_name}：超标\n"
                    report += f"   摄入量：{intake_amount}g（标准范围：{min_rec}-{max_rec}g）\n"
                    report += f"   超出：{gap}g\n"
                    report += f"   建议：{self._get_warning_suggestion(food_type, gap, standard)}\n\n"
                elif status == '未录入':
                    report += f"⏸️ {chinese_name}：未录入\n"
                    report += f"   状态：暂未录入该食材\n"
                    report += f"   建议：如已摄入{chinese_name}，请补充录入；如未摄入，建议适当增加\n\n"
        
        # 健康提示
        report += "【健康提示】\n"
        report += "-"*50 + "\n"
        
        if standard:
            characteristics = standard.get('characteristics', '')
            if characteristics:
                report += f"💡 人群特点：{characteristics}\n\n"
        
        # 具体建议
        report += "📋 综合建议：\n"
        report += "• 保持多样化的饮食结构，不偏食不挑食\n"
        report += "• 根据实际年龄和身体状况调整摄入量\n"
        report += "• 如有特殊疾病或过敏史，请遵医嘱调整饮食\n"
        report += "• 定期监测营养状况，保持健康生活方式\n\n"
        
        report += "="*60 + "\n"
        report += "注：本评估基于联合国 WHO 营养标准，仅供参考。\n"
        report += "如有健康问题，请咨询专业营养师或医生。\n"
        
        return report
    
    def _get_positive_comment(self, food_type, intake_amount, standard):
        """获取达标项目的积极评价 / Get positive comment for sufficient item"""
        comments = {
            'vegetables': '蔬菜摄入充足，能提供丰富的维生素、矿物质和膳食纤维，有助于维持肠道健康。',
            'fruits': '水果摄入充足，能补充维生素 C 和天然抗氧化剂，增强免疫力。',
            'meat': '肉类摄入适量，能提供优质蛋白质和铁、锌等矿物质，维持身体正常功能。',
            'eggs': '蛋类摄入适量，能提供完全蛋白质和多种维生素，营养价值高。'
        }
        return comments.get(food_type, '摄入合理，有助于维持营养均衡。')
    
    def _get_improvement_suggestion(self, food_type, gap, standard):
        """获取不达标项目的改善建议 / Get improvement suggestion for insufficient item"""
        suggestions = {
            'vegetables': f'建议增加绿叶蔬菜、根茎类蔬菜的摄入，如菠菜、胡萝卜、西兰花等。可以尝试在每餐中增加一份蔬菜，或制作蔬菜沙拉、蔬菜汁。',
            'fruits': f'建议增加新鲜水果的摄入，如苹果、香蕉、橙子等。可以在早餐或下午茶时间吃一个水果，或制作水果沙拉。',
            'meat': f'建议适量增加瘦肉、禽类、鱼类的摄入。可以选择鸡胸肉、鱼肉等低脂高蛋白的肉类，避免过多摄入肥肉。',
            'eggs': f'建议每天保证 1-2 个鸡蛋的摄入。可以选择水煮蛋、蒸蛋等健康烹饪方式，避免过多油炸。'
        }
        return suggestions.get(food_type, '建议适当增加该类食物的摄入。')
    
    def _get_warning_suggestion(self, food_type, gap, standard):
        """获取超标项目的警告建议 / Get warning suggestion for excessive item"""
        warnings = {
            'vegetables': '蔬菜摄入过多可能影响其他食物的摄入，建议适当减少，保持饮食多样化。',
            'fruits': '水果摄入过多可能导致糖分摄入过量，建议控制摄入量，特别是糖尿病患者。',
            'meat': '肉类摄入过多可能增加脂肪和胆固醇摄入，建议选择瘦肉，减少肥肉和加工肉制品。',
            'eggs': '蛋类摄入过多可能增加胆固醇摄入，建议控制每天 1-2 个鸡蛋，高血脂人群需特别注意。'
        }
        return warnings.get(food_type, '该类食物摄入过多，建议适当减少。')
    
    def check_and_auto_recommend(self):
        """检查营养状况并自动生成解决方案（整合全天数据）"""
        if not self.data.get('daily_intake_records'):
            return
        
        # 获取今日所有记录
        today = datetime.now().strftime('%Y-%m-%d')
        all_records = self.data.get('daily_intake_records', [])
        today_records = [r for r in all_records if r.get('date') == today]
        
        if not today_records:
            return
        
        # 整合今日所有数据
        total_intake = {
            'vegetables': sum(r.get('vegetables', 0) for r in today_records),
            'fruits': sum(r.get('fruits', 0) for r in today_records),
            'meat': sum(r.get('meat', 0) for r in today_records),
            'eggs': sum(r.get('eggs', 0) for r in today_records)
        }
        
        print(f"\n📊 整合评估：已汇总今日{len(today_records)}条摄入记录")
        print(f"   总量：蔬菜{total_intake['vegetables']}g, 水果{total_intake['fruits']}g, 肉类{total_intake['meat']}g, 蛋类{total_intake['eggs']}g")
        
        population_group = self.data.get('population_group', 'adults')
        
        # 营养评估（使用总量）
        assessment = nutrition_assessment(total_intake, population_group)
        
        # 检查评估结果是否有效
        if not isinstance(assessment, dict) or 'error' in assessment:
            print(f"⚠️ 营养评估失败：{assessment.get('error', '未知错误')}")
            return
        
        # 检查是否有不达标项目
        has_insufficient = any(result['status'] == '不足' for result in assessment.values())
        has_excessive = any(result['status'] == '超标' for result in assessment.values())
        
        if has_insufficient or has_excessive:
            # 显示整合提示
            summary_msg = f"✅ 已将前{len(today_records)}次食谱的摄入数据整合完毕！\n\n"
            summary_msg += f"📊 今日总摄入：\n"
            summary_msg += f"   🥬 蔬菜：{total_intake['vegetables']}g\n"
            summary_msg += f"   🍎 水果：{total_intake['fruits']}g\n"
            summary_msg += f"   🥩 肉类：{total_intake['meat']}g\n"
            summary_msg += f"   🥚 蛋类：{total_intake['eggs']}g\n\n"
            summary_msg += f"系统正在为您生成改善方案..."
            
            messagebox.showinfo("📊 整合评估", summary_msg)
            
            # 直接跳转到首页并自动生成方案，不再询问用户
            print(f"\n💡 检测到营养不均衡，自动生成改善方案...")
            self.show_page('home')
            # 延迟执行，确保页面切换完成
            self.after(500, lambda: self.generate_today_recommendation())
        else:
            # 全部达标，显示鼓励信息
            print(f"\n✅ 所有营养指标都达标！")
    
    def show_7days_history(self):
        """显示近 7 天历史记录弹窗 / Show 7-Day History Dialog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("📊 近 7 天摄入记录")
        dialog.geometry("850x650")
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 850) // 2
        y = (dialog.winfo_screenheight() - 650) // 2
        dialog.geometry(f"850x650+{x}+{y}")
        
        # 标题
        title_frame = ctk.CTkFrame(dialog, fg_color=COLORS['card_bg'])
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkLabel(title_frame, text="📊 近 7 天摄入记录", 
                    font=("Arial", 24, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=10)
        
        ctk.CTkLabel(title_frame, text="查看您最近 7 天的饮食摄入情况与营养状况",
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 14)).pack(pady=(0, 10))
        
        # 创建文本框显示历史记录
        history_text = ctk.CTkTextbox(dialog, wrap=tk.WORD, width=800, height=450,
                                     font=("Consolas", 12))
        history_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 获取近 7 天的记录
        records = self.data.get('daily_intake_records', [])
        records_sorted = sorted(records, key=lambda x: x.get('date', ''), reverse=True)[:7]
        
        # 显示表头
        header = "="*90 + "\n"
        header += f"{'日期':<12} {'蔬菜 (g)':<10} {'水果 (g)':<10} {'肉类 (g)':<10} {'蛋类 (g)':<10} {'营养状况':<20}\n"
        header += "="*90 + "\n"
        history_text.insert(tk.END, header)
        
        # 逐行显示
        for record in records_sorted:
            date = record.get('date', '未知')
            vegetables = record.get('vegetables', 0)
            fruits = record.get('fruits', 0)
            meat = record.get('meat', 0)
            eggs = record.get('eggs', 0)
            
            # 评估营养状况
            intake = {
                'vegetables': vegetables,
                'fruits': fruits,
                'meat': meat,
                'eggs': eggs
            }
            population_group = self.data.get('population_group', 'adults')
            assessment = nutrition_assessment(intake, population_group)
            
            status_list = [result['status'] for result in assessment.values() if result['status'] != '未录入']
            adequate_count = status_list.count('达标')
            recorded_count = len(status_list)  # 已录入的食材数
            
            # 根据已录入的食材数判断
            if recorded_count == 0:
                status_str = "⏸️ 未录入"
            elif adequate_count == recorded_count:
                status_str = "✅ 全部达标"
            elif adequate_count >= recorded_count / 2:
                status_str = "⚠️ 部分达标"
            else:
                status_str = "❌ 需要改善"
            
            line = f"{date:<12} {vegetables:<10} {fruits:<10} {meat:<10} {eggs:<10} {status_str:<20}\n"
            history_text.insert(tk.END, line)
        
        # 表尾统计
        footer = "="*90 + "\n\n"
        footer += f"📊 共显示 {len(records_sorted)} 条记录（总计 {len(records)} 条）\n\n"
        
        # 健康统计（只计算已录入的食材）
        def is_all_adequate(record):
            """判断一条记录是否全部达标（排除未录入的）"""
            intake = {
                'vegetables': record.get('vegetables', 0),
                'fruits': record.get('fruits', 0),
                'meat': record.get('meat', 0),
                'eggs': record.get('eggs', 0)
            }
            assessment = nutrition_assessment(intake, self.data.get('population_group', 'adults'))
            # 排除未录入的，检查已录入的是否都达标
            status_list = [result['status'] for result in assessment.values() if result['status'] != '未录入']
            return len(status_list) > 0 and all(s == '达标' for s in status_list)
        
        all_adequate_days = sum(1 for r in records if is_all_adequate(r))
        
        footer += f"📈 健康统计:\n"
        footer += f"   ✅ 全部达标天数：{all_adequate_days} 天\n"
        footer += f"   ⚠️ 部分达标天数：{len(records) - all_adequate_days} 天\n"
        footer += f"   📈 健康得分：{all_adequate_days / len(records) * 100:.1f}%\n" if records else ""
        footer += "\n💡 提示：保持绿色（✅ 全部达标）的天数越多，说明您的饮食越健康！\n"
        
        history_text.insert(tk.END, footer)
        
        # 禁用编辑
        history_text.configure(state='disabled')
        
        # 关闭按钮
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        close_btn = ctk.CTkButton(btn_frame, text="关闭",
                                 command=dialog.destroy,
                                 fg_color=COLORS['primary'],
                                 hover_color=COLORS['secondary'],
                                 text_color="white",
                                 height=40,
                                 width=120)
        close_btn.pack()
    
    def refresh_history_table(self):
        """刷新历史记录表格（首页当天表格，支持编辑和删除） / Refresh History Table"""
        try:
            # 检查是否有表格容器引用
            if not hasattr(self, 'history_table_container'):
                print(f"  ✗ 找不到表格容器")
                return
            
            table_container = self.history_table_container
            
            # 清空表格容器中的所有行（保留表头）
            for widget in table_container.winfo_children():
                widget.destroy()
            
            # 重新创建表头
            header_frame = ctk.CTkFrame(table_container, fg_color=COLORS['primary'])
            header_frame.pack(fill=tk.X)
            
            headers = ["序号", "时间", "蔬菜 (g)", "水果 (g)", "肉类 (g)", "蛋类 (g)", "操作"]
            widths = [50, 120, 80, 80, 80, 80, 100]
            
            for i, header in enumerate(headers):
                lbl = ctk.CTkLabel(header_frame, text=header, 
                                 font=("Arial", 13, "bold"),
                                 text_color="white",
                                 width=widths[i])
                lbl.pack(side=tk.LEFT, padx=1, pady=2)
            
            # 重新获取今日数据并创建表格行
            today = datetime.now().strftime('%Y-%m-%d')
            records = self.data.get('daily_intake_records', [])
            
            # 筛选今日记录，最多显示 5 条
            today_records = [r for r in records if r.get('date') == today]
            today_records = today_records[-5:]  # 只保留最后 5 条
            
            # 清空并重建可编辑条目引用
            self.editable_entries = {}
            
            # 显示表格内容
            if today_records:
                for idx, record in enumerate(today_records, 1):
                    row_frame = ctk.CTkFrame(table_container, fg_color=COLORS['card_bg'])
                    row_frame.pack(fill=tk.X, pady=1)
                    
                    # 序号
                    ctk.CTkLabel(row_frame, text=str(idx), 
                               text_color=COLORS['text_primary'],
                               width=widths[0]).pack(side=tk.LEFT, padx=1, pady=5)
                    
                    # 时间（带日期）
                    time_str = record.get('time', 'N/A')
                    date_str = record.get('date', today)
                    full_time = f"{date_str} {time_str}"
                    ctk.CTkLabel(row_frame, text=full_time, 
                               text_color=COLORS['text_primary'],
                               width=widths[1],
                               justify=tk.LEFT).pack(side=tk.LEFT, padx=1, pady=5)
                    
                    # 创建编辑区域（包含输入框、确定按钮、删除按钮）
                    edit_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    edit_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    
                    # 蔬菜
                    veg_entry = ctk.CTkEntry(edit_frame, width=70,
                                           fg_color=COLORS['card_bg'],
                                           border_color=COLORS['primary'],
                                           text_color=COLORS['text_primary'])
                    veg_entry.insert(0, str(record.get('vegetables', 0)))
                    veg_entry.pack(side=tk.LEFT, padx=2)
                    
                    # 水果
                    fruit_entry = ctk.CTkEntry(edit_frame, width=70,
                                             fg_color=COLORS['card_bg'],
                                             border_color=COLORS['primary'],
                                             text_color=COLORS['text_primary'])
                    fruit_entry.insert(0, str(record.get('fruits', 0)))
                    fruit_entry.pack(side=tk.LEFT, padx=2)
                    
                    # 肉类
                    meat_entry = ctk.CTkEntry(edit_frame, width=70,
                                            fg_color=COLORS['card_bg'],
                                            border_color=COLORS['primary'],
                                            text_color=COLORS['text_primary'])
                    meat_entry.insert(0, str(record.get('meat', 0)))
                    meat_entry.pack(side=tk.LEFT, padx=2)
                    
                    # 蛋类
                    egg_entry = ctk.CTkEntry(edit_frame, width=70,
                                           fg_color=COLORS['card_bg'],
                                           border_color=COLORS['primary'],
                                           text_color=COLORS['text_primary'])
                    egg_entry.insert(0, str(record.get('eggs', 0)))
                    egg_entry.pack(side=tk.LEFT, padx=2)
                    
                    # 确定按钮
                    confirm_btn = ctk.CTkButton(edit_frame, text="✓ 确定",
                                               width=60, height=28,
                                               fg_color=COLORS['primary'],
                                               hover_color=COLORS['secondary'],
                                               text_color="white",
                                               font=("Arial", 12, "bold"),
                                               command=lambda r=idx-1: self.on_confirm_edit(r))
                    confirm_btn.pack(side=tk.LEFT, padx=5)
                    
                    # 删除按钮
                    delete_btn = ctk.CTkButton(edit_frame, text="🗑️ 删除",
                                              width=70, height=28,
                                              fg_color="#dc3545",
                                              hover_color="#c82333",
                                              text_color="white",
                                              font=("Arial", 12, "bold"),
                                              command=lambda r=idx-1: self.on_delete_record(r))
                    delete_btn.pack(side=tk.LEFT, padx=2)
                    
                    # 存储引用
                    rec_idx = len(today_records) - idx  # 计算在 today_records 中的索引
                    self.editable_entries[rec_idx] = {
                        'vegetables': veg_entry,
                        'fruits': fruit_entry,
                        'meat': meat_entry,
                        'eggs': egg_entry,
                        'status_label': None
                    }
            else:
                # 无数据时显示提示
                no_data_label = ctk.CTkLabel(table_container, 
                                           text="📭 今日暂无摄入记录\n请先保存摄入数据",
                                           text_color=COLORS['text_secondary'],
                                           font=("Arial", 14))
                no_data_label.pack(pady=30)
            
            print(f"  ✓ 表格刷新完成，今日共有 {len(today_records)} 条记录")
        except Exception as e:
            print(f"  ✗ 刷新表格失败：{e}")
    
    def update_people_label(self, value):
        """更新人数标签 / Update People Label"""
        people = int(float(value))
        self.people_label.configure(text=f"{people} {TEXTS['people_label'].split()[0]}")
        # 实时重新计算环保数据（本地公式快速计算）
        self._recalculate_impact()
    
    def update_appetite_label(self, value):
        """更新饭量标签 / Update Appetite Label"""
        appetite = float(value)
        self.appetite_label.configure(text=f"{appetite:.1f}")
        # 实时重新计算环保数据（本地公式快速计算）
        self._recalculate_impact()
    
    def _recalculate_impact(self):
        """重新计算环保数据并更新显示（本地公式快速计算）/ Recalculate Impact using Local Formula"""
        # 修复 BUG：只有在已生成食谱后才允许重新计算
        if not self.generated_menu:
            return
        
        # 读取当前最新的设置值
        people = self.people_var.get()
        appetite = self.appetite_var.get()
            
        # 读取当前食材输入
        custom_ingredients = self.custom_food_entry.get().strip()
        if not custom_ingredients:
            return
            
        ingredients_list = [item.strip() for item in custom_ingredients.split(',') if item.strip()]
        if not ingredients_list:
            return
            
        try:
            # 直接使用本地公式快速估算（实时响应，无延迟）
            impact = self.calculate_impact(ingredients_list, people_num=people, portion_coefficient=appetite)
            self.current_impact = impact
            self.update_impact_display()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def generate_menu(self):
        """生成菜单（异步非阻塞） / Generate Menu"""
        
        try:
            # 读取自定义食材输入
            custom_ingredients = self.custom_food_entry.get().strip()
            
            if not custom_ingredients:
                messagebox.showerror("错误", "请输入至少一种主要食材。")
                return
            
            # 解析食材列表（取消数量限制）
            ingredients_list = [item.strip() for item in custom_ingredients.split(',') if item.strip()]
            
            # 获取其他参数
            people = self.people_var.get()
            meal_type = self.meal_var.get()
            appetite = self.appetite_var.get()
            
            # ========== 立即显示加载提示并启动异步线程 ==========
            # 清空旧的菜单内容
            for widget in self.menu_frame.winfo_children():
                widget.destroy()
            
            # 显示加载提示（在 menu_frame 中显示标签）
            ctk.CTkLabel(self.menu_frame, 
                        text="🤖 AI 正在生成智能食谱，请稍候...\n\n⏳ 生成中，请勿关闭程序", 
                        font=("Arial", 16),
                        text_color=COLORS['primary']).pack(pady=50)
            
            # 禁用生成按钮
            if hasattr(self, 'generate_menu_btn'):
                self.generate_menu_btn.configure(state='disabled', text="⏳ 生成中...")
            
            # 异步调用 AI
            def call_ai_async():
                try:
                    # 计算影响 / Calculate Impact - 使用最新的人数和系数
                    impact = self.calculate_impact(ingredients_list, people_num=people, portion_coefficient=appetite)
                    
                    # 更新累计数据 / Update Cumulative Data
                    self.data['waste_reduced'] += impact['food_waste']
                    self.data['water_saved'] += impact['water']
                    self.data['co2_reduced'] += impact['carbon']
                    save_data(self.data)
                    
                    # 更新首页的环保卡片显示
                    self.update_cumulative_impact()
                    
                    food_str = "、".join(ingredients_list)
                    # 构建 AI 提示词
                    ai_prompt = f"""请根据以下食材生成家庭食谱：
【基本信息】
- 主要食材：{food_str}
- 就餐人数：{people}人
- 饭量系数：{appetite}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入"牛奶、苹果、鸡蛋"→ 做成"牛奶苹果炒鸡蛋"（非常恶心！）
   - ✅ 正确示例：用户输入"牛奶、苹果、鸡蛋"→ 
     * 早餐方案1：牛奶煮鸡蛋 + 餐后吃苹果
     * 早餐方案2：蒸鸡蛋羹 + 温牛奶 + 新鲜苹果切片
     * 早餐方案3：苹果牛奶昔 + 水煮蛋
   
2. **智能判断食材搭配的合理性：**
   - 🥛 饮品/乳制品类（牛奶、豆浆、酸奶等）：通常单独饮用或作为饮品搭配
   - 🍎 水果类（苹果、香蕉、橙子等）：通常生吃、做沙拉、榨汁，很少与肉类同炒
   - 🥚 蛋类：可以炒菜、蒸蛋、煮蛋，但不要与水果混炒
   - 🥩 肉类 + 🥬 蔬菜：经典搭配，可以一起烹饪
   - 🐟 水产 + 🥬 蔬菜：常见搭配
   - 🧀 豆制品 + 🥬 蔬菜：健康搭配
   
3. **灵活的菜品组织方式：**
   - 如果食材适合分开食用，就设计成多道独立的菜品/饮品
   - 例如："牛奶、苹果、鸡蛋"可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者："番茄、鸡蛋、面包"可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是"主食 + 饮品 + 水果"的组合
   - 午餐/晚餐：可以是"主菜 + 配菜 + 汤"的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

2. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（要体现"家常"特色）
   【食材类别】xxx（如：肉类 + 蔬菜类、蛋类 + 豆制品等）
   【用料清单】
   - 主料 1: xxx 克（精准计算，考虑人数和饭量系数）
   - 主料 2: xxx 克
   - 辅料：适量
   【制作步骤】
   步骤 1: xxx
   步骤 2: xxx
   步骤 3: xxx
   步骤 4: xxx
   步骤 5: xxx
   【环保价值】
   - 预计减少食物浪费：xxx 克
   - 预计节约水资源：xxx 升
   - 预计减少碳排放：xxx 克
   - 环保说明：xxx

【通用要求】
1. 识别每种食材的类别（肉类/蔬菜/蛋类/水产/豆制品等）并给予专属烹饪建议
2. 精准计算每种食材的用量（克数），考虑人数和饭量系数
3. 制作步骤详细清晰（至少 5 步）
4. **重点：为每个菜品计算环保价值数据**
   - 减少食物浪费（克）：基于传统做法会多准备 25% 的食物
   - 节约水资源（升）：每克食物约消耗 0.5 升水（中国膳食加权平均）
   - 减少碳排放（克 CO2e）：每克食物约排放 0.003 克 CO2e（中国膳食混合平均）

【返回格式示例】
如果生成多个菜品，请按以下格式依次列出：

=== 菜品 1 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 【用户输入】主料 1: xxx 克
- 【冰箱库存】辅料：xxx 克（如果有使用）
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

（如有更多菜品，继续按此格式列出）"""
                    
                    # 调用智能 API（自动选择最佳可用 API）
                    api_result = call_ai_api(ai_prompt, api_type="auto")
                    
                    use_ai_recipe = False
                    recipe = None
                    
                    if api_result['success']:
                        try:
                            # 检查 AI 返回的内容是否有效
                            ai_content = api_result['content']
                            if ai_content and len(ai_content.strip()) > 50:
                                # 使用 AI 生成的食谱
                                recipe = ai_content
                                use_ai_recipe = True
                                
                                # 尝试从 AI 返回内容中提取环保数据（覆盖本地计算结果）
                                try:
                                    import re
                                    # 提取减少浪费
                                    waste_match = re.search(r'减少食物浪费 [:：]\s*(\d+(?:\.\d+)?)\s* 克', ai_content)
                                    if waste_match:
                                        impact['food_waste'] = float(waste_match.group(1))
                                                            
                                    # 提取节约水
                                    water_match = re.search(r'节约水资源 [:：]\s*(\d+(?:\.\d+)?)\s* 升', ai_content)
                                    if water_match:
                                        impact['water'] = float(water_match.group(1))
                                                            
                                    # 提取减少碳排放
                                    carbon_match = re.search(r'减少碳排放 [:：]\s*(\d+(?:\.\d+)?)\s* 克', ai_content)
                                    if carbon_match:
                                        impact['carbon'] = float(carbon_match.group(1))
                                                            
                                    # 更新为 AI 计算的精准数据
                                except Exception as e:
                                    pass
                            else:
                                pass
                        except Exception as e:
                            pass
                    
                    if not use_ai_recipe:
                        # 使用本地保底方案
                        recipe = f"【{food_str}家常环保食谱】\n\n"
                        recipe += "▪️ 用料清单：\n"
                        for food in ingredients_list:
                            recipe += f"- {food}: 300g\n"
                        recipe += "- 葱姜蒜：适量\n- 油盐酱醋：家用基础量\n\n"
                        recipe += "▪️ 制作步骤：\n"
                        recipe += "1. 所有食材清洗干净，改刀处理成适合入口的大小\n"
                        recipe += "2. 锅中倒油，油热后下葱姜蒜爆香，放入主料翻炒至断生\n"
                        recipe += "3. 加入适量盐、生抽调味，翻炒均匀\n"
                        recipe += "4. 加少量清水焖煮 1-2 分钟，确保食材熟透入味\n"
                        recipe += "5. 大火收浓汤汁，即可出锅装盘\n"
                    
                    # 使用 after 方法在主线程更新 UI
                    def update_ui():
                        # 保存生成的食谱数据
                        self.generated_menu = {
                            'people': people,
                            'meal_type': TEXTS[f'meal_{meal_type}'],
                            'ingredients': ingredients_list,
                            'portions': {ing: BASE_PORTIONS.get(INGREDIENT_MAP.get(ing, ing.lower()), 100) * people * MEAL_MULTIPLIERS[meal_type] * appetite 
                                        for ing in ingredients_list},
                            'menu': {},
                            'is_ai_recipe': use_ai_recipe  # 标记是否为 AI 生成的食谱
                        }
                        self.current_impact = impact
                        
                        # 更新显示 / Update Display
                        self.update_impact_display()
                        self.update_menu_display()
                        
                        # 恢复按钮状态
                        if hasattr(self, 'generate_menu_btn'):
                            self.generate_menu_btn.configure(state='normal', text="🍽️ 生成菜单")
                    
                    self.after(0, update_ui)
                except Exception as e:
                    error_msg = str(e)  # 先保存错误消息，避免作用域问题
                    def show_error():
                        if hasattr(self, 'menu_output'):
                            self.menu_output.delete(1.0, tk.END)
                            self.menu_output.insert(tk.END, f"❌ 生成菜单失败：{error_msg}\n\n请检查网络连接或稍后重试。")
                        if hasattr(self, 'generate_menu_btn'):
                            self.generate_menu_btn.configure(state='normal', text="🍽️ 生成菜单")
                    
                    self.after(0, show_error)
            
            # 启动异步线程
            thread = threading.Thread(target=call_ai_async)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"生成菜单时出错：{e}")

    def ai_generate_menu(self):
        """AI 生成食谱（异步非阻塞版本）/ AI Generate Menu (Async Non-blocking)"""
        # ========== 界面控件真实变量名 ==========
        INPUT_BOX_NAME = "custom_food_entry"
        # 注意：输出区域是 menu_frame，我们在其中动态创建文本框
        OUTPUT_CONTAINER = "menu_frame"
        # ========================================

        # 1. 读取用户输入，全异常兜底
        try:
            input_box = getattr(self, INPUT_BOX_NAME)
            user_input = input_box.get().strip()
            
        except AttributeError as e:
            messagebox.showerror("错误", f"找不到输入框！请检查变量名：{INPUT_BOX_NAME}")
            return
        except Exception as e:
            messagebox.showerror("错误", f"读取输入失败：{e}")
            return

        # 输入内容校验
        if not user_input:
            messagebox.showerror("提示", "请输入食材后再生成")
            return
        food_list = [food.strip() for food in user_input.split(",") if food.strip()]
        
        food_str = "、".join(food_list)
        
        # 获取其他参数
        current_people = self.people_var.get()
        current_appetite = self.appetite_var.get()
        use_fridge = self.use_fridge_var.get()

        # ========== 立即显示加载提示并清空旧内容 ==========
        # 清空旧的菜单内容
        output_container = getattr(self, OUTPUT_CONTAINER)
        for widget in output_container.winfo_children():
            widget.destroy()
        
        # 显示加载提示
        ctk.CTkLabel(output_container, 
                    text="🤖 AI 正在生成智能食谱，请稍候...\n\n⏳ 生成中，请勿关闭程序", 
                    font=("Arial", 16),
                    text_color=COLORS['primary']).pack(pady=50)
        
        # 禁用生成按钮（需要查找按钮）
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "AI 生成环保食谱":
                widget.configure(state='disabled', text="⏳ 生成中...")
                break
        
        # ========== 异步调用 AI ==========
        def call_ai_async():
            try:
                # 2. 环保数据计算
                reduce_waste = 0
                save_water = 0
                reduce_carbon = 0
                
                # 获取主窗口
                main_window = self
                if not hasattr(main_window, 'calculate_impact'):
                    main_window = self.winfo_toplevel()
                if not hasattr(main_window, 'calculate_impact'):
                    main_window = self.master

                has_calc_func = hasattr(main_window, 'calculate_impact')
                has_update_func = hasattr(main_window, 'update_impact_display')
                
                # 计算并更新环保数据
                if has_calc_func:
                    main_window.current_impact = main_window.calculate_impact(food_list, people_num=current_people, portion_coefficient=current_appetite)
                    reduce_waste = round(main_window.current_impact.get('food_waste', 0), 2)
                    save_water = round(main_window.current_impact.get('water', 0), 2)
                    reduce_carbon = round(main_window.current_impact.get('carbon', 0), 2)
                
                # ==================== 【核心功能】AI API 智能食谱生成 开始 ====================
                # 检查是否使用冰箱食材
                fridge_items = self.data.get('fridge_inventory', []) if use_fridge else []
                
                # 构建 AI 提示词
                if use_fridge and fridge_items:
                    fridge_item_names = [item['name'] for item in fridge_items]
                    fridge_str = "、".join(fridge_item_names)
                    ai_prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{food_str}
- 冰箱现有食材：{fridge_str}
- 就餐人数：{current_people}人
- 饭量系数：{current_appetite}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入"牛奶、苹果、鸡蛋"→ 做成"牛奶苹果炒鸡蛋"（非常恶心！）
   - ✅ 正确示例：用户输入"牛奶、苹果、鸡蛋"→ 
     * 早餐方案1：牛奶煮鸡蛋 + 餐后吃苹果
     * 早餐方案2：蒸鸡蛋羹 + 温牛奶 + 新鲜苹果切片
     * 早餐方案3：苹果牛奶昔 + 水煮蛋
   
2. **智能判断食材搭配的合理性：**
   - 🥛 饮品/乳制品类（牛奶、豆浆、酸奶等）：通常单独饮用或作为饮品搭配
   - 🍎 水果类（苹果、香蕉、橙子等）：通常生吃、做沙拉、榨汁，很少与肉类同炒
   - 🥚 蛋类：可以炒菜、蒸蛋、煮蛋，但不要与水果混炒
   - 🥩 肉类 + 🥬 蔬菜：经典搭配，可以一起烹饪
   - 🐟 水产 + 🥬 蔬菜：常见搭配
   - 🧀 豆制品 + 🥬 蔬菜：健康搭配
   
3. **灵活的菜品组织方式：**
   - 如果食材适合分开食用，就设计成多道独立的菜品/饮品
   - 例如："牛奶、苹果、鸡蛋"可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者："番茄、鸡蛋、面包"可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是"主食 + 饮品 + 水果"的组合
   - 午餐/晚餐：可以是"主菜 + 配菜 + 汤"的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **优先使用用户输入的食材**：
   - ⭐ 用户输入的食材（{food_str}）必须作为主料
   - 🧊 冰箱食材（{fridge_str}）可以作为搭配或辅料
   - ✅ 每个菜品都必须标注哪些是【用户输入】的食材，哪些是【冰箱库存】的食材

2. **标注格式要求**：
   在每个菜品的【用料清单】中，必须这样标注：
   - 【用户输入】主料 1: xxx 克
   - 【冰箱库存】辅料：xxx 克
   
3. **如果用户输入的食材较少**：
   - 可以合理搭配冰箱中的常见食材
   - 但必须明确标注来源

4. **如果用户输入的食材较多**：
   - 优先使用用户输入的食材
   - 冰箱食材作为辅助调味或配菜

5. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

6. **优先使用用户输入的食材作为主料**：
   - ⭐ **第一优先级**：用户输入的食材必须作为每个菜品的**主料**（主要食材）
   - ⭐ **第二优先级**：其他辅料（葱姜蒜、调味料、配菜等）仅作为辅助，不要喧宾夺主
   - ✅ 正确示例：用户输入"土豆、牛肉"→ "土豆炖牛肉"（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入"土豆、牛肉"→ "青椒土豆丝"（青椒不是用户输入的，却成了主料）
   - 如果确实需要搭配其他食材，应该明确标注哪些是"主料"（用户输入的），哪些是"辅料"（额外搭配的）
   - 搭配的其他食材应该是常见的调味品或辅料（如葱姜蒜、酱油、盐等），而不是新的主菜食材

3. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把"土豆、萝卜、冬瓜、南瓜"全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例："土豆炖牛肉"（土豆 + 肉类）、"清炒萝卜丝"（单独蔬菜）、"南瓜炒蛋"（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡
   - 如果同类型食材过多（如 3 种蔬菜），应该分成不同的菜品，不要全部堆在一起

4. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（要体现"家常"特色）
   【食材类别】xxx（如：肉类 + 蔬菜类、蛋类 + 豆制品等）
   【用料清单】
   - 主料 1: xxx 克（精准计算，考虑人数和饭量系数）
   - 主料 2: xxx 克
   - 辅料：适量
   【制作步骤】
   步骤 1: xxx
   步骤 2: xxx
   步骤 3: xxx
   步骤 4: xxx
   步骤 5: xxx
   【环保价值】
   - 预计减少食物浪费：xxx 克
   - 预计节约水资源：xxx 升
   - 预计减少碳排放：xxx 克
   - 环保说明：xxx

【通用要求】
1. 识别每种食材的类别（肉类/蔬菜/蛋类/水产/豆制品等）并给予专属烹饪建议
2. 精准计算每种食材的用量（克数），考虑人数和饭量系数
3. 制作步骤详细清晰（至少 5 步）
4. **重点：为每个菜品计算环保价值数据**
   - 减少食物浪费（克）：基于传统做法会多准备 25% 的食物
   - 节约水资源（升）：每克食物约消耗 0.5 升水（中国膳食加权平均）
   - 减少碳排放（克 CO2e）：每克食物约排放 0.003 克 CO2e（中国膳食混合平均）

【返回格式示例】
如果生成多个菜品，请按以下格式依次列出：

=== 菜品 1 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 【用户输入】主料 1: xxx 克
- 【冰箱库存】辅料：xxx 克（如果有使用）
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

=== 菜品 2 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 【用户输入】主料 1: xxx 克
- 【冰箱库存】辅料：xxx 克（如果有使用）
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

（如有更多菜品，继续按此格式列出）"""
                else:
                    # 不使用冰箱食材，使用普通提示词
                    ai_prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{food_str}
- 就餐人数：{current_people}人
- 饭量系数：{current_appetite}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入"牛奶、苹果、鸡蛋"→ 做成"牛奶苹果炒鸡蛋"（非常恶心！）
   - ✅ 正确示例：用户输入"牛奶、苹果、鸡蛋"→ 
     * 早餐方案1：牛奶煮鸡蛋 + 餐后吃苹果
     * 早餐方案2：蒸鸡蛋羹 + 温牛奶 + 新鲜苹果切片
     * 早餐方案3：苹果牛奶昔 + 水煮蛋
   
2. **智能判断食材搭配的合理性：**
   - 🥛 饮品/乳制品类（牛奶、豆浆、酸奶等）：通常单独饮用或作为饮品搭配
   - 🍎 水果类（苹果、香蕉、橙子等）：通常生吃、做沙拉、榨汁，很少与肉类同炒
   - 🥚 蛋类：可以炒菜、蒸蛋、煮蛋，但不要与水果混炒
   - 🥩 肉类 + 🥬 蔬菜：经典搭配，可以一起烹饪
   - 🐟 水产 + 🥬 蔬菜：常见搭配
   - 🧀 豆制品 + 🥬 蔬菜：健康搭配
   
3. **灵活的菜品组织方式：**
   - 如果食材适合分开食用，就设计成多道独立的菜品/饮品
   - 例如："牛奶、苹果、鸡蛋"可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者："番茄、鸡蛋、面包"可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是"主食 + 饮品 + 水果"的组合
   - 午餐/晚餐：可以是"主菜 + 配菜 + 汤"的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

2. **优先使用用户输入的食材作为主料**：
   - ⭐ **第一优先级**：用户输入的食材必须作为每个菜品的**主料**（主要食材）
   - ⭐ **第二优先级**：其他辅料（葱姜蒜、调味料、配菜等）仅作为辅助，不要喧宾夺主
   - ✅ 正确示例：用户输入"土豆、牛肉"→ "土豆炖牛肉"（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入"土豆、牛肉"→ "青椒土豆丝"（青椒不是用户输入的，却成了主料）

3. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把"土豆、萝卜、冬瓜、南瓜"全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例："土豆炖牛肉"（土豆 + 肉类）、"清炒萝卜丝"（单独蔬菜）、"南瓜炒蛋"（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡
   - 如果同类型食材过多（如 3 种蔬菜），应该分成不同的菜品，不要全部堆在一起

4. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（要体现"家常"特色）
   【食材类别】xxx（如：肉类 + 蔬菜类、蛋类 + 豆制品等）
   【用料清单】
   - 主料 1: xxx 克（精准计算，考虑人数和饭量系数）
   - 主料 2: xxx 克
   - 辅料：适量
   【制作步骤】
   步骤 1: xxx
   步骤 2: xxx
   步骤 3: xxx
   步骤 4: xxx
   步骤 5: xxx
   【环保价值】
   - 预计减少食物浪费：xxx 克
   - 预计节约水资源：xxx 升
   - 预计减少碳排放：xxx 克
   - 环保说明：xxx

【通用要求】
1. 识别每种食材的类别（肉类/蔬菜/蛋类/水产/豆制品等）并给予专属烹饪建议
2. 精准计算每种食材的用量（克数），考虑人数和饭量系数
3. 制作步骤详细清晰（至少 5 步）
4. **重点：为每个菜品计算环保价值数据**
   - 减少食物浪费（克）：基于传统做法会多准备 25% 的食物
   - 节约水资源（升）：每克食物约消耗 0.5 升水（中国膳食加权平均）
   - 减少碳排放（克 CO2e）：每克食物约排放 0.003 克 CO2e（中国膳食混合平均）

【返回格式示例】
如果生成多个菜品，请按以下格式依次列出：

=== 菜品 1 ===
【菜名】xxx
【食材类别】xxx
【用料清单】
- 主料 1: xxx 克
- 主料 2: xxx 克
- 辅料：适量
【制作步骤】
步骤 1: xxx
步骤 2: xxx
步骤 3: xxx
步骤 4: xxx
步骤 5: xxx
【环保价值】
- 预计减少食物浪费：xxx 克
- 预计节约水资源：xxx 升
- 预计减少碳排放：xxx 克
- 环保说明：xxx

（如有更多菜品，继续按此格式列出）"""
                
                # 调用智能 API（自动选择最佳可用 API）
                api_result = call_ai_api(ai_prompt, api_type="auto")
                
                use_ai_recipe = False
                recipe = None
                
                if api_result['success']:
                    try:
                        ai_content = api_result['content']
                        if ai_content and len(ai_content.strip()) > 50:
                            recipe = ai_content
                            use_ai_recipe = True
                            
                            # 尝试从 AI 返回内容中提取环保数据
                            try:
                                import re
                                waste_match = re.search(r'减少食物浪费 [:：]\s*(\d+(?:\.\d+)?)\s* 克', ai_content)
                                if waste_match:
                                    reduce_waste = float(waste_match.group(1))
                                water_match = re.search(r'节约水资源 [:：]\s*(\d+(?:\.\d+)?)\s* 升', ai_content)
                                if water_match:
                                    save_water = float(water_match.group(1))
                                carbon_match = re.search(r'减少碳排放 [:：]\s*(\d+(?:\.\d+)?)\s* 克', ai_content)
                                if carbon_match:
                                    reduce_carbon = float(carbon_match.group(1))
                                
                                main_window.current_impact = {
                                    'food_waste': reduce_waste,
                                    'water': save_water,
                                    'carbon': reduce_carbon
                                }
                            except Exception as e:
                                pass
                    except Exception as e:
                        pass
                
                if not use_ai_recipe:
                    # 使用本地保底方案
                    recipe = f"【{food_str}家常防浪费食谱】\n\n"
                    recipe += "▪️ 菜品名称：家常" + food_str + "\n\n"
                    recipe += "▪️ 本次环保价值（基于精准计算）：\n"
                    recipe += f"- 预计减少食物浪费：{reduce_waste}克\n"
                    recipe += f"- 预计节约水资源：{save_water}升\n"
                    recipe += f"- 预计减少碳排放：{reduce_carbon}克\n\n"
                    recipe += "▪️ 精准用料清单：\n"
                    for food in food_list:
                        recipe += f"- {food}: 300g\n"
                    recipe += "- 葱姜蒜：适量\n"
                    recipe += "▪️ 详细制作步骤：\n"
                    recipe += "1. 所有食材清洗干净，改刀处理\n"
                    recipe += "2. 锅中倒油，油热后下葱姜蒜爆香\n"
                    recipe += "3. 放入食材翻炒至断生，加调料\n"
                    recipe += "4. 加少量清水焖煮 1-2 分钟\n"
                    recipe += "5. 大火收浓汤汁，即可出锅\n"
                
                # 使用 after 在主线程更新 UI
                def update_ui():
                    # 清空容器内所有现有内容
                    output_container = getattr(self, OUTPUT_CONTAINER)
                    for widget in output_container.winfo_children():
                        widget.destroy()
                    
                    # 创建结果展示框架
                    result_frame = ctk.CTkFrame(output_container, fg_color=COLORS['card_bg'],
                                               corner_radius=15)
                    result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                    
                    # 创建可滚动文本框显示食谱
                    result_text = tk.Text(result_frame, wrap=tk.WORD, height=30, 
                                        bg=COLORS['card_bg'], fg=COLORS['text_primary'],
                                        font=("Arial", 20))
                    result_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
                    result_text.insert(tk.END, recipe)
                    result_text.config(state=tk.DISABLED)
                    
                    # 保存生成的食谱数据
                    self.generated_menu = {
                        'people': current_people,
                        'meal_type': TEXTS[f'meal_{self.meal_var.get()}'],
                        'ingredients': food_list,
                        'portions': {ing: BASE_PORTIONS.get(INGREDIENT_MAP.get(ing, ing.lower()), 100) * current_people * MEAL_MULTIPLIERS[self.meal_var.get()] * current_appetite 
                                    for ing in food_list},
                        'menu': {},
                        'is_ai_recipe': use_ai_recipe
                    }
                    
                    # 更新首页累计数据
                    if hasattr(main_window, 'current_impact') and main_window.current_impact:
                        try:
                            current_waste = float(self.data.get('waste_reduced', 0))
                            current_water = float(self.data.get('water_saved', 0))
                            current_carbon = float(self.data.get('co2_reduced', 0))
                            
                            new_waste = current_waste + main_window.current_impact['food_waste']
                            new_water = current_water + main_window.current_impact['water']
                            new_carbon = current_carbon + main_window.current_impact['carbon']
                            
                            self.data['waste_reduced'] = round(new_waste, 2)
                            self.data['water_saved'] = round(new_water, 2)
                            self.data['co2_reduced'] = round(new_carbon, 2)
                            
                            save_data(self.data)
                            
                            if hasattr(self, 'cumulative_frame'):
                                self.update_cumulative_impact()
                        except Exception as e:
                            pass
                    
                    # 恢复按钮状态
                    for widget in self.winfo_children():
                        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "AI 生成环保食谱":
                            widget.configure(state='normal', text="AI 生成环保食谱")
                            break
                    
                    # 计数器 +1
                    self.recipe_generation_count += 1
                    print(f"\n📊 智能食谱已生成 {self.recipe_generation_count} 次")
                    
                    # 自动录入摄入数据
                    self.auto_extract_and_save_intake_from_recipe()
                
                self.after(0, update_ui)
                
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    output_container = getattr(self, OUTPUT_CONTAINER)
                    for widget in output_container.winfo_children():
                        widget.destroy()
                    ctk.CTkLabel(output_container, 
                                text=f"❌ 生成失败：{error_msg}\n\n请检查网络连接或稍后重试。", 
                                font=("Arial", 16),
                                text_color="red").pack(pady=50)
                    
                    for widget in self.winfo_children():
                        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == "AI 生成环保食谱":
                            widget.configure(state='normal', text="AI 生成环保食谱")
                            break
                    
                    self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()
    
    def auto_extract_and_save_intake_from_recipe(self):
        """从智能食谱中自动提取并保存摄入数据（第 3 次生成时触发）"""
        try:
            print("\n========== 开始自动录入摄入数据 ==========")
            
            # 获取用户输入的食材
            user_input = self.custom_food_entry.get().strip()
            if not user_input:
                print("⚠️ 用户未输入食材，跳过录入")
                return
            
            food_list = [food.strip() for food in user_input.split(",") if food.strip()]
            print(f"📝 识别到食材：{food_list}")
            
            # 分类统计食材
            vegetables = 0
            fruits = 0
            meat = 0
            eggs = 0
            
            # 关键词匹配分类（注意：先判断蛋类，再判断肉类，因为"鸡蛋"含"鸡"字）
            if not user_input:
                print("⚠️ 用户未输入食材，跳过录入")
                return
            
            food_list = [food.strip() for food in user_input.split(",") if food.strip()]
            print(f"📝 识别到食材：{food_list}")
            
            # 分类统计食材
            vegetables = 0
            fruits = 0
            meat = 0
            eggs = 0
            
            # 关键词匹配分类（注意：先判断蛋类，再判断肉类，因为"鸡蛋"含"鸡"字）
            for food in food_list:
                # 蔬菜类
                if any(kw in food for kw in ["菜", "萝卜", "瓜", "笋", "菇", "豆", "葱", "蒜", "姜", "辣椒"]):
                    vegetables += 200
                    print(f"  🥬 {food} → 蔬菜 +200g (累计：{vegetables}g)")
                # 水果类（如果有）
                elif any(kw in food for kw in ["苹果", "香蕉", "梨", "桃", "葡萄", "橙", "柚"]):
                    fruits += 150
                    print(f"  🍎 {food} → 水果 +150g (累计：{fruits}g)")
                # 蛋类（优先判断，避免被误判为肉类）
                elif "蛋" in food:
                    eggs += 50
                    print(f"  🥚 {food} → 蛋类 +50g (累计：{eggs}g)")
                # 肉类（注意："鸡蛋"会被上面的"蛋"字捕获，不会到这里）
                elif any(kw in food for kw in ["猪", "牛", "羊", "鸡", "鸭", "鱼", "虾", "肉"]):
                    meat += 150
                    print(f"  🥩 {food} → 肉类 +150g (累计：{meat}g)")
            
            # 如果没有检测到任何食材，使用默认值
            if vegetables == 0 and fruits == 0 and meat == 0 and eggs == 0:
                # 不自动添加默认值，避免用户没有蔬菜却自动添加
                print(f"  ⚠️ 未识别到具体食材，将保留空值")
                # vegetables = 300
                # meat = 150
            
            print(f"\n📊 最终统计结果:")
            print(f"   蔬菜：{vegetables}g | 水果：{fruits}g | 肉类：{meat}g | 蛋类：{eggs}g")
            
            # 构建摄入记录（每次都创建新记录，不累加）
            today = datetime.now().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M')
            intake_record = {
                'date': today,
                'time': now_time,  # 添加时间戳
                'vegetables': vegetables,
                'fruits': fruits,
                'meat': meat,
                'eggs': eggs
            }
            
            # 保存到数据文件（每次都追加新记录）
            if 'daily_intake_records' not in self.data:
                self.data['daily_intake_records'] = []
                print(f"  ✅ 创建新的摄入记录数组")
            
            # 直接追加新记录（不检查是否已存在）
            self.data['daily_intake_records'].append(intake_record)
            print(f"  ✅ 添加新记录到数组：{intake_record}")
            
            # 保存到文件
            save_data(self.data)
            print(f"  ✅ 数据已保存到 fgai_local_data.json")
            
            # 提示成功（显示实际次数）
            msg = f"✅ 智能食谱生成第 {self.recipe_generation_count} 次，系统自动录入今日摄入数据：\n\n"
            msg += f"🥬 蔬菜：+{vegetables}g\n"
            msg += f"🍎 水果：+{fruits}g\n"
            msg += f"🥩 肉类：+{meat}g\n"
            msg += f"🥚 蛋类：+{eggs}g\n\n"
            msg += f"数据已自动保存到历史记录！"
            
            # 第 1、2 次生成时不弹出提示框，只在第 3 次才提示
            if self.recipe_generation_count < 3:
                print(f"📝 第{self.recipe_generation_count}次食谱生成，仅录入数据，暂不评估")
            else:
                messagebox.showinfo("📊 自动录入成功", msg)
            
            # ========== 关键修复：确保刷新生效 ==========
            print(f"\n🔄 准备刷新界面显示...")
            
            # 1. 刷新历史表格（立即刷新）
            if hasattr(self, 'refresh_history_table'):
                print(f"  ✓ 调用 refresh_history_table()")
                self.refresh_history_table()  # 直接调用，不延迟
            else:
                print(f"  ✗ 找不到 refresh_history_table 函数")
            
            # 2. 更新今日摄入记录的输入框显示（显示今日总摄入量）
            if hasattr(self, 'vegetables_entry') and hasattr(self, 'fruits_entry') and hasattr(self, 'meat_entry') and hasattr(self, 'eggs_entry'):
                print(f"  ✓ 更新今日摄入输入框显示")
                
                # 获取今日所有记录并计算总量
                today = datetime.now().strftime('%Y-%m-%d')
                all_records = self.data.get('daily_intake_records', [])
                today_records = [r for r in all_records if r.get('date') == today]
                
                if today_records:
                    # 计算今日总摄入
                    total_vegetables = sum(r.get('vegetables', 0) for r in today_records)
                    total_fruits = sum(r.get('fruits', 0) for r in today_records)
                    total_meat = sum(r.get('meat', 0) for r in today_records)
                    total_eggs = sum(r.get('eggs', 0) for r in today_records)
                    
                    print(f"  📊 今日总摄入：蔬菜{total_vegetables}g, 水果{total_fruits}g, 肉类{total_meat}g, 蛋类{total_eggs}g (共{len(today_records)}条记录)")
                    
                    # 清空并填入总量值
                    self.vegetables_entry.delete(0, tk.END)
                    self.vegetables_entry.insert(0, str(total_vegetables))
                    
                    self.fruits_entry.delete(0, tk.END)
                    self.fruits_entry.insert(0, str(total_fruits))
                    
                    self.meat_entry.delete(0, tk.END)
                    self.meat_entry.insert(0, str(total_meat))
                    
                    self.eggs_entry.delete(0, tk.END)
                    self.eggs_entry.insert(0, str(total_eggs))
                    
                    print(f"  ✅ 今日摄入输入框已更新为总量")
                else:
                    print(f"  ⚠️ 今日暂无记录")
            else:
                print(f"  ✗ 找不到摄入输入框控件")
            
            # 3. 检查营养状况并自动生成解决方案（只在第 3 次生成时才评估）
            if self.recipe_generation_count >= 3 and hasattr(self, 'check_and_auto_recommend'):
                print(f"  ✓ 已生成{self.recipe_generation_count}次，调用 check_and_auto_recommend() 整合评估")
                self.after(1000, lambda: self.check_and_auto_recommend())
            else:
                print(f"  ℹ️ 第{self.recipe_generation_count}次生成，暂不评估")
            
            print(f"\n========== 自动录入完成 ==========")
        
        except Exception as e:
            import traceback
            print(f"\n❌ 自动录入摄入数据失败：{e}")
            print(traceback.format_exc())
    
    def update_impact_display(self):
        """更新影响显示 / Update Impact Display"""
        # 先清空现有的内容
        for widget in self.impact_frame.winfo_children():
            widget.destroy()
        
        if not self.current_impact:
            # 如果没有环保数据，隐藏 impact_frame，不占用空间
            self.impact_frame.pack_forget()
            return
        
        # 如果有数据，显示 impact_frame（使用 pack_once 避免重复 pack）
        # 检查是否已经 pack 过
        if not self.impact_frame.winfo_ismapped():
            self.impact_frame.pack(fill=tk.X, pady=(0, 10), before=self.menu_frame)
        
        # 标题（小字体）
        ctk.CTkLabel(self.impact_frame, text="🌱 本次环保贡献", 
                    font=("Arial", 16, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 5))
        
        impact = self.current_impact
        impact_metrics = [
            (TEXTS['waste_this'], round(impact['food_waste'], 2), TEXTS['unit_g']),
            (TEXTS['water_this'], round(impact['water'], 2), TEXTS['unit_l']),
            (TEXTS['co2_this'], round(impact['carbon'], 2), TEXTS['unit_g'])
        ]
        
        # 橙色背景卡片，白色文字（紧凑版）
        metrics_frame = ctk.CTkFrame(self.impact_frame, fg_color="transparent")
        metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        for i, (name, value, unit) in enumerate(impact_metrics):
            # 小型橙色卡片，白色文字
            card_frame = ctk.CTkFrame(metrics_frame, 
                                     fg_color=COLORS['primary'],
                                     corner_radius=8,
                                     width=180,
                                     height=80)
            card_frame.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.BOTH)
            card_frame.pack_propagate(False)
            
            # 数值（中等字体）
            ctk.CTkLabel(card_frame, text=f"{value} {unit}", 
                        font=("Arial", 18, "bold"),
                        text_color="white").pack(pady=(10, 2))
            
            # 名称（小字体）
            ctk.CTkLabel(card_frame, text=name, 
                        text_color="white",
                        font=("Arial", 10)).pack(pady=(0, 8))
        
        ctk.CTkLabel(self.impact_frame, text=TEXTS['goal'], 
                    text_color=COLORS['text_secondary']).pack(pady=(0, 20))
    
    def update_menu_display(self):
        """更新菜单显示 / Update Menu Display"""
        # 清空现有的菜单内容
        for widget in self.menu_frame.winfo_children():
            widget.destroy()
        
        if not self.generated_menu:
            ctk.CTkLabel(self.menu_frame, text=TEXTS['menu_placeholder'], 
                        text_color=COLORS['text_secondary'],
                        font=("Arial", 14)).pack(pady=20)
            return
        
        menu_data = self.generated_menu
        
        # 菜单信息 / Menu Info - 放大字体
        info_text = TEXTS['menu_info'].format(menu_data['people'], menu_data['meal_type'], ', '.join(menu_data['ingredients']))
        ctk.CTkLabel(self.menu_frame, text=info_text, 
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 14)).pack(pady=(0, 15))
        
        # 份量 / Portions - 放大字体
        for ing, portion in menu_data['portions'].items():
            portion_text = TEXTS['portion'].format(ing, round(portion, 2))
            ctk.CTkLabel(self.menu_frame, text=portion_text, 
                        text_color=COLORS['text_primary'],
                        font=("Arial", 14)).pack(anchor=tk.W, pady=(3, 0))
        
        # 菜品 / Dishes - 放大字体
        ctk.CTkLabel(self.menu_frame, text=TEXTS['dishes'], 
                    font=("Arial", 18, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(25, 15))
        
        for dish, steps in menu_data['menu'].items():
            dish_frame = ctk.CTkFrame(self.menu_frame, fg_color=COLORS['card_bg'],
                                     corner_radius=10)
            dish_frame.pack(fill=tk.X, pady=(0, 15))
            
            ctk.CTkLabel(dish_frame, text=dish, 
                        font=("Arial", 18, "bold"),
                        text_color=COLORS['text_primary']).pack(pady=(15, 10))
            ctk.CTkLabel(dish_frame, text=TEXTS['steps'], 
                        font=("Arial", 15, "bold"),
                        text_color=COLORS['text_primary']).pack(anchor=tk.W, pady=(0, 10))
            
            for step in steps:
                ctk.CTkLabel(dish_frame, text=step, 
                            text_color=COLORS['text_primary'],
                            font=("Arial", 14)).pack(anchor=tk.W, pady=(3, 0))
        
        # 提示 / Tip - 放大字体
        tip = TEXTS['tip_reduce'] if len(menu_data['ingredients']) >= 3 else TEXTS['tip_add']
        ctk.CTkLabel(self.menu_frame, text=tip, 
                    text_color=COLORS['tertiary'],
                    font=("Arial", 13)).pack(pady=(15, 25))
    
    def ai_generate_scrap(self):
        """异步生成边角料环保处理方案"""
        custom_scrap = self.custom_scrap_entry.get().strip()
        if not custom_scrap:
            messagebox.showerror("错误", TEXTS['empty_scrap'])
            return
                    
        # 解析边角料列表（取消数量限制）
        scrap_list = [item.strip() for item in custom_scrap.split(',') if item.strip()]
        
        # 显示加载提示
        if hasattr(self, 'scrap_output'):
            self.scrap_output.delete(1.0, tk.END)
            self.scrap_output.insert(tk.END, "🤖 AI 正在生成环保处理方案，请稍候...\n\n")
        
        # 异步调用 AI
        def call_ai_async():
            try:
                scrap_str = "、".join(scrap_list)
                
                # 构建 AI 提示词
                ai_prompt = f"""请为以下厨余边角料提供环保再利用方案：
【边角料食材】{scrap_str}

【要求】
1. **完全不涉及食用**，所有方案均为非食用的环保处理方式
2. 提供 2 套方案：
   - 方案 1：简易家用环保处理（零门槛，当天可完成，适合新手）
   - 方案 2：进阶长效环保利用（可持续使用，环保价值更高）
3. 每套方案必须包含：
   - 核心用途（一句话概括）
   - 所需材料清单（精确到用量）
   - 详细操作步骤（至少 5 步）
   - 环保意义说明
4. 根据边角料类型智能匹配最佳处理方案：
   - 果蔬皮类 → 堆肥、清洁剂、除味剂等
   - 柑橘皮类 → 天然清洁剂、驱虫剂、香薰等
   - 骨头类 → 天然肥料、钙粉等
   - 剩饭剩菜 → 发酵营养水、蚯蚓堆肥等

【返回格式示例】
【{scrap_str}零浪费环保再利用方案】

本方案均为家庭可轻松操作的环保处理方式，实现厨余废弃物资源化，减少垃圾排放，助力自然生态循环

▪️ 方案 1：简易家用环保处理（零门槛，当天可完成）
核心用途：xxx
所需材料：
- 材料 1: xxx
- 材料 2: xxx
操作步骤：
1. xxx
2. xxx
3. xxx
4. xxx
5. xxx
环保意义：xxx

▪️ 方案 2：进阶长效环保利用（可持续使用，环保价值更高）
核心用途：xxx
所需材料：
- 材料 1: xxx
- 材料 2: xxx
操作步骤：
1. xxx
2. xxx
3. xxx
4. xxx
5. xxx
环保意义：xxx"""
                
                # 调用智能 API（自动选择最佳可用 API）
                api_result = call_ai_api(ai_prompt, api_type="auto")
                
                use_ai_scheme = False
                scheme = None
                
                if api_result['success']:
                    try:
                        # 检查 AI 返回的内容是否有效
                        ai_content = api_result['content']
                        if ai_content and len(ai_content.strip()) > 50:
                            # 使用 AI 生成的方案
                            scheme = ai_content
                            use_ai_scheme = True
                            print(f"AI 方案预览：{ai_content[:300]}...")
                    except Exception as e:
                        pass
                
                if not use_ai_scheme:
                    error_msg = api_result.get('error', '未知错误')
                    print(f"使用的 API: {api_result.get('api_used', 'none')}")
                    print(f"API 返回的原始内容：{api_result.get('content', 'None')[:200] if api_result.get('content') else 'None'}")
                    # 使用本地保底方案
                    scheme = f"【{scrap_str}环保处理建议】\n\n由于无法获取 AI 方案，建议您将边角料进行分类处理：\n1. 果蔬皮类可用于堆肥\n2. 柑橘皮可制作天然清洁剂\n3. 骨头类可制成天然肥料\n\n请注意分类投放，保护环境。"
                
                # 使用 after 在主线程更新 UI
                def update_ui():
                    if hasattr(self, 'scrap_output'):
                        self.scrap_output.delete(1.0, tk.END)
                        
                        # 添加方案来源标识
                        if use_ai_scheme:
                            header = "🤖 【AI 智能生成】\n\n"
                        else:
                            header = "💾 【本地保底方案】\n\n"
                        
                        self.scrap_output.insert(tk.END, header + scheme)
                
                self.after(0, update_ui)
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    if hasattr(self, 'scrap_output'):
                        self.scrap_output.delete(1.0, tk.END)
                        self.scrap_output.insert(tk.END, f"❌ 生成失败：{error_msg}")
                self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()
    
    # ==========================================================================
    # 【新增功能】C. 智能营养分析 / Intelligent Nutrition Analysis
    # =========================================================================
    
    def create_nutrition_page(self, parent):
        """创建智能营养分析页面 / Create Nutrition Analysis Page"""
        # 标题
        title_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(title_frame, text="🔍 智能营养分析", 
                    font=("Arial", 20, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=15)
        
        # 副标题
        ctk.CTkLabel(title_frame, text="AI 驱动的营养成分检测与健康影响评估",
                    text_color=COLORS['text_secondary'],
                    font=("Arial", 13)).pack(pady=(0, 25))
    
        # 主要内容区 - 左右分栏
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        content_frame.grid_columnconfigure(0, weight=4)
        content_frame.grid_columnconfigure(1, weight=6)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # 左侧：输入区
        left_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                 corner_radius=15)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        left_content = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 输入说明
        ctk.CTkLabel(left_content, text="请输入食材或食谱名称",
                    text_color=COLORS['text_primary'],
                    font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # 食材输入框
        self.nutri_input = ctk.CTkEntry(left_content,
                                       placeholder_text="例如：土豆炖牛肉、西红柿炒鸡蛋",
                                       width=400,
                                       fg_color=COLORS['card_bg'],
                                       border_color=COLORS['primary'],
                                       border_width=2,
                                       text_color=COLORS['text_primary'])
        self.nutri_input.pack(fill=tk.X, pady=(0, 10))
        
        # 人数选择
        people_frame = ctk.CTkFrame(left_content, fg_color="transparent")
        people_frame.pack(fill=tk.X, pady=(10, 10))
        ctk.CTkLabel(people_frame, text="就餐人数：",
                    text_color=COLORS['text_primary']).pack(side=tk.LEFT)
        self.nutri_people_var = tk.IntVar(value=3)
        self.nutri_people_entry = ctk.CTkEntry(people_frame, textvariable=self.nutri_people_var,
                                               width=60, justify='center')
        self.nutri_people_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # 分析按钮
        analyze_btn = ctk.CTkButton(left_content, text="🔍 AI 营养分析",
                                   command=self.analyze_nutrition,
                                   fg_color=COLORS['primary'],
                                   hover_color=COLORS['secondary'],
                                   text_color="white",
                                   corner_radius=8,
                                   height=45)
        analyze_btn.pack(fill=tk.X, pady=(20, 10))
        
        # 使用说明
        info_frame = ctk.CTkFrame(left_content, fg_color=COLORS['card_bg'])
        info_frame.pack(fill=tk.X, pady=(20, 0))
        
        ctk.CTkLabel(info_frame, text="💡 分析内容：\n• 热量、蛋白质、脂肪、碳水化合物\n• 维生素、矿物质含量\n• 营养均衡评估\n• 健康饮食建议",
                    text_color=COLORS['text_secondary'],
                    justify=tk.LEFT).pack(padx=10, pady=10)
        
        # 右侧：结果展示
        right_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        # 滚动文本框
        self.nutri_output = ctk.CTkTextbox(right_frame, wrap=tk.WORD,
                                          font=("Arial", 14))
        self.nutri_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def analyze_nutrition(self):
        """异步 AI 营养分析 / Asynchronous Analyze Nutrition with AI"""
        user_input = self.nutri_input.get().strip()
        if not user_input:
            messagebox.showerror("提示", "请输入食材或食谱名称")
            return
        
        people = self.nutri_people_var.get()
        
        # 清空输出并显示加载提示
        self.nutri_output.delete(1.0, tk.END)
        self.nutri_output.insert(tk.END, "🤖 AI 正在分析营养成分，请稍候...\n\n")
        
        # 异步调用 AI
        def call_ai_async():
            try:
                # 构建 AI 提示词
                ai_prompt = f"""请对以下【{people}人份】的食材/食谱进行专业营养分析：

【食材/食谱】{user_input}

【⚠️ 重要原则：智能识别食材组合方式】
**在分析前，请先判断用户输入的食材应该如何理解：**

1. **如果用户输入的是多道独立的菜品**（用顿号、逗号分隔）：
   - 示例："土豆炖牛肉、西红柿炒鸡蛋、米饭"
   - 处理方式：分别分析每道菜，然后给出整体营养评估
   
2. **如果用户输入的是多种食材但未说明做法**：
   - 示例："牛奶、苹果、鸡蛋"
   - ❌ 错误做法：假设这些食材被做成一道菜（如"牛奶苹果炒鸡蛋"）
   - ✅ 正确做法：
     * 方案A：假设这是早餐组合 → 分别分析"温牛奶"、"新鲜苹果"、"水煮蛋"
     * 方案B：询问用户这些食材的具体做法
     * 方案C：给出几种合理的食用方式及其营养分析
   
3. **如果用户输入的是单一菜品**：
   - 示例："土豆炖牛肉"
   - 处理方式：直接分析这道菜的营养成分

【分析要求】
请按以下结构详细分析（每人份）：

📋 **第一步：食材组合解读**
- 说明你如何理解用户输入的食材/菜品
- 如果是多种食材，说明它们的合理食用方式
- 如果有歧义，给出2-3种可能的解读

1️⃣ **基础营养数据**（精确计算）
- 总热量：XXX 大卡
- 蛋白质：XX 克
- 脂肪：XX 克
- 碳水化合物：XX 克
- 膳食纤维：XX 克

2️⃣ **微量营养素**（估算）
- 维生素 A：XX 微克
- 维生素 C：XX 毫克
- 钙：XX 毫克
- 铁：XX 毫克
- 钾：XX 毫克

3️⃣ **营养均衡评估**
- 蛋白质来源：优质/一般/不足
- 脂肪类型：饱和/不饱和比例
- 碳水类型：简单/复杂碳水
- 总体评价：优秀/良好/需改进

4️⃣ **健康建议**
- 适合人群：xxx
- 食用建议：xxx
- 搭配建议：xxx
- 注意事项：xxx

5️⃣ **特殊标签**（如有）
- [ ] 高蛋白 ✅
- [ ] 低脂肪 ✅
- [ ] 低碳水 ✅
- [ ] 高纤维 ✅
- [ ] 富含维生素 ✅

请用清晰格式呈现，数据要科学合理。**如果食材组合不合理，请明确指出并给出改进建议！**"""
                
                # 调用 AI API
                api_result = call_ai_api(ai_prompt, api_type="auto")
                
                # 使用 after 在主线程更新 UI
                def update_ui():
                    if api_result['success']:
                        ai_content = api_result['content']
                        self.nutri_output.delete(1.0, tk.END)
                        self.nutri_output.insert(tk.END, "✅ 营养分析完成！\n\n")
                        self.nutri_output.insert(tk.END, ai_content)
                        print(f"【营养分析】✅ AI 分析成功，长度：{len(ai_content)} 字符")
                    else:
                        error_msg = api_result.get('error', '未知错误')
                        self.nutri_output.delete(1.0, tk.END)
                        self.nutri_output.insert(tk.END, f"❌ 分析失败：{error_msg}\n\n建议使用其他食材重试")
                        print(f"【营养分析】❌ API 调用失败：{error_msg}")
                
                self.after(0, update_ui)
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    self.nutri_output.delete(1.0, tk.END)
                    self.nutri_output.insert(tk.END, f"❌ 发生错误：{error_msg}")
                self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()

    # =============================================================================
    # 【新增功能】F. AI 对话助手 / AI Chat Assistant
    # =============================================================================
    
    def create_chat_page(self, parent):
        """创建 AI 对话助手页面 / Create AI Chat Assistant Page"""
        # 标题
        title_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ctk.CTkLabel(title_frame, text="💬 AI 烹饪助手",
                                  font=("Arial", 28, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(title_frame, text="有任何烹饪问题？随时问我！",
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 聊天区域
        chat_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                 corner_radius=15)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 聊天记录（滚动框）
        self.chat_history = ctk.CTkTextbox(chat_frame, wrap=tk.WORD,
                                          font=("Arial", 14),
                                          state='disabled')
        self.chat_history.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 底部输入区
        input_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        input_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 快捷问题
        quick_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        quick_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        ctk.CTkLabel(quick_frame, text="💡 常见问题：",
                    text_color=COLORS['text_primary'],
                    font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        quick_questions = [
            "土豆发芽了能吃吗？",
            "如何保存蔬菜？",
            "肉类替代品？",
            "怎么去除腥味？"
        ]
        
        for q in quick_questions:
            btn = ctk.CTkButton(quick_frame, text=q, width=120, height=30,
                               command=lambda x=q: self.ask_quick_question(x),
                               fg_color=COLORS['secondary'],
                               hover_color=COLORS['primary'],
                               text_color="white",
                               corner_radius=8,
                               font=("Arial", 12))
            btn.pack(side=tk.LEFT, padx=5)
        
        # 输入框和发送按钮
        entry_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        entry_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        self.chat_input = ctk.CTkEntry(entry_frame, placeholder_text="输入您的问题...",
                                      width=600,
                                      fg_color=COLORS['card_bg'],
                                      border_color=COLORS['primary'],
                                      border_width=2,
                                      text_color=COLORS['text_primary'])
        self.chat_input.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        send_btn = ctk.CTkButton(entry_frame, text="📤 发送",
                                command=self.send_message,
                                fg_color=COLORS['primary'],
                                hover_color=COLORS['secondary'],
                                text_color="white",
                                corner_radius=8,
                                height=40,
                                width=100)
        send_btn.pack(side=tk.LEFT)
        
        # 绑定回车键
        self.chat_input.bind("<Return>", lambda e: self.send_message())
    
    def ask_quick_question(self, question):
        """快捷提问 / Ask Quick Question"""
        self.chat_input.delete(0, tk.END)
        self.chat_input.insert(0, question)
        self.send_message()
    
    def send_message(self):
        """发送消息到 AI 助手 / Send Message to AI"""
        user_input = self.chat_input.get().strip()
        if not user_input:
            return
        
        # 显示用户问题
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, f"\n👤 您：{user_input}\n\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')
        
        # 清空输入框
        self.chat_input.delete(0, tk.END)
        
        # 显示思考中
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, "🤖 AI 思考中...\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')
        
        # 构建 AI 提示词
        ai_prompt = f"""你是一位专业的烹饪和食品安全顾问。请简洁、专业地回答以下问题：

用户问题：{user_input}

要求：
1. 回答要简洁明了（200 字以内）
2. 提供实用建议
3. 如果有安全隐患，要明确指出
4. 语气友好、专业
5. 可适当使用表情符号增强可读性"""
        
        # 异步调用 AI
        import threading
        def ai_task():
            api_result = call_ai_api(ai_prompt, api_type="auto")
            
            if api_result['success']:
                ai_response = api_result['content']
                # 更新 UI（线程安全）
                self.chat_history.after(0, lambda: self.update_chat_response(ai_response))
            else:
                error_msg = api_result.get('error', '未知错误')
                self.chat_history.after(0, lambda: self.update_chat_response(f"❌ 抱歉，出现错误：{error_msg}"))
        
        threading.Thread(target=ai_task, daemon=True).start()
    
    def update_chat_response(self, response):
        """更新聊天响应 / Update Chat Response"""
        self.chat_history.configure(state='normal')
        # 删除"思考中"
        content = self.chat_history.get(1.0, tk.END)
        content = content.replace("🤖 AI 思考中...\n", "")
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.insert(tk.END, content)
        # 插入 AI 回答
        self.chat_history.insert(tk.END, f"💡 AI：{response}\n\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')
        print(f"【AI 对话】✅ 回复成功，长度：{len(response)} 字符")

    # =============================================================================
    # 【新增功能】E. 智能冰箱管理 / Smart Fridge Management
    # =============================================================================
    
    def create_fridge_page(self, parent):
        """创建智能冰箱管理页面 / Create Smart Fridge Management Page"""
        # 标题
        title_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ctk.CTkLabel(title_frame, text="🧊 智能冰箱管理",
                                  font=("Arial", 28, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(title_frame, text="管理家中食材，避免浪费，智能推荐菜谱",
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 添加食材区域
        add_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                corner_radius=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(add_frame, text="➕ 添加新食材", 
                    font=("Arial", 16, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 10))
        
        # 输入框行
        input_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        input_row.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(input_row, text="名称:", 
                    text_color=COLORS['text_primary']).pack(side=tk.LEFT, padx=(0, 5))
        self.new_ingredient_name = ctk.CTkEntry(input_row, width=150,
                                               fg_color=COLORS['card_bg'],
                                               border_color=COLORS['primary'],
                                               text_color=COLORS['text_primary'])
        self.new_ingredient_name.pack(side=tk.LEFT, padx=(0, 15))
        
        ctk.CTkLabel(input_row, text="数量 (g):", 
                    text_color=COLORS['text_primary']).pack(side=tk.LEFT, padx=(0, 5))
        self.new_ingredient_quantity = ctk.CTkEntry(input_row, width=100,
                                                   fg_color=COLORS['card_bg'],
                                                   border_color=COLORS['primary'],
                                                   text_color=COLORS['text_primary'])
        self.new_ingredient_quantity.insert(0, "500")
        self.new_ingredient_quantity.pack(side=tk.LEFT, padx=(0, 15))
        
        add_btn = ctk.CTkButton(input_row, text="添加", 
                               command=self.add_ingredient_to_fridge,
                               fg_color=COLORS['primary'],
                               hover_color=COLORS['secondary'],
                               text_color="white",
                               height=32)
        add_btn.pack(side=tk.LEFT)
        
        # 现有食材列表
        list_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                 corner_radius=15)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        ctk.CTkLabel(list_frame, text="📦 当前库存", 
                    font=("Arial", 16, "bold"),
                    text_color=COLORS['text_primary']).pack(pady=(15, 10))
        
        # 创建滚动区域显示食材
        self.fridge_items_frame = ctk.CTkScrollableFrame(list_frame, 
                                                        fg_color="transparent")
        self.fridge_items_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 刷新显示
        self.refresh_fridge_inventory()
    
    def refresh_fridge_inventory(self):
        """刷新冰箱食材列表显示"""
        # 清空现有内容
        for widget in self.fridge_items_frame.winfo_children():
            widget.destroy()
        
        # 获取当前库存
        inventory = self.data.get('fridge_inventory', [])
        
        if not inventory:
            ctk.CTkLabel(self.fridge_items_frame, text="📭 冰箱空空如也，快添加一些食材吧！",
                        text_color=COLORS['text_secondary'],
                        font=("Arial", 14)).pack(pady=20)
            return
        
        # 显示每个食材
        for i, item in enumerate(inventory):
            item_frame = ctk.CTkFrame(self.fridge_items_frame, 
                                     fg_color=COLORS['background'],
                                     corner_radius=10)
            item_frame.pack(fill=tk.X, pady=(0, 10))
            
            # 食材信息
            info_label = ctk.CTkLabel(item_frame, 
                                     text=f"{item['name']} - {item.get('quantity', 0)}g",
                                     text_color=COLORS['text_primary'],
                                     font=("Arial", 14))
            info_label.pack(side=tk.LEFT, padx=15, pady=10)
            
            # 删除按钮
            delete_btn = ctk.CTkButton(item_frame, text="❌ 删除",
                                      command=lambda idx=i: self.remove_ingredient_from_fridge(idx),
                                      fg_color="transparent",
                                      border_width=2,
                                      border_color=COLORS['danger'],
                                      text_color=COLORS['danger'],
                                      hover_color=COLORS['danger'],
                                      height=28,
                                      width=80)
            delete_btn.pack(side=tk.RIGHT, padx=15, pady=10)
    
    def add_ingredient_to_fridge(self):
        """添加食材到冰箱"""
        name = self.new_ingredient_name.get().strip()
        try:
            quantity = int(self.new_ingredient_quantity.get().strip())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数量")
            return
        
        if not name:
            messagebox.showerror("错误", "请输入食材名称")
            return
        
        # 添加到数据
        if 'fridge_inventory' not in self.data:
            self.data['fridge_inventory'] = []
        
        self.data['fridge_inventory'].append({
            'name': name,
            'quantity': quantity,
            'unit': 'g',
            'added_date': datetime.now().strftime('%Y-%m-%d')
        })
        
        save_data(self.data)
        
        # 清空输入框
        self.new_ingredient_name.delete(0, tk.END)
        self.new_ingredient_quantity.delete(0, tk.END)
        self.new_ingredient_quantity.insert(0, "500")
        
        # 刷新显示
        self.refresh_fridge_inventory()
        
        messagebox.showinfo("成功", f"✅ 已添加 {name} {quantity}g 到冰箱")
    
    def remove_ingredient_from_fridge(self, index):
        """从冰箱删除食材"""
        if 'fridge_inventory' not in self.data:
            return
        
        if 0 <= index < len(self.data['fridge_inventory']):
            removed_item = self.data['fridge_inventory'].pop(index)
            save_data(self.data)
            self.refresh_fridge_inventory()
            messagebox.showinfo("已删除", f"已从冰箱移除：{removed_item['name']}")
    
    # =============================================================================
    # 【新增功能】D. 智能采购清单 / Smart Shopping List
    # =============================================================================
    
    def create_shopping_page(self, parent):
        """创建智能采购清单页面 / Create Smart Shopping List Page"""
        # 标题
        title_frame = ctk.CTkFrame(parent, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ctk.CTkLabel(title_frame, text="🛒 智能采购清单",
                                  font=("Arial", 28, "bold"),
                                  text_color=COLORS['text_primary'])
        title_label.pack(pady=(20, 10))
        
        sub_label = ctk.CTkLabel(title_frame, text="想吃什么菜？AI 帮你生成购物清单",
                                text_color=COLORS['text_secondary'],
                                font=("Arial", 14))
        sub_label.pack(pady=(0, 20))
        
        # 主要内容 - 左右分栏
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        content_frame.grid_columnconfigure(0, weight=4)
        content_frame.grid_columnconfigure(1, weight=6)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # 左侧：输入区
        left_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                 corner_radius=15)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        left_content = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 输入说明
        ctk.CTkLabel(left_content, text="我想吃这些菜...",
                    text_color=COLORS['text_primary'],
                    font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # 菜品输入框
        self.shopping_input = ctk.CTkEntry(left_content,
                                          placeholder_text="例如：红烧肉、麻婆豆腐、西红柿蛋汤",
                                          width=400,
                                          fg_color=COLORS['card_bg'],
                                          border_color=COLORS['primary'],
                                          border_width=2,
                                          text_color=COLORS['text_primary'])
        self.shopping_input.pack(fill=tk.X, pady=(0, 10))
        
        # 人数选择
        people_frame = ctk.CTkFrame(left_content, fg_color="transparent")
        people_frame.pack(fill=tk.X, pady=(10, 10))
        ctk.CTkLabel(people_frame, text="就餐人数：",
                    text_color=COLORS['text_primary']).pack(side=tk.LEFT)
        self.shopping_people_var = tk.IntVar(value=3)
        self.shopping_people_entry = ctk.CTkEntry(people_frame, textvariable=self.shopping_people_var,
                                                  width=60, justify='center')
        self.shopping_people_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # 生成清单按钮
        generate_btn = ctk.CTkButton(left_content, text="📝 生成购物清单",
                                    command=self.generate_shopping_list,
                                    fg_color=COLORS['primary'],
                                    hover_color=COLORS['secondary'],
                                    text_color="white",
                                    corner_radius=8,
                                    height=45)
        generate_btn.pack(fill=tk.X, pady=(20, 10))
        
        # 预算估算开关
        self.budget_var = tk.BooleanVar(value=True)
        budget_check = ctk.CTkCheckBox(left_content, text="💰 估算预算",
                                      variable=self.budget_var,
                                      text_color=COLORS['text_primary'])
        budget_check.pack(anchor=tk.W, pady=(10, 0))
        
        # 使用说明
        info_frame = ctk.CTkFrame(left_content, fg_color=COLORS['card_bg'])
        info_frame.pack(fill=tk.X, pady=(20, 0))
        
        ctk.CTkLabel(info_frame, text="💡 功能说明：\n• 根据想吃的菜自动生成食材清单\n• 按超市区域分类（蔬菜区、肉类区等）\n• 精确计算用量\n• 可选：估算总价格",
                    text_color=COLORS['text_secondary'],
                    justify=tk.LEFT).pack(padx=10, pady=10)
        
        # 右侧：结果展示
        right_frame = ctk.CTkFrame(content_frame, fg_color=COLORS['card_bg'],
                                  corner_radius=15)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        # 滚动文本框
        self.shopping_output = ctk.CTkTextbox(right_frame, wrap=tk.WORD,
                                             font=("Arial", 14))
        self.shopping_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def generate_shopping_list(self):
        """异步生成智能采购清单 / Asynchronously Generate Shopping List"""
        user_input = self.shopping_input.get().strip()
        if not user_input:
            messagebox.showerror("提示", "请输入想吃的菜品")
            return
        
        people = self.shopping_people_var.get()
        include_budget = self.budget_var.get()
        
        # 清空输出并显示加载提示
        self.shopping_output.delete(1.0, tk.END)
        self.shopping_output.insert(tk.END, "🤖 AI 正在生成购物清单，请稍候...\n\n")
        
        # 异步调用 AI
        def call_ai_async():
            try:
                # 构建 AI 提示词
                budget_instruction = "\n6. 💰 **预算估算**：为每种食材估算价格（人民币），并计算总金额" if include_budget else ""
                
                ai_prompt = f"""请为以下【{people}人份】的菜品生成详细的采购清单：

【想吃的菜品】{user_input}

请生成完整的购物清单，包含以下内容：

1️⃣ **按超市区域分类**
- 🥬 蔬菜区：xxx
- 🥩 肉类区：xxx
- 🐟 水产区：xxx
- 🍞 粮油副食区：xxx
- 🧂 调味品区：xxx
- 🥛 乳制品区：xxx
- ❄️ 冷冻食品区：xxx

2️⃣ **精确用量**（考虑{people}人份）
- 每种食材标注具体用量（克/个/毫升）
- 适量调味料也要给出建议用量

3️⃣ **挑选建议**
- 如何挑选新鲜食材
- 注意事项

4️⃣ **储存建议**
- 哪些食材需要冷藏
- 保质期提醒

5️⃣ **替代方案**
- 如果某些食材买不到，有什么替代品{budget_instruction}

请用清晰的表格或列表格式呈现，方便用户在超市购物时使用。"""
                
                # 调用 AI API
                api_result = call_ai_api(ai_prompt, api_type="auto")
                
                # 使用 after 在主线程更新 UI
                def update_ui():
                    if api_result['success']:
                        ai_content = api_result['content']
                        self.shopping_output.delete(1.0, tk.END)
                        self.shopping_output.insert(tk.END, "✅ 购物清单已生成！\n\n")
                        self.shopping_output.insert(tk.END, ai_content)
                        print(f"【购物清单】✅ AI 生成成功，长度：{len(ai_content)} 字符")
                    else:
                        error_msg = api_result.get('error', '未知错误')
                        self.shopping_output.delete(1.0, tk.END)
                        self.shopping_output.insert(tk.END, f"❌ 生成失败：{error_msg}\n\n")
                        self.shopping_output.insert(tk.END, "💡 建议：\n• 检查网络连接\n• 稍后重试")
                        print(f"【购物清单】❌ AI 调用失败：{error_msg}")
                
                self.after(0, update_ui)
            except Exception as e:
                error_msg = str(e)  # 先保存错误消息，避免作用域问题
                def show_error():
                    self.shopping_output.delete(1.0, tk.END)
                    self.shopping_output.insert(tk.END, f"❌ 发生错误：{error_msg}")
                self.after(0, show_error)
        
        # 启动异步线程
        thread = threading.Thread(target=call_ai_async)
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    app = FoodGuardianAI()
    app.mainloop()
