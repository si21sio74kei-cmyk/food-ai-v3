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

- **population_group**: 人群标识（代码中使用，如 'adults'、'children'）
- **age_range**: 年龄范围（显示用，如 '18-60 岁'）
- **standard_source**: 数据来源（'WHO_2025' 表示 WHO 2025版标准）
- **characteristics**: 人群特征描述（中文说明）
- **daily_recommendations**: 每日营养推荐（包含7种营养素）
  - **vegetables**: 蔬菜摄入量 (min/max: 克)
  - **fruits**: 水果摄入量 (min/max: 克)
  - **meat**: 肉类摄入量 (min/max: 克)
  - **eggs**: 蛋类摄入量 (min/max: 克)
  - **calories**: 热量摄入 (min/max: kcal)
  - **protein**: 蛋白质摄入 (min/max: 克)
  - **calcium**: 钙质摄入 (min/max: mg)
  - **min/max**: 推荐摄入范围的最小值和最大值
  - **unit**: 单位（g/kcal/mg）

---

## 📊 四类人群详细数据解析

### 文件结构概览

```json
[
  { 成人数据 },      // 第 2-44 行
  { 儿童数据 },      // 第 45-87 行
  { 青少年数据 },    // 第 88-130 行
  { 老年人数据 }     // 第 131-174 行
]
```

**总计**：174 行 JSON 代码，包含 4 类人群的完整营养标准。

---

### 1️⃣ 成人 (adults) - 第 2-44 行

**基本信息**：
- **年龄范围**：18-60 岁
- **特点**：成年人处于生命中的旺盛期，需要充足的营养以维持健康
- **适用人群**：上班族、学生、一般成年人

**每日营养需求表**：

| 营养素 | 最小值 | 最大值 | 单位 | 说明 |
|--------|--------|--------|------|------|
| 🥬 蔬菜 | 400 | 800 | g | 每日蔬菜摄入量 |
| 🍎 水果 | 200 | 400 | g | 每日水果摄入量 |
| 🥩 肉类 | 50 | 150 | g | 每日肉类摄入量 |
| 🥚 蛋类 | 30 | 70 | g | 每日蛋类摄入量 |
| 🔥 热量 | 2000 | 2500 | kcal | 每日卡路里 |
| 💪 蛋白质 | 50 | 70 | g | 每日蛋白质 |
| 🦴 钙质 | 1000 | 1200 | mg | 每日钙摄入 |

**营养特点**：
- ✅ 作为基准标准，其他人群以此为参考
- ✅ 营养需求适中，适合大多数成年人
- ✅ 热量和蛋白质需求处于中等水平

---

### 2️⃣ 儿童 (children) - 第 45-87 行

**基本信息**：
- **年龄范围**：6-12 岁
- **特点**：儿童处于生长发育的关键时期，需要充足的营养以支持其身体和智力的发展
- **适用人群**：小学生、学龄儿童

**每日营养需求表**：

| 营养素 | 最小值 | 最大值 | 单位 | 对比成人 |
|--------|--------|--------|------|----------|
| 🥬 蔬菜 | 300 | 500 | g | ↓ 略少（-25%） |
| 🍎 水果 | 150 | 300 | g | ↓ 略少（-25%） |
| 🥩 肉类 | 30 | 100 | g | ↓ 较少（-40%） |
| 🥚 蛋类 | 25 | 75 | g | ≈ 相近 |
| 🔥 热量 | 1600 | 2400 | kcal | ↓ 较少（-20%） |
| 💪 蛋白质 | 30 | 50 | g | ↓ 较少（-40%） |
| 🦴 钙质 | 800 | 1000 | mg | ↓ 略少（-20%） |

**营养特点**：
- 📈 生长发育期，需要均衡营养
- 🧠 智力发展关键期，需要充足蛋白质
- 🦴 骨骼发育需要适量钙质
- ⚡ 活动量大但体型小，总热量需求低于成人

---

### 3️⃣ 青少年 (teens) - 第 88-130 行

**基本信息**：
- **年龄范围**：13-17 岁
- **特点**：青少年处于生长发育的第二个高峰期，身体快速发育，学习压力大，需要充足全面的营养支持
- **适用人群**：初中生、高中生

**每日营养需求表**：

