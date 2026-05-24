"""
自动回复和通话脚本 - 适配微信 4.1.9.30

功能：
1. 开启脚本后，监听指定好友/群的新消息
2. 如果收到包含特定关键字的消息，自动回复指定内容
3. 回复后自动发起语音通话

使用方法：
- 修改 TARGET_CONTACTS 设置要监听的对象
- 修改 CALL_TARGET_CONTACT 设置要发起语音通话的对象
- 修改 KEYWORD 和 REPLY_MESSAGE 设置关键字和回复内容
"""

import time
import re
import sys
import os

# 确保从父目录导入 wxauto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wxauto.wxauto import WeChat, ChatWnd
import pyautogui
import pygetwindow as gw

# --- 配置区域 ---
# 设置要监听的对象（可以是好友或群）
TARGET_CONTACTS = ["纯棉的"]

# 设置要发起语音通话的对象
CALL_TARGET_CONTACT = "纯棉的"

# 监听关键字（匹配"直接扣"后跟4位数字）
KEYWORD_PATTERN = r'直接扣\s*(\d{4})'

# 触发关键字后的回复内容
REPLY_MESSAGE = ""  # 将被动态替换为提取的验证码

# 语音通话按钮的屏幕坐标（需要根据实际调整）
VOICE_CALL_X = 483
VOICE_CALL_Y = 425

# 超时设置
TIMEOUT_WAIT_FOR_CALL_STATUS = 15
MAX_CALL_RETRIES = 10
TIMEOUT_RETRY_CALL = 30

# --- 全局变量 ---
wx_instance = None
all_chat_objects = {}
script_should_stop = False


def activate_chat_and_call(target_contact_name):
    """
    激活与目标联系人的聊天窗口并发起语音通话
    """
    global wx_instance, all_chat_objects, script_should_stop
    retries = 0

    while retries <= MAX_CALL_RETRIES and not script_should_stop:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 第 {retries + 1} 次尝试...")

            # 获取目标聊天对象
            chat_obj = all_chat_objects.get(target_contact_name)
            if not chat_obj:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 未找到 {target_contact_name} 的聊天对象")
                return False

            # 使用 WeChat 切换到目标聊天
            wx_instance.ChatWith(target_contact_name)
            time.sleep(2)

            # 点击微信 tab 确保在聊天界面
            wx = wx_instance._get_fresh_window()
            wechat_tab = wx.ButtonControl(Name='微信', searchDepth=10)
            if wechat_tab.Exists(0.5):
                wechat_tab.Click(simulateMove=False)
                time.sleep(0.5)

            # 获取并点击语音通话按钮
            call_btn = wx.ButtonControl(Name='语音通话', searchDepth=10)
            if call_btn.Exists(maxSearchSeconds=2):
                call_btn.Click(simulateMove=False)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 已点击语音通话按钮")
                time.sleep(1)
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 未找到语音通话按钮")

            # 等待通话状态
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 等待 {TIMEOUT_WAIT_FOR_CALL_STATUS} 秒...")
            for _ in range(TIMEOUT_WAIT_FOR_CALL_STATUS):
                if script_should_stop:
                    return False
                time.sleep(1)

            # 重试逻辑
            if retries < MAX_CALL_RETRIES:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] {TIMEOUT_RETRY_CALL} 秒后重试...")
                time.sleep(TIMEOUT_RETRY_CALL)
                retries += 1
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 达到最大重试次数")
                return False

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话错误] {e}")
            import traceback
            traceback.print_exc()
            if retries < MAX_CALL_RETRIES:
                time.sleep(TIMEOUT_RETRY_CALL)
                retries += 1
            else:
                return False

    return False


def auto_reply_callback(message, chat_obj):
    """
    监听回调函数
    - 检测关键字
    - 自动回复
    - 发起语音通话
    """
    global all_chat_objects, wx_instance, script_should_stop

    try:
        msg_content = getattr(message, 'content', '').strip()
        sender = getattr(message, 'sender', '[未知发送者]')
        msg_type = getattr(message, 'type', '[未知类型]')
        chat_who = getattr(chat_obj, 'who', '[未知聊天对象]')

        # 跳过时间消息
        if msg_type == 'time':
            return

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 收到消息: {msg_content[:50]}...")

        # 检测通话状态关键字
        status_keywords = ['对方已拒绝', '已拒绝', '通话时长', '通话已结束', '通话结束', '挂断']
        for kw in status_keywords:
            if kw in msg_content:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [监听] 检测到通话状态: {kw}")
                script_should_stop = True
                return

        # 匹配关键字模式
        match = re.search(KEYWORD_PATTERN, msg_content)
        if match:
            extracted_code = match.group(1).strip()

            if extracted_code.isdigit() and len(extracted_code) == 4:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [匹配] 提取验证码: {extracted_code}")

                # 回复指定内容
                try:
                    wx_instance.SendMsg(msg=extracted_code, who=chat_who)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [回复] 已发送至 {chat_who}: {extracted_code}")
                except Exception as e:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送失败: {e}")

                # 发起语音通话
                activate_chat_and_call(CALL_TARGET_CONTACT)

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [回调错误] {e}")
        import traceback
        traceback.print_exc()


# --- 主程序 ---
print("=" * 60)
print("微信自动回复和通话脚本 v2.0")
print("适配微信 4.1.9.30")
print("=" * 60)

print("\n正在启动 wxauto...")
try:
    wx_instance = WeChat()
    print("[OK] 微信实例创建成功")
    print(f"[OK] 当前登录用户: {wx_instance.nickname}")

    # 添加监听
    successfully_listened = []
    for contact_name in TARGET_CONTACTS:
        try:
            chat_obj = wx_instance.AddListenChat(nickname=contact_name, callback=auto_reply_callback)
            if chat_obj and isinstance(chat_obj, ChatWnd):
                print(f"[OK] 已成功添加对 '{contact_name}' 的监听")
                successfully_listened.append(contact_name)
                all_chat_objects[contact_name] = chat_obj
            else:
                print(f"[FAIL] 未能添加对 '{contact_name}' 的监听")
        except Exception as e:
            print(f"[FAIL] 添加监听 '{contact_name}' 失败: {e}")

    if not successfully_listened:
        print("\n没有成功添加任何监听，程序退出。")
        exit(1)

    print(f"\n[OK] 已监听以下对象: {successfully_listened}")
    print(f"[OK] 通话目标: {CALL_TARGET_CONTACT}")
    print(f"[OK] 关键字模式: {KEYWORD_PATTERN}")
    print("\n" + "=" * 60)
    print("微信已连接并开始监听消息。按 Ctrl+C 停止。")
    print("=" * 60)

    # 保持运行
    wx_instance.KeepRunning()

except KeyboardInterrupt:
    print("\n收到中断信号，正在停止...")
    script_should_stop = True
except Exception as e:
    print(f"\n初始化失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    if wx_instance:
        wx_instance.StopListening(remove=True)
    print("监听已停止，程序退出。")