"""
New wxauto - 适配微信 4.1.9.30
基于 UI Automation 技术实现微信自动化

窗口类名变化:
- 微信主窗口: mmui::MainWindow (原 WeChatMainWndForPC)
- 聊天列表: mmui::ChatMasterView
- 聊天详情: mmui::ChatDetailView
- 会话列表: mmui::XTableView (Name="会话")
- 消息列表: mmui::RecyclerListView (Name="消息")
- 输入框: mmui::ChatInputField
"""

import sys
import os
import time
import re
import logging
import threading
from collections import defaultdict

try:
    import uiautomation as uia
except ImportError:
    print("错误: 需要 uiautomation 模块")
    print("安装命令: pip install uiautomation")
    sys.exit(1)

from .utils import *

# 设置日志
wxlog = logging.getLogger('wxauto')
wxlog.setLevel(logging.INFO)


class Message:
    """消息对象"""
    def __init__(self, msg_dict, chat_who):
        self.content = msg_dict.get('content', '')
        self.type = msg_dict.get('type', 'text')
        self.sender = msg_dict.get('sender', chat_who)
        self.id = msg_dict.get('id', '')
        self._raw = msg_dict.get('raw')

    def __repr__(self):
        return f"<Message: {self.type} from {self.sender}>"


class ChatWnd:
    """微信聊天窗口对象"""

    def __init__(self, who, wx_instance, callback=None):
        """
        初始化聊天窗口对象

        Args:
            who: 聊天对象名称
            wx_instance: WeChat 实例引用
            callback: 消息回调函数
        """
        self.who = who
        self._wx = wx_instance
        self.callback = callback
        self.usedmsgid = []  # 已处理的消息ID列表

    def GetNewMessage(self):
        """获取新消息（返回Message对象列表）"""
        msgs = self._wx.GetAllMessage(target_who=self.who)
        new_msgs = []
        for msg in msgs:
            msg_id = msg.get('id', '')
            if msg_id and msg_id not in self.usedmsgid:
                # 转换为 Message 对象
                msg_obj = Message(msg, self.who)
                new_msgs.append(msg_obj)
                self.usedmsgid.append(msg_id)
        return new_msgs

    def SendMsg(self, msg):
        """发送消息"""
        self._wx.SendMsg(msg, who=self.who)

    def __repr__(self):
        return f"<ChatWnd: {self.who}>"