| 营养素 | 最小值 | 最大值 | 单位 | 对比成人 |
|--------|--------|--------|------|----------|
| 🥬 蔬菜 | 400 | 600 | g | ≈ 相近 |
| 🍎 水果 | 200 | 350 | g | ≈ 相近 |
| 🥩 肉类 | 80 | 150 | g | ↑ 略高（+60%） |
| 🥚 蛋类 | 50 | 100 | g | ↑ 较高（+67%） |
| 🔥 热量 | 2200 | 2800 | kcal | ↑ 最高（+12%） |
| 💪 蛋白质 | 60 | 80 | g | ↑ 较高（+20%） |
| 🦴 钙质 | 1200 | 1500 | mg | ↑ 最高（+20%） |

**为什么青少年需求最高？**
- 📈 **身体快速发育期**：身高体重快速增长
- 🏃 **活动量大**：体育运动、日常活动消耗多
- 📚 **学习压力消耗**：脑力劳动需要能量
- 🦴 **骨骼生长需要大量钙质**：预防骨质疏松
- 💪 **肌肉发育需要高蛋白**：支持体格增长

**营养重点**：
- ⭐ **热量需求最高**：所有人群中卡路里需求最大
- ⭐ **钙质需求最高**：骨骼发育关键期
- ⭐ **蛋白质需求高**：肌肉和组织生长

---

### 4️⃣ 老年人 (elderly) - 第 131-174 行

**基本信息**：
- **年龄范围**：60 岁以上
- **特点**：老年人代谢减慢，消化吸收能力下降，需要适当的营养摄入以维持健康
- **适用人群**：退休人员、老年群体

**每日营养需求表**：

| 营养素 | 最小值 | 最大值 | 单位 | 对比成人 |
|--------|--------|--------|------|----------|
| 🥬 蔬菜 | 300 | 500 | g | ↓ 略少（-25%） |
| 🍎 水果 | 150 | 300 | g | ↓ 略少（-25%） |
| 🥩 肉类 | 30 | 100 | g | ↓ 较少（-40%） |
| 🥚 蛋类 | 25 | 75 | g | ↓ 略少（-17%） |
| 🔥 热量 | 1800 | 2200 | kcal | ↓ 较少（-12%） |
| 💪 蛋白质 | 45 | 65 | g | ↓ 略少（-10%） |
| 🦴 钙质 | 1000 | 1200 | mg | ≈ 相近（防骨质疏松） |

**为什么老年人需求降低？**
- 🐌 **代谢率下降**：基础代谢降低，能量需求减少
- 🍽️ **消化能力减弱**：吸收效率下降，不宜过量
- 🛋️ **活动量减少**：日常活动减少，消耗降低
- 🦴 **但仍需高钙质防骨质疏松**：钙质需求不降反升

**营养重点**：
- ⚠️ **控制总热量**：避免肥胖和慢性病
- ⚠️ **易消化食物**：选择软烂、易吸收的食材
- ⚠️ **保持钙质摄入**：预防骨质疏松和骨折
- ⚠️ **适量蛋白质**：维持肌肉质量，防止肌少症

---

## 📈 四类人群营养需求对比图

### 热量对比 (kcal)

```
儿童   ████████████████████ 1600-2400
成人   ██████████████████████████ 2000-2500
老年人 ██████████████████████ 1800-2200
青少年 ██████████████████████████████ 2200-2800 (最高)
```

### 钙质对比 (mg)

```
儿童   ████████████████ 800-1000
成人   ████████████████████ 1000-1200
老年人 ████████████████████ 1000-1200
青少年 ██████████████████████████ 1200-1500 (最高)
```

### 蛋白质对比 (g)

```
儿童   ██████████████ 30-50
成人   ████████████████████ 50-70
老年人 ██████████████████ 45-65
青少年 ████████████████████████ 60-80 (最高)
```

### 蔬菜对比 (g)

```
儿童   ██████████████████ 300-500
成人   ██████████████████████████ 400-800
老年人 ██████████████████ 300-500
青少年 ████████████████████████ 400-600
```

---

## 💡 数据应用要点

### 1. 营养评估逻辑

系统根据用户选择的"人群类型"加载对应标准：

```python
# 用户选择人群
group = user_data.get('population_group', 'adults')  # 默认成人

# 获取标准
standard = standards[group]  # 从JSON数组中查找

# 提取营养需求
requirements = standard['daily_recommendations']

# 对比评估
if intake < requirements['vegetables']['min']:
    status = "不足"
elif intake > requirements['vegetables']['max']:
    status = "超标"
else:
    status = "达标"
```

### 2. 智能警报规则

基于 WHO 标准的三级警报系统：

| 警报级别 | 条件 | 示例 |
|----------|------|------|
| ⚠️ 严重不足 | 摄入量 < 最小值的50% | 蔬菜 150g < 400g×50%=200g |
| 🔶 略低 | 摄入量 < 最小值 | 蔬菜 350g < 400g |
| ✅ 达标 | 最小值 ≤ 摄入量 ≤ 最大值 | 蔬菜 500g 在 400-800g 范围内 |
| 🔴 过量 | 摄入量 > 最大值 | 蔬菜 900g > 800g |

