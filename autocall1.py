import time
import re # 需要在文件顶部导入 re 模块
from wxauto import WeChat
import pyautogui # 引入 GUI 自动化库
import pygetwindow as gw # 用于查找窗口
# 图像识别相关代码已移除，改为基于聊天消息关键字检测通话状态（例如: '对方已拒绝', '通话时长' 等）。

# --- 配置区域 ---
# 设置你想要自动回复的联系人或群聊名称（精确匹配）
TARGET_CONTACTS = ["【禁言】环球青藤兼职群","曹京君","叶丽萍","19986676188"] # <-- 修改这里为你想自动回复的联系人或群聊名称

# 指定要发起通话的联系人
CALL_TARGET_CONTACT = "19986676188"

# 自动回复的内容
AUTO_REPLY_MESSAGE = "[自动回复] 您好，我现在有事不在，稍后回复您。" # <-- 可修改为你想要的回复内容

# 语音通话按钮的屏幕绝对坐标 (单位: 像素)
# 这些坐标是您提供的，假设是在全屏或特定分辨率下的值
VOICE_CALL_ABSOLUTE_X = 483  # 屏幕绝对 X 坐标
VOICE_CALL_ABSOLUTE_Y = 425 # 屏幕绝对 Y 坐标

# 注意：不再使用截图来判断通话状态，改为依赖监听到的聊天消息内的关键字（参见 `auto_reply_callback`）。


# 等待时间 (秒)
TIMEOUT_FIND_WINDOW = 5 # 查找窗口超时时间
TIMEOUT_FIND_CHAT = 5   # 切换到聊天窗口的等待时间
TIMEOUT_CLICK_ACTION = 1 # 点击操作之间的等待时间
TIMEOUT_WAIT_FOR_CALL_STATUS = 15 # 等待通话状态判断的时间 (秒)
TIMEOUT_RETRY_CALL = 30 # 每次重试呼叫之间的间隔时间 (秒)
MAX_CALL_RETRIES = 10   # 最大重试次数，防止无限循环

# --- 全局变量 ---
wx_instance = None
all_chat_objects = {} # 存储所有监听的 Chat 对象 {contact_name: chat_obj}
script_should_stop = False # 全局标志，用于通知脚本停止运行

# 已移除基于截图的通话状态检测函数，改为依赖 `auto_reply_callback` 中的关键字检测。

