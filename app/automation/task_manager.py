# -*- coding: utf-8 -*-

"""
自动化任务管理器
负责管理多线程查询任务
"""

import threading
import queue
import time
import os
from .browser_manager import BrowserManager
from .scrapers.official_scraper import OfficialScraper
from .scrapers.safety_cert_scraper import SafetyCertScraper

class AutomationTaskManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.results = []
        self.is_running = False
        self.threads = []
        self.browser_manager = BrowserManager()
        self.proxies = [] # 代理列表
        
        self.headless = False
        self.num_threads = 1
        self.delay_range = (2, 5)
        
    def set_config(self, headless=False, num_threads=1, proxies=None, delay_range=(2, 5)):
        self.headless = headless
        cpu_count = os.cpu_count() or 1
        max_by_cpu = max(1, cpu_count // 2)
        safe_threads = max(1, min(num_threads, max_by_cpu))
        if proxies:
            self.proxies = proxies
            safe_threads = max(1, min(safe_threads, len(self.proxies)))
        self.num_threads = safe_threads
        self.delay_range = delay_range
        
    def add_tasks(self, id_cards):
        for id_card in id_cards:
            self.queue.put(id_card)
            
    def start(self, update_callback=None, finish_callback=None):
        if self.is_running:
            return
            
        self.is_running = True
        self.results = []
        self.threads = []
        
        print(f"Starting automation with {self.num_threads} threads, headless={self.headless}")
        
        for i in range(self.num_threads):
            t = threading.Thread(target=self._worker, args=(i, update_callback))
            t.daemon = True
            t.start()
            self.threads.append(t)
            
        # 启动监控线程
        monitor_thread = threading.Thread(target=self._monitor, args=(finish_callback,))
        monitor_thread.daemon = True
        monitor_thread.start()
        
    def stop(self):
        self.is_running = False
        # 等待线程结束
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=1.0)
        print("Automation stopped")
        
    def _worker(self, thread_id, update_callback):
        print(f"Worker {thread_id} started")
        
        # 分配代理 (简单的轮询分配)
        proxy = None
        if self.proxies:
            proxy = self.proxies[thread_id % len(self.proxies)]
            
        # 创建浏览器实例
        driver = self.browser_manager.create_driver(headless=self.headless, proxy=proxy)
        if not driver:
            print(f"Worker {thread_id} failed to create driver")
            return
            
        official_scraper = OfficialScraper(driver)
        safety_scraper = SafetyCertScraper(driver)
        
        try:
            # 登录 (如果需要)
            # scraper.login()
            
            while self.is_running and not self.queue.empty():
                try:
                    id_card = self.queue.get(timeout=1.0)
                    
                    print(f"Worker {thread_id} processing {id_card}")
                    
                    # 1. Run Official Scraper
                    print(f"Worker {thread_id}: Running OfficialScraper for {id_card}")
                    result1 = official_scraper.query(id_card)
                    print(f"Worker {thread_id}: OfficialScraper finished for {id_card}, status={result1['status']}")
                    
                    # 2. Run Safety Cert Scraper
                    print(f"Worker {thread_id}: Running SafetyCertScraper for {id_card}")
                    result2 = safety_scraper.query(id_card)
                    print(f"Worker {thread_id}: SafetyCertScraper finished for {id_card}, status={result2['status']}")
                    
                    # Merge results
                    final_result = result1.copy()
                    if result2 and result2.get('data'):
                         if 'data' not in final_result:
                             final_result['data'] = {}
                         final_result['data'].update(result2['data'])
                    
                    # If Official failed but Safety succeeded, treat as partial success (or Success if that's enough)
                    # We'll just ensure status is Success if at least one succeeded with data
                    if final_result['status'] != 'Success' and result2 and result2['status'] == 'Success':
                         final_result['status'] = 'Success'
                         final_result['extra_info'] = result2.get('extra_info', 'Verified via Safety Cert')
                    
                    if final_result:
                        self.results.append(final_result)
                        if update_callback:
                            update_callback(final_result)
                    
                    self.queue.task_done()
                    
                    # 模拟人类操作延迟
                    import random
                    time.sleep(random.uniform(*self.delay_range))
                    
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"Worker {thread_id} error: {e}")
                    
        finally:
            driver.quit()
            print(f"Worker {thread_id} finished")
            
    def _monitor(self, finish_callback):
        """监控任务完成状态"""
        while self.is_running:
            # 检查是否所有线程都已结束
            alive_threads = [t for t in self.threads if t.is_alive()]
            if not alive_threads:
                break
            time.sleep(1)
            
        self.is_running = False
        if finish_callback:
            finish_callback(self.results)


class AutomationService:
    def __init__(self, task_manager=None):
        self.task_manager = task_manager or AutomationTaskManager()

    def run_async(self, id_cards, config, update_callback=None, finish_callback=None):
        headless = config.get("headless", False)
        num_threads = config.get("num_threads", 1)
        proxies = config.get("proxies") or []
        delay_range = config.get("delay_range", (2, 5))

        self.task_manager.set_config(
            headless=headless,
            num_threads=num_threads,
            proxies=proxies,
            delay_range=delay_range,
        )
        self.task_manager.add_tasks(id_cards)
        self.task_manager.start(
            update_callback=update_callback,
            finish_callback=finish_callback,
        )

    def stop(self):
        self.task_manager.stop()
