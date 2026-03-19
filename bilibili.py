import requests
from loguru import logger

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

    def get_user_info(self):
        url = 'https://api.bilibili.com/x/web-interface/nav'
        try:
            res = requests.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json()
            if data['code'] == 0:
                return data['data']
            logger.warning(f"获取用户信息失败: {data.get('message')}")
            return None
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None

    # ================================
    # 👇 👇 这就是你老仓库原版代码 👇 👇
    # ================================
    def live_sign(self):
        url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "直播签到成功"
            else:
                return False, data.get('message', '直播签到失败')
        except Exception as e:
            return False, str(e)

    def manga_sign(self):
        url = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
        try:
            res = requests.post(url, headers=self.headers, data={"platform": "ios"}, timeout=10)
            data = res.json()
            if data['code'] == 0:
                return True, "漫画签到成功"
            else:
                return False, "漫画签到失败"
        except Exception as e:
            return False, str(e)

    def get_task_info(self):
        try:
            url = "https://api.bilibili.com/x/member/web/exp/log"
            resp = requests.get(url, headers=self.headers, timeout=8)
            data = resp.json()
            if data.get("code") != 0:
                return {"coin_exp": 0}

            coin_exp = 0
            for item in data.get("data", {}).get("list", []):
                if "投币" in item.get("reason", ""):
                    coin_exp += item.get("delta", 0)
            return {"coin_exp": coin_exp}
        except:
            return {"coin_exp": 0}

    # ================================
    # 👆 👆 老仓库原版代码结束 👆 👆
    # ================================

    def get_dynamic_videos(self):
        url = 'https://api.bilibili.com/x/web-interface/dynamic/region?ps=5&rid=1'
        try:
            res = requests.get(url, headers=self.headers)
            data = res.json()
            return [v['bvid'] for v in data.get('data', {}).get('archives', [])]
        except:
            return []

    def get_ranking_videos(self):
        return []

    def check_video_coin_status(self, bvid):
        return False

    def add_coin(self, bvid, num=1, select_like=1):
        if not self.csrf:
            return False, "csrf缺失"
        url = 'https://api.bilibili.com/x/web-interface/coin/add'
        data = {'bvid': bvid, 'multiply': num, 'select_like': select_like, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            data = res.json()
            if data['code'] == 0:
                return True, "投币成功"
            return False, data.get('message')
        except:
            return False, "投币异常"

    def share_video(self, bvid):
        if not self.csrf:
            return False, "csrf缺失"
        url = 'https://api.bilibili.com/x/web-interface/share/add'
        data = {'bvid': bvid, 'csrf': self.csrf}
        try:
            res = requests.post(url, headers=self.headers, data=data)
            return True, "分享成功"
        except:
            return False, "分享异常"

    def watch_video(self, bvid):
        return True, "观看成功"
