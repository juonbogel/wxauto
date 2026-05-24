"""
测试脚本：监听"纯棉的"的消息，收到指定内容后自动回复并语音呼叫

触发条件：
- 消息包含"数据分析兼职发布"
- 消息包含"直接扣"+4位数字

触发动作：
- 发送提取的4位数字
- 发起语音呼叫
- 成功后立即返回监听模式
- 30秒无应答则重新呼叫
"""

import sys
import os
import time
import re

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uiautomation as uia
from wxauto.wxauto import WeChat

# 全局变量
wx_instance = None
call_in_progress = False  # 通话是否进行中
last_call_time = 0  # 上次呼叫时间
pending_call = False  # 是否有待处理的呼叫


def make_voice_call():
    """发起语音呼叫，返回是否成功"""
    global call_in_progress, last_call_time

    try:
        chat_wnd = uia.WindowControl(ClassName='mmui::ChatSingleWindow', searchDepth=1)
        if not chat_wnd.Exists(maxSearchSeconds=1):
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 未找到聊天窗口")
            return False

        # 激活窗口
        chat_wnd.SwitchToThisWindow()
        time.sleep(0.3)

        # 第一次点击 语音通话 按钮
        call_btn = chat_wnd.ButtonControl(Name='语音通话', searchDepth=15)
        if call_btn.Exists(maxSearchSeconds=2):
            call_btn.Click(simulateMove=False)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 已点击语音通话按钮")
            time.sleep(0.5)

            # 第二次点击菜单中的 语音通话（MenuItemControl）
            menu_item = chat_wnd.MenuItemControl(Name='语音通话', searchDepth=10)
            if menu_item.Exists(maxSearchSeconds=2):
                menu_item.Click(simulateMove=False)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 已点击语音通话菜单项")
                call_in_progress = True
                last_call_time = time.time()
                return True
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 未找到语音通话菜单项")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 未找到语音通话按钮")
        return False
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 错误: {e}")
        return False


def on_message(msg, chat_obj):
    """消息回调函数"""
    global call_in_progress, pending_call, wx_instance

    msg_content = getattr(msg, 'content', '').strip()
    msg_type = getattr(msg, 'type', 'text')
    chat_who = getattr(chat_obj, 'who', '')

    # 跳过时间消息
    if msg_type == 'time':
        return

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 收到消息: {msg_content[:50]}...")

    # 检测通话状态关键字
    if any(kw in msg_content for kw in ['对方已拒绝', '已拒绝', '通话时长', '通话已结束', '通话结束', '挂断']):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 检测到通话状态: {msg_content}")
        if call_in_progress:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [通话] 通话结束，重置状态")
            call_in_progress = False
            # 如果有待处理的呼叫，重新发起
            if pending_call:
                pending_call = False
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 重新发起呼叫...")
                make_voice_call()
        return

    # 检测触发条件：包含"数据分析兼职发布"且包含"直接扣"+4位数字
    if '数据分析兼职发布' in msg_content:
        match = re.search(r'直接扣\s*(\d{4})', msg_content)
        if match:
            extracted_code = match.group(1).strip()

            if extracted_code.isdigit() and len(extracted_code) == 4:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [匹配] 提取验证码: {extracted_code}")

                # 发送消息
                try:
                    wx_instance.SendMsg(msg=extracted_code, who=chat_who)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [发送] 已发送至 {chat_who}: {extracted_code}")

                    # 发起语音呼叫（不阻塞）
                    time.sleep(1)
                    success = make_voice_call()
                    if not success:
                        # 呼叫失败，标记为待处理
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [语音] 呼叫失败，标记为待处理")
                        pending_call = True

                except Exception as e:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 发送失败: {e}")


# 全局变量
wx_instance = None


def main():
    global wx_instance

    print("=" * 60)
    print("微信消息监听测试脚本")
    print("=" * 60)

    try:
        # 初始化微信
        wx_instance = WeChat()
        print(f"[OK] 微信初始化成功")
        print(f"[OK] 当前用户: {wx_instance.nickname}")

        # 添加监听
        print(f"\n[INFO] 正在添加对 '纯棉的' 的监听...")
        chat_obj = wx_instance.AddListenChat('纯棉的', callback=on_message)

        if chat_obj:
            print(f"[OK] 已添加监听")
            print(f"[OK] 监听条件: 包含'数据分析兼职发布' + '直接扣'+4位数字")
            print(f"[OK] 触发动作: 发送提取的4位数字")
        else:
            print(f"[FAIL] 添加监听失败")
            return

        print("\n" + "=" * 60)
        print("开始监听 '纯棉的' 的消息")
        print("收到匹配消息后将自动发送回复...")
        print("按 Ctrl+C 停止")
        print("=" * 60)

        # 开始监听
        wx_instance.KeepRunning()

    except KeyboardInterrupt:
        print("\n[INFO] 收到停止信号，正在退出...")
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()