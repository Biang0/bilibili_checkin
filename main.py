import os
import sys
import time
import random
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
    """
    优化后的投币逻辑
    策略：根据配置尝试投币，由B站服务器验证每日上限
    """
    # 1. 获取配置
    try:
        want_coin = int(config.get('COIN_ADD_NUM', 5))
        if want_coin < 0:
            want_coin = 0
        elif want_coin > 5:
            want_coin = 5
    except:
        want_coin = 5
    
    if want_coin == 0:
        return True, "已设置不投币(COIN_ADD_NUM=0)"
    
    # 2. 获取实时硬币余额（关键修复：使用BilibiliTask的get_coin_balance方法）
    try:
        coin_left = bili.get_coin_balance()
    except Exception as e:
        logger.error(f"获取硬币余额失败: {e}")
        # 回退到从user_info获取
        coin_left = user_info.get("money", 0)
    
    # 3. 显示状态
    logger.info(f"========================================")
    logger.info(f"💰 硬币余额：{coin_left} 个")
    logger.info(f"🎯 计划投币：{want_coin} 个 (由COIN_ADD_NUM配置)")
    logger.info(f"⚠️  每日上限5个，最终以B站服务器确认为准")
    logger.info(f"========================================")
    
    # 4. 检查硬币余额
    if coin_left < want_coin:
        return False, f"硬币不足（余额{coin_left}，需要{want_coin}）"
    
    # 5. 获取视频列表
    video_list = bili.get_dynamic_videos()
    if not video_list:
        return False, "无可用视频"
    
    # 6. 执行投币
    try:
        select_like = int(config.get('COIN_SELECT_LIKE', 1))
    except:
        select_like = 1
    
    success = 0
    attempted = 0
    max_attempts = min(len(video_list), want_coin * 2)  # 最大尝试次数
    
    for bvid in video_list:
        if attempted >= max_attempts:
            break
        if success >= want_coin:
            break
        
        attempted += 1
        
        ok, msg = bili.add_coin(bvid, 1, select_like)
        if ok and "成功" in msg:
            success += 1
            logger.info(f"✅ 投币成功 ({success}/{want_coin}) - 视频: {bvid}")
        elif "已达上限" in msg:
            logger.info(f"⏹️  {msg}，停止投币")
            break
        elif "已投币" in msg:
            logger.debug(f"⏭️  视频 {bvid} 已投过币，跳过")
            continue
        else:
            logger.warning(f"❌ 投币失败: {msg}")
        
        # 随机延迟，避免请求过于频繁
        time.sleep(random.uniform(1, 2))
    
    # 7. 返回结果
    if success > 0:
        return True, f"投币完成: 成功{success}/{want_coin}个"
    else:
        return False, f"投币失败: 尝试{attempted}次，成功0次"

def run_all_tasks_for_account(bili, config):
    user_info = bili.get_user_info()
    if not user_info:
        return {'登录检查': (False, 'Cookie 失效')}, None
    
    username = user_info.get('uname', '未知用户')
    logger.info(f"账号名称: {mask_string(username)}")
    logger.info(f"用户等级: Lv.{user_info.get('level_info', {}).get('current_level', 0)}")
    
    tasks_result = {}
    video_list = bili.get_dynamic_videos()
    
    # 获取一个视频用于分享和观看任务
    bvid = video_list[0] if video_list else "BV1GJ411x7h7"
    
    # 执行各项任务
    logger.info("--- 开始执行分享任务 ---")
    tasks_result['分享视频'] = bili.share_video(bvid)
    
    logger.info("--- 开始执行直播签到 ---")
    tasks_result['直播签到'] = bili.live_sign()
    
    logger.info("--- 开始执行漫画签到 ---")
    tasks_result['漫画签到'] = bili.manga_sign()
    
    logger.info("--- 开始执行投币任务 ---")
    tasks_result['投币任务'] = execute_coin_task(bili, user_info, config)
    
    logger.info("--- 开始执行观看任务 ---")
    tasks_result['观看视频'] = bili.watch_video(bvid)
    
    return tasks_result, user_info

def format_push_message(all_results):
    content = ["### Bilibili 任务报告\n"]
    for result in all_results:
        user_info = result.get('user_info')
        if user_info:
            account_name = user_info.get('uname', '未知用户')
            level = user_info.get('level_info', {}).get('current_level', 0)
            content.append(f"--- \n#### 账号: {account_name} (Lv.{level})")
        else:
            account_name = f"账号 {result['account_index']}"
            content.append(f"--- \n#### {account_name}")

        for name, (success, message) in result['tasks'].items():
            status_icon = "✅" if success else "❌"
            reason = f" - {message}" if message else ""
            content.append(f"- **{name}**: {status_icon}{reason}")
        
        if user_info:
            # 尝试获取最新的硬币余额
            coin_balance = user_info.get('money', 0)
            content.append(f"- **硬币余额**: {coin_balance}")

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
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM", 5),  # 默认改为5
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
    
    logger.info(f"检测到 {len(cookies)} 个账号")

    for idx, cookie in enumerate(cookies, 1):
        logger.info(f"\n{'='*40}")
        logger.info(f"开始处理账号{idx}/{len(cookies)}")
        logger.info(f"{'='*40}")
        
        bili = BilibiliTask(cookie)
        tasks, user = run_all_tasks_for_account(bili, config)

        all_results.append({
            'account_index': idx,
            'user_info': user,
            'tasks': tasks
        })

        # 记录本账号任务结果
        logger.info(f"\n账号{idx} 任务结果:")
        for name, (ok, info) in tasks.items():
            status = "✅ 成功" if ok else "❌ 失败"
            logger.info(f"  {name}: {status} | {info}")
        
        logger.info(f"{'='*40}")
        logger.info(f"账号{idx} 任务完成")
        logger.info(f"{'='*40}\n")
        
        # 账号间延迟，避免请求过于频繁
        if idx < len(cookies):
            delay = random.uniform(3, 6)
            logger.info(f"等待 {delay:.1f} 秒后处理下一个账号...")
            time.sleep(delay)

    # 生成并发送报告
    if all_results:
        final_msg = format_push_message(all_results)
        logger.info("\n" + "="*50)
        logger.info("开始发送推送通知...")
        logger.info("="*50)
        
        send_to_pushplus(config["PUSH_PLUS_TOKEN"], "Bilibili 任务报告", final_msg)
        send_to_telegram(config["TG_BOT_TOKEN"], config["TG_CHAT_ID"], final_msg)
        
        logger.info("="*50)
        logger.info("所有任务处理完成！")
        logger.info("="*50)
    else:
        logger.error("没有有效的任务结果，跳过推送")

if __name__ == "__main__":
    main()
