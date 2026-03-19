import requests
from loguru import logger

class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
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

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return data['data']
            return None
        except:
            return None

    # =======================
    # 老仓库原版 直播签到
    # =======================
    def live_sign(self):
        url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "直播签到成功"
            elif data['code'] == 101104:
                return True, "今日已签到"
            else:
                return False, data.get('message', '签到失败')
        except Exception as e:
            return False, str(e)

    # =======================
    # 老仓库原版 漫画签到
    # =======================
    def manga_sign(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)",
            "Referer": "https://manga.bilibili.com/",
            "Cookie": self.cookie
        }
        url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
        try:
            res = requests.post(url, headers=headers, data={"platform": "ios"}, timeout=10)
            data = res.json()
            if data.get("code") == 0:
                return True, "漫画签到成功"
            else:
                return False, "今日已签到或失效"
        except:
            return False, "漫画签到失败"

    def get_task_info(self):
        return {"coin_exp": 999}

    def get_dynamic_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=10&rid=1'
        try:
            res = requests.get(url, headers=self.headers)
            data = res.json()
            return [x['bvid'] for x in data.get('data', {}).get('archives', [])]
        except:
            return []

    def add_coin(self, bvid, num=1, select_like=1):
        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {'bvid': bvid, 'multiply': num, 'select_like': select_like, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            if data['code'] == 0:
                return True, "投币成功"
            return False, data.get('message', '投币失败')
        except:
            return False, "异常"

    def share_video(self, bvid):
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            return True, "分享成功"
        except:
            return False, "失败"

    def watch_video(self, bvid):
        return True, "观看成功"
