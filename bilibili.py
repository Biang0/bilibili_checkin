"""
core function for scripts
"""
import time
import random
from typing import Optional

from core.bilibili_utils import random_video_para, get_insert_num
from utils.push import pushplus_push, wechat_push, sever_push
from core.bilibili_http import BilibiliHttp
from utils.log_f import print_f
from config import config


class Bilibili:
    """
    Bilibili的等级升级脚本
    你每天可以获得65个经验值
    """

    def __init__(self, ck: str) -> None:
        self.log = ''
        self.bilibili_http = BilibiliHttp(ck)
        self.start_time = time.time()  # 记录任务开始时间

    def __push_f(self, content: str):
        """拼接日志（兼容多端推送）"""
        temp = f'{content}</br>'
        self.log = f'{self.log}{temp}'

    def log_and_push(self, content: str):
        """打印日志 + 存入推送缓冲区"""
        self.__push_f(content)
        print_f(content)

    def is_insert(self) -> bool:
        """判断是否满足投币条件"""
        try:
            coin_num = self.bilibili_http.get_coin_num()
            return config.COIN_OR_NOT and coin_num >= 5
        except Exception as e:
            self.log_and_push(f'获取硬币数量失败：{str(e)}，跳过投币任务')
            return False

    def get_valid_video(self) -> Optional[tuple]:
        """获取有效视频参数，空则返回None"""
        try:
            video_list = self.bilibili_http.get_video_list()
            if not video_list:
                self.log_and_push('视频列表为空，无法执行任务')
                return None
            return random_video_para(video_list)
        except Exception as e:
            self.log_and_push(f'获取视频列表失败：{str(e)}')
            return None

    def insert_coins(self) -> bool:
        """单次投币，成功返回True，失败返回False"""
        video_info = self.get_valid_video()
        if not video_info:
            return False
        bvid, title, author, aid = video_info
        self.log_and_push(f'开始向{author}的视频《{title}》投币……')
        try:
            coin_res = self.bilibili_http.insert_coin(aid)
            if coin_res:
                self.log_and_push(f'投币成功：{author} - 《{title}》')
            else:
                self.log_and_push(f'投币失败：{author} - 《{title}》')
            return coin_res
        except Exception as e:
            self.log_and_push(f'投币接口调用失败：{str(e)}')
            return False

    def do_insert_coin(self, strict_mode: bool, coin_has_inserted_num: int):
        """优化后的投币逻辑"""
        if not self.is_insert():
            self.log_and_push('投币任务已跳过～')
            return

        # ===================== ✅ 你要的统计显示 =====================
        coin_left = self.bilibili_http.get_coin_num()  # 剩余硬币
        has_done = coin_has_inserted_num // 10         # 已投数量
        insert_num = get_insert_num(coin_has_inserted_num)  # 待投数量
        
        self.log_and_push(f'====================================')
        self.log_and_push(f'💰 硬币剩余：{coin_left} 个')
        self.log_and_push(f'✅ 今日已投：{has_done} / 5 个')
        self.log_and_push(f'🔄 本次待投：{insert_num} 个')
        self.log_and_push(f'====================================')
        # ===========================================================

        if insert_num <= 0:
            self.log_and_push('投币任务已完成～')
            return

        self.log_and_push(f'投币任务未完成，本次需投币{insert_num}个')
        success_count = 0
        fail_count = 0
        max_try = insert_num * 2  # 最多尝试次数（避免无限循环）

        while success_count < insert_num and success_count + fail_count < max_try:
            if self.insert_coins():
                success_count += 1
            else:
                fail_count += 1
            self.log_and_push(f'投币进度：成功{success_count}/{insert_num}，失败{fail_count}次')
            time.sleep(random.uniform(1, 3))  # 随机等待，避免风控

        if success_count >= insert_num:
            self.log_and_push(f'每日投币：完成~获得{insert_num * 10}点经验值')
        else:
            self.log_and_push(f'每日投币：未完成，成功{success_count}次，应投{insert_num}次')

    def do_share_video(self):
        """优化后的分享视频逻辑"""
        video_info = self.get_valid_video()
        if not video_info:
            self.log_and_push('分享视频任务失败：无可用视频')
            return

        bvid, title, author, aid = video_info
        self.log_and_push(f'开始分享{author}的视频《{title}》……')
        try:
            self.bilibili_http.share_video(bvid)
            self.log_and_push('分享视频任务已完成～')
        except Exception as e:
            self.log_and_push(f'分享视频失败：{str(e)}')

    def do_watch_video(self):
        """优化后的观看视频逻辑"""
        video_info = self.get_valid_video()
        if not video_info:
            self.log_and_push('观看视频任务失败：无可用视频')
            return

        bvid, title, author, aid = video_info
        self.log_and_push(f'开始观看{author}的视频《{title}》……')
        try:
            self.bilibili_http.watch_video(bvid)
            self.log_and_push('观看视频任务完成～')
        except Exception as e:
            self.log_and_push(f'观看视频失败：{str(e)}')

    def handle_login(self, status):
        self.log_and_push('登录任务已完成')

    def handle_watch_video(self, status):
        if status:
            self.log_and_push('观看视频任务已完成')
        else:
            self.log_and_push('观看视频任务未完成')
            self.do_watch_video()

    def handle_insert_coin(self, status):
        if status == 50:  # 50表示投币任务满经验
            # ===================== ✅ 满50时也显示 =====================
            self.log_and_push(f'====================================')
            self.log_and_push(f'💰 硬币剩余：{self.bilibili_http.get_coin_num()} 个')
            self.log_and_push(f'✅ 今日已投：5 / 5 个')
            self.log_and_push(f'🔄 本次待投：0 个')
            self.log_and_push(f'====================================')
            self.log_and_push('投币任务已完成')
            # ===========================================================
        else:
            self.do_insert_coin(strict_mode=config.STRICT_MODE, coin_has_inserted_num=status)

    def handle_share_video(self, status):
        if status:
            self.log_and_push('分享任务已完成')
        else:
            self.log_and_push('分享任务未完成')
            self.do_share_video()

    def do_job(self) -> None:
        """总任务调度（增加全局异常捕获）"""
        try:
            cookie_status = self.bilibili_http.get_cookie_status()
            if not cookie_status:
                self.log_and_push("Cookie无效，任务终止...")
                return
            self.log_and_push('Cookie有效，即将开始任务……')

            # 个人信息
            self.log_and_push('=========以下是个人信息=========')
            user_info = self.bilibili_http.get_info()
            self.log_and_push(user_info)

            # 直播签到
            self.log_and_push('=========直播签到========')
            live_sign_res = self.bilibili_http.live_sign()
            self.log_and_push(live_sign_res)

            # 银瓜子转硬币
            self.log_and_push('=========银瓜子转硬币========')
            if config.SILVER2COIN_OR_NOT:
                try:
                    silver_num = self.bilibili_http.inquire_live_info()
                    if silver_num > 700:
                        silver_to_coin_res = self.bilibili_http.silver_to_coin()
                        if silver_to_coin_res.get('status'):
                            self.log_and_push(f"转换成功～剩余瓜子{silver_to_coin_res.get('msg')}")
                        else:
                            self.log_and_push(f"转换失败：{silver_to_coin_res.get('msg')}")
                    else:
                        self.log_and_push(f'银瓜子不足700（当前{silver_num}），跳过转换~')
                except Exception as e:
                    self.log_and_push(f'银瓜子转换失败：{str(e)}')
            else:
                self.log_and_push('银瓜子转换币：跳过（配置关闭）~')

            # 漫画签到
            self.log_and_push('=========漫画签到情况========')
            try:
                if self.bilibili_http.check_comics_sign():
                    self.log_and_push("漫画签到：当天已签到~")
                else:
                    if self.bilibili_http.comics_sign():
                        self.log_and_push("漫画签到：完成~")
                    else:
                        self.log_and_push("漫画签到：失败~")
            except Exception as e:
                self.log_and_push(f'漫画签到异常：{str(e)}')

            # 核心任务（登录/看视频/分享/投币）
            self.log_and_push('=========核心任务状态========')
            inquire_job_res = self.bilibili_http.inquire_job()
            job_handlers = {
                'login': self.handle_login,
                'watch': self.handle_watch_video,
                'share': self.handle_share_video,
                'insert': self.handle_insert_coin,
            }
            for job_name, job_status in inquire_job_res.items():
                handler = job_handlers.get(job_name)
                if handler:
                    handler(job_status)
                else:
                    self.log_and_push(f'未知任务类型：{job_name}，跳过')

            # 等待任务同步（动态等待，最多30秒）
            wait_time = 0
            while wait_time < 30:
                time.sleep(5)
                wait_time += 5
                latest_job = self.bilibili_http.inquire_job()
                # 检查是否所有核心任务完成
                if (latest_job.get('login') and latest_job.get('watch') and
                    latest_job.get('share') and latest_job.get('insert') == 50):
                    break
            self.log_and_push('=========最终任务状态========')
            self.log_and_push(latest_job)

            # 任务耗时统计
            total_time = round(time.time() - self.start_time, 2)
            self.log_and_push(f'✅ 所有任务执行完毕，总耗时：{total_time}秒')

        except Exception as e:
            self.log_and_push(f'❌ 任务执行异常：{str(e)}')

    def go(self) -> None:
        """入口方法（增加推送异常捕获）"""
        self.do_job()
        # 推送结果（捕获推送异常，避免推送失败导致脚本崩溃）
        try:
            if config.PUSH_OR_NOT:
                pushplus_push(config.TOKEN, self.log)
            if config.WECHAT_PUSH_OR_NOT:
                wechat_push(self.log.replace("</br>", "\n"),
                            config.WECHAT_ID,
                            config.WECHAT_SECRET,
                            config.WECHAT_APP_ID)
            if config.SERVER_PUSH_OR_NOT:
                sever_push(self.log.replace("</br>", "\n"),
                           config.SERVER_KEY)
        except Exception as e:
            self.log_and_push(f'❌ 推送结果失败：{str(e)}')
            print_f(f'推送失败：{e}')
