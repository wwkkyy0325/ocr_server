#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试OCR子进程架构的简单脚本
"""

import sys
import os
import time
from PIL import Image
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_subprocess_architecture():
    """测试子进程架构"""
    print("=== 测试OCR子进程架构 ===")
    
    try:
        # 初始化配置管理器
        from app.core.config_manager import ConfigManager
        config_manager = ConfigManager()
        print("✓ 配置管理器初始化成功")
        
        # 获取子进程管理器
        from app.core.ocr_subprocess import get_ocr_subprocess_manager
        subprocess_manager = get_ocr_subprocess_manager(config_manager)
        print("✓ 子进程管理器获取成功")
        
        # 启动子进程
        print("\n--- 启动子进程 ---")
        success = subprocess_manager.start_process('mobile')
        if success:
            print("✓ 子进程启动成功")
            print(f"  状态: {subprocess_manager.get_status()}")
        else:
            print("✗ 子进程启动失败")
            return False
            
        # 创建测试图像
        print("\n--- 创建测试图像 ---")
        # 创建一个简单的测试图像
        test_image = Image.new('RGB', (400, 200), color='white')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_image)
        draw.text((50, 50), "测试文本 Test 123", fill='black')
        draw.rectangle([200, 100, 350, 150], outline='red', width=2)
        print("✓ 测试图像创建成功")
        
        # 在子进程中处理图像
        print("\n--- 处理图像 ---")
        start_time = time.time()
        try:
            result = subprocess_manager.process_image(test_image)
            processing_time = time.time() - start_time
            
            print("✓ 图像处理成功")
            print(f"  处理时间: {processing_time:.2f}秒")
            print(f"  识别结果: {result.get('full_text', 'N/A')}")
            print(f"  区域数量: {len(result.get('regions', []))}")
            
            # 显示详细结果
            regions = result.get('regions', [])
            if regions:
                print("  识别的文本区域:")
                for i, region in enumerate(regions[:3]):  # 只显示前3个
                    text = region.get('text', '')[:30]
                    conf = region.get('confidence', 0)
                    print(f"    [{i+1}] '{text}' (置信度: {conf:.2f})")
                if len(regions) > 3:
                    print(f"    ... 还有 {len(regions)-3} 个区域")
                    
        except Exception as e:
            print(f"✗ 图像处理失败: {e}")
            return False
            
        # 测试预设切换
        print("\n--- 测试预设切换 ---")
        switch_success = subprocess_manager.switch_preset('server')
        if switch_success:
            print("✓ 预设切换成功 (mobile → server)")
            print(f"  当前状态: {subprocess_manager.get_status()}")
        else:
            print("✗ 预设切换失败")
            
        # 再次处理图像
        start_time = time.time()
        try:
            result2 = subprocess_manager.process_image(test_image)
            processing_time2 = time.time() - start_time
            print("✓ Server模式图像处理成功")
            print(f"  处理时间: {processing_time2:.2f}秒")
            print(f"  识别结果: {result2.get('full_text', 'N/A')}")
        except Exception as e:
            print(f"✗ Server模式图像处理失败: {e}")
            
        # 停止子进程
        print("\n--- 停止子进程 ---")
        subprocess_manager.stop_process()
        print("✓ 子进程已停止")
        print(f"  最终状态: {subprocess_manager.get_status()}")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_ocr_engine():
    """测试直接使用OCR引擎（对比测试）"""
    print("\n=== 对比测试：直接使用OCR引擎 ===")
    
    try:
        from app.core.config_manager import ConfigManager
        from app.ocr.engine import OcrEngine
        
        config_manager = ConfigManager()
        ocr_engine = OcrEngine.get_instance(config_manager, preset='mobile')
        print("✓ OCR引擎初始化成功")
        
        # 创建测试图像
        test_image = Image.new('RGB', (400, 200), color='white')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_image)
        draw.text((50, 50), "对比测试 Compare", fill='black')
        
        # 处理图像
        start_time = time.time()
        result = ocr_engine.process_image(test_image)
        processing_time = time.time() - start_time
        
        print("✓ 直接OCR处理成功")
        print(f"  处理时间: {processing_time:.2f}秒")
        print(f"  识别结果: {result.get('full_text', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"✗ 直接OCR测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("OCR子进程架构测试")
    print("=" * 50)
    
    # 测试子进程架构
    subprocess_success = test_subprocess_architecture()
    
    # 测试直接OCR引擎
    direct_success = test_direct_ocr_engine()
    
    print("\n" + "=" * 50)
    print("测试总结:")
    print(f"  子进程架构测试: {'通过' if subprocess_success else '失败'}")
    print(f"  直接OCR测试: {'通过' if direct_success else '失败'}")
    
    if subprocess_success and direct_success:
        print("\n🎉 所有测试通过！子进程架构工作正常。")
    else:
        print("\n❌ 部分测试失败，请检查错误信息。")
