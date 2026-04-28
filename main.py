import os
import sys
import time
import random
from datetime import datetime, timedelta, timezone
from loguru import logger
from bilibili import BilibiliTask
import requests
import json

# ==============================================
#  B站 Cookie 防风控 核心修复（必开！）
# ==============================================
# 随机延迟 20-120 秒启动，避免机器人行为
if os.getenv("RANDOM_SLEEP", "true").lower() == "true":
    sleep_sec = random.randint(20, 120)
    logger.info(f"[防风控] 随机延迟 {sleep_sec} 秒后启动...")
    time.sleep(sleep_sec)

# 全局强制覆盖 UA 和请求头，伪装成真实电脑浏览器
REAL_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Sec-Ch-Ua": '"Chromium";v="130", "Not=A?Brand";v="99", "Microsoft Edge";v="130"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# 强制给 BilibiliTask 加上真实请求头
original_init = BilibiliTask.__init__
def patched_init(self, cookie):
    original_init(self, cookie)
    self.headers.update(REAL_BROWSER_HEADERS)
    logger.info("[防风控] 已加载真实浏览器请求头 ✅")
BilibiliTask.__init__ = patched_init

class BeijingFormatter:
    """自定义日志格式化器，显示北京时间"""
    @staticmethod
    def format(record):
        dt = datetime.fromtimestamp(record["time"].timestamp(), tz=timezone.utc)
        local_dt = dt + timedelta(hours=8)  # UTC+8
        record["extra"]["local_time"] = local_dt.strftime('%H:%M:%S,%f')[:-3]
        return "{time:YYYY-MM-DD HH:mm:ss,SSS}(CST {extra[local_time]}) - {level} - {message}\n"

# 配置日志输出
logger.remove()
logger.add(sys.stdout, format=BeijingFormatter.format, level="INFO", colorize=True)

def mask_string(s: str):
    """敏感信息脱敏，只显示第一个字符"""
    if not isinstance(s, str) or len(s) == 0:
        return "*"
    return s[0] + "*" * (len(s) - 1)

def execute_coin_task(bili, user_info, config):
    """
    执行投币任务
    核心逻辑：先检查今日已投币数量，避免重复投币
    """
    # 1. 获取今日已投币信息
    try:
        task_info = bili.get_task_info()
        today_coin = task_info.get("today_coin", 0)
        coin_exp = task_info.get("coin_exp", 0)
        logger.info(f"今日已投币: {today_coin}/5 个 (经验值: {coin_exp})")
    except Exception as e:
        logger.error(f"获取投币记录失败: {e}")
        today_coin = 0
        coin_exp = 0
    
    # 2. 如果今日已投满5个币，直接返回
    if today_coin >= 5:
        logger.info("✅ 今日已投满5个币，跳过投币任务")
        return True, f"今日已投满5个币 (经验值: {coin_exp})"
    
    # 3. 获取配置
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
    
    # 4. 计算还需要投多少个币
    remaining_coins = 5 - today_coin
    need_coin = min(want_coin, remaining_coins)
    
    if need_coin <= 0:
        return True, f"今日已投{today_coin}个币，已达上限或目标"
    
    # 5. 获取硬币余额
    try:
        coin_left = bili.get_coin_balance()
    except Exception as e:
        logger.error(f"获取硬币余额失败: {e}")
        coin_left = user_info.get("money", 0)
    
    # 6. 显示状态
    logger.info(f"========================================")
    logger.info(f"💰 硬币余额: {coin_left} 个")
    logger.info(f"📊 今日已投: {today_coin}/5 个")
    logger.info(f"🎯 计划投币: {want_coin} 个 (配置COIN_ADD_NUM)")
    logger.info(f"🔄 实际需投: {need_coin} 个")
    logger.info(f"========================================")
    
    if coin_left < need_coin:
        return False, f"硬币不足 (余额{coin_left}，需要{need_coin})"
    
    # 7. 获取视频列表
    video_list = bili.get_dynamic_videos()
    if not video_list:
        return False, "无可用视频"
    
    # 8. 执行投币
    try:
        select_like = int(config.get('COIN_SELECT_LIKE', 1))
    except:
        select_like = 1
    
    success = 0
    attempted = 0
    max_attempts = min(len(video_list), need_coin * 2)
    
    for bvid in video_list:
        if attempted >= max_attempts:
            break
        if success >= need_coin:
            break
        
        attempted += 1
        
        ok, msg = bili.add_coin(bvid, 1, select_like)
        
        if ok and "成功" in msg:
            success += 1
            today_coin += 1
            logger.info(f"✅ 投币成功 ({success}/{need_coin}) - 视频: {bvid}")
            logger.info(f"   今日累计: {today_coin}/5 个")
        elif "已达上限" in msg:
            logger.info(f"⏹️  {msg}，停止投币")
            break
        elif "已投币" in msg:
            logger.debug(f"⏭️  视频 {bvid} 已投过币，跳过")
            continue
        else:
            logger.warning(f"❌ 投币失败: {msg}")
        
        time.sleep(random.uniform(1.5, 3))  # 防风控：延迟加长
    
    # 9. 返回结果
    if success > 0:
        return True, f"投币完成: 成功{success}/{need_coin}个，今日累计{today_coin}/5个"
    elif success == 0 and attempted > 0:
        return False, f"投币失败: 尝试{attempted}次，成功0次"
    else:
        return True, "无需投币或已投满"

