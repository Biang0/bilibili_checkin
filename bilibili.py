import requests
from loguru import logger
from datetime import datetime, timedelta, timezone
import time
import random
import json

class BilibiliTask:
    """B站自动化任务API客户端"""
    
    def __init__(self, cookie):
        """初始化Bilibili任务客户端"""
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()
        self.session = requests.Session()  # 使用Session提高性能
        self.session.headers.update(self.headers)

    def _get_csrf(self):
        """从cookie中提取csrf token (bili_jct)"""
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        logger.error("未找到bili_jct，csrf token获取失败")
        return None

    def get_task_info(self):
        """
        获取今日投币任务信息
        返回包含今日已投币数量的字典
        """
        try:
            beijing_tz = timezone(timedelta(hours=8))
            today = datetime.now(beijing_tz)
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=beijing_tz)
            today_start_ts = int(today_start.timestamp())
            
            coin_exp = 0
            page = 1
            max_page = 5  # 最多查询5页，每页30条记录

            while page <= max_page:
                url = f"https://api.bilibili.com/x/member/web/exp/log?jsonp=jsonp&pn={page}&ps=30"
                res = self.session.get(url, timeout=10)
                data = res.json()

                if data.get("code") != 0 or not data.get("data", {}).get("list"):
                    break  # 没有数据或请求失败

                for item in data["data"]["list"]:
                    try:
                        ts = int(item.get("time", 0))
                        if ts < today_start_ts:
                            # 遇到昨天的记录，停止解析
                            today_coin = coin_exp // 10  # 10经验=1硬币
                            logger.debug(f"从经验日志解析今日已投币: {today_coin}个 (经验值: {coin_exp})")
                            return {"today_coin": today_coin, "coin_exp": coin_exp}

                        reason = item.get("reason", "")
                        exp = int(item.get("delta", 0))

                        # 检查是否是投币相关的经验
                        if "投币" in reason and exp > 0:
                            coin_exp += exp

                    except Exception as e:
                        logger.warning(f"解析经验日志项失败: {e}")
                        continue
                page += 1

            # 遍历完所有记录
            today_coin = coin_exp // 10
            logger.debug(f"今日投币经验解析完成: {today_coin}个 (经验值: {coin_exp})")
            return {"today_coin": today_coin, "coin_exp": coin_exp}

        except Exception as e:
            logger.error(f"获取投币信息失败: {e}")
            return {"today_coin": 0, "coin_exp": 0}

    def get_coin_balance(self):
        """获取用户当前硬币余额"""
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
        """获取用户基本信息"""
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
        """获取动态视频列表"""
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=10&rid=1'
        try:
            res = self.session.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('code') == 0:
                videos = [video.get('bvid') for video in data.get('data', {}).get('archives', [])]
                logger.debug(f"获取到{len(videos)}个动态视频")
                return videos
            return []
        except Exception as e:
            logger.error(f"获取动态视频异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        """检查视频投币状态"""
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = self.session.get(url, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                has_coined = data.get('data', {}).get('multiply', 0) > 0
                return has_coined
            return False
        except Exception as e:
            logger.error(f"检查视频投币状态异常: {e}")
            return False

    def add_coin(self, bvid, num=1, select_like=1, max_retry=2):
        """
        给视频投币
        返回: (成功与否, 消息)
        """
        if not self.csrf:
            return False, "csrf token不存在"
        
        # 检查是否已投过币
        if self.check_video_coin_status(bvid):
            return True, "该视频已投币"
        
        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {
            'bvid': bvid,
            'multiply': num,
            'select_like': select_like,
            'csrf': self.csrf
        }
        
        # 重试机制
        for attempt in range(max_retry):
            try:
                res = self.session.post(url, data=data, timeout=10)
                data_res = res.json()
                
                if data_res.get('code') == 0:
                    logger.info(f"投币成功: {bvid}")
                    return True, "投币成功"
                elif data_res.get('code') == 34005:
                    return True, "今日投币已达上限"  # B站服务端验证
                elif data_res.get('code') == 34004:
                    return False, "硬币不足"
                else:
                    error_msg = data_res.get('message', f"错误代码: {data_res.get('code')}")
                    if attempt < max_retry - 1:
                        time.sleep(1)  # 失败后等待1秒重试
                        continue
                    return False, error_msg
                    
            except Exception as e:
                if attempt < max_retry - 1:
                    time.sleep(1)
                    continue
                logger.error(f"投币请求异常: {e}")
                return False, "请求失败"
        
        return False, "重试后仍失败"

    def share_video(self, bvid):
        """分享视频"""
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
        """观看视频（心跳包）"""
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
        """直播签到"""
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/WebSign"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Referer': 'https://live.bilibili.com/',
                'Cookie': self.cookie
            }
            
            res = self.session.get(url, headers=headers, timeout=10)
            
            try:
                data = res.json()
                if data.get('code') == 0:
                    return True, "直播签到成功"
                elif data.get('code') == 1011040:
                    return True, "今日已签到"
                else:
                    return False, f"直播签到失败: {data.get('message', '未知错误')}"
            except json.JSONDecodeError as e:
                logger.warning(f"直播签到返回非JSON数据: {res.text[:100]}")
                if res.status_code == 200 and "成功" in res.text:
                    return True, "直播签到成功"
                return False, "直播签到响应格式异常"
                
        except Exception as e:
            logger.error(f"直播签到异常: {e}")
            return False, "直播签到异常"

    def manga_sign(self):
        """漫画签到"""
        try:
            url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Origin': 'https://manga.bilibili.com',
                'Referer': 'https://manga.bilibili.com/',
                'Content-Type': 'application/json; charset=utf-8',
                'Cookie': self.cookie
            }
            
            res = self.session.post(url, headers=headers, json={}, timeout=10)
            data = res.json()
            
            if data.get('code') == 0:
                return True, "漫画签到成功"
            elif data.get('code') == 1:
                return True, "今日已签到"
            else:
                return False, f"漫画签到失败: {data.get('msg', '未知错误')}"
                
        except Exception as e:
            logger.error(f"漫画签到异常: {e}")
            return False, "漫画签到异常"