# --- 辅助函数：激活聊天窗口并发起语音通话 ---
def activate_chat_and_call(target_contact_name):
    """
    使用 wxauto 获取 Chat 对象，然后激活其对应的窗口（即使已最小化），并点击语音通话。
    持续呼叫直到检测到"对方已拒绝"或"通话时长"，否则持续重试（最多 MAX_CALL_RETRIES 次）。
    直接使用已知的屏幕绝对坐标进行点击。
    """
    global wx_instance, all_chat_objects, script_should_stop
    retries = 0
    max_retries = MAX_CALL_RETRIES

    while retries <= max_retries and not script_should_stop:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] (第 {retries + 1} 次尝试) 正在尝试激活与 [{target_contact_name}] 的聊天窗口并发起通话...")

            # --- 关键：禁用 PyAutoGUI 的安全保护 ---
            pyautogui.FAILSAFE = False
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] PyAutoGUI Fail-Safe 已禁用。")

            # 1. 获取目标联系人的 Chat 对象
            chat_obj = all_chat_objects.get(target_contact_name)
            if not chat_obj or script_should_stop:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 未找到 [{target_contact_name}] 的聊天对象或脚本需停止。无法激活。")
                return False

            # 2. 获取 Chat 对象关联的窗口标题 (通常是联系人昵称或部分内容)
            target_window_title = getattr(chat_obj, 'who', '')
            if not target_window_title:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] Chat 对象缺少 'who' 属性，无法确定窗口标题。")
                return False

            # 3. 查找包含该标题的窗口 (应该是独立的聊天窗口)
            found_windows = gw.getWindowsWithTitle(target_window_title)
            if not found_windows:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [警告] 未找到标题为 '{target_window_title}' 的窗口，可能已被最小化或隐藏。尝试通过 pygetwindow 恢复...")
                # 查找所有微信相关的窗口
                all_wechat_windows = gw.getWindowsWithTitle("微信")
                target_window = None
                for win in all_wechat_windows:
                    if target_window_title in win.title:
                         target_window = win
                         break
                if not target_window:
                     print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 仍未能找到包含 '{target_window_title}' 的微信窗口。")
                     return False
            else:
                target_window = found_windows[0] # 假设只有一个匹配的窗口

            # 4. 激活窗口 (如果是最小化状态，这通常会将其恢复并置于前台)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 找到聊天窗口: '{target_window.title}'. 尝试激活...")
            try:
                target_window.restore() # 尝试恢复窗口 (如果最小化)
            except AttributeError:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [警告] pygetwindow 窗口对象无 restore 方法或无效，尝试 activate ...")
                pass # 继续尝试 activate

            target_window.activate() # 激活窗口
            time.sleep(TIMEOUT_CLICK_ACTION) # 给窗口时间响应

            # 5. 确认窗口已激活（可选，通过检查是否是前台窗口）
            active_window = gw.getActiveWindow()
            if active_window and target_window_title in active_window.title:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 窗口 '{target_window.title}' 已成功激活。")
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [警告] 窗口 '{target_window.title}' 可能未完全激活或被其他窗口遮挡。")

            # 6. 移动鼠标到安全位置 (屏幕中心)，减少误触角落的风险
            screen_width, screen_height = pyautogui.size()
            safe_x = screen_width // 2
            safe_y = screen_height // 2
            pyautogui.moveTo(safe_x, safe_y, duration=0.2)
            time.sleep(0.1)

            # 7. 直接点击已知的语音通话按钮绝对坐标
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 将点击屏幕绝对坐标: ({VOICE_CALL_ABSOLUTE_X}, {VOICE_CALL_ABSOLUTE_Y})")
            pyautogui.moveTo(VOICE_CALL_ABSOLUTE_X, VOICE_CALL_ABSOLUTE_Y, duration=0.5) # 缓慢移动到目标，方便观察
            time.sleep(0.2) # 短暂停顿

            pyautogui.click(VOICE_CALL_ABSOLUTE_X, VOICE_CALL_ABSOLUTE_Y)
            time.sleep(TIMEOUT_CLICK_ACTION) # 等待点击生效，可能弹出确认框或开始通话

            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已尝试点击语音通话按钮。等待通话状态判断...")

            # 8. 等待一段时间，让微信通过聊天消息传递通话状态关键字，并在等待期间轮询 "script_should_stop" 标志
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 等待 {TIMEOUT_WAIT_FOR_CALL_STATUS} 秒以便接收通话状态的关键字消息...")
            for _ in range(TIMEOUT_WAIT_FOR_CALL_STATUS):
                if script_should_stop:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 在等待期间检测到终止标志，停止呼叫流程。")
                    return False
                time.sleep(1)

            # 9. 如果在等待期间没有收到任何通话状态关键字，视为对方无应答或状态不明，按重试逻辑处理

            # --- 状态判断逻辑 (严格按照您的要求) ---
            # (已改为关键字检测) "对方已拒绝" 的处理在回调里完成。
            # (已改为关键字检测) 通话结束/时长的处理在回调里完成。
            # 3. 检查是否对方无应答 (中等优先级 - 重试)
            # 注释掉原来引用未定义变量的部分，因为现在使用消息回调来处理状态
            # if cancel_call_pos: # 检测到"取消呼叫" -> 对方无应答
            #     print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 检测到 '取消呼叫' 按钮，对方无应答或忙线。")
            #     if retries < max_retries and not script_should_stop: # 如果还有重试次数且未收到停止指令
            #         print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 将在 {TIMEOUT_RETRY_CALL} 秒后重试呼叫...")
            #         time.sleep(TIMEOUT_RETRY_CALL)
            #         retries += 1
            #         continue # 结束本次循环，继续下一次重试
            #     else:
            #         # 达到最大重试次数
            #         if script_should_stop:
            #             print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 脚本收到停止指令，停止重试。")
            #         else:
            #             print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已达到最大重试次数 ({max_retries})，停止呼叫。")
            #         return False # 从当前函数返回

            # 4. 检查挂断按钮 (通话中) - 视为"其他"情况，需要重试
            # if hang_up_pos:
            #      print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 检测到 '挂断' 按钮，可能通话已接通或状态异常。")
            #      print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 这属于"其他"情况，将继续重试呼叫。")
            #      if retries < max_retries and not script_should_stop: # 如果还有重试次数且未收到停止指令
            #          print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 将在 {TIMEOUT_RETRY_CALL} 秒后重试呼叫...")
            #          time.sleep(TIMEOUT_RETRY_CALL)
            #          retries += 1
            #          continue # 结束本次循环，继续下一次重试
            #      else:
            #          # 达到最大重试次数
            #          if script_should_stop:
            #              print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 脚本收到停止指令，停止重试。")
            #          else:
            #              print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已达到最大重试次数 ({max_retries})，停止呼叫。")
            #          return False # 从当前函数返回

            # 5. 未检测到通话状态关键字，按重试逻辑处理
            if retries < max_retries and not script_should_stop:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 将在 {TIMEOUT_RETRY_CALL} 秒后重试呼叫...")
                time.sleep(TIMEOUT_RETRY_CALL)
                retries += 1
                continue
            else:
                if script_should_stop:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 脚本收到停止指令，停止重试。")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已达到最大重试次数 ({max_retries})，停止呼叫。")
                return False



        except KeyboardInterrupt:
             print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 收到键盘中断信号。")
             script_should_stop = True
             return False
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话错误] 第 {retries + 1} 次尝试时发生异常: {e}")
            import traceback
            traceback.print_exc()
            # 发生异常也属于"其他"情况，应尝试重试
            if retries < max_retries and not script_should_stop:
                 print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 将在 {TIMEOUT_RETRY_CALL} 秒后重试...")
                 time.sleep(TIMEOUT_RETRY_CALL)
                 retries += 1
                 continue
            else:
                 if script_should_stop:
                     print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 脚本收到停止指令，停止重试。")
                 else:
                      print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已达到最大重试次数 ({max_retries}) 或发生错误，停止呼叫。")
                 return False
        finally:
            # --- 在每次循环结束前，重新启用 Fail-Safe ---
            pyautogui.FAILSAFE = True
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] PyAutoGUI Fail-Safe 已重新启用。")

    # 如果循环结束仍未触发任何终止条件（即达到最大重试次数）
    if script_should_stop:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 脚本收到停止指令，结束呼叫流程。")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 已达到最大重试次数 ({max_retries})，且未检测到终止条件，结束呼叫流程。")
    return False # 不管怎样，到这里也意味着流程结束


