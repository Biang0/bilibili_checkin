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
        # ✅ 修复：对标开源项目，精准获取官方投币数据
        task_info = bili.get_task_info()
        today_coin = task_info.get("today_coin", 0)
    except Exception as e:
        logger.error(f"获取投币记录失败: {e}")
        today_coin = 0

    # 显示精准数据
    coin_left = user_info.get("money", 0)
    need_coin = max(0, 5 - today_coin)
    
    logger.info(f"========================================")
    logger.info(f"💰 硬币剩余：{coin_left} 个")
    logger.info(f"✅ 今日已投：{today_coin} / 5 个")
    logger.info(f"🔄 今日待投：{need_coin} 个")
    logger.info(f"========================================")

    # ✅ 你的需求：已投币，跳过自动投币
    return True, f"已设置不投币(COIN_ADD_NUM=0)"

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

def format_push_message(all_results):
    content = ["### Bilibili 任务报告\n"]
    for result in all_results:
        user_info = result.get('user_info')
        if user_info:
            account_name = user_info['uname']
            content.append(f"--- \n#### 账号: {account_name} (Lv.{user_info['level_info']['current_level']})")
        else:
            account_name = f"账号 {result['account_index']}"
            content.append(f"--- \n#### {account_name}")

        for name, (success, message) in result['tasks'].items():
            status_icon = "✅" if success else "❌"
            reason = f" - {message}" if message else ""
            content.append(f"- **{name}**: {status_icon}{reason}")
        if user_info:
            content.append(f"- **硬币余额**: {user_info['money']}")

    beijing_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    content.append(f"\n> 报告时间: {beijing_time}")
    return "\n".join(content)

def send_to_pushplus(token, title, content):
    if not token:
        logger.warning("未配置 PushPlus，跳过推送")
        return
    url = "http://www.pushplus.plus/send"
    data = {"token": token, "title": title, "content": content, "template": "markdown"}
    try:
        res = requests.post(url, json=data, timeout=10)
        if res.json().get('code') == 200:
            logger.info('✅ PushPlus 推送成功！')
        else:
            logger.error(f'❌ PushPlus 推送失败: {res.json().get("msg", "未知错误")}')
    except Exception as e:
        logger.error(f"PushPlus 异常: {e}")

def send_to_telegram(bot_token, chat_id, content):
    if not bot_token or not chat_id:
        logger.warning("TG 未配置，跳过推送")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": content,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        if result.get("ok"):
            logger.info("✅ Telegram 推送成功！")
        else:
            logger.error(f'❌ TG 推送失败: {result.get("description")}')
    except Exception as e:
        logger.error(f"TG 异常: {e}")

def main():
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM", 0),
        "COIN_SELECT_LIKE": os.environ.get("COIN_SELECT_LIKE", 1),
        "PUSH_PLUS_TOKEN": os.environ.get("PUSH_PLUS_TOKEN", ""),
        "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN", ""),
        "TG_CHAT_ID": os.environ.get("TG_CHAT_ID", ""),
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置 BILIBILI_COOKIE")
        sys.exit(1)

    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split("###") if c.strip()]
    all_results = []

    for idx, cookie in enumerate(cookies, 1):
        logger.info(f"=== 账号{idx} 任务开始 ===")
        bili = BilibiliTask(cookie)
        tasks, user = run_all_tasks_for_account(bili, config)

        all_results.append({
            'account_index': idx,
            'user_info': user,
            'tasks': tasks
        })

        for name, (ok, info) in tasks.items():
            logger.info(f"[账号{idx}] {name}：{'成功' if ok else '失败'} | {info}")
        logger.info(f"=== 任务完成 ===\n")

    final_msg = format_push_message(all_results)
    send_to_pushplus(config["PUSH_PLUS_TOKEN"], "Bilibili 任务报告", final_msg)
    send_to_telegram(config["TG_BOT_TOKEN"], config["TG_CHAT_ID"], final_msg)

if __name__ == "__main__":
    main()
