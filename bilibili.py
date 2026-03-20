import requests
from loguru import logger
from datetime import datetime, timedelta, timezone
import time
import random

class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bilibili.com/',  # 已修复Referer
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()
        self.session = requests.Session()  # 使用Session提高性能

    def _get_csrf(self):
        """从cookie中提取csrf token (bili_jct)"""
        for item in self.cookie.split(';'):
            if item.strip().startswith('bili_jct'):
                return item.split('=')[1]
        logger.error("未找到bili_jct，csrf token获取失败")
        return None

    def get_coin_balance(self):
        """
        获取用户当前硬币余额
        返回整数，表示可用硬币数量
        """
        url = 'https://api.bilibili.com/x/web-interface/nav'  # 已修复：添加完整域名
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                coins = data['data'].get('money', 0)
                logger.debug(f"获取硬币余额成功: {coins}个")
                return coins
            else:
                logger.error(f"获取硬币余额失败: {data.get('message')}")
                return 0
        except Exception as e:
            logger.error(f"获取硬币余额异常: {e}")
            return 0

    def get_user_info(self):
        """获取用户基本信息"""
        url = 'https://api.bilibili.com/x/web-interface/nav'  # 已修复：添加完整域名
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']
            logger.error(f"获取用户信息失败: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None

    def get_dynamic_videos(self):
        """获取动态视频列表"""
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=10&rid=1'  # 已修复：添加完整域名
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                videos = [video['bvid'] for video in data.get('data', {}).get('archives', [])]
                logger.debug(f"获取到{len(videos)}个动态视频")
                return videos
            return []
        except Exception as e:
            logger.error(f"获取动态视频异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        """检查视频投币状态"""
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'  # 已修复：添加完整域名
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                has_coined = data['data']['multiply'] > 0
                logger.debug(f"视频{bvid}投币状态: {'已投币' if has_coined else '未投币'}")
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
        
        url = 'https://api.bilibili.com/x/web-interface/coin/add'  # 已修复：添加完整域名
        data = {
            'bvid': bvid,
            'multiply': num,
            'select_like': select_like,
            'csrf': self.csrf
        }
        
        # 重试机制
        for attempt in range(max_retry):
            try:
                res = self.session.post(url, headers=self.headers, data=data, timeout=10)
                data_res = res.json()
                
                if data_res['code'] == 0:
                    logger.info(f"投币成功: {bvid}")
                    return True, "投币成功"
                elif data_res['code'] == 34005:
                    return True, "今日投币已达上限"  # B站服务端验证
                elif data_res['code'] == 34004:
                    return False, "硬币不足"
                else:
                    error_msg = data_res.get('message', f"错误代码: {data_res['code']}")
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
        
        url = 'https://api.bilibili.com/x/web-interface/share/add'  # 已修复：添加完整域名
        data = {'bvid': bvid, 'csrf': self.csrf}
        
        try:
            res = self.session.post(url, headers=self.headers, data=data, timeout=10)
            data_res = res.json()
            if data_res['code'] == 0:
                return True, "分享成功"
            return False, f"分享失败: {data_res.get('message', '未知错误')}"
        except Exception as e:
            logger.error(f"分享视频异常: {e}")
            return False, "分享异常"

    def watch_video(self, bvid, played_time=30):
        """观看视频（心跳包）"""
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'  # 已修复：添加完整域名
        data = {
            'bvid': bvid,
            'played_time': played_time,
            'csrf': self.csrf
        }
        
        try:
            res = self.session.post(url, headers=self.headers, data=data, timeout=10)
            data_res = res.json()
            if data_res['code'] == 0:
                return True, "观看成功"
            return False, f"观看失败: {data_res.get('message', '未知错误')}"
        except Exception as e:
            logger.error(f"观看视频异常: {e}")
            return False, "观看异常"

    def live_sign(self):
        """直播签到"""
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/WebSign"  # 已修复：添加完整域名
            res = self.session.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return True, "直播签到成功"
            return False, "直播签到失败或已签到"
        except Exception as e:
            logger.error(f"直播签到异常: {e}")
            return False, "直播签到异常"

    def manga_sign(self):
        """漫画签到"""
        try:
            url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"  # 已修复：添加完整域名
            res = self.session.post(url, headers=self.headers, json={}, timeout=10)
            data = res.json()
            if data.get('code') == 0:
                return True, "漫画签到成功"
            return False, "漫画签到失败或已签到"
        except Exception as e:
            logger.error(f"漫画签到异常: {e}")
            return False, "漫画签到异常"