### 3. 个性化建议生成

AI 根据差距生成具体改进建议：

```python
# 计算差距
gap = requirements['vegetables']['min'] - current_intake

# 生成建议
if gap > 0:
    suggestion = f"建议增加{gap}克蔬菜摄入"
    # 转换为实际食物
    if gap >= 150:
        suggestion += "（约一份炒青菜）"
    elif gap >= 100:
        suggestion += "（约一个中等番茄）"
```

---

## 🔄 数据更新机制

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

## 🔄 数据更新机制

### 更新频率
- **每年审查一次**：跟随 WHO 最新指南更新
- **重大变化时立即更新**：如 WHO 发布新版营养指南

### 更新流程
1. **查阅 WHO 最新营养指南**
   - 访问 WHO 官方网站：https://www.who.int/nutrition
   - 关注《中国居民膳食指南》更新
   
2. **对比现有数据**
   - 比较新旧标准的差异
   - 分析变化的科学依据
   
3. **更新 JSON 文件**
   - 修改 `un_nutrition_standards.json`
   - 保持数据结构一致性
   
4. **测试系统兼容性**
   - 验证后端加载功能
   - 测试营养评估准确性
   - 检查前端显示正常
   
5. **发布更新说明**
   - 更新本文档的“最后更新”日期
   - 在 GitHub 提交记录中说明变更内容

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
└── un_nutrition_standards.json  ← 本文件（174行JSON）
```

### 加载方式
```python
import json
import os

def load_nutrition_standards():
    """加载联合国WHO营养标准"""
    try:
        # 获取文件路径（支持Vercel和本地环境）
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, 'un_nutrition_standards.json')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            standards = json.load(f)
            
        # 转换为字典格式，方便通过人群标识访问
        return {item['population_group']: item for item in standards}
        
    except FileNotFoundError:
        print("⚠️ 警告: 未找到营养标准文件，使用默认标准")
        return get_default_standards()
    except json.JSONDecodeError:
        print("⚠️ 错误: 营养标准文件格式错误")
        return get_default_standards()
```

### 使用示例

#### 1. 后端 API 中使用

```python
@app.route('/api/nutrition_assess', methods=['POST'])
def nutrition_assess():
    """营养评估API"""
    # 加载营养标准
    standards = load_nutrition_standards()
    
    # 获取用户数据
    user_data = request.json
    group = user_data.get('population_group', 'adults')
    intake = user_data.get('intake', {})
    
    # 获取对应人群标准
    if group not in standards:
        return jsonify({'error': '无效的人群类型'}), 400
    
    standard = standards[group]
    requirements = standard['daily_recommendations']
    
    # 进行评估
    result = {
        'population': standard['age_range'],
        'assessment': {}
    }
    
    for nutrient in ['vegetables', 'fruits', 'meat', 'eggs']:
        current = intake.get(nutrient, 0)
        req = requirements[nutrient]
        
        if current < req['min'] * 0.5:
            status = '严重不足'
        elif current < req['min']:
            status = '略低'
        elif current > req['max']:
            status = '过量'
        else:
            status = '达标'
        
        result['assessment'][nutrient] = {
            'current': current,
            'recommended_min': req['min'],
            'recommended_max': req['max'],
            'unit': req['unit'],
            'status': status
        }
    
    return jsonify(result)
```

#### 2. 前端 JavaScript 中使用

```javascript
// 加载营养标准（从后端API获取）
async function loadNutritionStandards() {
    const response = await fetch('/api/nutrition_standards');
    const standards = await response.json();
    return standards;
}

// 评估营养摄入
function assessNutrition(intake, populationGroup) {
    const standard = standards[populationGroup];
    const requirements = standard.daily_recommendations;
    
    const assessment = {};
    
    for (const [nutrient, value] of Object.entries(intake)) {
        const req = requirements[nutrient];
        
        if (value < req.min * 0.5) {
            assessment[nutrient] = {
                status: '严重不足',
                gap: req.min - value
            };
        } else if (value < req.min) {
            assessment[nutrient] = {
                status: '略低',
                gap: req.min - value
            };
        } else if (value > req.max) {
            assessment[nutrient] = {
                status: '过量',
                excess: value - req.max
            };
        } else {
            assessment[nutrient] = {
                status: '达标'
            };
        }
    }
    
    return assessment;
}
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
