# wxauto - 微信自动化 SDK

适配 PC 版微信 4.1.9.35 的自动化工具。

## 功能

- 消息发送与接收
- 聊天窗口管理
- 语音通话控制
- UI 自动化交互

## 安装

```bash
pip install -e .
```

或直接克隆到本地后使用。

## 依赖

- uiautomation>=2.0.0
- pywin32>=306
- comtypes>=1.2.1

## 使用示例

```python
from wxauto import WeChat

wx = WeChat()
wx.SendMsg(msg='Hello', who='好友名称')
```

## 版本

- v39.2.1 - 适配微信 4.1.9.35