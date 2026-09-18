#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FoodGuardian AI 自动化测试套件
使用 Flask test client + unittest.mock 模拟 AI API
运行: python test_app.py
"""

import json
import base64
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import food_guardian_ai_2 as fga

# ---- 常量 ----
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fgai_local_data.json')
DATA_FILE_BAK = DATA_FILE + '.test_bak'

TEST_FIXTURE = {
    'nickname': 'TestUser',
    'waste_reduced': 100,
    'water_saved': 50,
    'co2_reduced': 0.3,
    'population_group': 'adults',
    'daily_intake_records': [],
    'fridge_inventory': [],
    'generation_count': 0,
    'generation_date': ''
}


# ---- Mock 辅助函数 (接受 **kwargs 以兼容额外参数) ----
def _mock_ai_success(prompt, **kwargs):
    return {
        'success': True,
        'content': f'Mock AI response for: {prompt[:50]}...',
        'error': None,
        'model_used': 'test-mock'
    }


def _mock_ai_failure(prompt, **kwargs):
    return {
        'success': False,
        'content': None,
        'error': 'Simulated API error',
        'model_used': 'none'
    }


def _mock_ai_stream(prompt):
    yield 'Mock streaming '
    yield 'response '
    yield 'chunks for testing.'


class TestFoodGuardianAI(unittest.TestCase):
    """FoodGuardian AI 完整测试套件"""

    @classmethod
    def setUpClass(cls):
        cls._had_no_data = not os.path.exists(DATA_FILE)
        if os.path.exists(DATA_FILE):
            shutil.copy2(DATA_FILE, DATA_FILE_BAK)
            print(f'\n  已备份数据: {DATA_FILE_BAK}')

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(DATA_FILE_BAK):
            shutil.copy2(DATA_FILE_BAK, DATA_FILE)
            os.remove(DATA_FILE_BAK)
            print(f'\n  已恢复数据: {DATA_FILE}')
        elif cls._had_no_data and os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)

    def setUp(self):
        self._write_test_data(dict(TEST_FIXTURE))
        os.environ.pop('VERCEL', None)
        fga.ENABLE_DETAILED_LOGS = False

    def test_ai_connection_error_is_safe_and_actionable(self):
        raw_error = (
            "HTTPSConnectionPool(host='open.bigmodel.cn', port=443): "
            "[WinError 10013] socket access denied"
        )
        error = fga.requests.exceptions.ConnectionError(raw_error)

        with patch('food_guardian_ai_2.requests.post', side_effect=error):
            chunks = list(fga._call_zhipu_api_stream(
                fga.ZHIPU_API_URL,
                'test-key',
                'test prompt',
            ))

        message = ''.join(chunks)
        self.assertIn('open.bigmodel.cn:443', message)
        self.assertNotIn('HTTPSConnectionPool', message)
        self.assertNotIn('WinError', message)

    def test_supabase_headers_support_new_and_legacy_keys(self):
        original_key = fga.SUPABASE_KEY
        try:
            new_secret_key = 'sb_' + 'secret_example'
            fga.SUPABASE_KEY = new_secret_key
            new_headers = fga.build_supabase_headers()
            self.assertEqual(new_headers['apikey'], new_secret_key)
            self.assertNotIn('Authorization', new_headers)

            fga.SUPABASE_KEY = 'eyJlegacy.jwt.value'
            legacy_headers = fga.build_supabase_headers()
            self.assertEqual(legacy_headers['apikey'], 'eyJlegacy.jwt.value')
            self.assertEqual(
                legacy_headers['Authorization'],
                'Bearer eyJlegacy.jwt.value',
            )
        finally:
            fga.SUPABASE_KEY = original_key

    def tearDown(self):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)

    # ---- 辅助方法 ----
    def _write_test_data(self, data):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _read_test_data(self):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _parse_sse(self, response):
        """解析 SSE 流式响应 — Flask test client 兼容版"""
        # 使用 get_data() 获取完整响应体
        body = response.get_data(as_text=True)
        events = []
        for line in body.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line == 'data: [DONE]':
                events.append({'type': 'done'})
            elif line.startswith('data: '):
                data_str = line[6:]
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    events.append({'raw': data_str})
        return events

    def _create_client(self):
        return fga.app.test_client()

    def _assert_sse(self, response):
        """验证响应是 text/event-stream"""
        self.assertIn('text/event-stream', response.content_type)

    # ============================================================
    # 摄入与评估 (Intake & Assessment)
    # ============================================================

    def test_save_intake_single_meal(self):
        """保存单餐 → 记录正确存储"""
        client = self._create_client()
        resp = client.post('/api/save_intake', json={
            'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])

        stored = self._read_test_data()
        self.assertEqual(len(stored['daily_intake_records']), 1)
        self.assertEqual(stored['daily_intake_records'][0]['vegetables'], 100)

    def test_save_intake_keeps_meal_label(self):
        """每餐标签与来源会随记录一起保存。"""
        client = self._create_client()
        body = client.post('/api/save_intake', json={
            'vegetables': 80, 'fruits': 30, 'meat': 20, 'eggs': 10,
            'meal_type': 'breakfast', 'source': 'manual'
        }).get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['record']['meal_type'], 'breakfast')
        stored = self._read_test_data()['daily_intake_records'][0]
        self.assertEqual(stored['meal_type'], 'breakfast')
        self.assertTrue(stored['id'])

    def test_save_intake_three_meals(self):
        """保存三餐 → 累计总量正确"""
        client = self._create_client()
        meals = [
            {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            {'vegetables': 150, 'fruits': 80, 'meat': 60, 'eggs': 30},
            {'vegetables': 200, 'fruits': 100, 'meat': 80, 'eggs': 40},
        ]
        for i, meal in enumerate(meals):
            resp = client.post('/api/save_intake', json=meal)
            self.assertTrue(resp.get_json()['success'], f'Meal {i+1}')
            expected = {k: sum(m[k] for m in meals[:i+1]) for k in meal}
            self.assertEqual(resp.get_json()['total_intake'], expected)

        self.assertEqual(len(self._read_test_data()['daily_intake_records']), 3)

    def test_save_intake_rejects_invalid_values(self):
        """摄入记录 → 拒绝负数、布尔值和非数字，避免污染真实统计"""
        client = self._create_client()
        for bad_value in (-1, True, 'not-a-number'):
            resp = client.post('/api/save_intake', json={
                'vegetables': bad_value, 'fruits': 0, 'meat': 0, 'eggs': 0
            })
            self.assertEqual(resp.status_code, 400)
            self.assertFalse(resp.get_json()['success'])
        self.assertEqual(self._read_test_data()['daily_intake_records'], [])

    @patch('food_guardian_ai_2.save_data', return_value=False)
    def test_save_intake_reports_database_write_failure(self, _):
        """每餐保存 → 持久化失败时不得向前端谎报成功。"""
        response = self._create_client().post('/api/save_intake', json={
            'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20,
            'meal_type': 'lunch'
        })
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()['success'])
        self.assertIn('未能写入账号数据库', response.get_json()['error'])

    def test_save_intake_no_record_limit(self):
        """🔐 真实数据保存：今日记录超过3条 → 全部保留，营养评估汇总全部记录"""
        client = self._create_client()
        meal = {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20}
        for _ in range(5):
            resp = client.post('/api/save_intake', json=meal)
            self.assertTrue(resp.get_json()['success'])
        # 5 条全部保留在数据库（不删除旧记录）
        self.assertEqual(len(self._read_test_data()['daily_intake_records']), 5)
        # 第 6 条保存后 → total_intake 汇总全部 6 条（而非最新3条）
        resp = client.post('/api/save_intake', json=meal)
        self.assertEqual(resp.get_json()['total_intake'],
                         {'vegetables': 600, 'fruits': 300, 'meat': 180, 'eggs': 120})

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_nutrition_assess_insufficient(self, _):
        """低摄入 → 报告标注不足"""
        client = self._create_client()
        resp = client.post('/api/nutrition_assess', json={
            'user_intake': {'vegetables': 50, 'fruits': 30, 'meat': 10, 'eggs': 5},
            'population_group': 'adults', 'language': 'zh-CN'
        })
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('不足', data['report'])

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_nutrition_assess_excessive(self, _):
        """高摄入 → 报告标注超标"""
        client = self._create_client()
        resp = client.post('/api/nutrition_assess', json={
            'user_intake': {'vegetables': 2000, 'fruits': 1500, 'meat': 800, 'eggs': 400},
            'population_group': 'adults', 'language': 'zh-CN'
        })
        self.assertIn('超标', resp.get_json()['report'])

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_nutrition_assess_all_groups(self, _):
        """全人群模式 → 4 组都出现"""
        client = self._create_client()
        resp = client.post('/api/nutrition_assess', json={
            'user_intake': {'vegetables': 200, 'fruits': 150, 'meat': 100, 'eggs': 50},
            'population_group': 'all', 'language': 'zh-CN'
        })
        report = resp.get_json()['report']
        for label in ['成年人', '青少年', '儿童', '老年人']:
            self.assertIn(label, report)

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_nutrition_assess_english(self, _):
        """英文模式 → English keywords"""
        client = self._create_client()
        resp = client.post('/api/nutrition_assess', json={
            'user_intake': {'vegetables': 200, 'fruits': 150, 'meat': 100, 'eggs': 50},
            'population_group': 'adults', 'language': 'en-US'
        })
        report = resp.get_json()['report']
        self.assertIn('Vegetables', report)
        self.assertIn('Meets Standard', report)

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_nutrition_report_explains_source_and_scope(self, _):
        """营养报告明示人群、计算口径、WHO/FAO 来源及非医疗声明。"""
        report = self._create_client().post('/api/nutrition_assess', json={
            'user_intake': {'vegetables': 300, 'fruits': 200, 'meat': 80, 'eggs': 50},
            'population_group': 'adults', 'language': 'zh-CN'
        }).get_json()['report']
        self.assertIn('参考依据与计算口径', report)
        self.assertIn('18-60', report)
        self.assertIn('who.int', report)
        self.assertIn('fao.org', report)
        self.assertIn('不构成诊断', report)

    def test_shopping_preferences_and_price_feedback_are_bounded(self):
        """采购地区可保存，实付样本最多保留 20 条。"""
        client = self._create_client()
        saved = client.post('/api/shopping/preferences', json={
            'province': '广东省', 'city': '深圳市南山区'
        }).get_json()
        self.assertTrue(saved['success'])
        for price in range(1, 23):
            result = client.post('/api/shopping/price-feedback', json={
                'actual_total': price, 'region': '广东省 深圳市南山区',
                'dishes': '西红柿炒蛋', 'people_num': 3
            }).get_json()
            self.assertTrue(result['success'])
        preferences = client.get('/api/shopping/preferences').get_json()['preferences']
        self.assertEqual(preferences['province'], '广东省')
        self.assertEqual(len(preferences['price_samples']), 20)
        context = fga.shopping_price_context(preferences, '广东省 深圳市南山区')
        self.assertIn('实付样本', context)

    # ============================================================
    # SSE 流式端点 (SSE Streaming)
    # ============================================================

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_recipe_stream(self, _):
        """食谱 SSE → chunks + impact + [DONE]"""
        client = self._create_client()
        resp = client.post('/api/generate_recipe_stream', json={
            'custom_ingredients': '鸡肉,西兰花', 'people_num': 2,
            'meal_type': 'home', 'appetite': 1.0, 'language': 'zh-CN'
        })
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]['type'], 'done')

        done_event = events[-2]
        self.assertTrue(done_event.get('done'))
        self.assertIn('impact', done_event)
        self.assertIn('food_waste', done_event['impact'])

        content_events = [e for e in events if 'content' in e]
        self.assertGreater(len(content_events), 0)

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_recipe_stream_no_ingredients(self, _):
        """空食材 → SSE error"""
        client = self._create_client()
        resp = client.post('/api/generate_recipe_stream', json={
            'custom_ingredients': '', 'people_num': 2, 'language': 'zh-CN'
        })
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertIn('error', events[0])

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_recipe_stream_with_fridge(self, _):
        """冰箱食材 SSE → 正常输出"""
        client = self._create_client()
        data = dict(TEST_FIXTURE)
        data['fridge_inventory'] = [{
            'name': '鸡蛋', 'quantity': 12, 'unit': '个', 'expiry_date': '2026-07-15'
        }]
        self._write_test_data(data)

        resp = client.post('/api/generate_recipe_stream', json={
            'custom_ingredients': '番茄', 'people_num': 2,
            'use_fridge': True, 'language': 'zh-CN'
        })
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertEqual(events[-1]['type'], 'done')

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_daily_rec_stream(self, _):
        """每日推荐 SSE → 流式正常"""
        client = self._create_client()
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
        data = dict(TEST_FIXTURE)
        data['daily_intake_records'] = [{
            'date': today, 'time': '08:00',
            'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20
        }]
        self._write_test_data(data)

        resp = client.post('/api/generate_daily_recommendation_stream',
                           json={'language': 'zh-CN'})
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]['type'], 'done')

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_daily_rec_stream_all_groups(self, _):
        """全人群每日推荐 → done 事件正常"""
        client = self._create_client()
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
        data = dict(TEST_FIXTURE)
        data['population_group'] = 'all'
        data['daily_intake_records'] = [{
            'date': today, 'time': '12:00',
            'vegetables': 200, 'fruits': 100, 'meat': 80, 'eggs': 40
        }]
        self._write_test_data(data)

        resp = client.post('/api/generate_daily_recommendation_stream',
                           json={'language': 'zh-CN'})
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        done_events = [e for e in events if e.get('done')]
        self.assertGreater(len(done_events), 0, 'Should have at least one done event')

    def test_people_and_appetite_limits_are_enforced(self):
        """人数最多 20，饭量系数最多 2.0，前后端不可绕过。"""
        client = self._create_client()
        for payload in (
            {'custom_ingredients': '番茄', 'people_num': 21, 'appetite': 1.0},
            {'custom_ingredients': '番茄', 'people_num': 2, 'appetite': 2.1},
            {'custom_ingredients': '番茄', 'people_num': 1.5, 'appetite': 1.0},
        ):
            response = client.post('/api/generate_recipe_stream', json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.get_json()['success'])

        accepted = fga.parse_dining_preferences(
            {'people_num': 20, 'appetite': 2.0}
        )
        self.assertEqual(accepted, (20, 2.0))

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_daily_recommendation_keeps_assessment_per_person_and_scales_output(self, mock_ai):
        """今日评估保持单人口径，明日用量按自定义人数和饭量系数输出。"""
        client = self._create_client()
        response = client.post('/api/daily_recommendation', json={
            'user_intake': {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            'population_group': 'adults',
            'people_num': 20,
            'appetite': 2.0,
            'language': 'zh-CN'
        })
        self.assertTrue(response.get_json()['success'])
        prompt = mock_ai.call_args.args[0]
        self.assertIn('今日摄入是账号本人 1 人的实际摄入', prompt)
        self.assertIn('就餐人数：20 人', prompt)
        self.assertIn('个人饭量系数：2.0', prompt)

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    def test_daily_recommendation_uses_english_interface_language(self, mock_ai):
        """明日推荐 → 英文界面生成全英文提示词。"""
        response = self._create_client().post('/api/daily_recommendation', json={
            'user_intake': {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            'population_group': 'adults',
            'people_num': 2,
            'appetite': 1.2,
            'language': 'en-US'
        })
        self.assertTrue(response.get_json()['success'])
        prompt = mock_ai.call_args.args[0]
        self.assertIn('Please respond entirely in English', prompt)
        self.assertIn("Today's intake above is ONE account holder", prompt)

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_chat_stream(self, mock_stream):
        """聊天 SSE → 中文"""
        client = self._create_client()
        resp = client.post('/api/chat_stream', json={
            'message': '如何去除鱼腥味？', 'language': 'zh-CN'
        })
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]['type'], 'done')
        prompt = mock_stream.call_args.args[0]
        self.assertIn('请全程使用中文', prompt)

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_chat_stream_english(self, mock_stream):
        """聊天 SSE → 英文"""
        client = self._create_client()
        resp = client.post('/api/chat_stream', json={
            'message': 'How to store vegetables?', 'language': 'en-US'
        })
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]['type'], 'done')
        prompt = mock_stream.call_args.args[0]
        self.assertIn('in English', prompt)
        self.assertNotIn('请全程使用中文', prompt)

    @patch('food_guardian_ai_2.requests.post')
    def test_image_recognition_upload_flow(self, mock_post):
        """拍照识菜 → 图片压缩、视觉 API 请求和结果解析均可用。"""
        from PIL import Image
        image_buffer = io.BytesIO()
        Image.new('RGB', (4, 4), (220, 50, 40)).save(image_buffer, format='PNG')
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'choices': [{'message': {'content': '番茄,鸡蛋'}}]
        }

        response = self._create_client().post('/api/image_recognize', json={
            'image_base64': base64.b64encode(image_buffer.getvalue()).decode('ascii'),
            'language': 'zh-CN'
        })
        body = response.get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['ingredients'], '番茄,鸡蛋')
        self.assertEqual(mock_post.call_args.kwargs['json']['model'], 'glm-4v-flash')

    @patch('food_guardian_ai_2.requests.post')
    def test_voice_recognition_upload_flow(self, mock_post):
        """语音识别 → 音频上传、ASR 参数和文本返回均可用。"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'text': '今天吃什么'}

        response = self._create_client().post(
            '/api/voice_recognize',
            data={'audio': (io.BytesIO(b'RIFF-test-wave'), 'recording.wav'), 'language': 'zh'},
            content_type='multipart/form-data'
        )
        body = response.get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['text'], '今天吃什么')
        self.assertEqual(mock_post.call_args.kwargs['data']['model'], 'glm-asr-2512')

    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_shopping_list_stream(self, mock_stream):
        """采购清单 SSE → 地区预算进入 AI 提示并正常流式返回"""
        client = self._create_client()
        resp = client.post('/api/generate_shopping_list_stream', json={
            'dishes': '番茄炒蛋,青菜',
            'people_num': 3,
            'include_budget': True,
            'shopping_region': '广东省 深圳市南山区',
            'language': 'zh-CN'
        })
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[-1]['type'], 'done')
        prompt = mock_stream.call_args.args[0]
        self.assertIn('广东省 深圳市南山区预算估算', prompt)
        self.assertIn('参考单价', prompt)
        self.assertIn('价格区间', prompt)

    @patch('food_guardian_ai_2.call_ai_api',
           return_value={'success': True, 'content': '- 1份星云菜 ≈ 123g', 'error': None})
    def test_food_weight_query_ai_fallback(self, mock_ai):
        """食材重量查询 → 本地库未收录时 AI 估算并提取克数"""
        client = self._create_client()
        resp = client.post('/api/food_weight/query', json={'food_name': '星云菜'})
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['source'], 'ai')
        self.assertEqual(body['estimated_weight'], 123)
        self.assertEqual(body['result'], '- 1份星云菜 ≈ 123g')
        self.assertIn('请全程使用中文', mock_ai.call_args.args[0])

    @patch('food_guardian_ai_2.call_ai_api',
           return_value={'success': True, 'content': '1 serving is about 145 g', 'error': None})
    def test_food_weight_query_uses_interface_language(self, mock_ai):
        """重量查询 → 英文界面要求 AI 全程英文并返回可渲染 result。"""
        body = self._create_client().post('/api/food_weight/query', json={
            'food_name': 'nebula greens', 'language': 'en-US'
        }).get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['result'], '1 serving is about 145 g')
        self.assertIn('respond entirely in English', mock_ai.call_args.args[0])

    # ============================================================
    # CRUD (Data & CRUD)
    # ============================================================

    def test_data_get(self):
        """GET /api/data"""
        client = self._create_client()
        resp = client.get('/api/data')
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['nickname'], 'TestUser')

    def test_data_update(self):
        """POST /api/data → 持久化"""
        client = self._create_client()
        client.post('/api/data', json={'nickname': 'NewName'})
        self.assertEqual(
            client.get('/api/data').get_json()['data']['nickname'],
            'NewName'
        )

    def test_data_does_not_persist_chat_history(self):
        """数据库数据 → 不保存/不返回 AI 对话测试记录"""
        client = self._create_client()
        client.post('/api/data', json={
            'chat_history': [{'text': 'old test message', 'sender': 'user'}],
            'nickname': 'NoChat'
        })
        body = client.get('/api/data').get_json()['data']
        stored = self._read_test_data()
        self.assertEqual(body['nickname'], 'NoChat')
        self.assertNotIn('chat_history', body)
        self.assertNotIn('chat_history', stored)

    def test_data_keeps_only_latest_rolling_7_days(self):
        """数据库数据 → 保留滚动 7 天，第 8 天记录自动删除"""
        client = self._create_client()
        monday = fga.datetime(2026, 9, 21, 9, 0, tzinfo=fga.CHINA_TZ)
        day_7 = (monday - fga.timedelta(days=6)).strftime('%Y-%m-%d')
        day_8 = (monday - fga.timedelta(days=7)).strftime('%Y-%m-%d')
        with patch('food_guardian_ai_2.get_china_time', return_value=monday):
            client.post('/api/data', json={
                'daily_intake_records': [
                    {'date': day_7, 'time': '08:00', 'vegetables': 100, 'fruits': 0, 'meat': 0, 'eggs': 0},
                    {'date': day_8, 'time': '08:00', 'vegetables': 999, 'fruits': 0, 'meat': 0, 'eggs': 0},
                ]
            })
            records = client.get('/api/data').get_json()['data']['daily_intake_records']
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['date'], day_7)
        self.assertNotIn(day_8, [record['date'] for record in self._read_test_data()['daily_intake_records']])

    def test_generation_progress_is_scoped_to_current_day(self):
        """三餐进度 → 跨日自动归零，同一天保留且最多为 3。"""
        today = fga.datetime(2026, 9, 21, 9, 0, tzinfo=fga.CHINA_TZ)
        yesterday = (today - fga.timedelta(days=1)).date().isoformat()
        with patch('food_guardian_ai_2.get_china_time', return_value=today):
            stale = fga.sanitize_persisted_user_data({
                'generation_count': 2, 'generation_date': yesterday
            })
            current = fga.sanitize_persisted_user_data({
                'generation_count': 9, 'generation_date': today.date().isoformat()
            })
        self.assertEqual(stale['generation_count'], 0)
        self.assertEqual(stale['generation_date'], '2026-09-21')
        self.assertEqual(current['generation_count'], 3)

    def test_fridge_add_and_list(self):
        """冰箱 CRUD"""
        client = self._create_client()
        # 确保文件不存在，load_data 返回默认空数据
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)

        # 添加前确认列表为空
        initial = client.get('/api/fridge/list').get_json()
        self.assertEqual(len(initial['inventory']), 0)

        resp = client.post('/api/fridge/add', json={
            'name': '鸡蛋', 'quantity': 12, 'unit': '个', 'expiry_date': '2026-07-15'
        })
        self.assertEqual(len(resp.get_json()['inventory']), 1)

        final = client.get('/api/fridge/list').get_json()
        self.assertEqual(len(final['inventory']), 1)
        self.assertEqual(final['inventory'][0]['name'], '鸡蛋')

    # ============================================================
    # 集成测试 (Integration)
    # ============================================================

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_success)
    @patch('food_guardian_ai_2.call_ai_api_stream', side_effect=_mock_ai_stream)
    def test_three_meal_full_cycle(self, _, __):
        """完整三餐流程: 保存 → 评估 → 每日推荐"""
        client = self._create_client()
        meals = [
            {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            {'vegetables': 150, 'fruits': 80, 'meat': 60, 'eggs': 30},
            {'vegetables': 200, 'fruits': 100, 'meat': 80, 'eggs': 40},
        ]
        for meal in meals:
            self.assertTrue(client.post('/api/save_intake', json=meal).get_json()['success'])

        self.assertEqual(len(self._read_test_data()['daily_intake_records']), 3)

        total = {k: sum(m[k] for m in meals) for k in meals[0]}
        self.assertEqual(total, {'vegetables': 450, 'fruits': 230, 'meat': 170, 'eggs': 90})

        # 评估
        resp = client.post('/api/nutrition_assess', json={
            'user_intake': total, 'population_group': 'adults', 'language': 'zh-CN'
        })
        self.assertIn('超标', resp.get_json()['report'])  # 肉类 170 > 150

        # 每日推荐 SSE
        resp = client.post('/api/generate_daily_recommendation_stream',
                           json={'language': 'zh-CN'})
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertEqual(events[-1]['type'], 'done')

    def test_daily_recommendation_stream_uses_today_totals_and_fridge(self):
        """明日推荐流 → 汇总今日全部记录，并带入冰箱食材"""
        client = self._create_client()
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
        data = dict(TEST_FIXTURE)
        data['daily_intake_records'] = [
            {'date': today, 'time': '08:00', 'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            {'date': today, 'time': '18:00', 'vegetables': 200, 'fruits': 70, 'meat': 80, 'eggs': 10},
        ]
        data['fridge_inventory'] = [{'name': '鸡蛋', 'quantity': 12, 'unit': '个'}]
        self._write_test_data(data)

        captured = {}

        def fake_ai(prompt, **kwargs):
            captured['prompt'] = prompt
            return {'success': True, 'content': '明日推荐OK', 'error': None}

        with patch('food_guardian_ai_2.call_ai_api', side_effect=fake_ai):
            resp = client.post('/api/generate_daily_recommendation_stream',
                               json={'language': 'zh-CN'})
        self._assert_sse(resp)
        events = self._parse_sse(resp)
        self.assertTrue(any(e.get('done') for e in events))
        self.assertIn('蔬菜: 300g', captured['prompt'])
        self.assertIn('水果: 120g', captured['prompt'])
        self.assertIn('肉类: 110g', captured['prompt'])
        self.assertIn('蛋类: 30g', captured['prompt'])
        self.assertIn('鸡蛋12个', captured['prompt'])

    def test_calculate_impact(self):
        """环保影响 → 正常返回"""
        client = self._create_client()
        resp = client.post('/api/calculate_impact', json={
            'custom_ingredients': '鸡肉,西兰花,胡萝卜',
            'people_num': 3, 'meal_type': 'home'
        })
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertEqual(body['impact']['food_waste'], 217.5)
        self.assertEqual(body['impact']['water'], 108.75)
        self.assertEqual(body['impact']['carbon'], 652.5)

    # ============================================================
    # 错误处理 (Error Handling)
    # ============================================================

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_failure)
    def test_daily_recommendation_api_failure(self, _):
        """每日推荐 AI 失败 → recommendation 包含错误信息"""
        client = self._create_client()
        resp = client.post('/api/daily_recommendation', json={
            'user_intake': {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            'population_group': 'adults', 'language': 'zh-CN'
        })
        data = resp.get_json()
        # 注意: 该端点始终返回 success=True, 错误信息在 recommendation 字段中
        self.assertTrue(data['success'])
        self.assertIn('AI 生成失败', data['recommendation'])

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_failure)
    def test_daily_recommendation_api_failure_is_english_in_english_mode(self, _):
        data = self._create_client().post('/api/daily_recommendation', json={
            'user_intake': {'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20},
            'population_group': 'adults', 'language': 'en-US'
        }).get_json()
        self.assertTrue(data['success'])
        self.assertIn('AI generation failed', data['recommendation'])
        self.assertNotIn('生成失败', data['recommendation'])

    @patch('food_guardian_ai_2.call_ai_api', side_effect=_mock_ai_failure)
    def test_chat_api_failure(self, _):
        """聊天 AI 失败 → error"""
        client = self._create_client()
        resp = client.post('/api/chat', json={
            'message': 'test', 'language': 'zh-CN'
        })
        self.assertFalse(resp.get_json()['success'])


class TestFrontendMarkup(unittest.TestCase):
    """前端结构/CSS 回归测试"""

    def _read_index(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html'),
                  encoding='utf-8') as f:
            return f.read()

    def _read_locale(self, name):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales', name),
                  encoding='utf-8') as f:
            return json.load(f)

    def _has_i18n_key(self, data, key):
        value = data
        for part in key.split('.'):
            if not isinstance(value, dict) or part not in value:
                return False
            value = value[part]
        return True

    def test_home_uses_vertical_layout_on_desktop(self):
        """首页桌面端 → 保持竖向卡片流，避免左右两列高度不平衡"""
        html = self._read_index()
        self.assertIn('#page-home.active { display: block; }', html)

    def test_checked_radio_has_real_dark_background(self):
        """年龄段选中态 → 直接设置深色背景，避免白底白字"""
        html = self._read_index()
        self.assertRegex(
            html,
            r'\.radio-item input\[type="radio"\]:checked \+ \.radio-label \{[^}]*background:\s*#253026;'
        )

    def test_senior_friendly_guided_homepage_exists(self):
        """首页 → 有适老化三步引导与重点入口"""
        html = self._read_index()
        self.assertIn('body class="senior-friendly"', html)
        self.assertIn('class="guided-panel"', html)
        self.assertIn('class="card priority-card"', html)
        self.assertIn('home.workflow_step3_text', html)

    def test_recipe_auto_assessment_flow_still_exposed(self):
        """食谱页 → 三次生成后的自动评估/明日推荐链路仍在"""
        html = self._read_index()
        self.assertIn('class="automation-panel"', html)
        self.assertIn('autoIntakeAndAssess(customIngredients, peopleNum, appetite)', html)
        self.assertIn('generateDailyRecommendation()', html)

    def test_recipe_three_generation_frontend_order(self):
        """前端联动顺序 → 第3次先自动评估，再生成明日推荐"""
        html = self._read_index()
        generate_start = html.index('async function generateRecipe()')
        next_section = html.index('// ==================== 营养分析功能', generate_start)
        generate_block = html[generate_start:next_section]
        self.assertIn("if (appData.generation_date !== today)", generate_block)
        self.assertIn("if ((appData.generation_count || 0) >= 3)", generate_block)
        self.assertIn('if (currentMealCount <= 2)', generate_block)
        self.assertIn('intakeSaved = await autoIntakeOnly(customIngredients, peopleNum, currentMealCount, appetite);', generate_block)
        self.assertIn('if (intakeSaved)', generate_block)
        self.assertNotIn('appData.generation_count--', generate_block)
        self.assertLess(
            generate_block.index('intakeSaved = await autoIntakeAndAssess(customIngredients, peopleNum, appetite);'),
            generate_block.index('await generateDailyRecommendation({ peopleNum, appetite });')
        )

        assess_start = html.index('async function autoIntakeAndAssess')
        assess_end = html.index('// 更新今日饮食摄入记录输入框', assess_start)
        assess_block = html[assess_start:assess_end]
        self.assertIn("await safeApiCall('/api/save_intake'", assess_block)
        self.assertLess(
            assess_block.index("await safeApiCall('/api/save_intake'"),
            assess_block.index('await loadData();')
        )
        self.assertIn('const todayRecords = (appData.daily_intake_records || []).filter', assess_block)
        self.assertIn('await performNutritionAssessment(totalIntake);', assess_block)

        daily_start = html.index('async function generateDailyRecommendation(options = {})')
        daily_end = html.index('// ==================== 食材重量查询', daily_start)
        daily_block = html[daily_start:daily_end]
        self.assertIn("fetch('/api/generate_daily_recommendation_stream'", daily_block)

    def test_auto_intake_uses_per_person_age_group_portions(self):
        """自动摄入 → 按人群个人份量估算，不被用餐人数放大"""
        html = self._read_index()
        self.assertIn('function getPerMealIntakePortions(appetiteFactor = 1.0)', html)
        self.assertIn('adults: { vegetables: 200, fruits: 110, meat: 45, eggs: 20 }', html)
        self.assertIn('teens: { vegetables: 180, fruits: 110, meat: 45, eggs: 30 }', html)
        self.assertIn('children: { vegetables: 150, fruits: 90, meat: 30, eggs: 20 }', html)
        self.assertNotIn('vegetables *= peopleNum;', html)
        self.assertNotIn('fruits *= peopleNum;', html)
        self.assertNotIn('meat *= peopleNum;', html)
        self.assertNotIn('eggs *= peopleNum;', html)
        self.assertNotIn('const baseMeat = 80;', html)
        self.assertNotIn('const baseEgg = 30;', html)
        self.assertGreaterEqual(html.count("food.includes('西兰花')"), 2)

    def test_recommendation_controls_and_intake_scope_are_explicit(self):
        """推荐人数/饭量可配置，摄入记录明确为账号本人单人口径。"""
        html = self._read_index()
        self.assertIn('id="daily-rec-people"', html)
        self.assertIn('id="daily-rec-appetite"', html)
        self.assertIn('max="20"', html)
        self.assertIn('max="2.0"', html)
        self.assertIn('home.intake_scope_note', html)
        self.assertIn('people_num: peopleNum', html)
        self.assertIn('appetite\n', html)

    def test_frontend_result_containers_do_not_clip_content(self):
        """结果容器 → 不使用固定高度裁切长内容"""
        html = self._read_index()
        self.assertIn('overflow: visible;  /* 🔑 关键修复：改为visible，允许内容完整显示 */', html)
        self.assertIn('max-height: none;  /* 🔑 移除高度限制 */', html)
        self.assertIn("document.getElementById('recipe-result').style.display = 'block';", html)
        self.assertIn("resultContainer.style.display = 'block';", html)
        self.assertIn('overflow-x: hidden; overflow-wrap: break-word;', html)
        self.assertIn('overflow-wrap: break-word;', html)
        self.assertIn('word-break: break-word;', html)
        self.assertIn('.result-box table {', html)
        self.assertIn('overflow-x: auto;', html)

    def test_markdown_renderer_escapes_raw_html(self):
        """AI 文本渲染 → 先转义 HTML，再处理 Markdown，避免注入页面"""
        html = self._read_index()
        start = html.index('function formatMarkdown(text)')
        end = html.index('function updateGenerationCounterDisplay', start)
        block = html[start:end]
        self.assertLess(block.index(".replace(/</g, '&lt;')"), block.index("html.replace(/^##"))
        self.assertIn(".replace(/'/g, '&#039;')", block)

    def test_voice_page_uses_main_content_layout(self):
        """语音页 → 桌面端使用主内容区留白，不被左侧导航遮住"""
        html = self._read_index()
        self.assertRegex(
            html,
            r'<div class="page-container">[\s\S]*?<div id="page-voice" class="page">'
        )
        self.assertNotIn('#page-voice {', html)
        self.assertRegex(
            html,
            r'@media \(min-width: 1180px\) \{[\s\S]*?\.page-container \{[\s\S]*?margin-left:\s*calc\(174px'
        )
        self.assertEqual(html.count('id="recording-progress-fill"'), 1)

    def test_voice_ai_result_labels_follow_interface_language(self):
        """语音问答 → 问题、回答中和回答完成标题全部使用 i18n。"""
        html = self._read_index()
        start = html.index('async function confirmAndAskAI()')
        end = html.index('// ==================== 账号系统', start)
        block = html[start:end]
        for key in ('voice.question_label', 'voice.answer_title', 'voice.answering_title'):
            self.assertIn(key, block)
        self.assertNotIn("'问题：' + voiceRecognizedText", block)
        self.assertNotIn("displayEl.value = '✅ AI 回答：", block)
        self.assertNotIn("displayEl.value = '🤖 AI 回答中", block)

    def test_food_weight_request_sends_current_language(self):
        """重量查询 → 前端把当前界面语言传给后端。"""
        html = self._read_index()
        start = html.index('async function queryFoodWeight()')
        end = html.index('// ==================== 首页保存摄入', start)
        block = html[start:end]
        self.assertIn('language: getCurrentLanguage()', block)

    def test_navigation_and_shopping_region_controls(self):
        """导航与采购页 → 语义化按钮、完整地区控件和本地偏好存储"""
        html = self._read_index()
        self.assertIn('<nav class="tab-bar" aria-label="主要功能">', html)
        self.assertEqual(html.count('type="button" class="tab-item'), 7)
        self.assertIn('id="shopping-province"', html)
        self.assertIn('id="shopping-city"', html)
        self.assertIn('data-en="Macao SAR"', html)
        self.assertIn('function updateShoppingProvinceLabels()', html)
        self.assertIn("const SHOPPING_REGION_KEY = 'fgai_shopping_region';", html)
        self.assertIn('shopping_region: shoppingRegion', html)
        self.assertIn('shopping_province: province', html)
        self.assertIn("safeApiCall('/api/shopping/preferences'", html)
        self.assertIn("safeApiCall('/api/shopping/price-feedback'", html)
        self.assertGreaterEqual(html.count('${formatMarkdown(fullContent)}'), 2)

    def test_meal_labels_are_editable_and_recipe_linkage_labels_three_meals(self):
        """摄入概览可选择/修改餐次，食谱三次生成标记早午晚餐。"""
        html = self._read_index()
        self.assertIn('id="intake-meal-type-home"', html)
        self.assertIn('id="edit-meal-${originalIndex}"', html)
        self.assertIn("['breakfast', 'lunch', 'dinner'][count - 1]", html)
        self.assertIn("meal_type: 'dinner'", html)
        self.assertIn('meal_type: mealType', html)

    def test_auth_recovery_and_password_visibility_controls_exist(self):
        """账号弹窗提供密码显示、恢复码重设及退出前同步。"""
        html = self._read_index()
        self.assertIn('id="auth-forgot-btn"', html)
        self.assertIn('id="auth-recovery-view"', html)
        self.assertIn('id="recovery-code-modal"', html)
        self.assertIn("fetch('/api/auth/recover'", html)
        self.assertIn("togglePasswordVisibility('auth-password'", html)
        logout = html[html.index('async function handleLogout()'):]
        self.assertLess(logout.index('await saveData();'), logout.index("fetch('/api/auth/logout'"))

    def test_chat_history_is_not_persisted_from_frontend(self):
        """AI 对话 → 不再保存/恢复历史记录，避免测试记录残留"""
        html = self._read_index()
        self.assertNotIn('chat_history', html)
        self.assertNotIn('restoreChatHistory();', html)
        self.assertNotIn('appData.chat_history.push', html)

    def test_i18n_referenced_keys_exist_in_both_languages(self):
        """中英文翻译 → 页面引用 key 均存在"""
        html = self._read_index()
        zh = self._read_locale('zh-CN.json')
        en = self._read_locale('en-US.json')
        keys = set(re.findall(r'data-i18n(?:-[a-z]+)?="([^"]+)"', html))
        keys.update(re.findall(r"window\.i18n\.t\(['\"]([^'\"]+)['\"]", html))
        zh_missing = sorted(k for k in keys if not self._has_i18n_key(zh, k))
        en_missing = sorted(k for k in keys if not self._has_i18n_key(en, k))
        self.assertEqual(zh_missing, [])
        self.assertEqual(en_missing, [])

    def test_auth_short_password_error_is_translatable(self):
        """注册短密码 → 前端能显示明确的本地化错误"""
        html = self._read_index()
        zh = self._read_locale('zh-CN.json')
        en = self._read_locale('en-US.json')
        self.assertIn("'密码长度至少': 'auth.error_short_password'", html)
        self.assertEqual(zh['auth']['error_short_password'], '密码长度至少 6 位')
        self.assertEqual(en['auth']['error_short_password'], 'Password must be at least 6 characters')

    def test_auth_success_toast_is_visible_after_modal_closes(self):
        """认证提示 → 关闭遮罩后再在页面顶部显示，失败信息不会被复位清空"""
        html = self._read_index()
        start = html.index('async function submitAuth()')
        end = html.index('async function handleLogout()', start)
        block = html[start:end]
        self.assertLess(block.index('tryCloseAuthModal();'), block.index('showToast(msg);'))
        self.assertNotIn('switchAuthTab(authMode)', block)
        self.assertIn("window.i18n.t('auth.session_expired')", html)

    def test_auth_modal_is_mobile_safe(self):
        """登录弹窗 → 移动端居中且横屏可滚动，不因 padding 溢出屏幕"""
        html = self._read_index()
        self.assertIn('#auth-modal > div {', html)
        self.assertIn('width: min(100%, 380px) !important;', html)
        self.assertIn('width: min(340px, calc(100vw - 32px)) !important;', html)
        self.assertIn('justify-content: center !important;', html)
        self.assertIn('align-items: flex-start !important;', html)
        self.assertIn('max-height: calc(100dvh - 32px);', html)
        self.assertNotIn('justify-content: flex-start !important;', html)
        self.assertIn('box-sizing: border-box;', html)

    def test_mobile_navigation_and_narrow_actions_fit_without_horizontal_scroll(self):
        """窄屏布局 → 7 个菜单完整等宽显示，主要操作可纵向排列"""
        html = self._read_index()
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1.0">', html)
        self.assertIn('flex: 1 1 0;', html)
        self.assertIn('min-width: 0;', html)
        self.assertIn('width: calc(100% - 20px);', html)
        self.assertIn('class="inline-action-row chat-input-row"', html)
        self.assertIn('class="recipe-action-grid"', html)
        self.assertIn('class="image-action-row"', html)
        self.assertIn('flex-direction: column !important;', html)


class FakeSupabaseDB:
    """内存版 Supabase PostgREST 模拟器（用于账号系统测试）"""

    def __init__(self):
        self.users = []       # [{'id', 'username', 'password_hash'}]
        self.user_data = {}   # {user_id: data}
        self.intake_records = []

    def __call__(self, method, path, params=None, json_body=None, extra_headers=None):
        params = params or {}
        if path == 'users':
            if method == 'GET':
                uname = params.get('username', 'eq.')[3:]
                return [dict(u) for u in self.users if u['username'] == uname]
            if method == 'POST':
                row = dict(json_body[0])
                row['id'] = f'uid-{len(self.users) + 1}'
                self.users.append(row)
                return [dict(row)]
            if method == 'PATCH':
                uid = params.get('id', 'eq.')[3:]
                for user in self.users:
                    if user['id'] == uid:
                        user.update(json_body or {})
                return []
        if path == 'user_data':
            if method == 'GET':
                uid = params.get('user_id', 'eq.')[3:]
                d = self.user_data.get(uid)
                return [{'data': d}] if d is not None else []
            if method == 'POST':  # upsert
                for row in json_body:
                    self.user_data[row['user_id']] = row.get('data', {})
                return [dict(r) for r in json_body]
        if path == 'intake_records':
            if method == 'GET':
                uid = params.get('user_id', 'eq.')[3:]
                return [dict(r) for r in self.intake_records if r['user_id'] == uid]
            if method == 'DELETE':
                uid = params.get('user_id', 'eq.')[3:]
                keep_ids = set()
                id_filter = params.get('id', '')
                if id_filter.startswith('not.in.(') and id_filter.endswith(')'):
                    keep_ids = set(id_filter[8:-1].split(','))
                self.intake_records = [
                    r for r in self.intake_records
                    if r['user_id'] != uid or r['id'] in keep_ids
                ]
                return []
            if method == 'POST':
                for row in json_body or []:
                    self.intake_records = [r for r in self.intake_records if r['id'] != row['id']]
                    self.intake_records.append(dict(row))
                return [dict(r) for r in json_body or []]
        return []


class TestAuthSystem(unittest.TestCase):
    """账号系统测试（db_request 替换为内存模拟器，不访问真实数据库）"""

    def setUp(self):
        self._orig_url, self._orig_key = fga.SUPABASE_URL, fga.SUPABASE_KEY
        fga.SUPABASE_URL = 'https://fake.supabase.co'
        fga.SUPABASE_KEY = 'fake-key'
        fga.ENABLE_DETAILED_LOGS = False
        # 模拟 Vercel 环境：注册时不继承本地 fgai_local_data.json，保证测试确定性
        self._orig_vercel = os.environ.pop('VERCEL', None)
        os.environ['VERCEL'] = '1'
        self.fake_db = FakeSupabaseDB()
        self._patcher = patch('food_guardian_ai_2.db_request', self.fake_db)
        self._patcher.start()
        self.client = fga.app.test_client()
        fga._auth_failures.clear()

    def tearDown(self):
        self._patcher.stop()
        fga.SUPABASE_URL, fga.SUPABASE_KEY = self._orig_url, self._orig_key
        if self._orig_vercel is None:
            os.environ.pop('VERCEL', None)
        else:
            os.environ['VERCEL'] = self._orig_vercel

    # ---- 注册 ----

    def test_register_success_auto_login(self):
        """注册成功 → 自动登录 + 初始化云端数据"""
        resp = self.client.post('/api/auth/register',
                                json={'username': 'alice', 'password': 'secret123'})
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['username'], 'alice')

        # 会话已建立
        me = self.client.get('/api/auth/me').get_json()
        self.assertEqual(me['user']['username'], 'alice')

        # user_data 已初始化且昵称默认为用户名
        uid = data['user']['id']
        self.assertIn(uid, self.fake_db.user_data)
        self.assertEqual(self.fake_db.user_data[uid]['nickname'], 'alice')

    def test_register_password_hashed(self):
        """注册 → 数据库中绝不存储明文密码"""
        self.client.post('/api/auth/register',
                         json={'username': 'bob', 'password': 'secret123'})
        stored = self.fake_db.users[0]['password_hash']
        self.assertNotIn('secret123', stored)
        # 哈希可被校验
        self.assertTrue(fga.check_password_hash(stored, 'secret123'))

    def test_recovery_code_resets_password_and_rotates(self):
        """恢复码只返回明文一次，可重设密码并自动轮换。"""
        registered = self.client.post('/api/auth/register', json={
            'username': 'recover_user', 'password': 'secret123'
        }).get_json()
        code = registered['recovery_code']
        self.assertEqual(len(code), 12)
        self.assertNotEqual(self.fake_db.users[0]['recovery_hash'], code)

        reset = self.client.post('/api/auth/recover', json={
            'username': 'recover_user', 'recovery_code': code,
            'new_password': 'newsecret456'
        }).get_json()
        self.assertTrue(reset['success'])
        self.assertNotEqual(reset['recovery_code'], code)

        other = fga.app.test_client()
        self.assertTrue(other.post('/api/auth/login', json={
            'username': 'recover_user', 'password': 'newsecret456'
        }).get_json()['success'])

    def test_login_rate_limit_after_five_failures(self):
        """15 分钟内连续 5 次密码错误会被锁定。"""
        self.client.post('/api/auth/register', json={
            'username': 'limited_user', 'password': 'secret123'
        })
        attacker = fga.app.test_client()
        response = None
        for _ in range(5):
            response = attacker.post('/api/auth/login', json={
                'username': 'limited_user', 'password': 'wrong-password'
            })
        self.assertEqual(response.status_code, 429)
        body = response.get_json()
        self.assertFalse(body['success'])
        self.assertGreater(body['retry_after'], 0)

    def test_register_duplicate_username(self):
        """重复用户名 → 拒绝"""
        self.client.post('/api/auth/register', json={'username': 'alice', 'password': 'secret123'})
        resp = self.client.post('/api/auth/register',
                                json={'username': 'alice', 'password': 'other123'})
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('已被注册', resp.get_json()['error'])

    def test_register_validation(self):
        """非法用户名 / 短密码 → 拒绝"""
        r1 = self.client.post('/api/auth/register', json={'username': 'a', 'password': 'secret123'})
        self.assertFalse(r1.get_json()['success'])
        r2 = self.client.post('/api/auth/register', json={'username': 'valid', 'password': '123'})
        self.assertFalse(r2.get_json()['success'])

    def test_register_short_password_explicit_message(self):
        """密码少于 6 位 → 注册失败并明确提示长度要求"""
        resp = self.client.post('/api/auth/register',
                                json={'username': 'shortpwd', 'password': '12345'})
        body = resp.get_json()
        self.assertFalse(body['success'])
        self.assertIn('密码长度至少 6 位', body['error'])

    def test_register_chinese_username(self):
        """中文用户名 → 允许"""
        resp = self.client.post('/api/auth/register',
                                json={'username': '小明', 'password': 'secret123'})
        self.assertTrue(resp.get_json()['success'])

    def test_new_account_does_not_inherit_guest_data(self):
        """新账号初始化 → 不继承游客摄入、环保统计或测试对话"""
        old_vercel = os.environ.pop('VERCEL', None)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with open(os.path.join(tmpdir, 'fgai_local_data.json'), 'w', encoding='utf-8') as f:
                    data = dict(TEST_FIXTURE)
                    data['waste_reduced'] = 321
                    data['daily_intake_records'] = [{
                        'date': fga.get_china_time().strftime('%Y-%m-%d'),
                        'time': '08:00', 'vegetables': 500,
                        'fruits': 0, 'meat': 0, 'eggs': 0
                    }]
                    data['chat_history'] = [{'text': 'old test message', 'sender': 'user'}]
                    json.dump(data, f, ensure_ascii=False)

                with patch('food_guardian_ai_2.BASE_DIR', tmpdir):
                    initial = fga.build_initial_user_data('fresh_user')

            self.assertEqual(initial['nickname'], 'fresh_user')
            self.assertEqual(initial['waste_reduced'], 0)
            self.assertEqual(initial['daily_intake_records'], [])
            self.assertNotIn('chat_history', initial)
        finally:
            if old_vercel is not None:
                os.environ['VERCEL'] = old_vercel
            else:
                os.environ.pop('VERCEL', None)

    def test_register_falls_back_to_local_db_when_supabase_unavailable(self):
        """Supabase 连接失败 → 本地开发自动切换到 SQLite 账号库，注册仍成功"""
        old_vercel = os.environ.pop('VERCEL', None)
        old_local_db = fga.LOCAL_ACCOUNT_DB
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                fga.LOCAL_ACCOUNT_DB = os.path.join(tmpdir, 'accounts.db')
                with patch('food_guardian_ai_2.db_request', return_value=None):
                    client = fga.app.test_client()
                    resp = client.post('/api/auth/register',
                                       json={'username': 'fallback_user', 'password': 'secret123'})
                    body = resp.get_json()
                    self.assertTrue(body['success'])
                    self.assertEqual(body['user']['username'], 'fallback_user')

                    data = client.get('/api/data').get_json()
                    self.assertTrue(data['auth_enabled'])
                    self.assertEqual(data['user']['username'], 'fallback_user')
        finally:
            fga.LOCAL_ACCOUNT_DB = old_local_db
            if old_vercel is not None:
                os.environ['VERCEL'] = old_vercel
            else:
                os.environ.pop('VERCEL', None)

    def test_local_sqlite_intake_persists_after_new_login(self):
        """真实 SQLite → 保存餐次后，新会话登录仍可查看今日概览和 7 天记录"""
        old_vercel = os.environ.pop('VERCEL', None)
        old_url, old_key = fga.SUPABASE_URL, fga.SUPABASE_KEY
        old_local_db = fga.LOCAL_ACCOUNT_DB
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                fga.SUPABASE_URL, fga.SUPABASE_KEY = '', ''
                fga.LOCAL_ACCOUNT_DB = os.path.join(tmpdir, 'accounts.db')

                first = fga.app.test_client()
                registered = first.post('/api/auth/register', json={
                    'username': 'persist_user', 'password': 'secret123'
                }).get_json()
                self.assertTrue(registered['success'])
                saved = first.post('/api/save_intake', json={
                    'vegetables': 180, 'fruits': 90, 'meat': 45, 'eggs': 20,
                    'meal_type': 'lunch'
                }).get_json()
                self.assertTrue(saved['success'])

                db = sqlite3.connect(fga.LOCAL_ACCOUNT_DB)
                try:
                    self.assertEqual(
                        db.execute('SELECT COUNT(*) FROM intake_records').fetchone()[0], 1
                    )
                    profile = json.loads(db.execute('SELECT data FROM user_data').fetchone()[0])
                    self.assertNotIn('daily_intake_records', profile)
                finally:
                    db.close()

                second = fga.app.test_client()
                logged_in = second.post('/api/auth/login', json={
                    'username': 'persist_user', 'password': 'secret123'
                }).get_json()
                self.assertTrue(logged_in['success'])
                stored = second.get('/api/data').get_json()['data']['daily_intake_records']
                history = second.get('/api/intake/history/7days').get_json()['history']

                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0]['vegetables'], 180.0)
                self.assertEqual(stored[0]['meal_type'], 'lunch')
                self.assertEqual(history[0]['record_count'], 1)
                self.assertEqual(history[0]['vegetables'], 180.0)
        finally:
            fga.SUPABASE_URL, fga.SUPABASE_KEY = old_url, old_key
            fga.LOCAL_ACCOUNT_DB = old_local_db
            if old_vercel is not None:
                os.environ['VERCEL'] = old_vercel
            else:
                os.environ.pop('VERCEL', None)

    # ---- 登录/登出 ----

    def _register_and_new_client(self, username, password):
        """注册后返回携带独立会话的新 client（模拟另一台设备）"""
        self.client.post('/api/auth/register', json={'username': username, 'password': password})
        return fga.app.test_client()

    def test_login_logout_flow(self):
        """登录 → 建立 3 天无活动会话；登出 → 会话清除"""
        self.client.post('/api/auth/register', json={'username': 'carol', 'password': 'secret123'})
        other = fga.app.test_client()  # 新会话（未登录）

        resp = other.post('/api/auth/login', json={'username': 'carol', 'password': 'secret123'})
        self.assertTrue(resp.get_json()['success'])
        self.assertEqual(other.get('/api/auth/me').get_json()['user']['username'], 'carol')

        other.post('/api/auth/logout')
        self.assertIsNone(other.get('/api/auth/me').get_json()['user'])

    def test_session_expires_after_three_inactive_days(self):
        """账号连续 3 天无活动 → 自动退出并返回明确过期标记"""
        self.client.post('/api/auth/register', json={
            'username': 'idle_user', 'password': 'secret123'
        })
        with self.client.session_transaction() as sess:
            sess['last_activity_at'] = (
                fga.get_china_time() - fga.timedelta(days=3, seconds=1)
            ).isoformat()

        body = self.client.get('/api/data').get_json()
        self.assertIsNone(body['user'])
        self.assertTrue(body['session_expired'])
        self.assertEqual(fga.app.config['PERMANENT_SESSION_LIFETIME'], fga.timedelta(days=3))

    def test_active_session_is_refreshed_before_three_days(self):
        """账号 3 天内仍有活动 → 保持登录并刷新最后活动时间"""
        self.client.post('/api/auth/register', json={
            'username': 'active_user', 'password': 'secret123'
        })
        old_activity = (fga.get_china_time() - fga.timedelta(days=2)).isoformat()
        with self.client.session_transaction() as sess:
            sess['last_activity_at'] = old_activity

        body = self.client.get('/api/auth/me').get_json()
        self.assertEqual(body['user']['username'], 'active_user')
        self.assertFalse(body['session_expired'])
        with self.client.session_transaction() as sess:
            self.assertGreater(sess['last_activity_at'], old_activity)

    def test_login_wrong_password(self):
        """错误密码 → 拒绝"""
        self.client.post('/api/auth/register', json={'username': 'dave', 'password': 'secret123'})
        resp = fga.app.test_client().post('/api/auth/login',
                                          json={'username': 'dave', 'password': 'wrong'})
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('密码错误', resp.get_json()['error'])

    def test_login_unknown_user(self):
        """不存在的用户 → 明确提示先注册"""
        resp = self.client.post('/api/auth/login',
                                json={'username': 'ghost', 'password': 'whatever'})
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('没有该账号', resp.get_json()['error'])

    def test_auth_me_guest(self):
        """游客查询 → user 为 None"""
        self.assertIsNone(self.client.get('/api/auth/me').get_json()['user'])

    # ---- 数据隔离（核心） ----

    def test_data_isolation_between_users(self):
        """两个账号 → 数据完全隔离"""
        # 账号 A 注册并写入数据
        resp_a = self.client.post('/api/auth/register',
                                  json={'username': 'userA', 'password': 'secret123'})
        self.assertTrue(resp_a.get_json()['success'])
        self.assertTrue(self.client.post('/api/data', json={'nickname': 'AA', 'waste_reduced': 999}).get_json()['success'])

        # 账号 B 用独立会话注册自己的账号（数据应与 A 完全隔离）
        client_b = fga.app.test_client()
        resp_b = client_b.post('/api/auth/register',
                               json={'username': 'userB', 'password': 'secret123'})
        self.assertTrue(resp_b.get_json()['success'])

        # B 读到的数据不含 A 写入的 waste_reduced
        data_b = client_b.get('/api/data').get_json()
        self.assertNotEqual(data_b['data'].get('waste_reduced'), 999)
        self.assertEqual(data_b['user']['username'], 'userB')

        # A 重新登录后仍能读回自己的数据
        client_a2 = fga.app.test_client()
        client_a2.post('/api/auth/login', json={'username': 'userA', 'password': 'secret123'})
        data_a = client_a2.get('/api/data').get_json()
        self.assertEqual(data_a['data'].get('nickname'), 'AA')
        self.assertEqual(data_a['data'].get('waste_reduced'), 999)

    def test_intake_history_isolated_per_account(self):
        """🔐 今日摄入概览/近7天记录 → 登录哪个账号就看哪个账号的真实数据"""
        # 账号 A 注册并保存 2 条摄入记录
        self.client.post('/api/auth/register',
                         json={'username': 'userA', 'password': 'secret123'})
        for _ in range(2):
            self.assertTrue(self.client.post('/api/save_intake', json={
                'vegetables': 100, 'fruits': 50, 'meat': 30, 'eggs': 20
            }).get_json()['success'])
        hist_a = self.client.get('/api/intake/history/7days').get_json()['history']

        # 账号 B（独立会话）保存 1 条不同数值的记录
        client_b = fga.app.test_client()
        client_b.post('/api/auth/register',
                      json={'username': 'userB', 'password': 'secret123'})
        client_b.post('/api/save_intake', json={
            'vegetables': 300, 'fruits': 0, 'meat': 0, 'eggs': 0
        })
        hist_b = client_b.get('/api/intake/history/7days').get_json()['history']

        # 各自的 7 天历史只含自己的记录，条数与数值互不干扰
        self.assertEqual(len(hist_a), 1)
        self.assertEqual(hist_a[0]['record_count'], 2)
        self.assertEqual(hist_a[0]['vegetables'], 200)

        self.assertEqual(len(hist_b), 1)
        self.assertEqual(hist_b[0]['record_count'], 1)
        self.assertEqual(hist_b[0]['vegetables'], 300)

    def test_cloud_rolling_window_deletes_day_eight(self):
        """云端账号数据 → 新记录写入后删除第 8 天，保留跨周但仍在 7 天内的数据"""
        monday = fga.datetime(2026, 9, 21, 9, 0, tzinfo=fga.CHINA_TZ)
        day_7 = (monday - fga.timedelta(days=6)).strftime('%Y-%m-%d')
        day_8 = (monday - fga.timedelta(days=7)).strftime('%Y-%m-%d')
        with patch('food_guardian_ai_2.get_china_time', return_value=monday):
            registered = self.client.post('/api/auth/register', json={
                'username': 'weekly_user', 'password': 'secret123'
            }).get_json()
            user_id = registered['user']['id']
            self.fake_db.user_data[user_id]['daily_intake_records'] = [
                {'date': day_7, 'time': '20:00', 'vegetables': 70, 'fruits': 0, 'meat': 0, 'eggs': 0},
                {'date': day_8, 'time': '20:00', 'vegetables': 999, 'fruits': 0, 'meat': 0, 'eggs': 0}
            ]

            saved = self.client.post('/api/save_intake', json={
                'vegetables': 120, 'fruits': 60, 'meat': 30, 'eggs': 20
            }).get_json()

        self.assertTrue(saved['success'])
        stored = [
            {
                'date': row['record_date'],
                'vegetables': row['vegetables']
            }
            for row in self.fake_db.intake_records
            if row['user_id'] == user_id
        ]
        self.assertEqual(len(stored), 2)
        self.assertEqual([record['date'] for record in stored], [day_7, '2026-09-21'])
        self.assertNotIn(day_8, [record['date'] for record in stored])

    def test_data_response_contains_user_field(self):
        """/api/data → 响应携带 user 字段供前端同步登录态"""
        result = self.client.get('/api/data').get_json()
        self.assertIn('user', result)
        self.assertIsNone(result['user'])  # 游客

    def test_auth_disabled_without_db(self):
        """未配置数据库 → 明确报错而非崩溃"""
        fga.SUPABASE_URL, fga.SUPABASE_KEY = '', ''
        resp = self.client.post('/api/auth/login',
                                json={'username': 'x', 'password': 'y'})
        body = resp.get_json()
        self.assertFalse(body['success'])
        self.assertIn('未配置数据库', body['error'])

    # ---- 强制登录门开关 ----

    def test_data_response_contains_auth_enabled(self):
        """/api/data → 携带 auth_enabled 开关（前端据此决定是否强制登录）"""
        result = self.client.get('/api/data').get_json()
        self.assertTrue(result['auth_enabled'])  # setUp 中已配置假数据库

        # 未配置数据库 → 开关关闭，前端回退游客模式（不会锁死应用）
        fga.SUPABASE_URL, fga.SUPABASE_KEY = '', ''
        result = self.client.get('/api/data').get_json()
        self.assertFalse(result['auth_enabled'])

    def test_auth_me_contains_auth_enabled(self):
        """/api/auth/me → 携带 auth_enabled 开关"""
        result = self.client.get('/api/auth/me').get_json()
        self.assertTrue(result['auth_enabled'])


if __name__ == '__main__':
    print('=' * 60)
    print('  FoodGuardian AI - Test Suite')
    print('=' * 60)
    unittest.main(verbosity=2)
