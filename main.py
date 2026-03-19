import os
import sys
from datetime import datetime, timedelta, timezone
from loguru import logger
from bilibili import BilibiliTask
import requests

class BeijingFormatter:
    @staticmethod
    def format(record):
        dt = datetime.fromtimestamp(record["time"].timestamp(), tz=timezone.utc)
        local_dt = dt + timedelta(hours=8)
        record["extra"]["local_time"] = local_dt.strftime('%H:%M:%S,%f')[:-3]
        return "{time:YYYY-MM-DD HH:mm:ss,SSS}(CST {extra[local_time]}) - {level} - {message}\n"

logger.remove()
logger.add(sys.stdout, format=BeijingFormatter.format, level="INFO", colorize=True)

def mask_string(s: str):
    if not isinstance(s, str) or len(s) == 0:
        return "*"
    return s[0] + "*" * (len(s) - 1)

def execute_coin_task(bili, user_info, config):
    try:
        task_info = bili.get_task_info()
        coin_exp = task_info.get("coin_exp", 0)
        today_coin = coin_exp // 10
    except:
        today_coin = 0

    if today_coin >= 5:
        return True, f"今日已投{today_coin}/5 → 跳过"

    max_coin = int(config.get('COIN_ADD_NUM', 5))
    need_coin = min(max_coin, 5 - today_coin)
    if need_coin <= 0:
        return True, f"今日已投{today_coin}/5"

    balance = user_info.get("money", 0)
    if balance < need_coin:
        return False, f"硬币不足，需要{need_coin}个"

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
    return True, f"已投{today_coin + added}/5（今日经验{coin_exp}）"

def run_all_tasks_for_account(bili, config):
    user_info = bili.get_user_info()
    if not user_info:
        return {'登录检查': (False, 'Cookie 失效')}, None

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

# ==============================
# 推送工具函数
# ==============================
def send_pushplus(token, title, msg):
    if not token:
        logger.warning("未配置 PushPlus，跳过推送")
        return
    try:
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": msg.replace("\n", "<br>"),
            "template": "markdown"
        }
        res = requests.post(url, json=data, timeout=10)
        if res.json().get("code") == 200:
            logger.info("✅ PushPlus 推送成功")
        else:
            logger.error(f"❌ PushPlus 推送失败：{res.json().get('msg')}")
    except Exception as e:
        logger.error(f"PushPlus 异常：{e}")

def send_telegram(bot_token, chat_id, msg):
    if not bot_token or not chat_id:
        logger.warning("未配置 Telegram，跳过推送")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, data=data, timeout=10)
        if res.json().get("ok"):
            logger.info("✅ Telegram 推送成功")
        else:
            logger.error(f"❌ TG 推送失败：{res.json().get('description')}")
    except Exception as e:
        logger.error(f"TG 异常：{e}")

def main():
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM", 5),
        "COIN_SELECT_LIKE": os.environ.get("COIN_SELECT_LIKE", 1),
        "PUSH_PLUS_TOKEN": os.environ.get("PUSH_PLUS_TOKEN"),
        "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN"),
        "TG_CHAT_ID": os.environ.get("TG_CHAT_ID"),
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置 BILIBILI_COOKIE")
        sys.exit(1)

    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split("###") if c.strip()]
    final_msg = "📊 B站每日签到报告\n\n"

    for idx, cookie in enumerate(cookies, 1):
        logger.info(f"=== 账号{idx} 任务开始 ===")
        bili = BilibiliTask(cookie)
        tasks, user = run_all_tasks_for_account(bili, config)

        final_msg += f"===== 账号{idx} =====\n"
        for name, (ok, info) in tasks.items():
            icon = "✅" if ok else "❌"
            final_msg += f"{name}：{icon} {info}\n"
            logger.info(f"[账号{idx}] {name}：{'成功' if ok else '失败'} | {info}")

        logger.info("=== 任务完成 ===\n")

    # 双推送
    send_pushplus(config["PUSH_PLUS_TOKEN"], "B站签到报告", final_msg)
    send_telegram(config["TG_BOT_TOKEN"], config["TG_CHAT_ID"], final_msg)

if __name__ == "__main__":
    main()
    except Exception as e:
        logger.error(f"TG 异常：{e}")

def main():
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM", 5),
        "COIN_SELECT_LIKE": os.environ.get("COIN_SELECT_LIKE", 1),
        "PUSH_PLUS_TOKEN": os.environ.get("PUSH_PLUS_TOKEN"),
        "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN"),
        "TG_CHAT_ID": os.environ.get("TG_CHAT_ID"),
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置 BILIBILI_COOKIE")
        sys.exit(1)

    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split("###") if c.strip()]
    final_msg = "📊 B站每日签到报告\n\n"

    for idx, cookie in enumerate(cookies, 1):
        logger.info(f"=== 账号{idx} 任务开始 ===")
        bili = BilibiliTask(cookie)
        tasks, user = run_all_tasks_for_account(bili, config)

        final_msg += f"===== 账号{idx} =====\n"
        for name, (ok, info) in tasks.items():
            icon = "✅" if ok else "❌"
            final_msg += f"{name}：{icon} {info}\n"
            logger.info(f"[账号{idx}] {name}：{'成功' if ok else '失败'} | {info}")

        logger.info("=== 任务完成 ===\n")

    # 双推送
    send_pushplus(config["PUSH_PLUS_TOKEN"], "B站签到报告", final_msg)
    send_telegram(config["TG_BOT_TOKEN"], config["TG_CHAT_ID"], final_msg)

if __name__ == "__main__":
    main()
