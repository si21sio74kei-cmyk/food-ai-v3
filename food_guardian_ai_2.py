# -*- coding: utf-8 -*-
"""
FoodGuardian AI v2.0 - 智能食谱助手 (Web版)
Modern Web Application with iOS-style UI

运行方式:
python food_guardian_ai_2.py

访问地址: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import os
import requests
import time
import threading
from datetime import datetime, timezone, timedelta

# 中国时区 (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_time():
    """获取中国标准时间"""
    return datetime.now(CHINA_TZ)

app = Flask(__name__, static_folder='static', template_folder='templates')

# ====================== AI API 全局配置 ======================
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
# 🔒 安全修复：必须使用环境变量，禁止硬编码 API Key
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_API_KEY_TEXT = os.getenv("ZHIPU_API_KEY_TEXT")

# 检查API密钥是否配置
if not ZHIPU_API_KEY or not ZHIPU_API_KEY_TEXT:
    print("\n⚠️  警告: 未检测到API密钥！")
    print("请在Vercel环境变量中配置 ZHIPU_API_KEY 和 ZHIPU_API_KEY_TEXT")
    print("或创建 .env 文件（仅本地开发使用）\n")

API_TIMEOUT = 90
API_MAX_RETRIES = 3

# 启用详细日志
ENABLE_DETAILED_LOGS = True

# ====================== 常量定义 ======================
COLORS = {
    'primary': '#FF8C42',
    'secondary': '#FFB347',
    'tertiary': '#FFD93D',
    'background': '#FFF9F0',
    'card_bg': '#FFFFFF',
    'text_primary': '#2C2C2C',
    'text_secondary': '#5A5A5A',
    'danger': '#FF6B6B',
    'separator': '#E0E0E0'
}

BASE_PORTIONS = {
    'tomato': 80, 'chicken': 120, 'potato': 90, 'egg': 60, 'beef': 130, 'fish': 110
}

MEAL_MULTIPLIERS = {'home': 1.0, 'healthy': 0.9, 'vegetarian': 0.85, 'banquet': 1.15}

ENV_FACTORS = {'water_per_g': 0.5, 'co2_per_g': 0.003}
WASTE_RATIO = 0.25

INGREDIENT_MAP = {
    '番茄': 'tomato', '西红柿': 'tomato', '鸡肉': 'chicken', '鸡胸肉': 'chicken',
    '土豆': 'potato', '马铃薯': 'potato', '鸡蛋': 'egg', '蛋': 'egg',
    '牛肉': 'beef', '猪肉': 'beef', '羊肉': 'beef', '鱼': 'fish', '鱼类': 'fish', '鱼肉': 'fish', '虾': 'fish',
    '青菜': 'tomato', '菜': 'tomato', '白菜': 'tomato', '生菜': 'tomato', '菠菜': 'tomato',
    '萝卜': 'potato', '红薯': 'potato', '山药': 'potato', '芋头': 'potato', '莲藕': 'potato',
    '莴笋': 'potato', '黄瓜': 'tomato', '冬瓜': 'tomato', '南瓜': 'tomato', '丝瓜': 'tomato',
    '苦瓜': 'tomato', '菇': 'tomato', '菌': 'tomato', '香菇': 'tomato', '金针菇': 'tomato',
    '豆腐': 'tofu', '豆干': 'tofu', '豆芽': 'bean_sprout', '腐竹': 'tofu'
}

# ====================== 数据持久化 ======================
def load_data():
    """加载本地数据"""
    # Vercel 环境使用内存存储（只读文件系统）
    if os.getenv('VERCEL'):
        return getattr(load_data, '_memory_data', {
            'nickname': '', 
            'waste_reduced': 0, 
            'water_saved': 0, 
            'co2_reduced': 0,
            'population_group': 'adults',
            'daily_intake_records': [],
            'fridge_inventory': [],
            'generation_count': 0
        })
    
    # 本地环境使用文件存储
    if os.path.exists('fgai_local_data.json'):
        try:
            with open('fgai_local_data.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'nickname': '', 
        'waste_reduced': 0, 
        'water_saved': 0, 
        'co2_reduced': 0,
        'population_group': 'adults',
        'daily_intake_records': [],
        'fridge_inventory': [],
        'generation_count': 0  # 关键修复：添加计数器
    }

def save_data(data):
    """保存本地数据"""
    # Vercel 环境使用内存存储（只读文件系统）
    if os.getenv('VERCEL'):
        load_data._memory_data = data
        return
    
    # 本地环境使用文件存储
    try:
        with open('fgai_local_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存数据失败: {e}")

# ====================== AI API 调用 ======================
def _call_zhipu_api(url, api_key, prompt, max_retries):
    """智谱 AI GLM-4 API 调用(智能降级策略)"""
    if ENABLE_DETAILED_LOGS:
        print(f"\n🤖 [AI调用] 开始调用智谱 API...")
        print(f"   - Prompt长度: {len(prompt)} 字符")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    model_priority = [
        {"name": "glm-4-air", "desc": "GLM-4-Air"},
        {"name": "glm-4-flash", "desc": "GLM-4-Flash"}
    ]
    
    last_error = None
    
    for model_info in model_priority:
        model_name = model_info["name"]
        
        if ENABLE_DETAILED_LOGS:
            print(f"   🔄 尝试模型: {model_info['desc']}")
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2500,  # 🔑 关键修复：增加到2500，允许AI输出完整内容
            "temperature": 0.7
        }
        
        for attempt in range(max_retries + 1):
            try:
                if ENABLE_DETAILED_LOGS and attempt > 0:
                    print(f"      ⏳ 第{attempt + 1}次重试...")
                
                response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
                
                # 📊 记录配额信息（如果API返回）
                if ENABLE_DETAILED_LOGS:
                    rate_limit = response.headers.get('X-RateLimit-Limit', 'N/A')
                    rate_remaining = response.headers.get('X-RateLimit-Remaining', 'N/A')
                    rate_reset = response.headers.get('X-RateLimit-Reset', 'N/A')
                    if rate_limit != 'N/A':
                        print(f"      📊 配额信息: 总额度={rate_limit}, 剩余={rate_remaining}, 重置时间={rate_reset}")
                
                response.raise_for_status()
                
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    if ENABLE_DETAILED_LOGS:
                        print(f"   ✅ 成功! 使用模型: {model_name}")
                        print(f"   - 响应长度: {len(content)} 字符\n")
                    return {
                        'success': True,
                        'content': content,
                        'error': None,
                        'model_used': model_name
                    }
                else:
                    last_error = '返回格式异常'
                    break
                    
            except requests.exceptions.Timeout:
                last_error = f"{model_name} 超时"
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ 超时: {last_error}")
                break
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 'Unknown'
                last_error = f"HTTP {status_code}"
                
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ HTTP错误: {last_error}")
                
                if status_code in [401, 403, 429]:
                    break
                if attempt < max_retries:
                    time.sleep(1)
                continue
                
            except Exception as e:
                last_error = str(e)
                if ENABLE_DETAILED_LOGS:
                    print(f"      ❌ 异常: {last_error}")
                if attempt < max_retries:
                    time.sleep(1)
                continue
    
    if ENABLE_DETAILED_LOGS:
        print(f"   ❌ 所有模型调用失败: {last_error}\n")
    
    return {
        'success': False,
        'content': None,
        'error': last_error or '调用失败',
        'model_used': 'none'
    }

def call_ai_api(prompt, api_type="auto"):
    """智能 AI API 调用函数"""
    max_retries = API_MAX_RETRIES
    api_list = []
    
    if api_type == "auto" and ZHIPU_API_KEY:
        api_list.append({"type": "zhipu", "url": ZHIPU_API_URL, "key": ZHIPU_API_KEY})
    
    if not api_list:
        return {
            'success': False,
            'content': None,
            'error': '未配置 API Key',
            'api_used': 'none'
        }
    
    for api_info in api_list:
        api_name = api_info["type"]
        current_url = api_info["url"]
        current_key = api_info["key"]
        
        try:
            if api_name == "zhipu":
                result = _call_zhipu_api(current_url, current_key, prompt, max_retries)
            
            if result['success']:
                result['api_used'] = api_name
                return result
        
        except Exception as e:
            continue
    
    return {
        'success': False,
        'content': None,
        'error': '所有 API 调用失败',
        'api_used': 'none'
    }

# ====================== 营养评估引擎 ======================
def load_nutrition_standards():
    """加载联合国营养标准"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, 'un_nutrition_standards.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            standards = json.load(f)
        standards_dict = {s['population_group']: s for s in standards}
        return standards_dict
    except Exception as e:
        print(f"❌ 加载营养标准失败:{e}")
        return {}

def get_nutrition_standard(population_group):
    """获取指定人群的营养标准"""
    standards = load_nutrition_standards()
    return standards.get(population_group, standards.get('adults', None))

