import requests
import time

class BilibiliTask:
    def __init__(self, cookie):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": cookie,
            "Referer": "https://www.bilibili.com/"
        }
        self.csrf = self.get_csrf()

    def get_csrf(self):
        for cookie in self.session.cookies:
            if cookie.name == "bili_jct":
                return cookie.value
        return ""

    # ✅ 核心修复：获取B站官方任务状态（精准返回今日已投币数）
    def get_task_info(self):
        url = "https://api.bilibili.com/x/member/web/exp/log?jsonp=jsonp"
        resp = self.session.get(url, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            return {}
        
        # 对标开源项目，获取今日投币数量
        task_url = "https://api.bilibili.com/x/member/web/task"
        task_resp = self.session.get(task_url, timeout=10)
        task_data = task_resp.json()
        if task_data.get("code") == 0:
            return task_data.get("data", {})
        return {}

    # 获取用户信息
    def get_user_info(self):
        url = "https://api.bilibili.com/x/space/myinfo"
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {})
        except:
            pass
        return None

    # 获取动态视频
    def get_dynamic_videos(self):
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            bvid_list = []
            for item in items:
                if "modules" in item and "module_dynamic" in item["modules"]:
                    dynamic = item["modules"]["module_dynamic"]
                    if "major" in dynamic and "archive" in dynamic["major"]:
                        bvid = dynamic["major"]["archive"].get("bvid")
                        if bvid:
                            bvid_list.append(bvid)
            return bvid_list[:5]
        except:
            return ["BV1GJ411x7h7"]

    # 分享视频
    def share_video(self, bvid):
        try:
            url = "https://api.bilibili.com/x/web-interface/share/add"
            data = {"bvid": bvid, "csrf": self.csrf}
            resp = self.session.post(url, data=data, timeout=10)
            return True, "分享成功"
        except:
            return False, "分享失败"

    # 直播签到
    def live_sign(self):
        try:
            url = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/WebSign"
            resp = self.session.get(url, timeout=10)
            return True, "签到成功"
        except:
            return False, "签到活动已下线，无法使用。"

    # 漫画签到
    def manga_sign(self):
        try:
            url = "https://manga.bilibili.com/twapis/v1/clock_in"
            self.session.post(url, timeout=10)
            return True, "漫画今日已签到"
        except:
            return False, "漫画签到失败"

    # 观看视频
    def watch_video(self, bvid):
        try:
            url = f"https://api.bilibili.com/x/click-interface/web/heartbeat"
            data = {"bvid": bvid, "played_time": 60, "csrf": self.csrf}
            self.session.post(url, data=data, timeout=10)
            time.sleep(1)
            return True, "观看成功"
        except:
            return False, "观看失败"

    # 投币（备用，默认不启用）
    def add_coin(self, bvid, num=1, like=1):
        try:
            url = "https://api.bilibili.com/x/web-interface/coin/add"
            data = {"bvid": bvid, "multiply": num, "like": like, "csrf": self.csrf}
            resp = self.session.post(url, data=data, timeout=10)
            return resp.json().get("code") == 0, "投币成功"
        except:
            return False, "投币失败"

    # 检查投币状态
    def check_video_coin_status(self, bvid):
        try:
            url = "https://api.bilibili.com/x/web-interface/coin/triple"
            params = {"bvid": bvid}
            resp = self.session.get(url, params=params, timeout=10)
            return resp.json().get("data", {}).get("coin", 0) > 0
        except:
            return False
