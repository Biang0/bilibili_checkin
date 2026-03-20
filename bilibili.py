import requests
from loguru import logger
from datetime import datetime, timedelta, timezone

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
            res = requests.get("https://api.bilibili.com/x/member/web/exp/log", headers=self.headers, timeout=8)
            data = res.json()
            if data.get("code") != 0:
                logger.warning(f"获取经验日志失败: {data.get('message')}")
                return {"coin_exp": 0}

            beijing_tz = timezone(timedelta(hours=8))
            today_date = datetime.now(beijing_tz).date()

            coin_exp = 0
            for item in data.get("data", {}).get("list", []):
                reason = item.get("reason", "")
                if "投币" in reason:
                    ts = item.get("time")
                    if ts:
                        try:
                            ts_int = int(ts)
                            item_date = datetime.fromtimestamp(ts_int, tz=beijing_tz).date()
                            if item_date == today_date:
                                coin_exp += item.get("delta", 0)
                        except:
                            continue
            return {"coin_exp": coin_exp}
        except Exception as e:
            logger.error(f"解析投币经验异常: {e}")
            return {"coin_exp": 0}

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']
            logger.warning(f"获取用户信息失败: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"请求用户信息异常: {e}")
            return None

    def get_dynamic_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=10&rid=1'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return [video['bvid'] for video in data.get('data', {}).get('archives', [])]
            return []
        except Exception as e:
            logger.error(f"获取视频异常: {e}")
            return []

    def check_video_coin_status(self, bvid):
        url = f'https://api.bilibili.com/x/web-interface/archive/coins?bvid={bvid}'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return data['data']['multiply'] > 0
            return False
        except:
            return False

    def add_coin(self, bvid, num=1, select_like=1):
        if not self.csrf:
            return False, "csrf 未找到"
        if self.get_task_info()["coin_exp"] >= 50:
            return True, "今日已达上限"
        if self.check_video_coin_status(bvid):
            return True, "该视频已投币"

        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {'bvid': bvid, 'multiply': num, 'select_like': select_like, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "投币成功"
            return False, data.get('message', '投币失败')
        except Exception as e:
            return False, str(e)

    def share_video(self, bvid):
        if not self.csrf:
            return False, "csrf 未找到"
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "分享成功"
            return False, data.get('message', '分享失败')
        except Exception as e:
            return False, str(e)

    def watch_video(self, bvid):
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'bvid': bvid, 'played_time': 30, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "观看成功"
            return False, data.get('message', '观看失败')
        except Exception as e:
            return False, str(e)

    def live_sign(self):
        url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, data.get('data', {}).get('text', '直播签到成功')
            return False, data.get('message', '直播签到失败')
        except Exception as e:
            return False, str(e)

    def manga_sign(self):
        try:
            headers = self.headers.copy()
            headers['Referer'] = "https://manga.bilibili.com/"
            url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            res = requests.post(url, headers=headers, data={"platform": "ios"}, timeout=10)
            data = res.json()
            if data.get("code") == 0:
                return True, "漫画签到成功"
            elif "clockIn" in str(data) or data.get("code") in [-1, 1]:
                return True, "漫画今日已签到"
            else:
                return False, "漫画签到失败"
        except Exception as e:
            return False, f"漫画签到异常: {str(e)}"
