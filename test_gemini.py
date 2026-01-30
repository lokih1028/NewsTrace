#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NewsTrace 诊断脚本
用于测试 Gemini API 是否正常工作
"""

import os
import sys

def test_gemini_api():
    """测试 Gemini API"""
    print("=" * 60)
    print("NewsTrace Gemini API 诊断")
    print("=" * 60)
    print()
    
    # 1. 检查 API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 错误: 未设置 GEMINI_API_KEY 环境变量")
        print()
        print("请先设置:")
        print("  Windows: $env:GEMINI_API_KEY=\"your-key\"")
        print("  Linux/Mac: export GEMINI_API_KEY=\"your-key\"")
        return False
    
    print(f"✅ GEMINI_API_KEY 已设置: {api_key[:10]}...{api_key[-5:]}")
    print()
    
    # 2. 测试 Gemini Provider
    print("正在测试 Gemini Provider...")
    try:
        from src.llm_provider import GeminiProvider
        
        provider = GeminiProvider(
            api_key=api_key,
            model="gemini-2.0-flash",
            temperature=0.3,
            max_tokens=2000
        )
        
        print("✅ GeminiProvider 初始化成功")
        print()
        
        # 3. 测试简单调用
        print("正在测试 API 调用...")
        test_prompt = """请返回以下 JSON 格式:
{
  "audit_result": {
    "score": 75,
    "risk_level": "Medium",
    "warnings": ["测试成功"]
  },
  "recommended_tickers": []
}
"""
        
        response = provider.generate(test_prompt)
        print(f"✅ API 调用成功")
        print(f"   模型: {response.model}")
        print(f"   输入 tokens: {response.input_tokens}")
        print(f"   输出 tokens: {response.output_tokens}")
        print()
        print("响应内容:")
        print("-" * 60)
        print(response.content[:500])
        print("-" * 60)
        print()
        
        # 4. 测试 JSON 解析
        import json
        try:
            content = response.content
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            result = json.loads(content)
            print("✅ JSON 解析成功")
            print(f"   评分: {result.get('audit_result', {}).get('score')}")
            print(f"   风险等级: {result.get('audit_result', {}).get('risk_level')}")
            print()
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print("   这可能导致审计失败")
            return False
        
        print("=" * 60)
        print("✅ 所有测试通过! Gemini API 工作正常")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请确保在项目根目录运行此脚本")
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_gemini_api()
    sys.exit(0 if success else 1)
