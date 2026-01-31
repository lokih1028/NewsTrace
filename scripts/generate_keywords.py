#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能关键词配置工具
用法: python scripts/generate_keywords.py 600519.SH 000858.SZ
"""
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.keyword_generator import KeywordGenerator


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/generate_keywords.py <股票代码1> <股票代码2> ...")
        print("示例: python scripts/generate_keywords.py 600519.SH 000858.SZ")
        sys.exit(1)
    
    stock_codes = sys.argv[1:]
    
    print(f"\n🔍 为 {len(stock_codes)} 只股票生成关键词配置...\n")
    
    # 初始化生成器
    llm_config = {
        'api_key': os.getenv('OPENAI_API_KEY'),
        'model': 'gpt-4o-mini'
    }
    generator = KeywordGenerator(llm_config)
    
    # 生成配置
    config = generator.generate_config(stock_codes)
    
    # 打印结果
    print("=" * 60)
    print("📋 生成的配置:")
    print("=" * 60)
    print(f"\n总关键词数: {len(config['watch_keywords'])}")
    print(f"关键词列表: {config['watch_keywords']}\n")
    
    print("-" * 60)
    print("股票映射:")
    print("-" * 60)
    for code, keywords in config['stock_mapping'].items():
        print(f"\n{code}:")
        print(f"  关键词: {', '.join(keywords)}")
    
    # 保存到文件
    output_file = "config/auto_keywords.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 配置已保存到: {output_file}")
    print("\n💡 使用方法:")
    print("   在 main.py 中设置: WATCH_KEYWORDS = config['watch_keywords']")


if __name__ == "__main__":
    main()