def generate_multi_group_nutrition_report(user_intake, language='zh-CN'):
    """生成多人群营养对比报告（Markdown格式）"""
    print(f"\n👥 [generate_multi_group_nutrition_report] 用户摄入: {user_intake}, 语言: {language}")
    
    groups = ['adults', 'teens', 'children', 'elderly']
    
    if language == 'en-US':
        group_names = {
            'adults': 'Adults (18-60 years)',
            'teens': 'Teens (13-17 years)',
            'children': 'Children (6-12 years)',
            'elderly': 'Elderly (60+ years)'
        }
        food_names = {'vegetables': 'Vegetables', 'fruits': 'Fruits', 'meat': 'Meat', 'eggs': 'Eggs'}
        status_names = {'达标': 'Meets Standard', '不足': 'Insufficient', '超标': 'Excessive'}
        status_icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️'}
        
        report = "# 👥 Multi-Population Nutrition Assessment Report\n\n"
        report += "*Based on UN WHO nutrition standards, providing personalized recommendations for the whole family*\n\n"
        
        report += "## 【Your Current Intake】\n\n"
        report += f"- **Vegetables**: {user_intake.get('vegetables', 0)}g\n"
        report += f"- **Fruits**: {user_intake.get('fruits', 0)}g\n"
        report += f"- **Meat**: {user_intake.get('meat', 0)}g\n"
        report += f"- **Eggs**: {user_intake.get('eggs', 0)}g\n\n"
        
        for group in groups:
            standard = get_nutrition_standard(group)
            if not standard:
                continue
            
            group_name = group_names[group]
            characteristics_en = standard.get('characteristics_en', standard.get('characteristics', ''))
            
            report += f"---\n\n## 📋 {group_name}\n\n"
            
            if characteristics_en:
                report += f"**Group Characteristics**: {characteristics_en}\n\n"
            
            report += "### Nutrition Standards Comparison\n\n"
            report += "| Food Type | Recommended Range | Your Intake | Status |\n"
            report += "|----------|-------------------|-------------|--------|\n"
            
            recommendations = standard.get('daily_recommendations', {})
            
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                food_name = food_names[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    status = '不足'
                    gap = min_val - intake_amount
                    gap_text = f" (needs {gap}g more)"
                elif intake_amount > max_val:
                    status = '超标'
                    gap = intake_amount - max_val
                    gap_text = f" (exceeds by {gap}g)"
                else:
                    status = '达标'
                    gap = 0
                    gap_text = ''
                
                icon = status_icons[status]
                status_text = f"{icon} {status_names[status]}{gap_text}"
                
                report += f"| {food_name} | {min_val}-{max_val}g | {intake_amount}g | {status_text} |\n"
            
            report += "\n"
            
            report += "### 💡 Targeted Recommendations\n\n"
            
            has_issue = False
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                food_name = food_names[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    gap = min_val - intake_amount
                    report += f"- ⬇️ **Insufficient {food_name}**: For {group_name}, recommend increasing by {gap}g to reach above {min_val}g\n"
                    has_issue = True
                elif intake_amount > max_val:
                    gap = intake_amount - max_val
                    report += f"- ️ **Excessive {food_name}**: For {group_name}, recommend reducing by {gap}g to stay within {max_val}g\n"
                    has_issue = True
            
            if not has_issue:
                report += f"- ✅ **All Standards Met**: Current intake meets the nutritional needs of {group_name}, please keep it up!\n"
            
            report += "\n"
        
        report += "---\n\n## 🎯 Overall Recommendations\n\n"
        report += "Since different population groups have varying nutritional needs, we recommend:\n\n"
        report += "1. **Separate Meals**: Prepare food portions suitable for each group's nutritional needs\n"
        report += "2. **Key Focus**: Prioritize meeting the special nutritional needs of children and elderly\n"
        report += "3. **Flexible Adjustment**: Adjust food portions according to actual dining situations\n"
        report += "4. **Diverse Diet**: Ensure food variety and balanced nutrition\n\n"
        
        report += "---\n*This report is generated based on UN WHO nutrition standards, for reference only*"
    else:
        group_names = {
            'adults': '成年人 (18-60 岁)',
            'teens': '青少年 (13-17 岁)',
            'children': '儿童 (6-12 岁)',
            'elderly': '老年人 (60 岁以上)'
        }
        
        report = "# 👥 多人群营养评估报告\n\n"
        report += "*基于联合国 WHO 营养标准，为全家提供个性化建议*\n\n"
        
        report += "## 【您当前摄入】\n\n"
        report += f"- **蔬菜**: {user_intake.get('vegetables', 0)}g\n"
        report += f"- **水果**: {user_intake.get('fruits', 0)}g\n"
        report += f"- **肉类**: {user_intake.get('meat', 0)}g\n"
        report += f"- **蛋类**: {user_intake.get('eggs', 0)}g\n\n"
        
        for group in groups:
            standard = get_nutrition_standard(group)
            if not standard:
                continue
            
            group_name = group_names[group]
            report += f"---\n\n## 📋 {group_name}\n\n"
            
            if standard.get('characteristics'):
                report += f"**群体特点**: {standard['characteristics']}\n\n"
            
            report += "### 营养标准对比\n\n"
            report += "| 食物类型 | 推荐范围 | 您的摄入 | 状态 |\n"
            report += "|---------|---------|---------|------|\n"
            
            icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️'}
            recommendations = standard.get('daily_recommendations', {})
            
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                chinese_name = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    status = '不足'
                    gap = min_val - intake_amount
                elif intake_amount > max_val:
                    status = '超标'
                    gap = intake_amount - max_val
                else:
                    status = '达标'
                    gap = 0
                
                icon = icons.get(status, '❓')
                status_text = f"{icon} {status}"
                if gap > 0:
                    if status == '不足':
                        status_text += f" (还差 {gap}g)"
                    else:
                        status_text += f" (超出 {gap}g)"
                
                report += f"| {chinese_name} | {min_val}-{max_val}g | {intake_amount}g | {status_text} |\n"
            
            report += "\n"
            
            report += "### 💡 针对性建议\n\n"
            
            has_issue = False
            for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
                rec = recommendations.get(food_type, {})
                chinese_name = {'vegetables': '蔬菜', 'fruits': '水果', 'meat': '肉类', 'eggs': '蛋类'}[food_type]
                intake_amount = user_intake.get(food_type, 0)
                min_val = rec.get('min', 0)
                max_val = rec.get('max', 0)
                
                if intake_amount < min_val:
                    gap = min_val - intake_amount
                    report += f"- ️ **{chinese_name}不足**: 对于{group_name}，建议增加{gap}g，达到{min_val}g以上\n"
                    has_issue = True
                elif intake_amount > max_val:
                    gap = intake_amount - max_val
                    report += f"- ⬆️ **{chinese_name}超标**: 对于{group_name}，建议减少{gap}g，控制在{max_val}g以内\n"
                    has_issue = True
            
            if not has_issue:
                report += f"- ✅ **全部达标**: 当前摄入量符合{group_name}的营养需求，请继续保持！\n"
            
            report += "\n"
        
        report += "---\n\n## 🎯 综合建议\n\n"
        report += "由于不同人群的营养需求存在差异，建议：\n\n"
        report += "1. **分餐准备**: 为不同人群准备适合其营养需求的食物份量\n"
        report += "2. **重点关注**: 优先满足儿童和老年人的特殊营养需求\n"
        report += "3. **灵活调整**: 根据实际用餐情况，适当增减各类食物的份量\n"
        report += "4. **多样化饮食**: 确保食物种类丰富，营养均衡\n\n"
        
        report += "---\n*本报告基于联合国WHO营养标准生成，仅供参考*"
    
    return report

def generate_nutrition_report(user_intake, population_group, language='zh-CN'):
    """生成完整的营养评估报告（Markdown格式）"""
    assessment = nutrition_assessment(user_intake, population_group)
    
    if 'error' in assessment:
        return assessment['error']
    
    # 🌐 根据语言生成不同的报告
    if language == 'en-US':
        return generate_nutrition_report_en(user_intake, population_group, assessment)
    else:
        return generate_nutrition_report_zh(user_intake, population_group, assessment)

def generate_nutrition_report_en(user_intake, population_group, assessment):
    """Generate English nutrition assessment report"""
    group_names = {
        'adults': 'Adults (18-60 years)',
        'teens': 'Teens (13-17 years)',
        'children': 'Children (6-12 years)',
        'elderly': 'Elderly (60+ years)'
    }
    group_name = group_names.get(population_group, population_group)
    
    food_names = {
        'vegetables': 'Vegetables',
        'fruits': 'Fruits',
        'meat': 'Meat',
        'eggs': 'Eggs'
    }
    
    status_names = {
        '达标': 'Meets Standard',
        '不足': 'Insufficient',
        '超标': 'Excessive',
        '未录入': 'Not Recorded'
    }
    
    status_icons = {
        '达标': '✅',
        '不足': '⬇️',
        '超标': '️',
        '未录入': '️'
    }
    
    standard = get_nutrition_standard(population_group)
    
    report = "# 📊 Nutrition Assessment Report (Based on UN WHO Standards)\n\n"
    
    # Basic Information
    report += "## [Basic Information]\n\n"
    report += f"- **Assessment Date**: {get_china_time().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"- **Population Group**: {group_name}\n"
    
    total_intake = sum(user_intake.get(food, 0) for food in ['vegetables', 'fruits', 'meat', 'eggs'])
    report += f"- **Total Intake**: {total_intake}g\n\n"
    
    # Intake Data Comparison
    report += "## [Intake Data Comparison]\n\n"
    report += "| Food Type | Current Intake | Recommended Range | Status |\n"
    report += "|-----------|----------------|-------------------|--------|\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        intake_amount = data['intake']
        english_name = food_names.get(food_type, food_type)
        status = data['status']
        status_en = status_names.get(status, status)
        icon = status_icons.get(status, '❓')
        
        if standard and status != '未录入':
            recommendations = standard['daily_recommendations'].get(food_type, {})
            min_rec = recommendations.get('min', 0)
            max_rec = recommendations.get('max', 0)
            range_str = f"{min_rec}-{max_rec}g"
        else:
            range_str = "-"
        
        report += f"| {english_name} | {intake_amount}g | {range_str} | {icon} {status_en} |\n"
    
    report += "\n"
    
    # Detailed Analysis
    report += "## [Detailed Analysis]\n\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        english_name = food_names.get(food_type, food_type)
        status = data['status']
        icon = status_icons.get(status, '❓')
        
        report += f"### {icon} {english_name}\n\n"
        report += f"- **Current Intake**: {data['intake']}g\n"
        
        if data['gap'] > 0:
            if status == '不足':
                report += f"- **Gap**: {data['gap']}g below minimum recommendation\n"
            elif status == '超标':
                report += f"- **Excess**: {data['gap']}g above maximum recommendation\n"
        
        # Translate suggestion
        suggestion_en = translate_suggestion_to_en(data['suggestion'])
        report += f"- **Suggestion**: {suggestion_en}\n\n"
    
    # Comprehensive Evaluation
    report += "## [Comprehensive Evaluation]\n\n"
    
    status_count = {'达标': 0, '不足': 0, '超标': 0, '未录入': 0}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        status = assessment[food_type]['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    if status_count['达标'] == 4:
        report += "🎉 **Excellent!** All food categories meet the recommended standards. Please continue to maintain a balanced diet!\n\n"
    elif status_count['达标'] >= 2:
        report += "👍 **Good!** Most food categories are reasonable. Pay attention to adjusting insufficient or excessive categories.\n\n"
    elif status_count['未录入'] > 0:
        report += "️ **To be improved** Some food categories have not been recorded yet. It is recommended to supplement them for more accurate assessment.\n\n"
    else:
        report += "💡 **Needs improvement** Most food categories do not meet the standards. It is recommended to refer to the health tips below for adjustments.\n\n"
    
    # Health Tips
    report += "## [Health Tips]\n\n"
    
    tips = []
    if assessment['vegetables']['status'] == '不足':
        tips.append("🥬 Insufficient vegetable intake may lack dietary fiber and vitamins. It is recommended to increase green leafy vegetables.")
    if assessment['fruits']['status'] == '不足':
        tips.append("🍎 Insufficient fruit intake may lack vitamin C. It is recommended to add fresh fruits appropriately.")
    if assessment['meat']['status'] == '超标':
        tips.append(" Excessive meat intake may increase fat intake. It is recommended to reduce red meat and increase fish and poultry.")
    if assessment['eggs']['status'] == '超标':
        tips.append(" Excessive egg intake requires attention to cholesterol. It is recommended to control daily egg intake.")
    
    if not tips:
        tips.append("✨ Current diet structure is relatively reasonable. It is recommended to continue maintaining a diverse diet.")
        tips.append("💧 Don't forget to drink enough water every day (recommended 1500-2000ml).")
        tips.append("🏃 Combine with appropriate exercise for better results.")
    
    for tip in tips:
        report += f"- {tip}\n"
    
    report += "\n---\n*This report is generated based on UN WHO nutrition standards for reference only.*"
    
    return report

def generate_nutrition_report_zh(user_intake, population_group, assessment):
    """生成中文营养评估报告"""
    # 人群名称映射
    group_names = {
        'adults': '成年人 (18-60 岁)',
        'teens': '青少年 (13-17 岁)',
        'children': '儿童 (6-12 岁)',
        'elderly': '老年人 (60 岁以上)'
    }
    group_name = group_names.get(population_group, population_group)
    
    # 加载营养标准
    standard = get_nutrition_standard(population_group)
    
    # 生成报告
    report = "# 📊 营养评估报告（基于联合国 WHO 标准）\n\n"
    
    # 基本信息
    report += "## 【基本信息】\n\n"
    report += f"- **评估日期**: {get_china_time().strftime('%Y-%m-%d %H:%M')}\n"
    report += f"- **人群分类**: {group_name}\n"
    
    # 计算总摄入量
    total_intake = sum(user_intake.get(food, 0) for food in ['vegetables', 'fruits', 'meat', 'eggs'])
    report += f"- **总摄入量**: {total_intake}g\n\n"
    
    # 摄入数据对比
    report += "## 【摄入数据对比】\n\n"
    report += "| 食物类型 | 当前摄入 | 推荐范围 | 状态 |\n"
    report += "|---------|---------|---------|------|\n"
    
    icons = {'达标': '✅', '不足': '⬇️', '超标': '⬆️', '未录入': '⏸️'}
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        intake_amount = data['intake']
        chinese_name = data['chinese_name']
        status = data['status']
        icon = icons.get(status, '❓')
        
        if standard and status != '未录入':
            recommendations = standard['daily_recommendations'].get(food_type, {})
            min_rec = recommendations.get('min', 0)
            max_rec = recommendations.get('max', 0)
            range_str = f"{min_rec}-{max_rec}g"
        else:
            range_str = "-"
        
        report += f"| {chinese_name} | {intake_amount}g | {range_str} | {icon} {status} |\n"
    
    report += "\n"
    
    # 详细分析
    report += "## 【详细分析】\n\n"
    
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        data = assessment[food_type]
        chinese_name = data['chinese_name']
        status = data['status']
        suggestion = data['suggestion']
        
        icon = icons.get(status, '❓')
        report += f"### {icon} {chinese_name}\n\n"
        report += f"- **当前摄入**: {data['intake']}g\n"
        
        if data['gap'] > 0:
            if status == '不足':
                report += f"- **差距**: 还差 {data['gap']}g 达到最低推荐量\n"
            elif status == '超标':
                report += f"- **超出**: 超过最高推荐量 {data['gap']}g\n"
        
        report += f"- **建议**: {suggestion}\n\n"
    
    # 综合评价
    report += "## 【综合评价】\n\n"
    
    # 统计各种状态的数量
    status_count = {'达标': 0, '不足': 0, '超标': 0, '未录入': 0}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        status = assessment[food_type]['status']
        status_count[status] = status_count.get(status, 0) + 1
    
    if status_count['达标'] == 4:
        report += "🎉 **优秀！** 所有食物类别摄入均符合推荐标准，请继续保持均衡饮食！\n\n"
    elif status_count['达标'] >= 2:
        report += "👍 **良好！** 大部分食物类别摄入合理，注意调整不足或超标的类别。\n\n"
    elif status_count['未录入'] > 0:
        report += "⚠️ **待完善** 部分食物类别尚未录入，建议补充完整以获得更准确的评估。\n\n"
    else:
        report += "💡 **需改进** 多数食物类别摄入不达标，建议参考下方健康提示进行调整。\n\n"
    
    # 健康提示
    report += "## 【健康提示】\n\n"
    
    tips = []
    if assessment['vegetables']['status'] == '不足':
        tips.append("🥬 蔬菜摄入不足可能缺乏膳食纤维和维生素，建议增加绿叶蔬菜摄入")
    if assessment['fruits']['status'] == '不足':
        tips.append("🍎 水果摄入不足可能缺乏维生素C，建议适量增加新鲜水果")
    if assessment['meat']['status'] == '超标':
        tips.append("🥩 肉类摄入过多可能增加脂肪摄入，建议减少红肉，增加鱼类和禽类")
    if assessment['eggs']['status'] == '超标':
        tips.append("🥚 蛋类摄入过多需注意胆固醇，建议控制每日蛋类摄入量")
    
    if not tips:
        tips.append("✨ 当前饮食结构较为合理，建议继续保持多样化饮食")
        tips.append("💧 别忘了每天喝足够的水（建议1500-2000ml）")
        tips.append("🏃 配合适量运动，效果更佳")
    
    for tip in tips:
        report += f"- {tip}\n"
    
    report += "\n---\n*本报告基于联合国WHO营养标准生成，仅供参考*"
    
    return report

def translate_suggestion_to_en(suggestion):
    """Translate Chinese suggestion to English"""
    # Simple translation mapping
    translations = {
        '建议增加': 'Recommend increasing',
        '摄入': 'intake',
        '当前': 'current',
        '还差': 'still need',
        '达到最低推荐量': 'to reach minimum recommendation',
        '建议减少': 'Recommend reducing',
        '已超过推荐最大值': 'exceeds maximum recommendation by',
        '摄入充足': 'Intake is sufficient',
        '请继续保持': 'please keep it up',
        '暂未录入': 'Not yet recorded',
        '如已摄入请补充录入': 'if consumed, please supplement the record',
        '摄入较少': 'Intake is relatively low',
        '建议适当增加': 'recommend适当增加',
        '摄入略多': 'Intake is slightly high',
        '建议后续餐次适当控制': 'recommend controlling in subsequent meals',
    }
    
    result = suggestion
    for cn, en in translations.items():
        result = result.replace(cn, en)
    
    return result

def nutrition_assessment(user_intake, population_group):
    """全维度营养健康评估引擎"""
    standard = get_nutrition_standard(population_group)
    if not standard:
        return {'error': f'未找到人群 {population_group} 的营养标准'}
    
    intake_to_chinese = {
        'vegetables': '蔬菜',
        'fruits': '水果',
        'meat': '肉类',
        'eggs': '蛋类'
    }
    
    food_types = ['vegetables', 'fruits', 'meat', 'eggs']
    recorded_foods = []
    for food_type in food_types:
        v = user_intake.get(food_type, 0)
        try:
            if int(v) > 0:
                recorded_foods.append(food_type)
        except (ValueError, TypeError):
            pass
    is_partial_entry = len(recorded_foods) < 4
    
    assessment = {}
    for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
        intake = user_intake.get(food_type, 0)
        recommendations = standard['daily_recommendations'].get(food_type, {})
        min_rec = recommendations.get('min', 0)
        max_rec = recommendations.get('max', 0)
        
        if is_partial_entry and intake == 0:
            assessment[food_type] = {
                'intake': intake,
                'status': '未录入',
                'gap': 0,
                'chinese_name': intake_to_chinese[food_type],
                'suggestion': f"暂未录入{intake_to_chinese[food_type]},如已摄入请补充录入"
            }
        elif intake < min_rec:
            status = "不足"
            gap = min_rec - intake
            suggestion = f"建议增加{intake_to_chinese[food_type]}摄入,当前{intake}g,距离推荐最小值还差{gap}g"
            if is_partial_entry:
                suggestion = f"{intake_to_chinese[food_type]}摄入较少({intake}g),建议适当增加"
        elif intake > max_rec:
            status = "超标"
            gap = intake - max_rec
            suggestion = f"建议减少{intake_to_chinese[food_type]}摄入,当前{intake}g,已超过推荐最大值{gap}g"
            if is_partial_entry:
                suggestion = f"{intake_to_chinese[food_type]}摄入略多({intake}g),建议后续餐次适当控制"
        else:
            status = "达标"
            gap = 0
            suggestion = f"{intake_to_chinese[food_type]}摄入充足({intake}g),请继续保持"
        
        assessment[food_type] = {
            'intake': intake,
            'status': status,
            'gap': gap,
            'chinese_name': intake_to_chinese[food_type],
            'suggestion': suggestion
        }
    
    return assessment

def generate_personalized_plan(user_intake, population_group, fridge_items=None, language='zh-CN'):
    """分人群差异化饮食方案生成"""
    assessment = nutrition_assessment(user_intake, population_group)
    
    population_info = {
        'adults': '成年人,需要均衡营养以维持身体机能',
        'children': '儿童,处于生长发育期,需要充足的蛋白质和钙质',
        'elderly': '老年人,消化吸收能力下降,需要易消化、高钙的食物'
    }
    
    population_info_en = {
        'adults': 'Adults, need balanced nutrition to maintain body functions',
        'children': 'Children, in growth and development stage, need sufficient protein and calcium',
        'elderly': 'Elderly, decreased digestive capacity, need easily digestible and high-calcium foods'
    }
    
    insufficient = [k for k, v in assessment.items() if v['status'] == '不足']
    excessive = [k for k, v in assessment.items() if v['status'] == '超标']
    
    if language == 'en-US':
        prompt = f"""You are a professional nutritionist. Please generate a personalized diet plan based on the following information:

【User Information】
- Population Group: {population_group} ({population_info_en.get(population_group, '')})
- Today's Intake: Vegetables {user_intake.get('vegetables', 0)}g, Fruits {user_intake.get('fruits', 0)}g, Meat {user_intake.get('meat', 0)}g, Eggs {user_intake.get('eggs', 0)}g

【Nutrition Assessment Results】
- Insufficient Intake: {', '.join(insufficient) if insufficient else 'None'}
- Excessive Intake: {', '.join(excessive) if excessive else 'None'}

【Task Requirements】
1. Analyze the special nutritional needs of this population group
2. Provide supplementation suggestions for insufficient intake items
3. Provide control suggestions for excessive intake items
4. Generate tomorrow's diet recommendations (specific dishes + ingredient amounts)
5. Consider the digestive characteristics of this group (elderly: soft food, children: fun food, adults: balanced food)

【Output Format】
## Nutrition Assessment Summary
## Improvement Suggestions (at least 3)
## Tomorrow's Recipe Recommendations (2-3 dishes)

【Reply Requirements】
- Concise and clear, focus on key points
- Use structured headings and lists
- Avoid lengthy explanations
- Keep each suggestion under 50 words

Please respond entirely in English."""
    else:
        prompt = f"""你是一位专业营养师,请根据以下信息生成个性化饮食方案:

【用户信息】
- 人群标签:{population_group}({population_info.get(population_group, '')})
- 今日摄入:蔬菜{user_intake.get('vegetables', 0)}g、水果{user_intake.get('fruits', 0)}g、肉类{user_intake.get('meat', 0)}g、蛋类{user_intake.get('eggs', 0)}g

【营养评估结果】
- 摄入不足:{', '.join(insufficient) if insufficient else '无'}
- 摄入超标:{', '.join(excessive) if excessive else '无'}

【任务要求】
1. 分析该人群的特殊营养需求
2. 针对摄入不足项给出补充建议
3. 针对摄入超标项给出控制建议
4. 生成明日饮食建议(具体菜品 + 食材用量)
5. 考虑该人群的消化特点(老年人软烂、儿童趣味、成年人均衡)

【输出格式】
## 营养评估总结
## 改善建议(至少 3 条)
## 明日食谱推荐(2-3 道菜)

【回复要求】
- 简洁明了，重点突出
- 使用结构化标题和列表
- 避免冗长解释
- 每条建议控制在50字以内"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败:{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成方案时出错:{str(e)}"

def generate_daily_recommendation(user_intake, population_group, fridge_items, language='zh-CN'):
    """基于现有食材 + 营养数据的每日饮食推荐"""
    assessment = nutrition_assessment(user_intake, population_group)
    
    recommended_ingredients = []
    for food_type, data in assessment.items():
        if data['status'] == '不足':
            recommended_ingredients.extend(fridge_items[:3])
    
    if not recommended_ingredients and fridge_items:
        recommended_ingredients = fridge_items[:3]
    
    ingredients_str = ", ".join([f"{item['name']}{item.get('quantity', '')}g" for item in recommended_ingredients])
    
    if language == 'en-US':
        prompt = f"""Please generate tonight's dinner recipes based on the following ingredients:

【Available Ingredients】{ingredients_str if ingredients_str else 'Common household ingredients'}
【User Group】{population_group}
【Nutrition Gaps】Key nutrients to supplement: {', '.join([assessment[k]['chinese_name'] for k, v in assessment.items() if v['status'] == '不足']) if any(v['status']=='不足' for v in assessment.values()) else 'Balanced nutrition'}

【Requirements】
1. Must fully use the above ingredients
2. Consider digestion characteristics for {population_group}
3. Output 2-3 dishes
4. Label nutritional supplement direction for each dish

【Output Format】
## Recommended Dishes (2-3)
## Required Ingredients
## Brief Steps
## Nutritional Benefits

【Reply Requirements】
- Concise and clear, focus on key points
- Use structured headings and lists
- Avoid lengthy explanations
- Keep each suggestion under 50 words

Please respond entirely in English."""
    else:
        prompt = f"""请根据以下食材生成今晚食谱:

【可用食材】{ingredients_str if ingredients_str else '家常食材'}
【用户人群】{population_group}
【营养缺口】需要重点补充:{', '.join([assessment[k]['chinese_name'] for k, v in assessment.items() if v['status'] == '不足']) if any(v['status']=='不足' for v in assessment.values()) else '营养均衡'}

【要求】
1. 必须完全使用上述食材
2. 考虑{population_group}的消化特点
3. 输出 2-3 道菜品
4. 标注每道菜的营养补充方向

【输出格式】
## 推荐菜品(2-3 道)
## 所需食材
## 简要步骤
## 营养功效

【回复要求】
- 简洁明了，重点突出
- 使用结构化标题和列表
- 避免冗长解释
- 每条建议控制在50字以内"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        if api_result['success']:
            return api_result['content']
        else:
            return f"AI 生成失败:{api_result.get('error', '未知错误')}"
    except Exception as e:
        return f"生成推荐时出错:{str(e)}"

def calculate_impact(ingredients, people_num=3, portion_coefficient=1.0):
    """计算环保影响"""
    total_portion = 0
    for ing in ingredients:
        ing_en = INGREDIENT_MAP.get(ing, ing.lower())
        
        if ing_en in BASE_PORTIONS:
            base = BASE_PORTIONS[ing_en]
            multiplier = MEAL_MULTIPLIERS['home'] * portion_coefficient
            total_portion += base * people_num * multiplier
        else:
            total_portion += 100 * people_num * portion_coefficient

    traditional_portion = total_portion * (1 + WASTE_RATIO)
    waste_reduced = traditional_portion - total_portion
    water_saved = waste_reduced * ENV_FACTORS['water_per_g']
    co2_reduced = waste_reduced * ENV_FACTORS['co2_per_g']

    return {
        'food_waste': round(waste_reduced, 2),
        'water': round(water_saved, 2),
        'carbon': round(co2_reduced, 2)
    }

# ====================== 多语言支持 ======================
def get_language_from_request():
    """从请求中获取语言设置，默认为中文"""
    try:
        data = request.get_json(silent=True)
        if data and 'language' in data:
            return data['language']
    except:
        pass
    return 'zh-CN'

def build_recipe_prompt(ingredients, people_num, meal_type, appetite, use_fridge, language='zh-CN'):
    """根据语言构建食谱生成 Prompt"""
    
    if language == 'en-US':
        # 英文 Prompt
        ingredients_str = ', '.join(ingredients)
        fridge_data = load_data().get('fridge_inventory', [])
        fridge_item_names = [item['name'] for item in fridge_data[:5]]
        fridge_str = ', '.join(fridge_item_names) if fridge_item_names else 'None'
        
        prompt = f"""Please generate a family-friendly eco-friendly recipe based on the following ingredients:
【Basic Information】
- Main ingredients: {ingredients_str}
- Fridge ingredients: {fridge_str}
- Number of people: {people_num}
- Appetite level: {appetite}

【⚠️ IMPORTANT PRINCIPLE: Reasonable combination, do not force mismatched ingredients!】
**This is the most important rule, please follow strictly:**
1. **If ingredients are not suitable to be mixed together, absolutely DO NOT force them into one dish!**
   - ❌ Wrong example: User inputs "milk, apple, egg" → Make "Milk Apple Scrambled Eggs" (disgusting!)
   - ✅ Correct example: User inputs "milk, apple, egg" → 
     * Breakfast Option 1: Boiled eggs with milk + fresh apple after meal
     * Breakfast Option 2: Steamed egg custard + warm milk + sliced apple
     * Breakfast Option 3: Apple milkshake + boiled egg
   
2. **Smart judgment of ingredient compatibility:**
   - 🥛 Beverages/Dairy (milk, soy milk, yogurt, etc.): Usually consumed separately or as drinks
   - 🍎 Fruits (apple, banana, orange, etc.): Usually eaten raw, in salads, or juiced, rarely stir-fried with meat
   - 🥚 Eggs: Can be scrambled, steamed, or boiled, but do not mix with fruits
   - 🥩 Meat + 🥬 Vegetables: Classic combination, can be cooked together
   - 🐟 Seafood + 🥬 Vegetables: Common combination
   - 🧀 Soy products + 🥬 Vegetables: Healthy combination
   
3. **Flexible dish organization:**
   - If ingredients are better consumed separately, design them as multiple independent dishes/drinks
   - For example: "milk, apple, egg" can be designed as:
     * Main dish: Steamed egg custard
     * Drink: Warm milk
     * Fruit: Sliced apple (after meal)
   
4. **Consider dining scenarios and time:**
   - Breakfast: Can be "main dish + drink + fruit" combination
   - Lunch/Dinner: Can be "main course + side dish + soup" combination
   - Snack: Can be individual fruit or drink

【Smart Dish Generation Rules】
1. **Prioritize user-input ingredients**:
   - ⭐ User-input ingredients ({ingredients_str}) must be the main ingredients
   - 🧊 Fridge ingredients ({fridge_str}) can be used as complementary or auxiliary ingredients
   - ✅ Each dish must clearly label which ingredients are 【User Input】 and which are 【Fridge Stock】

2. **Labeling format requirements**:
   In the 【Ingredients List】 of each dish, must label like this:
   - 【User Input】Main ingredient 1: xxx grams
   - 【Fridge Stock】Auxiliary: xxx grams
   
3. **If user inputs few ingredients**:
   - Can reasonably combine with common fridge ingredients
   - But must clearly label the source

4. **If user inputs many ingredients**:
   - Prioritize using user-input ingredients
   - Fridge ingredients as seasoning or side dishes

5. **Smartly decide number of dishes based on ingredient count**:
   - If user inputs ≤3 types of ingredients, can generate 1-2 dishes/drinks
   - If user inputs >3 types of ingredients, must generate multiple dishes (2-4), distribute ingredients reasonably across different dishes
   - **Key: Not all ingredients need to be mixed in one dish! Can handle separately based on ingredient characteristics**
   - Ensure all input ingredients are fully utilized to avoid waste

6. **Prioritize user-input ingredients as main ingredients**:
   - ⭐ **First priority**: User-input ingredients must be the **main ingredients** of each dish
   - ⭐ **Second priority**: Other auxiliary ingredients (onion, ginger, garlic, seasonings, side vegetables) are only supplements
   - ✅ Correct example: User inputs "potato, beef" → "Braised beef with potato" (both potato and beef are main ingredients)
   - ❌ Wrong example: User inputs "potato, beef" → "Stir-fried potato strips with green pepper" (green pepper is not user-input but becomes main ingredient)

7. **Reasonably combine ingredients, do not force same-type ingredients together**:
   - ❌ Wrong example: Stir-fry "potato, radish, winter melon, pumpkin" all in one dish (all vegetables, but unreasonable combination)
   - ✅ Correct example: "Braised beef with potato", "Shredded radish stir-fry", "Pumpkin scrambled eggs"
   - Each dish should contain different categories of ingredients (e.g., meat + vegetables, eggs + vegetables), nutritionally balanced

8. **Each dish must include the following complete structure**:
【Dish Name】xxx (should reflect "home-style" characteristic)
【Ingredient Category】xxx (e.g., Meat + Vegetables, Eggs + Soy Products, etc.)
【Ingredients List】
- Main ingredient 1: xxx grams (precise calculation, considering number of people and appetite level)
- Main ingredient 2: xxx grams
- Auxiliary: appropriate amount
【Cooking Steps】
Step 1: xxx
Step 2: xxx
Step 3: xxx
Step 4: xxx
Step 5: xxx
【Environmental Value】
- Estimated food waste reduced: xxx grams
- Estimated water saved: xxx liters
- Estimated carbon emissions reduced: xxx grams
- Environmental explanation: xxx

【General Requirements】
1. Identify the category of each ingredient (meat/vegetables/eggs/seafood/soy products, etc.) and provide specific cooking suggestions
2. Precisely calculate the amount (grams) of each ingredient, considering number of people and appetite level
3. Cooking steps should be detailed and clear (at least 5 steps)
4. **Important: Calculate environmental value data for each dish**
   - Food waste reduced (grams): Based on traditional practices would prepare 25% more food
   - Water saved (liters): Each gram of food consumes about 0.5 liters of water (China dietary weighted average)
   - Carbon emissions reduced (grams CO2e): Each gram of food emits about 0.003 grams CO2e (China dietary mixed average)

【Return Format Example】
If generating multiple dishes, list them sequentially in the following format:

=== Dish 1 ===
【Dish Name】xxx
【Ingredient Category】xxx
【Ingredients List】
- 【User Input】Main ingredient 1: xxx grams
- 【Fridge Stock】Auxiliary: xxx grams (if used)
【Cooking Steps】
Step 1: xxx
Step 2: xxx
Step 3: xxx
Step 4: xxx
Step 5: xxx
【Environmental Value】
- Estimated food waste reduced: xxx grams
- Estimated water saved: xxx liters
- Estimated carbon emissions reduced: xxx grams
- Environmental explanation: xxx

=== Dish 2 ===
...

Please respond entirely in English."""
    else:
        # 中文 Prompt (原有逻辑)
        if use_fridge and ingredients:
            fridge_data = load_data().get('fridge_inventory', [])
            fridge_item_names = [item['name'] for item in fridge_data[:5]]
            fridge_str = "、".join(fridge_item_names)
            
            prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{', '.join(ingredients)}
- 冰箱现有食材：{fridge_str}
- 就餐人数：{people_num}人
- 饭量系数：{appetite}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入“牛奶、苹果、鸡蛋”→ 做成“牛奶苹果炒鸡蛋”（非常恶心！）
   - ✅ 正确示例：用户输入“牛奶、苹果、鸡蛋”→ 
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
   - 例如：“牛奶、苹果、鸡蛋”可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者：“番茄、鸡蛋、面包”可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是“主食 + 饮品 + 水果”的组合
   - 午餐/晚餐：可以是“主菜 + 配菜 + 汤”的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **优先使用用户输入的食材**：
   - ⭐ 用户输入的食材（{', '.join(ingredients)}）必须作为主料
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
   - ✅ 正确示例：用户输入“土豆、牛肉”→ “土豆炖牛肉”（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入“土豆、牛肉”→ “青椒土豆丝”（青椒不是用户输入的，却成了主料）
   - 如果确实需要搭配其他食材，应该明确标注哪些是“主料”（用户输入的），哪些是“辅料”（额外搭配的）
   - 搭配的其他食材应该是常见的调味品或辅料（如葱姜蒜、酱油、盐等），而不是新的主菜食材

7. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把“土豆、萝卜、冬瓜、南瓜”全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例：“土豆炖牛肉”（土豆 + 肉类）、“清炒萝卜丝”（单独蔬菜）、“南瓜炒蛋”（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡
   - 如果同类型食材过多（如 3 种蔬菜），应该分成不同的菜品，不要全部堆在一起

8. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（要体现“家常”特色）
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
...

请用中文回答。"""
        else:
            # 不使用冰箱食材的情况
            prompt = f"""请根据以下食材生成家庭环保食谱：
【基本信息】
- 主要食材：{', '.join(ingredients)}
- 就餐人数：{people_num}人
- 饭量系数：{appetite}

【⚠️ 重要原则：合理搭配，不要硬凑！】
**这是最重要的规则，请务必遵守：**
1. **如果食材不适合混合在一起，绝对不要强行组合！**
   - ❌ 错误示例：用户输入“牛奶、苹果、鸡蛋”→ 做成“牛奶苹果炒鸡蛋”（非常恶心！）
   - ✅ 正确示例：用户输入“牛奶、苹果、鸡蛋”→ 
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
   - 例如：“牛奶、苹果、鸡蛋”可以设计为：
     * 主菜：蒸鸡蛋羹
     * 饮品：温牛奶
     * 水果：苹果切片（餐后食用）
   - 或者：“番茄、鸡蛋、面包”可以设计为：
     * 主菜：番茄炒蛋
     * 主食：烤面包片
   
4. **考虑用餐场景和时间：**
   - 早餐：可以是“主食 + 饮品 + 水果”的组合
   - 午餐/晚餐：可以是“主菜 + 配菜 + 汤”的组合
   - 加餐/零食：可以是单独的水果或饮品

【智能菜品生成规则】
1. **优先使用用户输入的食材**：
   - ⭐ 用户输入的食材（{', '.join(ingredients)}）必须作为主料
   - ✅ 每个菜品都必须以用户输入的食材为主料

2. **根据食材数量智能决定菜品数量**：
   - 如果用户输入的食材种类≤3 种，可以只生成 1-2 个菜品/饮品
   - 如果用户输入的食材种类>3 种，必须生成多个菜品（2-4 个），合理分配食材到不同菜品中
   - **关键：不是所有食材都要混在一个菜里！可以根据食材特性分开处理**
   - 确保所有输入的食材都被充分利用，避免浪费

3. **优先使用用户输入的食材作为主料**：
   - ⭐ **第一优先级**：用户输入的食材必须作为每个菜品的**主料**（主要食材）
   - ⭐ **第二优先级**：其他辅料（葱姜蒜、调味料、配菜等）仅作为辅助，不要喧宾夺主
   - ✅ 正确示例：用户输入“土豆、牛肉”→ “土豆炖牛肉”（土豆和牛肉都是主料）
   - ❌ 错误示例：用户输入“土豆、牛肉”→ “青椒土豆丝”（青椒不是用户输入的，却成了主料）

4. **合理搭配食材，不要硬凑同类型食材**：
   - ❌ 错误示例：把“土豆、萝卜、冬瓜、南瓜”全部炒在一个菜里（都是蔬菜，但搭配不合理）
   - ✅ 正确示例：“土豆炖牛肉”（土豆 + 肉类）、“清炒萝卜丝”（单独蔬菜）、“南瓜炒蛋”（南瓜 + 蛋类）
   - 每个菜品应该包含不同类别的食材（如：肉类 + 蔬菜、蛋类 + 蔬菜），营养均衡

5. **每个菜品都必须包含以下完整结构**：
   【菜名】xxx（要体现“家常”特色）
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
...

请用中文回答。"""
    
    return prompt

# ====================== Flask 路由 ======================
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/locales/<lang>.json')
def get_locale_file(lang):
    """提供语言文件"""
    from flask import send_from_directory
    try:
        return send_from_directory('locales', f'{lang}.json')
    except:
        # 降级到中文
        return send_from_directory('locales', 'zh-CN.json')

@app.route('/api/data', methods=['GET'])
def get_data():
    """获取用户数据"""
    data = load_data()
    
    # 🔑 关键修复：确保旧数据文件也包含 generation_count 字段
    if 'generation_count' not in data:
        data['generation_count'] = 0
        save_data(data)  # 立即保存，避免下次再检查
        print('🔧 [数据迁移] 已为旧数据添加 generation_count 字段')
    
    return jsonify({'success': True, 'data': data})

@app.route('/api/data', methods=['POST'])
def update_data():
    """更新用户数据"""
    new_data = request.json
    current_data = load_data()
    current_data.update(new_data)
    save_data(current_data)
    return jsonify({'success': True, 'data': current_data})

@app.route('/api/generate_recipe', methods=['POST'])
def generate_recipe():
    """生成智能食谱"""
    data = request.json
    custom_ingredients = data.get('custom_ingredients', '')
    people_num = data.get('people_num', 3)
    meal_type = data.get('meal_type', 'home')
    appetite = data.get('appetite', 1.0)
    use_fridge = data.get('use_fridge', False)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    # 解析食材
    ingredients = [i.strip() for i in custom_ingredients.split(',') if i.strip()]
    
    if use_fridge:
        fridge_data = load_data().get('fridge_inventory', [])
        fridge_ingredients = [item['name'] for item in fridge_data[:5]]
        ingredients.extend(fridge_ingredients)
    
    if not ingredients:
        error_msg = '请至少输入一种食材' if language == 'zh-CN' else 'Please enter at least one ingredient'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 使用多语言 Prompt 构建函数
    prompt = build_recipe_prompt(ingredients, people_num, meal_type, appetite, use_fridge, language)
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            # 计算环保影响
            impact = calculate_impact(ingredients, people_num, appetite)
            
            return jsonify({
                'success': True,
                'recipe': api_result['content'],
                'impact': impact
            })
        else:
            return jsonify({
                'success': False,
                'error': f"AI 生成失败:{api_result.get('error', '未知错误')}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': f'服务器错误:{str(e)}'})

@app.route('/api/nutrition_assess', methods=['POST'])
def nutrition_assess():
    """营养评估 - 返回格式化报告"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        # 检查是否为"以上皆是"模式
        if population_group == 'all':
            # 生成多人群对比报告
            report = generate_multi_group_nutrition_report(user_intake, language)
        else:
            # 生成单人群报告
            report = generate_nutrition_report(user_intake, population_group, language)
        
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/daily_recommendation', methods=['POST'])
def daily_recommendation():
    """每日饮食推荐"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    fridge_items = data.get('fridge_items', [])
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items, language)
        return jsonify({'success': True, 'recommendation': recommendation})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/personalized_plan', methods=['POST'])
def personalized_plan():
    """个性化饮食方案"""
    data = request.json
    user_intake = data.get('user_intake', {})
    population_group = data.get('population_group', 'adults')
    fridge_items = data.get('fridge_items', [])
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    try:
        plan = generate_personalized_plan(user_intake, population_group, fridge_items, language)
        return jsonify({'success': True, 'plan': plan})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save_intake', methods=['POST'])
def save_intake():
    """保存摄入数据"""
    data = request.json
    intake_record = {
        'date': get_china_time().strftime('%Y-%m-%d'),
        'time': get_china_time().strftime('%H:%M'),
        'vegetables': data.get('vegetables', 0),
        'fruits': data.get('fruits', 0),
        'meat': data.get('meat', 0),
        'eggs': data.get('eggs', 0)
    }
    
    current_data = load_data()
    if 'daily_intake_records' not in current_data:
        current_data['daily_intake_records'] = []
    
    current_data['daily_intake_records'].append(intake_record)
    
    # 关键修改：今日只保留最新3条记录，多余的移到历史
    today = get_china_time().strftime('%Y-%m-%d')
    all_records = current_data['daily_intake_records']
    today_records = [r for r in all_records if r.get('date') == today]
    
    if len(today_records) > 3:
        # 保留最新3条，删除最旧的
        records_to_remove = today_records[:-3]  # 除了最新3条外的所有记录
        for old_record in records_to_remove:
            all_records.remove(old_record)
            print(f"⚠️ 今日记录超过3条，已将旧记录移入历史: {old_record}")
        current_data['daily_intake_records'] = all_records
    
    save_data(current_data)
    
    # 检查是否需要预警
    population_group = current_data.get('population_group', 'adults')
    today_records = [r for r in current_data['daily_intake_records'] if r['date'] == intake_record['date']]
    
    print(f"\n📊 [save_intake] 今日记录数: {len(today_records)}")
    for i, r in enumerate(today_records):
        print(f"   记录{i+1}: 蔬菜{r.get('vegetables', 0)}g, 水果{r.get('fruits', 0)}g, 肉类{r.get('meat', 0)}g, 蛋类{r.get('eggs', 0)}g")
    
    # 汇总今日所有记录（最多3条）进行营养评估
    total_intake = {
        'vegetables': sum(r.get('vegetables', 0) for r in today_records),
        'fruits': sum(r.get('fruits', 0) for r in today_records),
        'meat': sum(r.get('meat', 0) for r in today_records),
        'eggs': sum(r.get('eggs', 0) for r in today_records)
    }
    
    print(f"📊 [save_intake] 今日总摄入: 蔬菜{total_intake['vegetables']}g, 水果{total_intake['fruits']}g, 肉类{total_intake['meat']}g, 蛋类{total_intake['eggs']}g")
    print(f"   📝 记录数: {len(today_records)}条 (早中晚三餐)\n")
    
    # 🆕 关键改进：基于联合国标准的智能预警（针对三餐总和）
    warnings = []
    standard = get_nutrition_standard(population_group)
    
    if standard:
        daily_recs = standard['daily_recommendations']
        
        # 检查蔬菜
        veg_rec = daily_recs.get('vegetables', {})
        veg_min = veg_rec.get('min', 400)
        veg_max = veg_rec.get('max', 800)
        if total_intake['vegetables'] < veg_min * 0.5:  # 低于50%推荐最小值
            warnings.append(f"🥬 蔬菜摄入严重不足（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议增加至{veg_min}g以上")
        elif total_intake['vegetables'] < veg_min:  # 低于推荐最小值
            warnings.append(f"🥬 蔬菜摄入略少（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议适当增加")
        elif total_intake['vegetables'] > veg_max:  # 超过推荐最大值
            warnings.append(f"⚠️ 蔬菜摄入超标（当前{total_intake['vegetables']}g，推荐{veg_min}-{veg_max}g/天），建议后续餐次控制")
        
        # 检查水果
        fruit_rec = daily_recs.get('fruits', {})
        fruit_min = fruit_rec.get('min', 200)
        fruit_max = fruit_rec.get('max', 400)
        if total_intake['fruits'] < fruit_min * 0.5:
            warnings.append(f"🍎 水果摄入严重不足（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议补充")
        elif total_intake['fruits'] < fruit_min:
            warnings.append(f"🍎 水果摄入略少（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议适当增加")
        elif total_intake['fruits'] > fruit_max:
            warnings.append(f"⚠️ 水果摄入超标（当前{total_intake['fruits']}g，推荐{fruit_min}-{fruit_max}g/天），建议控制")
        
        # 检查肉类
        meat_rec = daily_recs.get('meat', {})
        meat_min = meat_rec.get('min', 50)
        meat_max = meat_rec.get('max', 150)
        if total_intake['meat'] < meat_min * 0.5:
            warnings.append(f"🥩 肉类摄入严重不足（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议增加蛋白质")
        elif total_intake['meat'] < meat_min:
            warnings.append(f"🥩 肉类摄入略少（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议适当增加")
        elif total_intake['meat'] > meat_max:
            warnings.append(f"⚠️ 肉类摄入超标（当前{total_intake['meat']}g，推荐{meat_min}-{meat_max}g/天），建议减少红肉，增加鱼类")
        
        # 检查蛋类
        egg_rec = daily_recs.get('eggs', {})
        egg_min = egg_rec.get('min', 30)
        egg_max = egg_rec.get('max', 70)
        if total_intake['eggs'] < egg_min * 0.5:
            warnings.append(f"🥚 蛋类摄入严重不足（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议补充")
        elif total_intake['eggs'] < egg_min:
            warnings.append(f"🥚 蛋类摄入略少（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议适当增加")
        elif total_intake['eggs'] > egg_max:
            warnings.append(f"⚠️ 蛋类摄入超标（当前{total_intake['eggs']}g，推荐{egg_min}-{egg_max}g/天），建议控制")
    else:
        # 降级方案：使用简化的预警逻辑
        for food_type in ['vegetables', 'fruits', 'meat', 'eggs']:
            amount = intake_record.get(food_type, 0)
            if amount > 0:
                if food_type == 'meat' and total_intake['meat'] > 300:
                    warnings.append(f"⚠️ 肉类摄入偏高,建议减少红肉,增加鱼类")
                elif food_type == 'vegetables' and total_intake['vegetables'] < 100:
                    warnings.append(f"🥬 蔬菜摄入严重不足,建议增加至300g以上")
    
    return jsonify({
        'success': True,
        'warnings': warnings,
        'total_intake': total_intake
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """AI 对话助手"""
    data = request.json
    message = data.get('message', '')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        prompt = f"""You are a professional smart recipe assistant.

[Response Requirements]
- Be concise and clear, focus on key points only
- Avoid lengthy explanations and background introductions
- Use bullet points instead of long paragraphs
- Keep responses under 200 words
- Provide practical advice directly

User question: {message}

Please respond in a friendly and professional tone in English."""
    else:
        prompt = f"""你是一个专业的智能食谱助手。

【回复要求】
- 简洁明了，只回答重点内容
- 避免冗长的解释和背景介绍
- 使用要点列表而非长段落
- 控制在200字以内
- 直接给出实用建议

用户问题:{message}

请用友好、专业的语气回答。"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({'success': True, 'reply': api_result['content']})
        else:
            return jsonify({'success': False, 'error': f"AI 回复失败:{api_result.get('error', '未知错误')}"})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/fridge/add', methods=['POST'])
def add_fridge_item():
    """添加冰箱食材"""
    data = request.json
    item = {
        'name': data.get('name', ''),
        'quantity': data.get('quantity', 0),
        'unit': data.get('unit', 'g'),
        'expiry_date': data.get('expiry_date', ''),
        'added_date': get_china_time().strftime('%Y-%m-%d')
    }
    
    current_data = load_data()
    if 'fridge_inventory' not in current_data:
        current_data['fridge_inventory'] = []
    
    current_data['fridge_inventory'].append(item)
    save_data(current_data)
    
    return jsonify({'success': True, 'inventory': current_data['fridge_inventory']})

@app.route('/api/fridge/list', methods=['GET'])
def list_fridge_items():
    """列出冰箱食材"""
    current_data = load_data()
    inventory = current_data.get('fridge_inventory', [])
    return jsonify({'success': True, 'inventory': inventory})

@app.route('/api/fridge/delete/<int:index>', methods=['DELETE'])
def delete_fridge_item(index):
    """删除冰箱食材"""
    current_data = load_data()
    inventory = current_data.get('fridge_inventory', [])
    
    if 0 <= index < len(inventory):
        inventory.pop(index)
        current_data['fridge_inventory'] = inventory
        save_data(current_data)
        return jsonify({'success': True, 'inventory': inventory})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/edit/<int:index>', methods=['PUT'])
def edit_intake_record(index):
    """编辑摄入记录"""
    data = request.json
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        
        # 更新数据
        records[original_index]['vegetables'] = data.get('vegetables', records[original_index].get('vegetables', 0))
        records[original_index]['fruits'] = data.get('fruits', records[original_index].get('fruits', 0))
        records[original_index]['meat'] = data.get('meat', records[original_index].get('meat', 0))
        records[original_index]['eggs'] = data.get('eggs', records[original_index].get('eggs', 0))
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'records': records})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/delete/<int:index>', methods=['DELETE'])
def delete_intake_record(index):
    """删除摄入记录"""
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        records.pop(original_index)
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'records': records})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/update/<int:index>', methods=['PUT'])
def update_intake_record(index):
    """🆕 更新摄入记录 - 允许用户手动修改摄入量"""
    data = request.json
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 筛选今日记录
    today = get_china_time().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    if 0 <= index < len(today_records):
        # 找到原始记录在总列表中的位置
        original_index = records.index(today_records[index])
        
        # 更新数据
        records[original_index]['vegetables'] = data.get('vegetables', 0)
        records[original_index]['fruits'] = data.get('fruits', 0)
        records[original_index]['meat'] = data.get('meat', 0)
        records[original_index]['eggs'] = data.get('eggs', 0)
        
        print(f"\n✏️ [update_intake] 更新记录 {index}:")
        print(f"   蔬菜: {records[original_index]['vegetables']}g")
        print(f"   水果: {records[original_index]['fruits']}g")
        print(f"   肉类: {records[original_index]['meat']}g")
        print(f"   蛋类: {records[original_index]['eggs']}g")
        
        current_data['daily_intake_records'] = records
        save_data(current_data)
        
        return jsonify({'success': True, 'record': records[original_index]})
    else:
        return jsonify({'success': False, 'error': '索引无效'})