# --- 回调函数定义 ---
def auto_reply_callback(message, chat_obj):
    """
    当监听的聊天对象有新消息时，此函数会被自动调用。
    功能：如果消息中包含 '直接扣***对接'，则向**所有**监听的聊天对象回复提取到的 ***。
    并且，在发送完广播消息后，自动激活与指定联系人的聊天窗口并发起语音通话。

    另外：也在这里检测通话状态类的消息（例如"对方已拒绝"、"通话时长"等），
    一旦检测到则设置停止标志并主动调用 StopListening()，以便让主循环退出。
    """
    global all_chat_objects, wx_instance, script_should_stop # 访问全局变量

    try:
        # 获取消息内容和发送者
        msg_content = getattr(message, 'content', '').strip() # 去除首尾空白
        sender = getattr(message, 'sender', '[未知发送者]')
        msg_type = getattr(message, 'type', '[未知类型]')
        chat_who = getattr(chat_obj, 'who', '[未知聊天对象]')

        # --- 日志记录 ---
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 收到{msg_type}消息 来自 {sender}: {msg_content}")

        # --- 新增：检测通话状态类系统消息，优先处理，发现则停止脚本 ---
        status_keywords = ['对方已拒绝', '已拒绝', '通话时长', '通话已结束', '通话结束', '挂断']
        for kw in status_keywords:
            if kw in msg_content:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [监听] 检测到通话状态关键字 '{kw}'，准备停止监听并退出。")
                script_should_stop = True
                try:
                    if wx_instance:
                        wx_instance.StopListening(remove=True)
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [监听] 已调用 StopListening() 停止监听。")
                except Exception as _e:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [警告] 调用 StopListening 失败: {_e}")
                return

        # --- 核心逻辑：匹配包含"直接扣"后跟4位数字的消息 ---
        # 使用正则表达式匹配包含 "直接扣" + 可选空格 + 4位数字的模式
        # .* : 匹配任意字符（包括空字符），允许"直接扣"前面有其他内容
        # 直接扣 : 精确匹配汉字"直接扣"
        # \s* : 匹配零个或多个空白字符（空格、制表符等）
        # (\d{4}) : 捕获组，匹配恰好4个数字字符
        # 
        # 匹配示例：
        # ✅ "直接扣6688" - 无空格，直接开始
        # ✅ "直接扣 6688" - 有空格
        # ✅ "abc直接扣6688" - 前面有其他字符
        # ✅ "插播一则兼职信息~具体需求：直接扣 6688 对接" - 中间有其他文字
        # ✅ "【PPT兼职发布】直接扣6688" - 前面有标点和其他文字
        # ❌ "直接6688" - 缺少"扣"字
        # ❌ "直接扣668" - 不足4位数字
        # ❌ "直接扣66888" - 超过4位数字
        
        match = re.search(r'.*直接扣\s*(\d{4})', msg_content)
        
        if match:
            # 提取捕获组中的4位数字
            extracted_code = match.group(1).strip()
            
            # 验证是否为有效的4位数字
            if extracted_code.isdigit() and len(extracted_code) == 4:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 匹配成功，提取到4位代码: '{extracted_code}'")

                # --- 向所有监听对象广播回复逻辑 ---
                reply_message = extracted_code  # 回复内容必须为相同的4位数字
                for target_contact_name in all_chat_objects.keys(): # 遍历所有监听对象的名称
                    try:
                        # 使用微信实例向指定聊天对象发送消息
                        wx_instance.SendMsg(msg=reply_message, who=target_contact_name)
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [广播回复] 已发送至 [{target_contact_name}]: {reply_message}")
                    except Exception as send_e:
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [错误] 向 [{target_contact_name}] 发送消息失败: {send_e}")

                # --- 广播完成后，自动激活窗口并发起语音通话 ---
                success = activate_chat_and_call(CALL_TARGET_CONTACT)
                if success:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 激活及通话流程结束。")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [自动通话] 激活及通话流程失败。")

            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 提取内容不符合4位数字要求: '{extracted_code}'")
        else:
            # 可选：打印未匹配的消息，方便调试
            # print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{chat_who}] 消息未匹配指定模式，不回复。")
            pass # 不做任何事情

    except Exception as cb_e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [回调错误] 处理消息时发生异常: {cb_e}")
        import traceback
        traceback.print_exc()


