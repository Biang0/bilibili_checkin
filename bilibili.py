import requests
from loguru import logger
from datetime import datetime, timedelta, timezone
import time
import random
import json

class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()

    def _get_csrf(self):
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        return None

    def get_task_info(self):
        try:
            beijing_tz = timezone(timedelta(hours=8))
            today = datetime.now(beijing_tz)
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=beijing_tz)
            
            coin_exp = 0
            page = 1
            max_page = 5

            while page <= max_page:
                url = f"https:///x/member/web/exp/log?jsonp=jsonp&pn={page}&ps=30"
                res = requests.get(url, headers=self.headers, timeout=10)
                data = res.json()

                if data.get("code") != 0 or not data.get("data", {}).get("list"):
                    break

                for item in data["data"]["list"]:
                    try:
                        time_str = item.get("time")
                        if not time_str:
                            continue
                        
                        item_time = None
                        try:
                            item_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                timestamp = int(time_str)
                                item_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                            except ValueError:
                                continue
                        
                        if item_time.tzinfo is None:
                            item_time = item_time.replace(tzinfo=timezone.utc)
                        item_time_beijing = item_time.astimezone(beijing_tz)
                        
                        if item_time_beijing.date() < today_start.date():
                            today_coin = coin_exp // 10
                            return {"today_coin": today_coin, "coin_exp": coin_exp}
                        
                        reason = item.get("reason", "")
                        exp = int(item.get("delta", 0))
                        if "投币" in reason and exp > 0:
                            coin_exp += exp

                    except Exception:
                        continue
                page += 1

            today_coin = coin_exp // 10
            return {"today_coin": today_coin, "coin_exp": coin_exp}

        except Exception as e:
            return {"today_coin": 0, "coin_exp": 0}

    def get_coin_balance(self):
        url = 'https:///x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('money', 0)
            return 0
        except Exception:
            return 0

    def get_user_info(self):
        url = 'https:///x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return data.get('data', {})
            return None
        except Exception:
            return None

    def get_dynamic_videos(self):
        url = 'https:///x/web-interface/dynamic/region?ps=5&rid=1'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return [video.get('bvid') for video in data.get('data', {}).get('archives', [])]
            return []
        except Exception:
            return []

    def get_ranking_videos(self):
        url = 'https:///x/web-interface/ranking/v2?rid=0&type=all'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return [video.get('bvid') for video in data.get('data', {}).get('list', [])]
            return []
        except Exception:
            return []

    def check_video_coin_status(self, bvid):
        url = f'https:///x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('multiply', 0) > 0
            return False
        except Exception:
            return False

    def add_coin(self, bvid, num=1, select_like=1, max_retry=2):
        if not self.csrf: 
            return False, "Bili_jct(csrf) 未找到"
        
        url = 'https:///x/web-interface/coin/add'
        data = {'bvid': bvid, 'multiply': num, 'select_like': select_like, 'csrf': self.csrf}
        
        for attempt in range(max_retry):
            try:
                res = requests.post(url, headers=self.headers, data=data, timeout=10)
                response_data = res.json()
                
                if response_data.get('code') == 0:
                    return True, "投币成功"
                elif response_data.get('code') == 34005:
                    return True, "今日投币已达上限"
                elif response_data.get('code') == 34004:
                    return False, "硬币不足"
                else:
                    if attempt < max_retry - 1:
                        time.sleep(1)
                        continue
                    return False, response_data.get('message', '投币失败')
            except Exception as e:
                if attempt < max_retry - 1:
                    time.sleep(1)
                    continue
                return False, str(e)
        
        return False, "重试后仍失败"

    def share_video(self, bvid):
        """基于原始代码逻辑修复的分享功能"""
        if not self.csrf: 
            return False, "Bili_jct(csrf) 未找到"
        
        # 使用原始代码的URL格式
        url = 'https:///x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            
            # 原始代码逻辑：只检查code==0
            if data.get('code') == 0:
                return True, "分享成功"
            
            # 但根据B站API，添加常见错误码处理
            elif data.get('code') == 87013:
                return True, "今日已分享"
            elif data.get('code') == -101:
                return False, "Cookie失效，请重新登录"
            
            return False, data.get('message', '分享失败')
        except Exception as e:
            return False, str(e)

    def watch_video(self, bvid, played_time=30):
        """基于原始代码逻辑修复的观看功能"""
        if not self.csrf:
            return False, "观看需要csrf token"
        
        # 使用原始代码的URL格式
        url = 'https:///x/click-interface/web/heartbeat'
        data = {'bvid': bvid, 'played_time': played_time, 'csrf': self.csrf}
        
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            
            # 原始代码逻辑：只检查code==0
            if data.get('code') == 0:
                return True, "观看成功"
            
            # 但根据B站API，添加常见错误码处理
            elif data.get('code') in [87014, 87015]:
                return True, "已记录观看"
            elif data.get('code') == -101:
                return False, "Cookie失效，请重新登录"
            
            return False, data.get('message', '观看失败')
        except Exception as e:
            return False, str(e)

    def live_sign(self):
        """基于原始代码逻辑修复的直播签到"""
        url = 'https:///xlive/web-ucenter/v1/sign/DoSign'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            
            if data.get('code') == 0:
                return True, data.get('data', {}).get('text', '直播签到成功')
            elif data.get('code') == 1011040:
                return True, "今日已签到"
            return False, data.get('message', '直播签到失败')
        except Exception as e:
            return False, str(e)

    def manga_sign(self):
        """漫画签到 - 保持原始代码完全不变"""
        url = 'https:///twirp/activity.v1.Activity/ClockIn'
        try:
            res = requests.post(url, headers=self.headers, data={'platform': 'ios'})
            data = res.json()
            if data.get('code') == 0:
                return True, "漫画签到成功"
            return False, data.get('message', '漫画签到失败')
        except Exception as e:
            return False, str(e)
