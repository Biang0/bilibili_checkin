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
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_csrf(self):
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        return None

    def get_task_info(self):
        """
        获取今日投币任务信息 - 保持原有逻辑不变
        """
        try:
            beijing_tz = timezone(timedelta(hours=8))
            today = datetime.now(beijing_tz)
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=beijing_tz)
            
            coin_exp = 0
            page = 1
            max_page = 5

            while page <= max_page:
                url = f"https://api.bilibili.com/x/member/web/exp/log?jsonp=jsonp&pn={page}&ps=30"
                res = self.session.get(url, timeout=10)
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
                                logger.debug(f"无法解析的时间格式，已跳过: {time_str}")
                                continue
                        
                        if item_time.tzinfo is None:
                            item_time = item_time.replace(tzinfo=timezone.utc)
                        item_time_beijing = item_time.astimezone(beijing_tz)
                        
                        if item_time_beijing.date() < today_start.date():
                            today_coin = coin_exp // 10
                            logger.info(f"从经验日志解析：今日已投币 {today_coin} 个（获得 {coin_exp} 经验）")
                            return {"today_coin": today_coin, "coin_exp": coin_exp}
                        
                        reason = item.get("reason", "")
                        exp = int(item.get("delta", 0))
                        if "投币" in reason and exp > 0:
                            coin_exp += exp
                            logger.debug(f"记录到投币经验: {time_str}, 原因: {reason}, 经验值: {exp}")

                    except Exception as e:
                        logger.warning(f"解析经验日志单条记录时出错（已跳过）: {e}")
                        continue
                page += 1

            today_coin = coin_exp // 10
            logger.info(f"经验日志解析完成：今日已投币 {today_coin} 个（获得 {coin_exp} 经验）")
            return {"today_coin": today_coin, "coin_exp": coin_exp}

        except Exception as e:
            logger.error(f"获取投币任务信息过程发生异常: {e}")
            return {"today_coin": 0, "coin_exp": 0}

    def get_coin_balance(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                coins = data.get('data', {}).get('money', 0)
                logger.debug(f"获取硬币余额成功: {coins}个")
                return coins
            return 0
        except Exception as e:
            logger.error(f"获取硬币余额异常: {e}")
            return 0

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                return data.get('data', {})
            logger.warning(f"获取用户信息失败: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"请求用户信息API异常: {e}")
            return None

    def get_dynamic_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=5&rid=1'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                return [video.get('bvid') for video in data.get('data', {}).get('archives', [])]
            return []
        except Exception as e:
            logger.error(f"请求动态视频API异常: {e}")
            return []

    def get_ranking_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                return [video.get('bvid') for video in data.get('data', {}).get('list', [])]
            return []
        except Exception as e:
            logger.error(f"请求排行榜视频API异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                has_coined = data.get('data', {}).get('multiply', 0) > 0
                return has_coined
            return False
        except Exception as e:
            logger.error(f"检查视频投币状态异常: {e}")
            return False

    def add_coin(self, bvid, num=1, select_like=1, max_retry=2):
        """投币功能 - 基于您的原始代码，但保持重试机制"""
        if not self.csrf: 
            return False, "Bili_jct(csrf) 未找到"
        
        for attempt in range(max_retry):
            try:
                url = 'https://api.bilibili.com/x/web-interface/coin/add'
                data = {
                    'bvid': bvid, 
                    'multiply': num, 
                    'select_like': select_like, 
                    'csrf': self.csrf
                }
                
                res = self.session.post(url, data=data, timeout=10)
                response_data = res.json()
                
                if response_data.get('code') == 0:
                    logger.info(f"投币成功: {bvid}")
                    return True, "投币成功"
                elif response_data.get('code') == 34005:
                    return True, "今日投币已达上限"
                elif response_data.get('code') == 34004:
                    return False, "硬币不足"
                else:
                    error_msg = response_data.get('message', f"错误代码: {response_data.get('code')}")
                    if attempt < max_retry - 1:
                        time.sleep(1)
                        continue
                    return False, error_msg
                    
            except Exception as e:
                if attempt < max_retry - 1:
                    time.sleep(1)
                    continue
                logger.error(f"投币请求异常: {e}")
                return False, str(e)
        
        return False, "重试后仍失败"

    def share_video(self, bvid):
        """分享视频 - 完全使用您的原始代码API"""
        if not self.csrf: 
            return False, "Bili_jct(csrf) 未找到"
        
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        
        try:
            res = self.session.post(url, data=data, timeout=10)
            response_data = res.json()
            if response_data.get('code') == 0:
                return True, "分享成功"
            return False, response_data.get('message', '分享失败')
        except Exception as e:
            return False, str(e)

    def watch_video(self, bvid, played_time=30):
        """观看视频 - 完全使用您的原始代码API"""
        if not self.csrf:
            return False, "观看需要csrf token"
        
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'bvid': bvid, 'played_time': played_time, 'csrf': self.csrf}
        
        try:
            res = self.session.post(url, data=data, timeout=10)
            response_data = res.json()
            if response_data.get('code') == 0:
                return True, "观看成功"
            return False, response_data.get('message', '观看失败')
        except Exception as e:
            return False, str(e)

    def live_sign(self):
        """直播签到 - 完全使用您的原始代码API"""
        url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign'
        try:
            res = self.session.get(url, timeout=10)
            response_data = res.json()
            if response_data.get('code') == 0:
                sign_data = response_data.get('data', {})
                text = sign_data.get('text', '直播签到成功')
                return True, text
            return False, response_data.get('message', '直播签到失败')
        except Exception as e:
            return False, str(e)

    def manga_sign(self):
        """漫画签到 - 完全使用您的原始代码API"""
        url = 'https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn'
        try:
            res = self.session.post(url, data={'platform': 'ios'}, timeout=10)
            response_data = res.json()
            if response_data.get('code') == 0:
                return True, "漫画签到成功"
            return False, response_data.get('message', '漫画签到失败')
        except Exception as e:
            return False, str(e)