def run_all_tasks_for_account(bili, config):
    """执行单个账号的所有任务"""
    user_info = bili.get_user_info()
    if not user_info:
        return {'登录检查': (False, 'Cookie 失效')}, None
    
    username = user_info.get('uname', '未知用户')
    logger.info(f"账号名称: {mask_string(username)}")
    logger.info(f"用户等级: Lv.{user_info.get('level_info', {}).get('current_level', 0)}")
    
    tasks_result = {}
    video_list = bili.get_dynamic_videos()
    bvid = video_list[0] if video_list else "BV1GJ411x7h7"  # 默认视频ID
    
    # 执行各项任务
    logger.info("--- 开始执行分享任务 ---")
    tasks_result['分享视频'] = bili.share_video(bvid)
    time.sleep(random.uniform(2,4))
    
    logger.info("--- 开始执行直播签到 ---")
    tasks_result['直播签到'] = bili.live_sign()
    time.sleep(random.uniform(2,4))
    
    logger.info("--- 开始执行漫画签到 ---")
    tasks_result['漫画签到'] = bili.manga_sign()
    time.sleep(random.uniform(2,4))
    
    logger.info("--- 开始执行投币任务 ---")
    tasks_result['投币任务'] = execute_coin_task(bili, user_info, config)
    time.sleep(random.uniform(2,4))
    
    logger.info("--- 开始执行观看任务 ---")
    tasks_result['观看视频'] = bili.watch_video(bvid)
    
    return tasks_result, user_info

def format_push_message(all_results):
    """格式化推送消息为Markdown格式"""
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
            coin_balance = user_info.get('money', 0)
            content.append(f"- **硬币余额**: {coin_balance}")

    beijing_time = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    content.append(f"\n> 报告时间: {beijing_time}")
    return "\n".join(content)

def send_to_pushplus(token, title, content):
    """发送推送消息到PushPlus"""
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
    """发送推送消息到Telegram"""
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
    """主函数"""
    # 从环境变量读取配置
    config = {
        "BILIBILI_COOKIE": os.environ.get("BILIBILI_COOKIE"),
        "COIN_ADD_NUM": os.environ.get("COIN_ADD_NUM", 5),
        "COIN_SELECT_LIKE": os.environ.get("COIN_SELECT_LIKE", 0),
        "PUSH_PLUS_TOKEN": os.environ.get("PUSH_PLUS_TOKEN", ""),
        "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN", ""),
        "TG_CHAT_ID": os.environ.get("TG_CHAT_ID", ""),
    }

    if not config["BILIBILI_COOKIE"]:
        logger.error("未配置 BILIBILI_COOKIE")
        sys.exit(1)

    # 支持多账号，用###分隔
    cookies = [c.strip() for c in config["BILIBILI_COOKIE"].split("###") if c.strip()]
    all_results = []
    
    logger.info(f"检测到 {len(cookies)} 个账号")

    # 为每个账号执行任务
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

        # 输出本账号任务结果
        logger.info(f"\n账号{idx} 任务结果:")
        for name, (ok, info) in tasks.items():
            status = "✅ 成功" if ok else "❌ 失败"
            logger.info(f"  {name}: {status} | {info}")
        
        logger.info(f"{'='*40}")
        logger.info(f"账号{idx} 任务完成")
        logger.info(f"{'='*40}\n")
        
        # 账号间延迟
        if idx < len(cookies):
            delay = random.uniform(6, 12)
            logger.info(f"[防风控] 等待 {delay:.1f} 秒后处理下一个账号...")
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
