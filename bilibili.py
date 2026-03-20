def execute_coin_task(bili, user_info, config):
    """
    简化的投币逻辑：尝试投出指定数量的硬币，由B站服务端验证上限
    """
    # 获取配置
    try:
        want_coin = int(config.get('COIN_ADD_NUM', 5))
        if want_coin < 0:
            want_coin = 0
        elif want_coin > 5:
            want_coin = 5
    except:
        want_coin = 5
    
    if want_coin == 0:
        return True, "已设置不投币"
    
    # 获取硬币余额
    coin_left = bili.get_coin_balance()
    if coin_left < want_coin:
        return False, f"硬币不足（余额{coin_left}，需要{want_coin}）"
    
    # 获取视频并投币
    video_list = bili.get_dynamic_videos()
    if not video_list:
        return False, "无可用视频"
    
    success = 0
    for bvid in video_list:
        if success >= want_coin:
            break
        
        ok, msg = bili.add_coin(bvid, 1, 1)
        if ok:
            success += 1
            logger.info(f"投币成功 ({success}/{want_coin}): {msg}")
        elif "已达上限" in msg:
            logger.info(f"今日投币已达上限，停止投币")
            break
        else:
            logger.warning(f"投币失败: {msg}")
        
        time.sleep(random.uniform(1, 2))  # 随机延迟
    
    return True, f"投币完成: 成功{success}/{want_coin}个"
