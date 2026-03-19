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
# ✅ 【只判断、绝对不投币】
# ===========================
def check_coin_status(bili):
    try:
        task_info = bili.get_task_info()
        coin_exp = task_info.get("coin_exp", 0)
        today_coin = coin_exp // 10
    except:
        today_coin = 0
        coin_exp = 0

    # 输出判断结果
    logger.info(f"======================================")
    logger.info(f"📊 今日投币状态（只判断，不投币）")
    logger.info(f"📊 投币获得经验：{coin_exp} / 50")
    logger.info(f"📊 今日已投硬币：{today_coin} / 5 个")
    logger.info(f"======================================")

    if today_coin >= 5:
        logger.info("✅ 状态：今日已投满 5 个，无需投币")
    else:
        logger.info(f"✅ 状态：今日可投，还能投 {5 - today_coin} 个")
    
    return True, "仅查询状态，未投币"

# ===========================
# 主任务（只查询，不投币）
# ===========================
def run_all_tasks_for_account(bili):
    user_info = bili.get_user_info()
    if not user_info:
        return {'登录检查': (False, 'Cookie失效')}, None

    logger.info(f"账号名称: {mask_string(user_info.get('uname'))}")
    tasks_result = {}
    
    # 只判断投币状态，绝对不投
    tasks_result['投币状态查询'] = check_coin_status(bili)
    
    return tasks_result, user_info

def main():
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置Cookie")
        sys.exit(1)

    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split('###') if c.strip()]
    for i, cookie in enumerate(cookies, 1):
        logger.info(f"=== 账号{i} 【只判断、不投币】模式 ===")
        bili = BilibiliTask(cookie)
        tasks_result, user_info = run_all_tasks_for_account(bili)

        for task_name, (success, msg) in tasks_result.items():
            logger.info(f"[账号{i}] {task_name}: {'成功' if success else '失败'} | {msg}")

        logger.info(f"=== 账号{i} 任务结束（未投任何币）===\n")

if __name__ == '__main__':
    main()