class WeChat:
    """微信自动化主类"""

    VERSION = '4.1.9.30'

    def __init__(self, language='cn', debug=False):
        """
        初始化微信自动化实例

        Args:
            language: 语言，目前固定为 'cn'
            debug: 是否开启调试模式
        """
        set_debug(debug)
        self.language = language

        # 微信主窗口
        self.UiaAPI = uia.WindowControl(ClassName='mmui::MainWindow', searchDepth=1)
        if not self.UiaAPI.Exists(maxSearchSeconds=5):
            raise RuntimeError("未找到微信窗口，请确保微信已启动并登录")

        # 当前聊天对象
        self.current_chat = None

        # 监听相关
        self._listeners = {}  # {who: ChatWnd}
        self._listener_callbacks = {}  # {who: callback}
        self._should_stop_listening = False

        # 获取昵称
        self._nickname = self._get_nickname()

    def _get_nickname(self):
        """获取当前登录用户的昵称"""
        try:
            # 从输入框获取昵称（输入框名称格式: "聊天名 按住 Ctrl..."）
            wx = self._get_fresh_window()
            input_box = wx.EditControl(ClassName='mmui::ChatInputField', searchDepth=20)
            if input_box.Exists(maxSearchSeconds=2):
                name = input_box.Name
                if ' 按住' in name:
                    return name.split(' 按住')[0]
        except:
            pass
        return "微信用户"

    @property
    def nickname(self):
        """获取当前登录用户的昵称"""
        return self._nickname

    def _show_window(self):
        """将微信窗口置前并确保在聊天界面"""
        self.UiaAPI.SwitchToThisWindow()
        time.sleep(0.05)
        try:
            wechat_tab = self.UiaAPI.ButtonControl(Name='微信', searchDepth=10)
            if wechat_tab.Exists(0.5):
                wechat_tab.Click(simulateMove=False)
                time.sleep(0.3)
        except:
            pass

    def _get_fresh_window(self):
        """获取新的窗口引用，避免引用过期问题"""
        return uia.WindowControl(ClassName='mmui::MainWindow', searchDepth=1)

    def _switch_to_chat_tab(self, wx):
        """切换到聊天 tab（带窗口恢复）"""
        try:
            # 确保微信窗口在前景
            wx.SwitchToThisWindow()
            time.sleep(0.2)

            wechat_tab = wx.ButtonControl(Name='微信', searchDepth=10)
            if wechat_tab.Exists(0.3):
                wechat_tab.Click(simulateMove=False)
                time.sleep(0.3)
            return True
        except:
            return False

    def _ensure_target_chat(self, target_who):
        """确保当前在目标聊天窗口（快速切换验证，不阻塞）"""
        try:
            chat_wnd = uia.WindowControl(ClassName='mmui::ChatSingleWindow', searchDepth=1)
            if not chat_wnd.Exists(0.3):
                return False

            title = chat_wnd.GroupControl(ClassName='mmui::ChatTitleBarChatSingleView', searchDepth=10)
            if title.Exists(0.2):
                name_ctrl = title.TextControl(foundIndex=1)
                if name_ctrl.Exists(0.2):
                    current_who = name_ctrl.Name
                    if target_who in current_who:
                        return True  # 已在目标聊天
            return False
        except:
            return False

    def GetSessionList(self):
        """获取会话列表（静默模式）"""
        try:
            self._show_window()

            sessions = []
            session_items = self.UiaAPI.ListItemControl(ClassName='mmui::ChatSessionCell', searchDepth=15)

            if session_items.Exists(maxSearchSeconds=1):
                for idx in range(1, 100):
                    try:
                        item = self.UiaAPI.ListItemControl(ClassName='mmui::ChatSessionCell', foundIndex=idx, searchDepth=15)
                        if item.Exists(0.1):
                            sessions.append(item)
                        else:
                            break
                    except:
                        break

            return sessions
        except:
            return []

    def GetSessionName(self, session_item):
        """从会话项中提取会话名称"""
        name = session_item.Name
        lines = name.split('\n')
        if lines:
            return lines[0]
        return name

    def ChatWith(self, who):
        """打开指定聊天会话（静默模式）"""
        try:
            self._show_window()

            sessions = self.GetSessionList()
            target_session = None

            for session in sessions:
                name = self.GetSessionName(session)
                if name == who:
                    target_session = session
                    break

            if not target_session:
                for session in sessions:
                    name = self.GetSessionName(session)
                    if who in name:
                        target_session = session
                        break

            if target_session:
                target_session.Click(simulateMove=False)
                self.current_chat = self.GetSessionName(target_session)
                time.sleep(2)
                return self.current_chat
        except:
            pass
        return None

    def CurrentChat(self):
        """获取当前聊天窗口名称"""
        try:
            wx = self._get_fresh_window()
            input_box = wx.EditControl(ClassName='mmui::ChatInputField', searchDepth=20)
            if input_box.Exists(maxSearchSeconds=1):
                input_name = input_box.Name
                if ' 按住' in input_name:
                    return input_name.split(' 按住')[0]
        except:
            pass
        return self.current_chat

    def SendMsg(self, msg, who=None):
        """发送文本消息（激活指定窗口）"""
        try:
            # 每次获取新的聊天窗口引用并激活
            chat_wnd = uia.WindowControl(ClassName='mmui::ChatSingleWindow', searchDepth=1)
            if not chat_wnd.Exists(maxSearchSeconds=1):
                return

            # 激活窗口
            chat_wnd.SwitchToThisWindow()
            time.sleep(0.3)

            # 找到输入框并发送消息
            input_box = chat_wnd.EditControl(ClassName='mmui::ChatInputField', searchDepth=20)
            if input_box.Exists(maxSearchSeconds=1):
                send_button = chat_wnd.ButtonControl(ClassName='mmui::XOutlineButton', searchDepth=20)
                if send_button.Exists(maxSearchSeconds=1):
                    input_box.Click(simulateMove=False)
                    time.sleep(0.1)
                    input_box.SendKeys('{Ctrl}a', waitTime=0.1)
                    SetClipboardText(msg)
                    input_box.SendKeys('{Ctrl}v', waitTime=0.3)
                    send_button.Click(simulateMove=False)
                    return
        except:
            pass

        return

    def GetAllMessage(self, target_who=None):
        """获取当前聊天窗口的所有消息"""
        try:
            chat_wnd = None

            if target_who:
                # 精确查找指定聊天窗口（遍历所有ChatSingleWindow）
                for idx in range(1, 20):
                    try:
                        wnd = uia.WindowControl(ClassName='mmui::ChatSingleWindow', foundIndex=idx, searchDepth=1)
                        if not wnd.Exists(0.1):
                            break

                        title = wnd.GroupControl(ClassName='mmui::ChatTitleBarChatSingleView', searchDepth=10)
                        if title.Exists(0.1):
                            name_ctrl = title.TextControl(foundIndex=1)
                            if name_ctrl.Exists(0.1):
                                current_who = name_ctrl.Name
                                if target_who in current_who:
                                    chat_wnd = wnd
                                    break
                    except:
                        break
            else:
                chat_wnd = uia.WindowControl(ClassName='mmui::ChatSingleWindow', searchDepth=1)

            if not chat_wnd or not chat_wnd.Exists(0.3):
                return []

            msg_list = chat_wnd.ListControl(ClassName='mmui::RecyclerListView', searchDepth=20)

            if not msg_list.Exists(maxSearchSeconds=1):
                return []

            msg_items = msg_list.GetChildren()
            if not msg_items:
                return []

            messages = []
            for item in msg_items:
                if item.ControlTypeName == 'ListItemControl':
                    msg_info = self._parse_message_item(item)
                    if msg_info:
                        messages.append(msg_info)

            return messages
        except:
            return []

    def _parse_message_item(self, item):
        """解析消息项"""
        try:
            text = item.Name

            if re.match(r'\d+月\d+日 \d+:\d+', text):
                return {
                    'type': 'time',
                    'content': text,
                    'id': ''.join([str(i) for i in item.GetRuntimeId()]),
                    'raw': item
                }

            return {
                'type': 'text',
                'content': text,
                'id': ''.join([str(i) for i in item.GetRuntimeId()]),
                'raw': item
            }

        except Exception as e:
            wxlog.debug(f"解析消息项失败: {e}")
            return None

    def GetNewMessage(self):
        """获取新消息（自上次调用以来的新消息）"""
        all_msgs = self._wx.GetAllMessage(target_who=self.who)
        return all_msgs

    def AddListenChat(self, nickname, callback=None):
        """
        添加监听聊天对象（不切换窗口）

        Args:
            nickname: 聊天对象名称
            callback: 消息回调函数

        Returns:
            ChatWnd: 聊天窗口对象，失败返回 None
        """
        try:
            if nickname in self._listeners:
                return self._listeners[nickname]

            # 不调用 ChatWith，直接创建 ChatWnd
            chat_obj = ChatWnd(nickname, self, callback)

            # 初始化已处理消息ID（使用正确的target_who）
            current_msgs = chat_obj._wx.GetAllMessage(target_who=nickname)
            for msg in current_msgs:
                msg_id = msg.get('id', '')
                if msg_id:
                    chat_obj.usedmsgid.append(msg_id)

            self._listeners[nickname] = chat_obj
            if callback:
                self._listener_callbacks[nickname] = callback

            return chat_obj

        except:
            return None

    def GetAllNewMessage(self):
        """获取所有监听对象的新消息（不重复切换聊天）"""
        all_messages = {}

        for who, chat_obj in self._listeners.items():
            try:
                # 不再每次调用 ChatWith(who)，只在添加监听时切换一次
                # 直接获取当前聊天的新消息
                new_msgs = chat_obj.GetNewMessage()

                if new_msgs:
                    all_messages[who] = new_msgs

                    # 调用回调
                    if who in self._listener_callbacks:
                        callback = self._listener_callbacks[who]
                        for msg in new_msgs:
                            try:
                                callback(msg, chat_obj)
                            except Exception as cb_e:
                                wxlog.error(f"回调执行失败: {cb_e}")

            except Exception as e:
                wxlog.debug(f"获取 {who} 的新消息失败: {e}")

        return all_messages

    def KeepRunning(self, poll_interval=0.5):
        """
        保持运行，持续监听新消息（不激活窗口）

        Args:
            poll_interval: 轮询间隔（秒）
        """
        while not self._should_stop_listening:
            try:
                if self._listeners:
                    first_who = next(iter(self._listeners))
                    chat_obj = self._listeners[first_who]
                    # 获取新消息，不切换窗口，不激活
                    new_msgs = chat_obj.GetNewMessage()
                    if new_msgs and first_who in self._listener_callbacks:
                        callback = self._listener_callbacks[first_who]
                        for msg in new_msgs:
                            try:
                                callback(msg, chat_obj)
                            except:
                                pass
            except:
                pass
            time.sleep(poll_interval)

    def StopListening(self, remove=False):
        """停止监听"""
        self._should_stop_listening = True

        if remove:
            self._listeners.clear()
            self._listener_callbacks.clear()


def main():
    """测试代码"""
    print(f"wxauto v{WeChat.VERSION}")
    print("初始化中...")

    try:
        wx = WeChat()
        print(f"✓ 初始化成功")
        print(f"✓ 登录用户: {wx.nickname}")

        sessions = wx.GetSessionList()
        print(f"✓ 获取到 {len(sessions)} 个会话")

        for i, session in enumerate(sessions[:5]):
            name = wx.GetSessionName(session)
            print(f"  {i+1}. {name}")

    except Exception as e:
        print(f"✗ 错误: {e}")


if __name__ == "__main__":
    main()