@app.route('/api/intake/history/7days', methods=['GET'])
def get_7days_history():
    """获取近7天摄入历史"""
    current_data = load_data()
    records = current_data.get('daily_intake_records', [])
    
    # 获取近7天的日期
    from datetime import timedelta
    today = get_china_time()
    dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    
    # 按日期分组统计
    history = []
    for date in dates:
        day_records = [r for r in records if r.get('date') == date]
        if day_records:
            total = {
                'date': date,
                'vegetables': sum(r.get('vegetables', 0) for r in day_records),
                'fruits': sum(r.get('fruits', 0) for r in day_records),
                'meat': sum(r.get('meat', 0) for r in day_records),
                'eggs': sum(r.get('eggs', 0) for r in day_records),
                'record_count': len(day_records)
            }
            history.append(total)
    
    return jsonify({'success': True, 'history': history})

@app.route('/api/food_weight/query', methods=['POST'])
def query_food_weight():
    """查询食材重量 - 优先使用本地数据库，未收录的调用AI"""
    data = request.json
    food_name = data.get('food_name', '').strip()
    
    if not food_name:
        return jsonify({'success': False, 'error': '请输入食材名称'})
    
    try:
        # 1. 优先从本地数据库查找
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_weight_database.json')
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                weight_db = json.load(f)
            
            # 在所有类别中搜索
            for category in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
                if food_name in weight_db.get(category, {}):
                    item = weight_db[category][food_name]
                    return jsonify({
                        'success': True,
                        'source': 'database',
                        'food_name': food_name,
                        'unit': item['unit'],
                        'weight_per_unit': item['weight_per_unit'],
                        'note': item['note'],
                        'estimated_weight': item['weight_per_unit']  # 默认按1个单位计算
                    })
        
        # 2. 数据库中未找到，调用AI估算
        prompt = f"""请提供以下常见食物的近似重量参考（帮助用户估算摄入量）：

食材名称：{food_name}

请以简洁的格式返回，例如：
- 1个中等大小的苹果 ≈ 200g
- 1碗米饭（标准碗）≈ 150g
- 1个鸡蛋 ≈ 50g
- 1片面包 ≈ 30g

如果是不常见的食材，请给出合理的估算。只返回重量信息，不要其他解释。"""
        
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            # 解析AI返回的结果，提取重量数值
            result_text = api_result['content']
            # 尝试提取数字（克数）
            import re
            numbers = re.findall(r'(\d+)\s*g', result_text)
            estimated_weight = int(numbers[0]) if numbers else 100  # 默认100g
            
            return jsonify({
                'success': True,
                'source': 'ai',
                'food_name': food_name,
                'ai_response': result_text,
                'estimated_weight': estimated_weight
            })
        else:
            return jsonify({'success': False, 'error': f"AI 查询失败:{api_result.get('error', '未知错误')}"})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/food_weight/batch_estimate', methods=['POST'])
