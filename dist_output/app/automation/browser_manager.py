# -*- coding: utf-8 -*-

"""
浏览器管理器
负责创建和配置 Selenium WebDriver，包含反爬虫对抗措施
"""

import os
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class BrowserManager:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]

    def create_driver(self, headless=False, proxy=None):
        """
        创建一个配置好的 Chrome WebDriver
        
        Args:
            headless (bool): 是否使用无头模式
            proxy (str): 代理地址 (例如 "ip:port" 或 "http://user:pass@ip:port")
            
        Returns:
            webdriver.Chrome: 配置好的驱动实例
        """
        options = Options()
        
        # 基础设置
        if headless:
            options.add_argument("--headless=new") # 新版无头模式更难被检测
        
        # 反爬虫对抗设置
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 随机 User-Agent
        user_agent = random.choice(self.user_agents)
        options.add_argument(f'user-agent={user_agent}')
        
        # 其他常规优化
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # 代理设置
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            
        try:
            # 自动管理 ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # 进一步移除 WebDriver 特征 (CDP 命令)
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            return driver
        except Exception as e:
            print(f"Error creating driver: {e}")
            return None
