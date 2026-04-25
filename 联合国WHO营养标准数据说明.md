# 联合国WHO营养标准数据文件

## 📄 文件说明

**文件名**: `un_nutrition_standards.json`  
**位置**: 项目根目录  
**用途**: 提供基于联合国世界卫生组织(WHO)标准的营养评估数据

---

## 🌍 数据来源

本数据文件基于 **联合国世界卫生组织 (UN WHO)** 的营养指南标准，为不同人群提供科学的营养摄入参考值。

### 权威性与科学性

- ✅ 基于WHO官方营养指南
- ✅ 覆盖全年龄段人群
- ✅ 定期更新以符合最新科学研究
- ✅ 国际公认的营养评估标准

---

## 👥 覆盖人群

数据文件包含以下4类人群的营养标准：

### 1. 成人 (Adults: 18-60岁)
- 日常营养需求基准
- 工作人群的健康标准

### 2. 青少年 (Teens: 13-17岁)
- 生长发育期特殊需求
- 高能量、高蛋白要求

### 3. 儿童 (Children: 6-12岁)
- 成长发育关键期
- 均衡营养的重要性

### 4. 老年人 (Elderly: 60+岁)
- 代谢减缓期的营养调整
- 预防慢性病的饮食建议

---

## 🌱 环保数据计算公式

### 数据来源

环保数据基于**中国膳食加权平均**的环境影响因子，参考《中国居民膳食指南》和生命周期评估（LCA）研究。

### 核心公式

```python
# 1. 计算精确份量（基于食材类型和用餐人数）
total_portion = Σ(食材基础份量 × 人数 × 饭量系数)

# 2. 计算传统做法的浪费量
traditional_portion = total_portion × (1 + WASTE_RATIO)
# WASTE_RATIO = 0.25（传统做法多准备25%的食物）

# 3. 计算减少的食物浪费
waste_reduced = traditional_portion - total_portion

# 4. 计算节约的水资源
water_saved = waste_reduced × ENV_FACTORS['water_per_g']
# water_per_g = 0.5（每克食物约消耗0.5升水，中国膳食加权平均）

# 5. 计算减少的碳排放
co2_reduced = waste_reduced × ENV_FACTORS['co2_per_g']
# co2_per_g = 0.003（每克食物约排放0.003克CO2e，中国膳食混合平均）
```

### 环保因子参数

| 参数 | 数值 | 单位 | 说明 |
|------|------|------|------|
| `WASTE_RATIO` | 0.25 | - | 传统做法多准备25%的食物 |
| `water_per_g` | 0.5 | 升/克 | 每克食物的水足迹（中国膳食加权平均） |
| `co2_per_g` | 0.003 | 克CO2e/克 | 每克食物的碳排放（中国膳食混合平均） |

### 食材基础份量参考

| 食材类型 | 基础份量 | 单位 | 说明 |
|----------|----------|------|------|
| 番茄/西红柿 | 80 | g | 蔬菜类代表 |
| 鸡肉/鸡胸肉 | 120 | g | 禽肉类代表 |
| 土豆/马铃薯 | 90 | g | 根茎类代表 |
| 鸡蛋/蛋 | 60 | g | 蛋类代表 |
| 牛肉/猪肉/羊肉 | 130 | g | 红肉类代表 |
| 鱼/鱼类/虾 | 110 | g | 水产类代表 |
| 其他未识别食材 | 100 | g | 默认值 |

### 饭量系数

| 饭量类型 | 系数 | 说明 |
|----------|------|------|
| 家常 (home) | 1.0 | 标准份量 |
| 健康 (healthy) | 0.9 | 减少10%（低脂低卡） |
| 素食 (vegetarian) | 0.85 | 减少15%（植物为主） |
| 聚餐 (banquet) | 1.15 | 增加15%（丰盛用餐） |

### 实际案例

**案例：3人用餐，生成番茄炒蛋食谱**

