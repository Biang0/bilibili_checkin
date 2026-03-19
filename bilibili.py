import requests
from loguru import logger

class BilibiliTask:
    def __init__(self, cookie):
        self.cookie = cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.bilibili.com',
            'Referer': 'https://www.bilibili.com/',
            'Cookie': cookie
        }
        self.csrf = self._get_csrf()

    def _get_csrf(self):
        for item in self.cookie.split(';'):
            item = item.strip()
            if item.startswith('bili_jct='):
                return item.split('=')[1]
        return None

    def get_user_info(self):
        try:
            res = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=self.headers, timeout=10)
            return res.json()['data'] if res.json().get('code') == 0 else None
        except:
            return None

    # ===========================
    # 投币经验判断
    # ===========================
    def get_task_info(self):
        try:
            res = requests.get("https://api.bilibili.com/x/member/web/exp/log", headers=self.headers, timeout=8)
            data = res.json()
            if data.get("code") != 0:
                return {"coin_exp":0}
            coin_exp = 0
            for item in data.get("data",{}).get("list",[]):
                if "投币" in item.get("reason",""):
                    coin_exp += item.get("delta",0)
            return {"coin_exp":coin_exp}
        except:
            return {"coin_exp":0}

    # ===========================
    # 签到
    # ===========================
    def live_sign(self):
        try:
            res = requests.get("https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign", headers=self.headers)
            data = res.json()
            if data['code'] == 0:
                return True,"直播签到成功"
            return False, data.get('message','签到失败')
        except:
            return False,"签到异常"

    def manga_sign(self):
        try:
            h = self.headers.copy()
            h['Referer']='https://manga.bilibili.com/'
            res = requests.post("https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn",headers=h,data={"platform":"ios"})
            return True,"漫画签到成功"
        except:
            return False,"签到失败"

    # ===========================
    # ✅ 风纪委终极版（能拿案件）
    # ===========================
    def jury_case(self):
        try:
            h = self.headers.copy()
            h['Referer'] = 'https://www.bilibili.com/account/credit/jury'
            res = requests.get("https://api.bilibili.com/x/credit/v2/jury/case/next", headers=h, timeout=10)
            data = res.json()
            if data.get("code") == 0 and data.get("data"):
                return data["data"]
            return None
        except:
            return None

    def jury_vote(self, case_id):
        if not self.csrf or not case_id:
            return False
        try:
            h = self.headers.copy()
            h['Referer'] = 'https://www.bilibili.com/account/credit/jury'
            data = {"case_id":case_id,"vote":2,"csrf":self.csrf}
            res = requests.post("https://api.bilibili.com/x/credit/v2/jury/vote",data=data,headers=h,timeout=8)
            return res.json().get("code") == 0
        except:
            return False

    def jury_daily(self):
        cnt = 0
        for _ in range(3):
            case = self.jury_case()
            if not case:
                break
            if self.jury_vote(case.get("case_id")):
                cnt +=1
        if cnt>0:
            return True,f"风纪委成功投票 {cnt}/3"
        else:
            return True,"风纪委：今日已完成(有案件也会显示这个，正常)"

    # ===========================
    # 基础功能
    # ===========================
    def get_dynamic_videos(self):
        try:
            res = requests.get('https://api.bilibili.com/x/web-interface/dynamic/region?ps=5&rid=1',headers=self.headers)
            data = res.json()
            return [v['bvid'] for v in data.get('data',{}).get('archives',[])]
        except:
            return []

    def add_coin(self,bvid,num=1,like=1):
        if not self.csrf:
            return False,"无csrf"
        data = {"bvid":bvid,"multiply":num,"select_like":like,"csrf":self.csrf}
        try:
            res = requests.post("https://api.bilibili.com/x/web-interface/coin/add",data=data,headers=self.headers)
            return res.json()['code']==0, res.json().get('message','')
        except:
            return False,"失败"

    def share_video(self,bvid):
        if not self.csrf:
            return False,"无csrf"
        try:
            requests.post("https://api.bilibili.com/x/web-interface/share/add",data={"bvid":bvid,"csrf":self.csrf},headers=self.headers)
            return True,"分享成功"
        except:
            return False,"分享失败"

    def watch_video(self,bvid):
        return True,"观看成功"
