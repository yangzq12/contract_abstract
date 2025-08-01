#!/usr/bin/env python3

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slither import Slither
from slither.exceptions import SlitherError

def test_slither_init():
    """测试 Slither 初始化"""
    print("开始测试 Slither 初始化...")
    
    try:
        # 测试一个简单的合约地址
        target = "0x7F37f78cBD74481E593F9C737776F7113d76B315"
        print(f"目标地址: {target}")
        
        # 这里应该会触发断点
        slither = Slither(target)
        print("Slither 初始化成功!")
        
        return slither
        
    except SlitherError as e:
        print(f"SlitherError: {e}")
        return None
    except Exception as e:
        print(f"其他异常: {e}")
        return None

if __name__ == "__main__":
    test_slither_init() 