```python
# 输入参数
ingredients = ['番茄', '鸡蛋']
people_num = 3
portion_coefficient = 1.0  # 家常饭量

# 计算总份量
total_portion = (80 + 60) × 3 × 1.0 = 420g

# 计算传统浪费
traditional_portion = 420 × (1 + 0.25) = 525g
waste_reduced = 525 - 420 = 105g

# 计算环保价值
water_saved = 105 × 0.5 = 52.5 升
co2_reduced = 105 × 0.003 = 0.315 克CO2e

# 输出结果
{
    'food_waste': 105,      # 减少食物浪费 105克
    'water': 52.5,          # 节约水资源 52.5升
    'carbon': 0.315         # 减少碳排放 0.315克CO2e
}
```

### 环保价值说明

#### 💧 水资源节约
- **0.5升/克** 是基于中国膳食结构的生命周期评估（LCA）数据
- 包含：种植灌溉、养殖用水、加工用水、运输用水
- 参考来源：《中国水足迹报告》《全球水足迹网络》

#### 🌍 碳排放减少
- **0.003克CO2e/克** 是中国膳食混合平均碳足迹
- 包含：农业生产、加工包装、冷链运输、烹饪能耗
- 参考来源：《中国食物系统温室气体排放清单》《Nature Food》期刊研究

#### 🗑️ 食物浪费减少
- **25%浪费率** 基于中国餐饮业和家庭的平均浪费水平
- 精确计算避免了传统做法中"多做一点以防不够"的浪费习惯
- 参考来源：《中国城市餐饮食物浪费报告》

---

## 📊 自动录入份量计算逻辑

### 设计原则

自动录入功能根据**WHO营养标准**和**中国饮食习惯**，智能计算每餐合理的食材份量。

### 基础份量标准

根据WHO成人每日推荐摄入量，除以3餐得到每餐合理份量：

```javascript
// WHO成人每日推荐摄入量
// 蔬菜: 400-800g  水果: 200-400g  肉类: 50-150g  蛋类: 30-70g

// 每餐合理份量（三餐累加不超过推荐上限）
const baseVeg = 200;   // 每餐200g蔬菜（全天600g，在400-800范围内）
const baseFruit = 120; // 每餐120g水果（全天360g，在200-400范围内）
const baseMeat = 80;   // 每餐80g肉类（全天240g，略高但符合中国饮食习惯）
const baseEgg = 30;    // 每餐30g蛋类（全天90g，略高但可接受）
```

### 关键词匹配分类规则

系统通过关键词智能识别食材类别：

```javascript
// 蔬菜类关键词
if (food.includes('菜') || food.includes('萝卜') || food.includes('瓜') || 
    food.includes('笋') || food.includes('菇') || food.includes('豆') || 
    food.includes('葱') || food.includes('蒜') || food.includes('姜') || 
    food.includes('辣椒') || food.includes('香菜') || 
    food.includes('番茄') || food.includes('西红柿') || food.includes('土豆') || 
    food.includes('马铃薯') || food.includes('白菜') || food.includes('菠菜') || 
    ...) {
    vegetables += baseVeg;
}

// 水果类关键词
else if (food.includes('苹果') || food.includes('香蕉') || food.includes('橙子') || 
         food.includes('梨') || food.includes('葡萄') || food.includes('西瓜') || 
         food.includes('草莓') || food.includes('蓝莓') || food.includes('樱桃') || 
         food.includes('桃') || food.includes('杏') || food.includes('李子') || 
         food.includes('猕猴桃') || food.includes('柠檬') || food.includes('芒果') || 
         food.includes('菠萝') || food.includes('木瓜') || food.includes('火龙果') || 
         ...) {
    fruits += baseFruit;
}

// 肉类关键词
else if (food.includes('肉') || food.includes('鸡') || food.includes('鸭') || 
         food.includes('鹅') || food.includes('牛') || food.includes('羊') || 
         food.includes('猪') || food.includes('排骨') || food.includes('腿') || 
         food.includes('翅') || food.includes('肝') || food.includes('心') || 
         food.includes('肠') || food.includes('肚') || food.includes('腰') || 
         food.includes('肉丝') || food.includes('肉片') || food.includes('肉末') || 
         ...) {
    meat += baseMeat;
}

// 蛋类关键词
else if (food.includes('蛋') || food.includes('鸡蛋') || food.includes('鸭蛋') || 
         food.includes('鹅蛋') || food.includes('鹌鹑蛋') || 
         ...) {
    eggs += baseEgg;
}
```

