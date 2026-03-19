import os
import sys
from datetime import datetime, timedelta, timezone
from loguru import logger
from bilibili import BilibiliTask
from push import format_push_message, send_to_pushplus

class BeijingFormatter:
    @staticmethod
    def format(record):
        dt = datetime.fromtimestamp(record["time"].timestamp(), tz=timezone.utc)
        local_dt = dt + timedelta(hours=8)
        record["extra"]["local_time"] = local_dt.strftime('%H:%M:%S,%f')[:-3]
        return "{time:YYYY-MM-DD HH:mm:ss,SSS}(CST {extra[local_time]}) - {level} - {message}\n"

logger.remove()
logger.add(sys.stdout, format=BeijingFormatter.format, level="INFO", colorize=True)

def mask_string(s: str) -> str:
    if not isinstance(s, str) or len(s) == 0:
        return '*'
    return s[0] + '*' * (len(s) - 1)

def mask_uid(uid: str) -> str:
    uid_str = str(uid)
    if len(uid_str) <= 2:
        return uid_str[0] + '*'
    return uid_str[:2] + '*' * 5

# ===========================
# ✅ 精准判断：经验 → 投币数量（已修复变量）
# ===========================
def execute_coin_task(bili, user_info, config):
    coin_exp = 0  # 提前定义，防止异常时报错
    try:
        task_info = bili.get_task_info()
        coin_exp = task_info.get("coin_exp", 0)
        today_coin = coin_exp // 10
    except:
        today_coin = 0

    if today_coin >= 5:
        return True, f"判断结果：今日已投{today_coin}/5 → 跳过"

    max_coin = int(config.get('COIN_ADD_NUM', 5))
    need_coin = min(max_coin, 5 - today_coin)

    if need_coin <= 0:
        return True, f"判断结果：无需投币"

    balance = user_info.get("money", 0)
    if balance < need_coin:
        return True, f"判断结果：硬币不足{need_coin}个"

    if config.get('COIN_VIDEO_SOURCE') == 'ranking':
        video_list = bili.get_ranking_videos()
    else:
        video_list = bili.get_dynamic_videos()

    if not video_list:
        return False, "获取视频失败"

    added = 0
    for bvid in video_list:
        if added >= need_coin:
            break
        ok, msg = bili.add_coin(bvid, 1, int(config.get('COIN_SELECT_LIKE', 1)))
        if ok:
            added += 1
            logger.info(f"投币成功 {added}/{need_coin}")
        elif "已达到" in msg:
            break

    return True, f"判断完成 ✅ 经验{coin_exp} → 已投{today_coin+added}/5"

# ===========================
# 主任务流程
# ===========================
def run_all_tasks_for_account(bili, config):
    tasks_to_run = ['live_sign','manga_sign','share_video','add_coin']
    user_info = bili.get_user_info()
    if not user_info:
        return {'登录检查': (False, 'Cookie失效')}, None

    logger.info(f"账号名称: {mask_string(user_info.get('uname'))}")
    tasks_result = {}
    video_list = bili.get_dynamic_videos()
    bvid = video_list[0] if video_list else "BV1GJ411x7h7"

    tasks_result['分享视频'] = bili.share_video(bvid)
    tasks_result['直播签到'] = bili.live_sign()
    tasks_result['漫画签到'] = bili.manga_sign()
    tasks_result['投币任务'] = execute_coin_task(bili, user_info, config)
    tasks_result['观看视频'] = bili.watch_video(bvid)
    return tasks_result, user_info

def main():
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM") or 5,
        "COIN_SELECT_LIKE": os.environ.get("COIN_SELECT_LIKE") or 1,
        "COIN_VIDEO_SOURCE": os.environ.get("COIN_VIDEO_SOURCE") or "dynamic"
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置Cookie")
        sys.exit(1)

    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split('###') if c.strip()]
    for i, cookie in enumerate(cookies, 1):
        logger.info(f"=== 账号{i} 任务开始 ===")
        bili = BilibiliTask(cookie)
        tasks_result, user_info = run_all_tasks_for_account(bili, config)

        for task_name, (success, msg) in tasks_result.items():
            logger.info(f"[账号{i}] {task_name}: {'成功' if success else '失败'} | {msg}")

        logger.info("=== 任务完成 ===")

IGNORE_FAIL_KEYWORDS = ["已下线","签到失败","跳过"]
if __name__ == '__main__':
    main()
