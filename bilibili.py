import requests
from loguru import logger
from datetime import datetime, timedelta, timezone
import time
import random
import json
import re


class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_csrf(self):
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        logger.error("未找到bili_jct，csrf token获取失败")
        return None

    def get_task_info(self):
        """
        修复版：获取今日投币任务信息。
        正确解析经验日志中的时间字符串，计算今日获得的投币经验。
        返回格式: {"today_coin": 今日已投硬币数, "coin_exp": 今日投币获得的总经验值}
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
            return None
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None

    def get_dynamic_videos(self):
        """
        修复版：获取视频列表（优先热门，备选分区推荐）
        """
        # 方案1：热门视频接口（最稳定）
        videos = self._get_popular_videos()
        if videos:
            logger.info(f"从热门视频获取到 {len(videos)} 个视频")
            return videos
        
        # 方案2：分区动态接口（备选）
        videos = self._get_region_videos()
        if videos:
            logger.info(f"从分区动态获取到 {len(videos)} 个视频")
            return videos
        
        # 方案3：推荐视频接口（备选）
        videos = self._get_recommend_videos()
        if videos:
            logger.info(f"从推荐视频获取到 {len(videos)} 个视频")
            return videos
        
        logger.error("所有视频获取接口都失败了！")
        return []

    def _get_popular_videos(self):
        """热门视频接口（最稳定）"""
        try:
            url = 'https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1'
            res = self.session.get(url, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                videos = [v.get('bvid') for v in data.get('data', {}).get('list', [])]
                random.shuffle(videos)  # 打乱顺序，避免每次投一样的
                return videos[:10]
            logger.warning(f"热门视频接口返回错误: code={data.get('code')}, msg={data.get('message')}")
            return []
        except Exception as e:
            logger.warning(f"获取热门视频异常: {e}")
            return []

    def _get_region_videos(self):
        """分区动态接口（备选）"""
        try:
            # 随机选一个分区，避免总是投同一个区
            regions = [1, 3, 4, 5, 160, 119, 155, 168]  # 动画、音乐、游戏、娱乐、生活、美食、动物、汽车
            rid = random.choice(regions)
            url = f'https://api.bilibili.com/x/web-interface/dynamic/region?ps=10&rid={rid}'
            res = self.session.get(url, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                videos = [video.get('bvid') for video in data.get('data', {}).get('archives', [])]
                return videos
            logger.warning(f"分区视频接口返回错误: code={data.get('code')}, msg={data.get('message')}")
            return []
        except Exception as e:
            logger.warning(f"获取分区视频异常: {e}")
            return []

    def _get_recommend_videos(self):
        """推荐视频接口（备选）"""
        try:
            url = 'https://api.bilibili.com/x/web-interface/index/top/feed/rcmd?ps=20&fresh_type=4'
            res = self.session.get(url, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                items = data.get('data', {}).get('item', [])
                videos = [item.get('bvid') for item in items if item.get('bvid')]
                return videos[:10]
            logger.warning(f"推荐视频接口返回错误: code={data.get('code')}, msg={data.get('message')}")
            return []
        except Exception as e:
            logger.warning(f"获取推荐视频异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = self.session.get(url, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                has_coined = data.get('data', {}).get('multiply', 0) > 0
                return has_coined
            logger.debug(f"检查投币状态返回: code={data.get('code')}, msg={data.get('message')}")
            return False
        except Exception as e:
            logger.error(f"检查视频投币状态异常: {e}")
            return False

    def add_coin(self, bvid, num=1, select_like=1, max_retry=2):
        if not self.csrf:
            return False, "csrf token不存在"
        
        if self.check_video_coin_status(bvid):
            return True, "该视频已投币"
        
        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {
            'bvid': bvid,
            'multiply': num,
            'select_like': select_like,
            'csrf': self.csrf
        }
        
        for attempt in range(max_retry):
            try:
                # 随机延迟，防风控
                if attempt > 0:
                    time.sleep(random.uniform(1, 3))
                
                res = self.session.post(url, data=data, timeout=10)
                data_res = res.json()
                
                code = data_res.get('code')
                message = data_res.get('message', '')
                
                if code == 0:
                    logger.info(f"投币成功: {bvid}")
                    return True, "投币成功"
                elif code == 34005:
                    return True, "今日投币已达上限"
                elif code == 34004:
                    return False, "硬币不足"
                elif code == -101:
                    return False, "账号未登录(Cookie可能失效)"
                elif code == -352:
                    return False, "请求被风控(-352)"
                elif code == 412:
                    return False, "请求被拦截(412，访问太频繁)"
                else:
                    error_msg = f"错误代码: {code}, 信息: {message}"
                    logger.warning(f"投币失败: {bvid}, {error_msg}")
                    
                    if attempt < max_retry - 1:
                        time.sleep(random.uniform(2, 4))
                        continue
                    return False, error_msg
                    
            except Exception as e:
                logger.error(f"投币请求异常: {e}")
                if attempt < max_retry - 1:
                    time.sleep(random.uniform(2, 4))
                    continue
                return False, f"请求异常: {str(e)}"
        
        return False, "重试后仍失败"

    def share_video(self, bvid):
        if not self.csrf:
            return False, "csrf token不存在"
        
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        
        try:
            res = self.session.post(url, data=data, timeout=10)
            data_res = res.json()
            if data_res.get('code') == 0:
                return True, "分享成功"
            return False, f"分享失败: {data_res.get('message', '未知错误')}"
        except Exception as e:
            logger.error(f"分享视频异常: {e}")
            return False, "分享异常"

    def watch_video(self, bvid, played_time=30):
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {
            'bvid': bvid,
            'played_time': played_time,
            'csrf': self.csrf
        }
        
        try:
            res = self.session.post(url, data=data, timeout=10)
            data_res = res.json()
            if data_res.get('code') == 0:
                return True, "观看成功"
            return False, f"观看失败: {data_res.get('message', '未知错误')}"
        except Exception as e:
            logger.error(f"观看视频异常: {e}")
            return False, "观看异常"

    def live_sign(self):
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': 'https://live.bilibili.com/',
                'Cookie': self.cookie
            }
            
            res = self.session.get(url, headers=headers, timeout=10)
            data = res.json()
            
            if data.get('code') == 0:
                return True, data.get('data', {}).get('text', '直播签到成功')
            elif data.get('code') == 1011040:
                return True, "今日已签到"
            return False, data.get('message', '直播签到失败')
                
        except Exception as e:
            logger.error(f"直播签到异常: {e}")
            return False, "直播签到异常"

    def manga_sign(self):
        """
        漫画签到 - 按照原生代码格式
        注意：使用data参数而不是json参数
        """
        url = 'https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn'
        try:
            # 注意：这里使用data参数，而不是json参数
            res = self.session.post(url, headers=self.headers, data={'platform': 'ios'}, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return True, "漫画签到成功"
            elif data.get('code') == 1:
                return True, "今日已签到"
            return False, data.get('message', '漫画签到失败')
        except Exception as e:
            logger.error(f"漫画签到异常: {e}")
            return False, str(e)