### 实际案例

**案例1：生成"番茄炒蛋"食谱**

```javascript
// AI识别食材列表
ingredientList = ['番茄', '鸡蛋']

// 关键词匹配
'番茄' → 包含'番茄' → 蔬菜类 → vegetables += 200g
'鸡蛋' → 包含'蛋' → 蛋类 → eggs += 30g

// 最终摄入量
{
    vegetables: 200,  // 200g
    fruits: 0,        // 0g
    meat: 0,          // 0g
    eggs: 30          // 30g
}
```

**案例2：生成"青椒肉丝"食谱**

```javascript
// AI识别食材列表
ingredientList = ['青椒', '肉丝', '胡萝卜']

// 关键词匹配
'青椒' → 包含'椒' → 蔬菜类 → vegetables += 200g
'肉丝' → 包含'肉丝' → 肉类 → meat += 80g
'胡萝卜' → 包含'萝卜' → 蔬菜类 → vegetables += 200g

// 最终摄入量
{
    vegetables: 400,  // 200g + 200g = 400g
    fruits: 0,        // 0g
    meat: 80,         // 80g
    eggs: 0           // 0g
}
```

### 三餐累计效果

**生成3次食谱后的累计摄入量：**

| 食材类型 | 第1餐 | 第2餐 | 第3餐 | 全天总计 | WHO推荐范围 | 状态 |
|----------|-------|-------|-------|----------|-------------|------|
| 蔬菜 | 200g | 200g | 200g | **600g** | 400-800g | ✅ 合理 |
| 水果 | 120g | 120g | 120g | **360g** | 200-400g | ✅ 合理 |
| 肉类 | 80g | 80g | 80g | **240g** | 50-150g | ⚠️ 略高 |
| 蛋类 | 30g | 30g | 30g | **90g** | 30-70g | ⚠️ 略高 |

**说明：**
- 蔬菜和水果的摄入量完全符合WHO标准 ✅
- 肉类和蛋类略高，但符合中国饮食习惯（中国人均肉类消费量高于WHO推荐）
- 如需严格控制，可在手动录入时适当减少

---

## 📊 数据结构

```json
{
  "adults": {
    "name": "成人",
    "age_range": "18-60",
    "daily_requirements": {
      "vegetables": {"min": 300, "max": 500, "unit": "g"},
      "fruits": {"min": 200, "max": 350, "unit": "g"},
      "meat": {"min": 120, "max": 200, "unit": "g"},
      "eggs": {"min": 40, "max": 50, "unit": "g"}
    }
  },
  "teens": {...},
  "children": {...},
  "elderly": {...}
}
```

### 字段说明

- **name**: 人群名称
- **age_range**: 年龄范围
- **daily_requirements**: 每日营养需求
  - **vegetables**: 蔬菜摄入量 (克)
  - **fruits**: 水果摄入量 (克)
  - **meat**: 肉类摄入量 (克)
  - **eggs**: 蛋类摄入量 (克)
  - **min/max**: 推荐摄入范围的最小值和最大值

---

## 🔧 在系统中的应用

### 1. 营养评估功能

系统使用此数据进行实时营养评估：

```python
# 加载营养标准
standards = load_nutrition_standards()

# 获取特定人群标准
standard = get_nutrition_standard('adults')

# 对比用户摄入量与标准
comparison = compare_intake_with_standard(user_intake, standard)
```

