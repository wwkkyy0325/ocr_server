# -*- coding: utf-8 -*-

# 文件说明：
# - 作用：爬虫基类，规范查询与登录接口
# - 核心实现：抽象方法 query/login 由子类实现具体站点逻辑
# - 关联关系：OfficialScraper/SafetyCertScraper 继承此类，在 AutomationTaskManager 中被调度
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    def __init__(self, driver):
        self.driver = driver
        
    @abstractmethod
    def query(self, id_card):
        """
        根据身份证号查询信息
        
        Args:
            id_card (str): 身份证号
            
        Returns:
            dict: 查询结果字典，失败返回 None
        """
        pass
    
    @abstractmethod
    def login(self):
        """
        如果需要登录，在此实现
        """
        pass