def batch_estimate_food_weight():
    """批量估算食材重量 - 用于自动录入时调用
    
    ⚠️ 重要改进：让AI直接返回分类汇总后的总重量，而不是单个食材重量
    这样可以避免前端汇总时的误差，提高数据准确性
    """
    data = request.json
    ingredients = data.get('ingredients', [])  # 食材列表
    people_num = data.get('people_num', 1)  # 人数
    
    if not ingredients:
        return jsonify({'success': False, 'error': '请提供食材列表'})
    
    try:
        # 加载本地数据库（用于调试和回退）
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_weight_database.json')
        weight_db = {}
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                weight_db = json.load(f)
        
        print(f"\n📊 [batch_estimate] 开始处理 {len(ingredients)} 种食材，{people_num}人份")
        print(f"   食材列表: {', '.join(ingredients)}")
        
        # 构建Prompt，让AI直接返回分类汇总结果
        prompt = f"""你是一个专业的营养师和食材分析师。请分析以下食材清单，并计算每类食物的总重量。

【基本信息】
- 食材清单：{', '.join(ingredients)}
- 就餐人数：{people_num}人

【任务要求】
请将这些食材按以下6个类别进行分类，并计算每类的总重量（单位：克）：

1. vegetables（蔬菜类）：包括所有蔬菜（叶菜、根茎、瓜果类蔬菜）、菌菇、豆制品（豆腐、豆干等）
2. fruits（水果类）：包括所有新鲜水果（苹果、香蕉、橙子等）
3. meat（肉类）：包括猪牛羊肉、禽类（鸡鸭鹅）、水产海鲜（鱼虾蟹贝）、加工肉制品（香肠、腊肉等）
4. eggs（蛋类）：包括鸡蛋、鸭蛋、鹌鹑蛋等
5. grains（主食类）：包括米饭、面条、面包、馒头、粥等
6. dairy（乳制品）：包括牛奶、酸奶、奶酪、黄油等

【⚠️ 重要规则 - 必须严格遵守】
1. **肉类包含范围（非常重要）**：
   - ✅ 猪肉、牛肉、羊肉、鸡肉、鸭肉、鹅肉 → meat
   - ✅ 鱼肉、虾、蟹、贝类、鱿鱼、章鱼等海鲜 → meat
   - ✅ 香肠、腊肉、火腿、培根等加工肉 → meat
   - ❌ 豆制品（豆腐、豆干）不属于meat，属于vegetables
   
2. **蔬菜类包含范围**：
   - ✅ 叶菜类：白菜、菠菜、生菜、油麦菜等
   - ✅ 根茎类：土豆、胡萝卜、白萝卜、洋葱等
   - ✅ 瓜果类：番茄、黄瓜、茄子、青椒等
   - ✅ 菌菇类：香菇、金针菇、木耳等
   - ✅ 豆制品：豆腐、豆干、腐竹、豆浆等
   - ✅ 香菜、葱、姜、蒜等调味蔬菜
   
3. **水果类**：
   - ✅ 香蕉、苹果、橙子、葡萄、西瓜等所有新鲜水果
   - ❌ 番茄虽然是果实，但在营养学上归类为蔬菜
   
4. **重量计算原则**：
   - 参考常见食材的标准份量
   - 考虑{people_num}人份的总量
   - 例如：如果1人份羊肉约100g，那么{people_num}人份就是{people_num * 100}g
   - 例如：如果1人份香蕉约150g，那么{people_num}人份就是{people_num * 150}g
   
5. **只返回JSON格式**，不要其他解释

【输出格式】
请严格按以下JSON格式返回：
{{
  "vegetables": 数字（总克数）,
  "fruits": 数字（总克数）,
  "meat": 数字（总克数）,
  "eggs": 数字（总克数）,
  "grains": 数字（总克数）,
  "dairy": 数字（总克数）
}}

【示例1 - 含肉类和蔬菜】
输入：羊排 200g, 香菜 50g, 白菜 150g
输出：{{"vegetables": 200, "fruits": 0, "meat": 200, "eggs": 0, "grains": 0, "dairy": 0}}
说明：羊排→meat 200g, 香菜+白菜→vegetables 200g

【示例2 - 含水果】
输入：香蕉 2根, 苹果 1个
输出：{{"vegetables": 0, "fruits": 350, "meat": 0, "eggs": 0, "grains": 0, "dairy": 0}}
说明：香蕉+苹果→fruits 350g（假设1根香蕉150g，1个苹果200g）

【示例3 - 混合食材】
输入：牛肉 150g, 番茄 200g, 土豆 150g, 米饭 2碗
输出：{{"vegetables": 350, "fruits": 0, "meat": 150, "eggs": 0, "grains": 300, "dairy": 0}}
说明：番茄+土豆→vegetables 350g, 牛肉→meat 150g, 米饭→grains 300g

现在请分析以下食材：{', '.join(ingredients)}（{people_num}人份）
只返回JSON，不要其他内容。"""
        
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            import re
            import json as json_module
            
            print(f"   🤖 AI响应: {api_result['content'][:200]}...")
            
            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', api_result['content'], re.DOTALL)
                if json_match:
                    ai_result = json_module.loads(json_match.group())
                    
                    # 验证返回的数据结构
                    required_keys = ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']
                    if all(key in ai_result for key in required_keys):
                        print(f"   ✅ AI返回的分类汇总数据:")
                        print(f"      蔬菜: {ai_result['vegetables']}g")
                        print(f"      水果: {ai_result['fruits']}g")
                        print(f"      肉类: {ai_result['meat']}g")
                        print(f"      蛋类: {ai_result['eggs']}g")
                        print(f"      主食: {ai_result['grains']}g")
                        print(f"      乳制品: {ai_result['dairy']}g")
                        
                        # 构造详细的食材明细（用于调试）
                        detailed_results = []
                        for ingredient in ingredients:
                            ingredient = ingredient.strip()
                            if not ingredient:
                                continue
                            
                            # 尝试从数据库或INGREDIENT_MAP找到类别
                            category = 'unknown'
                            weight = 0
                            
                            # 检查数据库
                            for cat in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
                                if ingredient in weight_db.get(cat, {}):
                                    category = cat
                                    weight = weight_db[cat][ingredient]['weight_per_unit']
                                    break
                            
                            # 检查INGREDIENT_MAP
                            if category == 'unknown' and ingredient in INGREDIENT_MAP:
                                mapped = INGREDIENT_MAP[ingredient]
                                if mapped in ['tomato', 'potato', 'tofu', 'bean_sprout']:
                                    category = 'vegetables'
                                elif mapped in ['fish', 'chicken', 'beef']:
                                    category = 'meat'
                                elif mapped == 'egg':
                                    category = 'eggs'
                            
                            detailed_results.append({
                                'ingredient': ingredient,
                                'source': 'database' if weight > 0 else 'ai_estimated',
                                'category': category,
                                'estimated_weight': weight if weight > 0 else 100
                            })
                        
                        return jsonify({
                            'success': True,
                            'results': detailed_results,  # 保留详细列表用于调试
                            'total_count': len(detailed_results),
                            'db_count': sum(1 for r in detailed_results if r['source'] == 'database'),
                            'ai_count': sum(1 for r in detailed_results if r['source'] == 'ai_estimated'),
                            # 关键：返回分类汇总的总重量
                            'category_totals': {
                                'vegetables': ai_result['vegetables'],
                                'fruits': ai_result['fruits'],
                                'meat': ai_result['meat'],
                                'eggs': ai_result['eggs'],
                                'grains': ai_result['grains'],
                                'dairy': ai_result['dairy']
                            }
                        })
                    else:
                        print(f"   ❌ AI返回的JSON缺少必要字段")
                        raise ValueError("JSON格式不完整")
                else:
                    print(f"   ❌ 未找到JSON格式")
                    raise ValueError("无法解析JSON")
            except Exception as e:
                print(f"   ❌ JSON解析失败: {e}")
                # 降级到旧方法
                return _fallback_batch_estimate(ingredients, people_num, weight_db)
        else:
            print(f"   ❌ AI调用失败: {api_result.get('error')}")
            return _fallback_batch_estimate(ingredients, people_num, weight_db)
        
    except Exception as e:
        print(f"   ❌ 批量估算异常: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


def _fallback_batch_estimate(ingredients, people_num, weight_db):
    """降级方案：使用数据库+INGREDIENT_MAP进行估算"""
    print(f"   🔄 使用降级方案估算食材重量")
    
    results = []
    category_totals = {
        'vegetables': 0,
        'fruits': 0,
        'meat': 0,
        'eggs': 0,
        'grains': 0,
        'dairy': 0
    }
    
    for ingredient in ingredients:
        ingredient = ingredient.strip()
        if not ingredient:
            continue
        
        found = False
        # 检查数据库
        for category in ['vegetables', 'fruits', 'meat', 'eggs', 'grains', 'dairy']:
            if ingredient in weight_db.get(category, {}):
                item = weight_db[category][ingredient]
                weight = item['weight_per_unit'] * people_num  # 乘以人数
                category_totals[category] += weight
                results.append({
                    'ingredient': ingredient,
                    'source': 'database',
                    'category': category,
                    'estimated_weight': weight
                })
                print(f"      📊 {ingredient} → {category}: {weight}g (数据库)")
                found = True
                break
        
        # 检查INGREDIENT_MAP
        if not found and ingredient in INGREDIENT_MAP:
            mapped = INGREDIENT_MAP[ingredient]
            if mapped in ['tomato', 'potato', 'tofu', 'bean_sprout']:
                category = 'vegetables'
                weight = 150 * people_num
            elif mapped in ['fish', 'chicken', 'beef']:
                category = 'meat'
                weight = 120 * people_num
            elif mapped == 'egg':
                category = 'eggs'
                weight = 50 * people_num
            else:
                category = 'vegetables'
                weight = 100 * people_num
            
            category_totals[category] += weight
            results.append({
                'ingredient': ingredient,
                'source': 'map_fallback',
                'category': category,
                'estimated_weight': weight
            })
            print(f"      📊 {ingredient} → {category}: {weight}g (映射表)")
            found = True
        
        # 默认值
        if not found:
            # 根据关键词猜测类别
            if any(kw in ingredient for kw in ['菜', '瓜', '菇', '豆', '萝卜']):
                category = 'vegetables'
                weight = 150 * people_num
            elif any(kw in ingredient for kw in ['苹果', '香蕉', '梨', '桃', '葡萄']):
                category = 'fruits'
                weight = 150 * people_num
            elif any(kw in ingredient for kw in ['猪', '牛', '羊', '鸡', '鸭', '鱼', '肉']):
                category = 'meat'
                weight = 120 * people_num
            elif '蛋' in ingredient:
                category = 'eggs'
                weight = 50 * people_num
            else:
                category = 'vegetables'
                weight = 100 * people_num
            
            category_totals[category] += weight
            results.append({
                'ingredient': ingredient,
                'source': 'keyword_guess',
                'category': category,
                'estimated_weight': weight
            })
            print(f"      📊 {ingredient} → {category}: {weight}g (关键词猜测)")
    
    print(f"   ✅ 降级方案完成，分类汇总:")
    print(f"      蔬菜: {category_totals['vegetables']}g")
    print(f"      水果: {category_totals['fruits']}g")
    print(f"      肉类: {category_totals['meat']}g")
    print(f"      蛋类: {category_totals['eggs']}g")
    
    return jsonify({
        'success': True,
        'results': results,
        'total_count': len(results),
        'db_count': sum(1 for r in results if r['source'] == 'database'),
        'ai_count': sum(1 for r in results if r['source'] != 'database'),
        'category_totals': category_totals
    })

@app.route('/api/generate_shopping_list', methods=['POST'])
def generate_shopping_list():
    """生成智能采购清单"""
    data = request.json
    dishes = data.get('dishes', '')
    people_num = data.get('people_num', 3)
    include_budget = data.get('include_budget', True)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    if not dishes:
        error_msg = '请输入想吃的菜品' if language == 'zh-CN' else 'Please enter dish names'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        budget_instruction = "\n6. 💰 **Budget Estimation**: Estimate the price for each ingredient (RMB) and calculate the total amount" if include_budget else ""
        
        prompt = f"""Please generate a detailed shopping list for the following dishes for [{people_num} servings]:

[Dishes to Cook] {dishes}

Please generate a complete shopping list including:

1️⃣ **Categorized by Supermarket Sections**
- 🥬 Vegetables Section: xxx
- 🥩 Meat Section: xxx
- 🐟 Seafood Section: xxx
- 🍞 Grains & Oils Section: xxx
- 🧂 Condiments Section: xxx
- 🥛 Dairy Section: xxx
- ❄️ Frozen Foods Section: xxx

2️⃣ **Precise Quantities** (considering {people_num} servings)
- Label specific quantities for each ingredient (grams/pieces/ml)
- Provide suggested amounts for seasonings

3️⃣ **Selection Tips**
- How to choose fresh ingredients
- Precautions

4️⃣ **Storage Recommendations**
- Which ingredients need refrigeration
- Shelf life reminders

5️⃣ **Alternatives**
- What are the substitutes if certain ingredients are unavailable{budget_instruction}

Please present in a clear table or list format for easy use while shopping.

Please respond entirely in English."""
    else:
        budget_instruction = "\n6. 💰 **预算估算**：为每种食材估算价格（人民币），并计算总金额" if include_budget else ""
        
        prompt = f"""请为以下【{people_num}人份】的菜品生成详细的采购清单：

【想吃的菜品】{dishes}

请生成完整的购物清单，包含以下内容：

1️⃣ **按超市区域分类**
- 🥬 蔬菜区：xxx
- 🥩 肉类区：xxx
- 🐟 水产区：xxx
- 🍞 粮油副食区：xxx
- 🧂 调味品区：xxx
- 🥛 乳制品区：xxx
- ❄️ 冷冻食品区：xxx

2️⃣ **精确用量**（考虑{people_num}人份）
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
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({'success': True, 'shopping_list': api_result['content']})
        else:
            return jsonify({'success': False, 'error': f"AI 生成失败:{api_result.get('error', '未知错误')}"})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate_daily_recommendation', methods=['POST'])
def generate_daily_recommendation_route():
    """生成今日饮食推荐"""
    current_data = load_data()
    population_group = current_data.get('population_group', 'adults')
    fridge_items = current_data.get('fridge_inventory', [])
    
    # 🌐 从请求中获取语言设置
    language = request.json.get('language', 'zh-CN') if request.is_json else 'zh-CN'
    
    # 获取用户今日总摄入数据
    today = get_china_time().strftime('%Y-%m-%d')
    all_records = current_data.get('daily_intake_records', [])
    today_records = [r for r in all_records if r.get('date') == today]
    
    if today_records:
        # 关键修复：只汇总最新的3条记录（三餐），而不是全部5条
        latest_3_records = today_records[-3:] if len(today_records) > 3 else today_records
        user_intake = {
            'vegetables': sum(r.get('vegetables', 0) for r in latest_3_records),
            'fruits': sum(r.get('fruits', 0) for r in latest_3_records),
            'meat': sum(r.get('meat', 0) for r in latest_3_records),
            'eggs': sum(r.get('eggs', 0) for r in latest_3_records)
        }
    else:
        user_intake = {'vegetables': 0, 'fruits': 0, 'meat': 0, 'eggs': 0}
    
    try:
        # 检查是否为"以上皆是"模式
        if population_group == 'all':
            # 为所有人群生成推荐
            groups = ['adults', 'teens', 'children', 'elderly']
                    
            # 🌐 根据语言设置人群名称
            if language == 'en-US':
                group_names = {
                    'adults': 'Adults',
                    'teens': 'Teens',
                    'children': 'Children',
                    'elderly': 'Elderly'
                }
            else:
                group_names = {
                    'adults': '成年人',
                    'teens': '青少年',
                    'children': '儿童',
                    'elderly': '老年人'
                }
                        
            recommendations = {}
            for group in groups:
                rec = generate_daily_recommendation(user_intake, group, fridge_items, language)
                recommendations[group_names[group]] = rec
                
            return jsonify({
                'success': True, 
                'recommendation': recommendations,
                'is_multi_group': True,
                'user_intake': user_intake
            })
        else:
            recommendation = generate_daily_recommendation(user_intake, population_group, fridge_items, language)
            return jsonify({'success': True, 'recommendation': recommendation, 'is_multi_group': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/image_recognize', methods=['POST'])
def image_recognize():
    """拍照识菜 - 图像识别食材"""
    data = request.json
    image_base64 = data.get('image_base64', '')
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    if not image_base64:
        return jsonify({'success': False, 'error': '请上传图片'})
    
    try:
        import base64
        from PIL import Image
        import io
        
        # 解码 base64 图片
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        # 压缩图片（减少网络传输）
        max_size = 800
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # 转换为 JPEG 并重新编码为 base64
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='JPEG', quality=85, optimize=True)
        image_bytes.seek(0)
        compressed_base64 = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
        
        # 调用智谱 AI GLM-4V-Flash 视觉模型
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 🌐 根据语言设置 AI 提示词
        if language == 'en-US':
            prompt_text = """Please identify the food ingredients in this image.

【Important Requirements】
1. Only list specific ingredient names (e.g., tomato, egg, bell pepper, beef)
2. Separate with English commas (,)
3. No descriptive language, don't say 'I see', 'the image contains', etc.
4. If it's a dish, list main ingredients, not dish name
5. When uncertain, give the most likely ingredient name
6. List each ingredient separately, don't combine (e.g., 'potato,beef' not 'potato beef stew')
7. If no obvious ingredients in image, return 'Cannot identify'

【Common Ingredient Examples】
- Vegetables: cabbage, spinach, lettuce, tomato, cucumber, eggplant, bell pepper, onion, potato, carrot
- Meat: pork, beef, lamb, chicken, duck, fish, shrimp, crab
- Eggs: chicken egg, duck egg
- Fruits: apple, banana, orange, grape
- Others: tofu, dried tofu, mushroom, wood ear mushroom

Please return the ingredient list directly, for example:
tomato,egg,bell pepper"""
        else:  # zh-CN
            prompt_text = """请识别这张图片中的食材。

【重要要求】
1. 只列出具体的食材名称（如：西红柿、鸡蛋、青椒、牛肉）
2. 用英文逗号分隔（,）
3. 不要描述性语言，不要说'我看到'、'图片中有'等
4. 如果是菜品，列出主要食材而不是菜名
5. 不确定时给出最可能的食材名称
6. 每个食材单独列出，不要组合（例如：'土豆,牛肉'而不是'土豆炖牛肉'）
7. 如果图片中没有明显食材，返回'无法识别'

【常见食材示例】
- 蔬菜类：白菜、菠菜、生菜、番茄、黄瓜、茄子、青椒、洋葱、土豆、胡萝卜
- 肉类：猪肉、牛肉、羊肉、鸡肉、鸭肉、鱼肉、虾、蟹
- 蛋类：鸡蛋、鸭蛋
- 水果类：苹果、香蕉、橙子、葡萄
- 其他：豆腐、豆干、蘑菇、木耳

请直接返回食材列表，例如：
西红柿,鸡蛋,青椒"""
        
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
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "max_tokens": 200,
            "temperature": 0.3
        }
        
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            ingredients_text = result['choices'][0]['message']['content']
            
            print(f"\n📸 [image_recognize] AI识别结果:")
            print(f"   原始文本: {ingredients_text}")
            print(f"   长度: {len(ingredients_text)} 字符\n")
            
            return jsonify({
                'success': True,
                'ingredients': ingredients_text
            })
        else:
            error_msg = f"API 调用失败：{response.status_code}"
            if response.status_code == 401:
                error_msg += "\n智谱 AI API 密钥无效或已过期"
            elif response.status_code == 429:
                error_msg += "\n请求过于频繁，请稍后再试"
            
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'识别失败：{str(e)}'})

@app.route('/api/analyze_nutrition', methods=['POST'])
def analyze_nutrition():
    """AI 营养分析 - 分析食材/食谱的营养成分"""
    data = request.json
    food_input = data.get('food_input', '').strip()
    people = data.get('people', 3)
    language = data.get('language', 'zh-CN')  # 🌐 获取语言设置
    
    if not food_input:
        error_msg = '请输入食材或食谱名称' if language == 'zh-CN' else 'Please enter food or recipe name'
        return jsonify({'success': False, 'error': error_msg})
    
    # 🌐 根据语言构建Prompt
    if language == 'en-US':
        prompt = f"""Please provide a professional nutritional analysis for the following ingredients/recipe for [{people} servings]:

[Food/Recipe] {food_input}

[⚠️ IMPORTANT PRINCIPLE: Smart Recognition of Ingredient Combinations]
**Before analyzing, please determine how to interpret the user's input:**

1. **If the user inputs multiple independent dishes** (separated by commas):
   - Example: "Braised Beef with Potato, Tomato Scrambled Eggs, Rice"
   - Approach: Analyze each dish separately, then provide overall nutritional assessment
   
2. **If the user inputs multiple ingredients without specifying preparation**:
   - Example: "Milk, Apple, Egg"
   - ❌ Wrong approach: Assume these ingredients are made into one dish (like "Milk Apple Scrambled Eggs")
   - ✅ Correct approach:
     * Option A: Assume this is a breakfast combination → Analyze "Warm Milk", "Fresh Apple", "Boiled Egg" separately
     * Option B: Ask the user about the specific preparation method
     * Option C: Provide several reasonable consumption methods with their nutritional analysis
   
3. **If the user inputs a single dish**:
   - Example: "Braised Beef with Potato"
   - Approach: Directly analyze the nutritional composition of this dish

[Analysis Requirements]
Please analyze in detail (per serving) according to the following structure:

📋 **Step 1: Ingredient Combination Interpretation**
- Explain how you understand the user's input ingredients/dishes
- If multiple ingredients, explain their reasonable consumption methods
- If ambiguous, provide 2-3 possible interpretations

1️⃣ **Basic Nutritional Data** (Precise Calculation)
- Total Calories: XXX kcal
- Protein: XX g
- Fat: XX g
- Carbohydrates: XX g
- Dietary Fiber: XX g

2️⃣ **Micronutrients** (Estimate)
- Vitamin A: XX μg
- Vitamin C: XX mg
- Calcium: XX mg
- Iron: XX mg
- Potassium: XX mg

3️⃣ **Nutritional Balance Assessment**
- Protein Source: High Quality/Average/Insufficient
- Fat Type: Saturated/Unsaturated Ratio
- Carbohydrate Type: Simple/Complex Carbs
- Overall Evaluation: Excellent/Good/Needs Improvement

4️⃣ **Health Recommendations**
- Suitable for: xxx
- Consumption Advice: xxx
- Pairing Suggestions: xxx
- Precautions: xxx

5️⃣ **Special Labels** (if applicable)
- High Protein: ✅ / ❌ (Mark ✅ only if protein content is actually high)
- Low Fat: ✅ / ❌ (Mark ✅ only if fat content is below normal level)
- Low Carb: ✅ / ❌ (Mark ✅ only if carb content is below normal level)
- High Fiber: ✅ / ❌ (Mark ✅ only if fiber content is above normal level)
- Rich in Vitamins: ✅ / ❌ (Mark ✅ only if vitamin content is actually high)

Please present in a clear format with scientifically sound data. **If the ingredient combination is unreasonable, please point it out clearly and provide improvement suggestions!

⚠️ IMPORTANT: Special labels must be objectively marked based on actual nutritional content. Only use ✅ or ❌, do not use [ ] or other symbols!**

Please respond entirely in English."""
    else:
        # 中文 Prompt (原有逻辑)
        prompt = f"""请对以下【{people}人份】的食材/食谱进行专业营养分析：

【食材/食谱】{food_input}

【⚠️ 重要原则：智能识别食材组合方式】
**在分析前，请先判断用户输入的食材应该如何理解：**

1. **如果用户输入的是多道独立的菜品**（用顿号、逗号分隔）：
   - 示例：“土豆炖牛肉、西红柿炒鸡蛋、米饭”
   - 处理方式：分别分析每道菜，然后给出整体营养评估
   
2. **如果用户输入的是多种食材但未说明做法**：
   - 示例：“牛奶、苹果、鸡蛋”
   - ❌ 错误做法：假设这些食材被做成一道菜（如“牛奶苹果炒鸡蛋”）
   - ✅ 正确做法：
     * 方案A：假设这是早餐组合 → 分别分析“温牛奶”、“新鲜苹果”、“水煮蛋”
     * 方案B：询问用户这些食材的具体做法
     * 方案C：给出几种合理的食用方式及其营养分析
   
3. **如果用户输入的是单一菜品**：
   - 示例：“土豆炖牛肉”
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
- 高蛋白：✅ / ❌ （根据实际营养成分标注，只有符合才算）
- 低脂肪：✅ / ❌ （脂肪含量低于正常水平标✅，否则标❌）
- 低碳水：✅ / ❌ （碳水含量低于正常水平标✅，否则标❌）
- 高纤维：✅ / ❌ （纤维含量高于正常水平标✅，否则标❌）
- 富含维生素：✅ / ❌ （维生素含量高标✅，否则标❌）

请用清晰格式呈现，数据要科学合理。**如果食材组合不合理，请明确指出并给出改进建议！

⚠️ 重要：特殊标签必须根据实际情况客观标注，只能使用✅或❌，不要使用[ ]或其他符号！**"""
    
    try:
        api_result = call_ai_api(prompt, api_type="auto")
        
        if api_result['success']:
            return jsonify({
                'success': True,
                'analysis': api_result['content']
            })
        else:
            return jsonify({
                'success': False,
                'error': f"AI 分析失败：{api_result.get('error', '未知错误')}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/voice_recognize', methods=['POST'])
def voice_recognize():
    """语音识别 - 将音频转换为文字（使用智谱GLM-ASR API）"""
    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': '未找到音频文件'})
    
    audio_file = request.files['audio']
    
    try:
        # 读取音频文件
        audio_data = audio_file.read()
        
        # 检查文件大小（限制25MB）
        if len(audio_data) > 25 * 1024 * 1024:
            return jsonify({'success': False, 'error': '音频文件过大，请录制不超过25MB的音频'})
        
        # 调用智谱语音识别API（使用multipart/form-data方式）
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}"
        }
        
        # 构建multipart/form-data请求
        files = {
            'file': ('recording.wav', audio_data, 'audio/wav')
        }
        
        # 🌐 从请求中获取语言设置（默认为auto自动检测）
        language = request.form.get('language', 'auto')
        
        data = {
            'model': 'glm-asr-2512',
            'stream': 'false'
        }
        
        # 如果指定了语言，添加到请求中
        if language in ['zh', 'en']:
            data['language'] = language
        
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '')
            
            return jsonify({
                'success': True,
                'text': text
            })
        else:
            error_msg = f"API调用失败：{response.status_code}"
            if response.status_code == 401:
                error_msg += "\n智谱AI API密钥无效"
            elif response.status_code == 400:
                error_msg += "\n请求参数错误，请检查音频格式"
            elif response.status_code == 429:
                error_msg += "\n请求过于频繁，请稍后再试"
            
            # 尝试获取详细错误信息
            try:
                error_detail = response.json()
                if 'error' in error_detail:
                    error_msg += f"\n详细信息：{error_detail['error']}"
            except:
                pass
            
            return jsonify({'success': False, 'error': error_msg})
            
    except Exception as e:
        error_msg = str(e)
        if "RequestError" in error_msg or "connection" in error_msg.lower():
            return jsonify({'success': False, 'error': '网络连接失败，请检查网络后重试'})
        else:
            return jsonify({'success': False, 'error': f'识别失败：{error_msg}'})

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🍽️  FoodGuardian AI v2.0 - 智能食谱助手 (Web版)")
    print("="*70)
    print("\n✨ 功能特性:")
    print("   • 智能食谱生成 - 基于AI的个性化菜谱推荐")
    print("   • 营养分析评估 - 联合国营养标准对照")
    print("   • 冰箱库存管理 - 智能食材搭配建议")
    print("   • 环保价值计算 - 量化食物浪费减少")
    print("   • 拍照识菜功能 - 图像识别食材")
    print("   • 语音交互支持 - 语音输入与识别（智谱免费GLM-ASR）")
    print("   • 采购清单生成 - 智能购物建议")
    print("\n🎨 UI设计:")
    print("   • 温暖棕色系配色方案")
    print("   • iOS风格毛玻璃效果")
    print("   • 流畅动画过渡")
    print("   • 响应式布局设计")
    print("\n📱 正在启动服务器...")
    print("🌐 访问地址: http://localhost:5000")
    print("💡 按 Ctrl+C 停止服务器\n")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