# --- 初始化 ---
print("正在启动 wxauto...")
try:
    # 创建微信实例
    wx_instance = WeChat()
    print("微信实例创建成功。")
    print(f"当前登录用户: {wx_instance.nickname}")

    # --- 为每个目标聊天对象添加监听，并存储 Chat 对象 ---
    successfully_listened = []
    for contact_name in TARGET_CONTACTS:
        try:
            # AddListenChat 会为该聊天创建一个独立窗口并设置回调
            result = wx_instance.AddListenChat(nickname=contact_name, callback=auto_reply_callback)
            # AddListenChat 返回 Chat 对象表示成功，或 WxResponse 对象表示失败
            if hasattr(result, 'who'): # 假设成功的返回有 who 属性
                 print(f"已成功添加对聊天对象 '{contact_name}' 的监听。")
                 successfully_listened.append(contact_name)
                 # 将创建的 Chat 对象存入全局字典
                 all_chat_objects[contact_name] = result
            else: # 假设失败的返回是 WxResponse
                 print(f"警告：未能添加对聊天对象 '{contact_name}' 的监听: {result.msg if hasattr(result, 'msg') else result}")
        except Exception as add_e:
            print(f"添加监听 '{contact_name}' 时发生异常: {add_e}")

    if not successfully_listened:
        print("没有成功添加任何监听。程序退出。")
        exit(1)
    else:
         print(f"已成功监听以下聊天对象: {successfully_listened}")
         print(f"将对其中任一对象的消息进行广播回复，并在之后自动激活与 [{CALL_TARGET_CONTACT}] 的聊天窗口并发起语音通话。")
         print("注意：自动通话依赖于 pyautogui, pygetwindow 和 opencv-python。")
         print("注意：请确保 'cancel_call_button.png', 'hang_up_button.png', 'reject_notice.png', 'end_call_notice.png' 文件路径正确，并且截图清晰。")
         print("注意：首次运行时，请将鼠标保持在屏幕中央区域，避免触发 Fail-Safe。")

    print("微信已连接并开始监听消息。按 Ctrl+C 停止。")

except Exception as e:
    print(f"初始化微信失败: {e}")
    import traceback
    traceback.print_exc()
    print("请确保：")
    print("1. 已安装 PC 版微信并登录。")
    print("2. 微信窗口未被最小化到系统托盘（可以是最小化状态，但不要退出）。")
    print("3. Python 脚本以管理员权限运行。")
    print("4. wxauto, pyautogui, pygetwindow, opencv-python, Pillow 库均已正确安装 (`pip install wxauto pyautogui pygetwindow opencv-python Pillow`)。")
    exit(1)


# --- 主循环 (监听模式的核心) ---
# KeepRunning 会阻塞在此处，直到收到 KeyboardInterrupt (Ctrl+C)
try:
    # 在这里捕获中断信号并处理
    wx_instance.KeepRunning()
except KeyboardInterrupt:
    print("\n收到中断信号，正在停止监听...")
    script_should_stop = True
except Exception as e:
    print(f"\n运行过程中出现异常: {e}")
    import traceback
    traceback.print_exc()
finally:
    # 停止监听并清理资源
    try:
        wx_instance.StopListening(remove=True) # remove=True 会关闭监听的独立窗口
    except Exception as e:
        print(f"停止监听时出现错误: {e}")
    print("监听已停止，程序退出。")
    # 确保在程序退出时也重新启用 Fail-Safe
    pyautogui.FAILSAFE = True
    print("PyAutoGUI Fail-Safe 已在退出时重新启用。")