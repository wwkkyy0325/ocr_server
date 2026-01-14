# -*- coding: utf-8 -*-

import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper

class SafetyCertScraper(BaseScraper):
    def __init__(self, driver):
        super().__init__(driver)
        self.url = "https://zlaq.mohurd.gov.cn/fwmh/bjxcjgl/fwmh/pages/construction_safety/qyaqscglry/qyaqscglry.html"
        
    def login(self):
        pass
        
    def query(self, id_card):
        print(f"[SafetyCertScraper] Starting query for {id_card}")
        windows_before = self.driver.window_handles
        try:
            self.driver.get(self.url)
            print(f"[SafetyCertScraper] Navigated to {self.url}")
            time.sleep(random.uniform(1.0, 2.0))
            
            # Input ID Card
            input_selector = "input.keyword-ipt"
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, input_selector))
                )
            except Exception as e:
                print(f"[SafetyCertScraper] Input box not found: {e}")
                return {
                    "id_card": id_card,
                    "status": "Error",
                    "extra_info": "Input box not found"
                }
                
            input_box = self.driver.find_element(By.CSS_SELECTOR, input_selector)
            input_box.clear()
            input_box.send_keys(id_card)
            
            # Click Query
            btn_selector = "a.btn.search"
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, btn_selector))
            )
            search_btn = self.driver.find_element(By.CSS_SELECTOR, btn_selector)
            self._safe_click(search_btn)
            print(f"[SafetyCertScraper] Clicked search button")
            
            # Wait for results
            print(f"[SafetyCertScraper] Waiting for results...")
            
            row_xpath = "//tr[contains(@class, 'common-table-tr')]"
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, row_xpath))
                )
            except:
                 print(f"[SafetyCertScraper] No result row found (Timeout)")
                 return {
                    "id_card": id_card,
                    "status": "Success", 
                    "data": {
                        "b_cert_status": "未获得",
                        "b_cert_issue_date": "",
                        "b_cert_expiry_date": ""
                    }
                }
                
            # Extract data from List Page directly (Clear text)
            found_data = False
            b_status = ""
            b_expiry = ""
            relative_link = None
            
            try:
                rows = self.driver.find_elements(By.XPATH, row_xpath)
                print(f"[SafetyCertScraper] Found {len(rows)} rows")
                
                target_row = None
                
                # Construct expected masked ID pattern (First 3 + 13 stars + Last 2)
                # Note: The website uses 13 stars for 18-digit ID
                expected_mask_start = id_card[:3]
                expected_mask_end = id_card[-2:]
                
                for row in rows:
                    try:
                        # ID is in td[4]
                        id_cell = row.find_element(By.XPATH, "./td[4]")
                        id_text = id_cell.text.strip()
                        id_title = id_cell.get_attribute("title")
                        
                        # Check match
                        # We check if the cell contains the start and end of our ID
                        match = False
                        if id_text and id_text.startswith(expected_mask_start) and id_text.endswith(expected_mask_end):
                            match = True
                        elif id_title and id_title.startswith(expected_mask_start) and id_title.endswith(expected_mask_end):
                            match = True
                            
                        if match:
                            target_row = row
                            print(f"[SafetyCertScraper] Matched row with ID: {id_text or id_title}")
                            break
                    except Exception as e:
                        print(f"[SafetyCertScraper] Error checking row: {e}")
                        continue
                
                # If no specific match found but there is only 1 row, assume it's the one
                if not target_row and len(rows) == 1:
                    print(f"[SafetyCertScraper] No exact ID match, but only 1 row found. Using it.")
                    target_row = rows[0]
                
                if target_row:
                    # Status: td[8]
                    # Note: Use .text on the cell, or get title if text is empty
                    status_cell = target_row.find_element(By.XPATH, "./td[8]")
                    b_status = status_cell.text.strip() or status_cell.get_attribute("title")
                    
                    # Expiry: td[10]
                    expiry_cell = target_row.find_element(By.XPATH, "./td[10]")
                    b_expiry = expiry_cell.text.strip() or expiry_cell.get_attribute("title")
                    
                    # Link: td[3]/a
                    try:
                        link_el = target_row.find_element(By.XPATH, "./td[3]/a")
                        relative_link = link_el.get_attribute("href")
                    except:
                        relative_link = None
                        
                    print(f"[SafetyCertScraper] List Page Extracted: Status={b_status}, Expiry={b_expiry}, Link={relative_link}")
                    found_data = True
                else:
                    print(f"[SafetyCertScraper] No matching row found for ID {id_card}")
                    
            except Exception as e:
                print(f"[SafetyCertScraper] Failed to extract list data: {e}")

            if not found_data:
                 return {
                    "id_card": id_card,
                    "status": "Success", 
                    "data": {
                        "b_cert_status": "未找到",
                        "b_cert_issue_date": "",
                        "b_cert_expiry_date": ""
                    }
                }

            # Navigate to detail page for Issue Date
            b_issue_date = ""
            if relative_link:
                try:
                    import urllib.parse
                    full_url = urllib.parse.urljoin(self.driver.current_url, relative_link)
                    print(f"[SafetyCertScraper] Navigating to detail: {full_url}")
                    
                    self.driver.get(full_url)
                    
                    WebDriverWait(self.driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')
                    time.sleep(1)
                    
                    # Try to extract Issue Date from detail page
                    # Issue Date XPath on detail page
                    issue_xpath = '/html/body/div/div[2]/main/div[2]/div[2]/div/div/div/table/tbody/tr[7]/td[2]'
                    try:
                        b_issue_date = self.driver.find_element(By.XPATH, issue_xpath).text.strip()
                    except:
                        pass
                        
                    print(f"[SafetyCertScraper] Detail Page Extracted Issue Date: {b_issue_date}")
                    
                except Exception as e:
                    print(f"[SafetyCertScraper] Failed to navigate/extract detail: {e}")
            
            return {
                "id_card": id_card,
                "status": "Success",
                "data": {
                    "b_cert_status": b_status,
                    "b_cert_issue_date": b_issue_date,
                    "b_cert_expiry_date": b_expiry
                }
            }
        except Exception as e:
            print(f"[SafetyCertScraper] Error: {e}")
            return {
                "id_card": id_card,
                "status": "Error",
                "extra_info": str(e)
            }
        finally:
            # 清理窗口
            try:
                current_handles = self.driver.window_handles
                if len(current_handles) > len(windows_before):
                    for w in current_handles:
                        if w not in windows_before:
                            self.driver.switch_to.window(w)
                            self.driver.close()
                self.driver.switch_to.window(windows_before[0])
            except:
                pass
            
    def _safe_click(self, element):
        """安全点击，防止被遮挡"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            element.click()
        except:
            try:
                self.driver.execute_script("arguments[0].click();", element)
            except:
                pass
