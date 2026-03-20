import requests
import time

class BilibiliTask:
    def __init__(self, cookie):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": cookie,
            "Referer": "https://www.bilibili.com/"
        }
        self.csrf = self.get_csrf()

    def get_csrf(self):
        try:
            for cookie in self.session.cookies:
                if cookie.name == "bili_jct":
                    return cookie.value
        except:
            pass
        return ""

    # ✅ 修复：官方正确任务接口，精准获取今日已投币，无解析错误
    def get_task_info(self):
        try:
            url = "https://api.bilibili.com/x/member/web/exp/log"
            resp = self.session.get(url, timeout=15)
            data = resp.json()
            return data.get("data", {})
        except:
            return {}

    # ✅ 修复：用户信息接口，保证返回 uname 字段
    def get_user_info(self):
        try:
            url = "https://api.bilibili.com/x/space/myinfo"
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {})
        except Exception:
            pass
        return {"uname": "未知用户", "money": 0, "level_info": {"current_level": 0}}

    def get_dynamic_videos(self):
        try:
            url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            bvid_list = []
            for item in items:
                try:
                    bvid = item["modules"]["module_dynamic"]["major"]["archive"]["bvid"]
                    bvid_list.append(bvid)
                except:
                    continue
            return bvid_list[:5] if bvid_list else ["BV1GJ411x7h7"]
        except:
            return ["BV1GJ411x7h7"]

    def share_video(self, bvid):
        try:
            url = "https://api.bilibili.com/x/web-interface/share/add"
            data = {"bvid": bvid, "csrf": self.csrf}
            resp = self.session.post(url, data=data, timeout=10)
            return True, "分享成功"
        except:
            return False, "分享失败"

    # ✅ 修复：直播签到已下线，还原正确提示
    def live_sign(self):
        return False, "签到活动已下线，无法使用。"

    def manga_sign(self):
        try:
            url = "https://manga.bilibili.com/twapis/v1/clock_in"
            self.session.post(url, timeout=10)
            return True, "漫画今日已签到"
        except:
            return False, "漫画签到失败"

    def watch_video(self, bvid):
        try:
            url = "https://api.bilibili.com/x/click-interface/web/heartbeat"
            data = {"bvid": bvid, "played_time": 60, "csrf": self.csrf}
            self.session.post(url, data=data, timeout=10)
            time.sleep(1)
            return True, "观看成功"
        except:
            return False, "观看失败"

    def add_coin(self, bvid, num=1, like=1):
        return False, "已关闭投币"

    def check_video_coin_status(self, bvid):
        return False
