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
