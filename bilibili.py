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

    # ====================== ✅ 终极修复：读取完整今日投币经验 ======================
    def get_task_info(self):
        try:
            # 获取今日 0 点北京时间
            beijing_tz = timezone(timedelta(hours=8))
            today = datetime.now(beijing_tz)
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=beijing_tz)
            today_start_ts = int(today_start.timestamp())

            coin_exp = 0
            page = 1
            max_page = 5  # 最多读5页，防止死循环

            while page <= max_page:
                url = f"https://api.bilibili.com/x/member/web/exp/log?jsonp=jsonp&pn={page}&ps=30"
                res = requests.get(url, headers=self.headers, timeout=10)
                data = res.json()

                if data.get("code") != 0 or not data.get("data", {}).get("list"):
                    break

                for item in data["data"]["list"]:
                    try:
                        # 时间判断
                        ts = int(item.get("time", 0))
                        if ts < today_start_ts:
                            # 已翻到昨日，直接结束
                            return {"coin_exp": coin_exp}

                        # 只统计【投币】获得的经验
                        reason = item.get("reason", "")
                        exp = int(item.get("delta", 0))

                        if "投币" in reason and exp > 0:
                            coin_exp += exp

                    except:
                        continue

                page += 1

            return {"coin_exp": coin_exp}

        except Exception as e:
            logger.error(f"获取经验日志失败: {e}")
            return {"coin_exp": 0}

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']
            return None
        except:
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
        except:
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
            return False, "csrf 不存在"
        if self.check_video_coin_status(bvid):
            return True, "该视频已投币"
        if self.get_task_info()["coin_exp"] >= 50:
            return True, "今日投币已达上限"

        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {
            'bvid': bvid,
            'multiply': num,
            'select_like': select_like,
            'csrf': self.csrf
        }

        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "投币成功"
            return False, data.get('message', '未知错误')
        except:
            return False, "请求失败"

    def share_video(self, bvid):
        if not self.csrf:
            return False, "csrf 不存在"
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            return (data['code'] == 0, "分享成功" if data['code'] == 0 else "分享失败")
        except:
            return False, "分享异常"

    def watch_video(self, bvid):
        url = 'https://api.bilibili.com/x/click-interface/web/heartbeat'
        data = {'bvid': bvid, 'played_time': 30, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data, timeout=10)
            data = res.json()
            return (data['code'] == 0, "观看成功" if data['code'] == 0 else "观看失败")
        except:
            return False, "观看异常"

    def live_sign(self):
        url = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "直播签到成功"
            return False, data.get('message', '直播签到失败')
        except:
            return False, "直播签到异常"

    def manga_sign(self):
        try:
            headers = self.headers.copy()
            headers['Referer'] = 'https://manga.bilibili.com/'
            url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
            res = requests.post(url, headers=headers, data={"platform": "ios"}, timeout=10)
            data = res.json()
            if data.get("code") == 0:
                return True, "漫画签到成功"
            return False, "漫画今日已签到"
        except:
            return False, "漫画签到异常"
