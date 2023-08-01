from asyncio.log import logger

from pywebio import *

import socket
import threading
import time

from source.advance_page import AdvancePage
from source.time import timer_module


class MainPage(AdvancePage):
    def __init__(self):
        super().__init__()
        self.log_list = []
        self.log_history = []
        self.log_list_lock = threading.Lock()
        self.ui_statement = -1
        self.refresh_flow_info_timer = timer_module.Timer()
        self.ui_mission_select = ""
        self.is_task_start = False

    def _on_load(self):  # 加载事件
        super()._on_load()
        pin.pin['FlowMode'] = 0

    def _event_thread(self):
        while self.loaded:  # 当界面被加载时循环运行
            try:
                pin.pin['isSessionExist']
            except SessionNotFoundException:
                logger.info("未找到会话，可能由于窗口关闭。请刷新页面重试。")
                return
            except SessionClosedException:
                logger.info("未找到会话，可能由于窗口关闭。请刷新页面重试。")
                return

            self.log_list_lock.acquire()
            for text, color in self.log_list:
                if text == "$$end$$":
                    output.put_text("", scope='LogArea')
                else:
                    output.put_text(text, scope='LogArea', inline=True).style(f'color: {color}; font_size: 20px')

            self.log_list.clear()
            self.log_list_lock.release()

            if self.refresh_flow_info_timer.get_diff_time() >= 0.2:
                self.refresh_flow_info_timer.reset()

            time.sleep(0.1)

    def _load(self):
        # 标题
        # 获得链接按钮
        with output.use_scope(self.main_scope):
            output.put_row([
                output.put_button(label="Get IP address", onclick=self.on_click_ip_address, scope=self.main_scope),
                output.put_link('View Document', url='https://genshinimpactassistant.github.io/GIA-Document',
                                new_window=True).style('font-size: 20px')
            ])

            task_options = [
                {
                    "label": "Launch genshin",
                    "value": "LaunchGenshinTask"
                },
                {
                    "label": "Domain Task",
                    "value": "DomainTask"
                },
                {
                    "label": "Daily Commission",
                    "value": "CommissionTask"
                },
                {
                    "label": "Claim Reward",
                    "value": "ClaimRewardTask"
                },
                {
                    "label": "Ley Line Outcrop",
                    "value": "LeyLineOutcropTask"
                },
                {
                    "label": "Mission",
                    "value": "MissionTask"
                }
            ]
            output.put_row([  # 横列
                output.put_column([  # 左竖列
                    output.put_markdown('## ' + "Task List"),
                    output.put_markdown("Can only be activated from the button"),
                    pin.put_checkbox(name="task_list", options=task_options),
                    output.put_row([output.put_text('启动/停止Task'), None, output.put_scope('Button_StartStop')],
                                   size='40% 10px 60%'),

                    output.put_markdown('## Statement'),
                    output.put_row([output.put_text('任务状态'), None, output.put_scope('StateArea')], size='40% 10px 60%'),
                    output.put_markdown('## Semi-automatic Functions'),  # 左竖列标题
                    output.put_markdown("Can only be activated from the hotkey \'[\'"),
                    output.put_text('Do not enable semi-automatic functions and tasks at the same time'),
                    output.put_row([  # FlowMode
                        output.put_text('Semi-automatic Functions'),

                    ],

                    )
                ], size='auto'), None,
                output.put_scope('Log')

            ], scope=self.main_scope, size='40% 10px 60%')

            # Log
            output.put_markdown('## Log', scope='Log')
            output.put_scrollable(output.put_scope('LogArea'), height=600, keep_bottom=True, scope='Log')
            '''self.main_pin_change_thread = threading.Thread(target=self._main_pin_change_thread, daemon=False)
            self.main_pin_change_thread.start()'''





    def on_click_ip_address(self):
        LAN_ip = f"{socket.gethostbyname(socket.gethostname())}{session.info.server_host[session.info.server_host.index(':'):]}"
        WAN_ip = "Not Enabled"
        output_text = 'LAN IP' + " : " + LAN_ip + '\n' + "WAN IP" + ' : ' + WAN_ip
        output.popup(f'ip address', output_text, size=output.PopupSize.SMALL)


