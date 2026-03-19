import os
import sys
from datetime import datetime, timedelta, timezone
from loguru import logger
from bilibili import BilibiliTask

class BeijingFormatter:
    @staticmethod
    def format(record):
        dt = datetime.fromtimestamp(record["time"].timestamp(), tz=timezone.utc)
        local_dt = dt + timedelta(hours=8)
        record["extra"]["local_time"] = local_dt.strftime('%H:%M:%S,%f')[:-3]
        return "{time:YYYY-MM-DD HH:mm:ss,SSS}(CST {extra[local_time]}) - {level} - {message}\n"

logger.remove()
logger.add(sys.stdout, format=BeijingFormatter.format, level="INFO", colorize=True)

def mask_name(s):
    return s[0] + "*" if s else "*"

def coin_task(bili, user):
    exp = bili.get_task_info().get("coin_exp",0)
    today = exp // 10
    if today >=5:
        return True,f"判断结果：今日已投{today}/5 → 跳过"
    return True,f"今日可投，当前已投{today}/5"

def run(bili):
    user = bili.get_user_info()
    if not user:
        return {"登录":(False,"Cookie失效")}
    logger.info(f"账号：{mask_name(user.get('uname',''))}")
    bv = bili.get_dynamic_videos()[:1]
    bvid = bv[0] if bv else "BV1xx411c7mq"
    return {
        "分享视频": bili.share_video(bvid),
        "直播签到": bili.live_sign(),
        "漫画签到": bili.manga_sign(),
        "投币任务": coin_task(bili, user),
        "观看视频": bili.watch_video(bvid),
        "风纪委": bili.jury_daily()
    }

def main():
    cookie = os.environ.get("BILIBILI_COOKIE")
    if not cookie:
        logger.error("未配置Cookie")
        return
    for i, ck in enumerate([x.strip() for x in cookie.split("###") if x.strip()],1):
        logger.info(f"=== 账号{i} 任务开始 ===")
        res = run(BilibiliTask(ck))
        for k,(ok,msg) in res.items():
            logger.info(f"[账号{i}] {k}: {'成功' if ok else '失败'} | {msg}")
        logger.info("=== 任务完成 ===")

if __name__ == '__main__':
    main()