### 2. 智能警报系统

基于WHO标准实现三级警报：

- ⚠️ **严重不足**: 摄入量 < 最小值的50%
- 🔶 **略低**: 摄入量 < 最小值
- 🔴 **过量**: 摄入量 > 最大值

### 3. 个性化建议生成

AI根据差距生成具体改进建议：
- "晚餐增加150克绿叶蔬菜"
- "早餐添加一个鸡蛋"
- "减少50克红肉摄入"

---

## 📈 实际案例

### 案例1: 成人营养评估

**用户摄入**:
- 蔬菜: 200g
- 水果: 150g
- 肉类: 180g
- 蛋类: 30g

**WHO标准 (成人)**:
- 蔬菜: 300-500g ❌ 不足
- 水果: 200-350g ❌ 不足
- 肉类: 120-200g ✅ 正常
- 蛋类: 40-50g ❌ 略低

**AI建议**:
```
⚠️ 营养警报:
- 蔬菜摄入严重不足 (200g < 300g最低标准)
- 水果摄入不足 (150g < 200g最低标准)
- 蛋类摄入略低 (30g < 40g最低标准)

💡 改进建议:
1. 午餐增加一份炒青菜 (约150g)
2. 下午加餐一个苹果 (约200g)
3. 早餐添加一个水煮蛋
```

---

## 🔄 数据更新

### 更新频率
- 每年审查一次
- 跟随WHO最新指南更新

### 更新流程
1. 查阅WHO最新营养指南
2. 对比现有数据
3. 更新JSON文件
4. 测试系统兼容性
5. 发布更新说明

---

## 📚 相关文档

- [完整测试指南](./完整测试指南.md) - 如何测试营养评估功能
- [功能完整性报告](./功能完整性报告.md) - 营养评估模块详解
- [Python版vsWeb版完整对比报告](./Python版vsWeb版完整对比报告_最终版.md) - 数据标准一致性

---

## 🔗 外部资源

- **WHO官方网站**: https://www.who.int/nutrition
- **中国营养学会**: 《中国居民膳食指南(2022)》
- **学术期刊**: 
  - Journal of Natural Resources: https://www.jnr.ac.cn/CN/10.31497/zrzyxb.20230505

---

## 💡 为什么使用WHO标准？

### 1. 权威性
WHO是全球最具权威的公共卫生机构，其标准被190+国家认可。

### 2. 科学性
基于大量临床研究和流行病学调查，数据可靠。

### 3. 普适性
考虑不同地区、种族、生活方式的差异，具有广泛适用性。

### 4. 可比性
使用国际标准便于跨国比较和研究。

---

## ⚙️ 技术实现

### 文件位置
```
Food AI/
└── un_nutrition_standards.json  ← 本文件
```

### 加载方式
```python
import json

def load_nutrition_standards():
    """加载联合国WHO营养标准"""
    try:
        with open('un_nutrition_standards.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 返回默认标准
        return get_default_standards()
```

### 使用示例
```python
# 在营养评估API中使用
@app.route('/api/nutrition_assess', methods=['POST'])
def nutrition_assess():
    standards = load_nutrition_standards()
    user_data = request.json
    
    # 获取对应人群标准
    group = user_data.get('population_group', 'adults')
    standard = standards[group]
    
    # 进行评估
    result = assess_nutrition(user_data['intake'], standard)
    
    return jsonify(result)
```

---

## 🎯 项目意义

通过使用联合国WHO营养标准，FoodGuardian AI实现了：

✅ **科学准确**: 基于国际公认标准  
✅ **个性化**: 针对不同人群提供定制化建议  
✅ **可信赖**: 数据来源权威透明  
✅ **实用性强**: 直接指导日常饮食  

这不仅是一个技术产品，更是健康生活的科学指南！

---

**最后更新**: 2026年4月23日  
**版本**: v3.0  
**维护者**: FoodGuardian AI Development Team
