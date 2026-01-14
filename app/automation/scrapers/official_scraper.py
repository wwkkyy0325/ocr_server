# -*- coding: utf-8 -*-

import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper

class OfficialScraper(BaseScraper):
    def __init__(self, driver):
        super().__init__(driver)
        # 实际的目标网址
        self.url = "https://jzsc.mohurd.gov.cn/data/person" 
        
    def login(self):
        """
        处理登录逻辑 (如有需要)
        """
        pass
        
    def query(self, id_card):
        """
        执行查询逻辑
        """
        windows_before = self.driver.window_handles
        try:
            # 1. 访问查询页面
            self.driver.get(self.url)
            
            # 模拟随机延迟
            time.sleep(random.uniform(1.0, 2.0))
            
            # 2. 输入身份证号
            input_xpath = '//*[@id="app"]/div/div/div[2]/div[2]/div[1]/div[3]/div[2]/div/input'
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, input_xpath))
            )
            input_box = self.driver.find_element(By.XPATH, input_xpath)
            input_box.clear()
            input_box.send_keys(id_card)
            
            # 3. 点击查询
            btn_xpath = '//*[@id="app"]/div/div/div[2]/div[2]/div[2]/div[4]/span'
            # 确保按钮可点击
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, btn_xpath))
            )
            search_btn = self.driver.find_element(By.XPATH, btn_xpath)
            self._safe_click(search_btn)
            
            # 4. 等待结果并点击链接
            link_xpath = '//*[@id="app"]/div/div/div[2]/div[3]/div[1]/div[3]/table/tbody/tr/td[2]/div/div/span'
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, link_xpath))
                )
            except:
                return {
                    "id_card": id_card,
                    "status": "NotFound",
                    "extra_info": "No results found or timeout"
                }
            
            # 重新获取窗口句柄，以防点击前有变化
            windows_before_click = self.driver.window_handles
            
            link_element = self.driver.find_element(By.XPATH, link_xpath)
            self._safe_click(link_element)
            
            # 5. 切换到新窗口
            try:
                WebDriverWait(self.driver, 10).until(EC.new_window_is_opened(windows_before_click))
                new_window = [w for w in self.driver.window_handles if w not in windows_before_click][0]
                self.driver.switch_to.window(new_window)
            except:
                # 如果没有打开新窗口，可能是在当前页打开或者失败
                pass
            
            # 等待详情页加载
            WebDriverWait(self.driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            time.sleep(2) # 额外缓冲
            
            # 提取详情数据
            details = self._extract_details()
            
            # 增加停留时间，方便用户观察
            time.sleep(1)
            
            return {
                "id_card": id_card,
                "status": "Success",
                "extra_info": "Verified",
                "data": details
            }
            
        except Exception as e:
            # 尝试截图
            try:
                import os
                if not os.path.exists("logs/screenshots"):
                    os.makedirs("logs/screenshots")
                self.driver.save_screenshot(f"logs/screenshots/error_{id_card}.png")
            except:
                pass
                
            return {
                "id_card": id_card,
                "status": "Error",
                "extra_info": str(e)
            }
        finally:
            # 清理窗口：关闭除初始窗口外的所有窗口
            try:
                current_handles = self.driver.window_handles
                if len(current_handles) > len(windows_before):
                    for w in current_handles:
                        if w not in windows_before:
                            self.driver.switch_to.window(w)
                            self.driver.close()
                self.driver.switch_to.window(windows_before[0])
            except Exception as e:
                print(f"Error cleaning up windows: {e}")


    def _safe_click(self, element):
        """
        安全点击：先尝试普通点击，如果被拦截则使用 JS 点击
        """
        try:
            # 尝试滚动到视图中心
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            # 等待可点击
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(element))
            element.click()
        except Exception:
            # Fallback to JS click
            self.driver.execute_script("arguments[0].click();", element)

    def _extract_details(self):
        """
        提取详情页信息 - 基于用户提供的 HTML 结构优化
        """
        details = {}
        try:
            details['url'] = self.driver.current_url
            print(f"[Info] Current URL: {details['url']}")
            
            # 1. 姓名 (Name)
            try:
                # 姓名通常在顶部的 h3 span 中
                name_xpath = '//*[@id="app"]/div/div/div[2]/h3/span'
                details['name'] = self.driver.find_element(By.XPATH, name_xpath).text.strip()
                print(f"[Info] Extracted Name: {details['name']}")
            except Exception as e:
                print(f"[Error] Failed to extract name: {e}")
                details['name'] = ""

            # 2. 证书信息 (Certificates)
            certificates = []
            
            # 查找所有证书块 (div class="cert-header")
            cert_headers = self.driver.find_elements(By.CLASS_NAME, "cert-header")
            print(f"[Info] Found {len(cert_headers)} certificate headers")
            
            if not cert_headers:
                # 尝试打印页面源码片段以供调试
                try:
                    body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
                    print(f"[Debug] Body HTML snippet: {body_html[:500]}...")
                except:
                    pass

            for index, header in enumerate(cert_headers):
                try:
                    cert_info = {}
                    
                    # 2.1 等级 (Level) - h3 class="cert-header__title"
                    try:
                        title_el = header.find_element(By.CLASS_NAME, "cert-header__title")
                        cert_info['level'] = title_el.text.strip()
                        print(f"[Info] Cert {index+1} Level: {cert_info['level']}")
                    except Exception as e:
                        print(f"[Error] Cert {index+1} Level not found: {e}")
                        cert_info['level'] = ""

                    # 辅助函数：根据 label 文本查找对应的 value
                    def get_value_by_label(parent, label_text):
                        try:
                            # 查找包含特定文本的 label 元素的下一个兄弟元素 value
                            # XPath: .//div[contains(@class, 'label') and contains(text(), 'TEXT')]/following-sibling::div[contains(@class, 'value')]
                            xpath = f".//div[contains(@class, 'label') and contains(text(), '{label_text}')]/following-sibling::div[contains(@class, 'value')]"
                            val_el = parent.find_element(By.XPATH, xpath)
                            return val_el.text.strip()
                        except:
                            return None

                    # 2.2 注册单位 (Company)
                    company = get_value_by_label(header, "注册单位")
                    if not company:
                        # 如果直接获取为空，可能是因为 value 内部包含链接 (a -> span)
                        try:
                            xpath = ".//div[contains(@class, 'label') and contains(text(), '注册单位')]/following-sibling::div[contains(@class, 'value')]//span[contains(@class, 'link')]"
                            company = header.find_element(By.XPATH, xpath).text.strip()
                        except:
                            pass
                    cert_info['company'] = company or ""
                    print(f"[Info] Cert {index+1} Company: {cert_info['company']}")

                    # 2.3 注册编号 (Reg Number Only)
                    # 用户指示：证书编号不一定有，只保留注册编号
                    # 遍历列寻找包含 "注册编号" 或 "执业印章号" 的 label
                    try:
                        info_div = header.find_element(By.CLASS_NAME, "cert-header__info")
                        info_row = info_div.find_element(By.CLASS_NAME, "el-row")
                        cols = info_row.find_elements(By.CLASS_NAME, "el-col")
                        
                        reg_number = ""
                        for col in cols:
                            try:
                                label = col.find_element(By.CLASS_NAME, "label").text
                                if "注册编号" in label or "执业印章号" in label:
                                    reg_number = col.find_element(By.CLASS_NAME, "value").text.strip()
                                    break
                            except:
                                continue
                        
                        cert_info['reg_number'] = reg_number

                    except Exception as e:
                        print(f"[Error] Reg number extraction failed: {e}")
                        cert_info['reg_number'] = ""
                    
                    print(f"[Info] Cert {index+1} Reg Number: {cert_info['reg_number']}")

                    # 2.5 注册专业和有效期 (Details)
                    # 位于 header 下的 el-row 中
                    cert_info['details'] = []
                    
                    rows = header.find_elements(By.CLASS_NAME, "el-row")
                    for row in rows:
                        try:
                            row_text = row.text
                            # 只有同时包含这两个关键词的行才被认为是专业详情行
                            if "注册专业" in row_text and "有效期" in row_text:
                                prof = get_value_by_label(row, "注册专业")
                                expiry = get_value_by_label(row, "有效期")
                                
                                if prof:
                                    cert_info['details'].append({
                                        "profession": prof,
                                        "expiry": expiry or ""
                                    })
                                    print(f"[Info] Cert {index+1} Detail: {prof} - {expiry}")
                        except Exception as e:
                            pass
                            
                    certificates.append(cert_info)
                    
                except Exception as e:
                    print(f"[Error] Failed to parse cert header {index}: {e}")
            
            details['certificates'] = certificates
            
            # 3. 数据平铺 (Backward Compatibility)
            # 将第一个证书的信息提取到顶层，以便存入数据库的旧字段
            if certificates:
                first = certificates[0]
                details['level'] = first.get('level', '')
                details['company'] = first.get('company', '')
                details['reg_number'] = first.get('reg_number', '')
                
                # 平铺专业信息 (profession_1, expiry_1, ...)
                first_details = first.get('details', [])
                for i, item in enumerate(first_details):
                    idx = i + 1
                    details[f'profession_{idx}'] = item.get('profession', '')
                    details[f'expiry_{idx}'] = item.get('expiry', '')
                
                # 序列化所有证书信息
                import json
                details['certificates_json'] = json.dumps(certificates, ensure_ascii=False)
            
        except Exception as e:
            print(f"[Error] Fatal error in _extract_details: {e}")
            
        return details
