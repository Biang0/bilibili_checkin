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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
                res = self.session.post(url, data=data, timeout=10)
                data_res = res.json()
                
                if data_res.get('code') == 0:
                    logger.info(f"投币成功: {bvid}")
                    return True, "投币成功"
                elif data_res.get('code') == 34005:
                    return True, "今日投币已达上限"
                elif data_res.get('code') == 34004:
                    return False, "硬币不足"
                else:
                    error_msg = data_res.get('message', f"错误代码: {data_res.get('code')}")
                    if attempt < max_retry - 1:
                        time.sleep(1)
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
        """
        修复的分享视频功能
        只修改此函数，其他不变
        """
        if not self.csrf:
            return False, "csrf token不存在"
        
        # 使用当前的分享接口
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        
        # 准备请求数据
        data = {
            'bvid': bvid,
            'csrf': self.csrf,
            'share_id': 'main.ugc-video-detail.0.0',  # 添加分享标识
            'share_origin': 'qq'  # 分享来源，可以是qq/weibo/wechat等
        }
        
        # 更新请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'https://www.bilibili.com/video/{bvid}',
            'Origin': 'https://www.bilibili.com',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Cookie': self.cookie
        }
        
        try:
            res = self.session.post(url, headers=headers, data=data, timeout=10)
            data_res = res.json()
            
            if data_res.get('code') == 0:
                logger.info(f"分享成功: {bvid}")
                return True, "分享成功"
            elif data_res.get('code') == -101:
                return False, "Cookie失效，请重新登录"
            elif data_res.get('code') == 87013:
                return True, "今日已分享"  # 已分享过
            else:
                error_msg = data_res.get('message', f"错误代码: {data_res.get('code')}")
                return False, f"分享失败: {error_msg}"
        except Exception as e:
            logger.error(f"分享视频异常: {e}")
            return False, "分享请求异常"

    def watch_video(self, bvid, played_time=30):
        """
        修复的观看视频功能
        只修改此函数，其他不变
        """
        if not self.csrf:
            return False, "观看视频需要csrf token"
        
        # 当前可用的心跳接口
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        
        # 完整的请求参数
        data = {
            'bvid': bvid,
            'played_time': played_time,
            'real_played_time': played_time,
            'csrf': self.csrf,
            'type': 3,  # 网页端
            'dt': 2,    # 设备类型
            'play_type': 1,  # 播放类型
            'start_ts': int(time.time()),  # 开始时间戳
            'epid': 0,
            'sid': 0,
            'cid': 0
        }
        
        # 更新请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'https://www.bilibili.com/video/{bvid}',
            'Origin': 'https://www.bilibili.com',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Cookie': self.cookie
        }
        
        try:
            res = self.session.post(url, headers=headers, data=data, timeout=10)
            data_res = res.json()
            
            if data_res.get('code') == 0:
                logger.info(f"观看心跳发送成功: {bvid}")
                return True, "观看成功"
            elif data_res.get('code') == -101:
                return False, "Cookie失效，请重新登录"
            else:
                error_msg = data_res.get('message', f"错误代码: {data_res.get('code')}")
                logger.warning(f"观看心跳返回异常: {error_msg}")
                
                # 即使返回错误，也可能已记录观看
                if data_res.get('code') in [87014, 87015]:
                    return True, "已记录观看"
                return False, f"观看失败: {error_msg}"
        except Exception as e:
            logger.error(f"观看视频异常: {e}")
            return False, "观看请求异常"

    def live_sign(self):
        """
        修复的直播签到功能
        只修改此函数，其他不变
        """
        try:
            # 当前可用的直播签到接口
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://live.bilibili.com/',
                'Origin': 'https://live.bilibili.com',
                'Cookie': self.cookie
            }
            
            res = self.session.get(url, headers=headers, timeout=10)
            data = res.json()
            
            # 处理各种可能的返回状态
            if data.get('code') == 0:
                sign_data = data.get('data', {})
                text = sign_data.get('text', '')
                special_text = sign_data.get('specialText', '')
                
                if text or special_text:
                    return True, f"直播签到成功: {text or special_text}"
                return True, "直播签到成功"
                
            elif data.get('code') == 1011040:
                return True, "今日已签到"
                
            elif data.get('message') and "已下线" in data.get('message'):
                # 尝试备用接口
                backup_url = "https://api.live.bilibili.com/sign/doSign"
                try:
                    res2 = self.session.get(backup_url, headers=headers, timeout=10)
                    data2 = res2.json()
                    
                    if data2.get('code') == 0:
                        return True, "直播签到成功（备用接口）"
                    elif data2.get('code') == -500:
                        return True, "今日已签到（备用接口）"
                except:
                    pass
                    
                return False, "直播签到功能已下线，请手动签到"
                
            else:
                error_msg = data.get('message', f"错误代码: {data.get('code')}")
                return False, f"直播签到失败: {error_msg}"
                
        except Exception as e:
            logger.error(f"直播签到异常: {e}")
            return False, f"直播签到异常: {str(e)}"

    def manga_sign(self):
        """
        漫画签到 - 保持不变
        此函数功能正常，不做任何修改
        """
        try:
            url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            headers = {
                'User-Agent': self.headers['User-Agent'],
                'Content-Type': 'application/json; charset=utf-8',
                'Cookie': self.cookie
            }
            
            data = {
                'platform': 'ios'
            }
            
            res = self.session.post(url, headers=headers, json=data, timeout=10)
            res_data = res.json()
            
            if res_data.get('code') == 0:
                return True, "漫画签到成功"
            elif res_data.get('code') == 1:
                return True, "今日已签到"
            else:
                return False, f"漫画签到失败: {res_data.get('msg', '未知错误')}"
                
        except Exception as e:
            logger.error(f"漫画签到异常: {e}")
            return False, "漫画签到异常"
