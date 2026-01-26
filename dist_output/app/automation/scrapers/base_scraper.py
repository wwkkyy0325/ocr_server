# -*- coding: utf-8 -*-

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
