from __future__ import annotations

import warnings
from textual.app import App
from textual.binding import Binding
from textual.events import MouseDown

from ..event import RosEntitySelected
from ..ros import RosClient, RosEntity, RosEntityType
from ..screens import RosEntityInspection
from ..utility import History


import subprocess
from textual.events import MouseDown
import time
import threading

warnings.simplefilter("ignore", ResourceWarning)


class InspectApp(App):
    TITLE = "ROS Inspect"
    BINDINGS = [
        Binding("b", "back", "Prev Page", key_display="b"),
        Binding("f", "forward", "Next Page", key_display="f"),
        Binding("r", "reload", "Reload", key_display="r"),
        # Binding("e", "toggle_echo", "Toggle Echo", key_display="e"),
        Binding("q", "quit", "Quit", key_display="q"),
    ]

    """
    鼠标左键:
        1. 点击: 下一页
        2. 双击: 开启/取消 打开终端启动ros2命令
    鼠标右键:
        1. 点击: 上一页
    鼠标中键:
        1. 点击: 重新加载数据
    """

    def __init__(self, ros: RosClient, init_target: RosEntityType) -> None:
        super().__init__()
        self._ros = ros
        self._init_target = init_target
        self._history = History[RosEntity](20)
        self.fix = False

        self.ros_helper = RosCommandHelper()
        self.mouse_handler = MouseEventHandler(self)
        self.nav_handler = NavigationHandler(self._history, self.show_ros_entity)

        for t in RosEntityType:
            if self._ros.available(t):
                self.add_mode(t.name, RosEntityInspection(ros, t))

        self.mouse_click_timer = None

    def show_ros_entity(self, entity: RosEntity, append_history: bool = True) -> None:
        if self.fix:
            # if entity_back := self._history.current():            # 获取当前的 entity
            #     if entity_back.type == RosEntityType.MsgType:
            self.ros_helper.execute_command(entity)
            return

        if entity.type == RosEntityType.Service:
            self.notify(f"{entity.type.name} 不允许跳转")
            return

        self.switch_mode(entity.type.name)
        screen: RosEntityInspection = self.screen
        screen.set_entity_name(entity.name)

        if append_history:
            self._history.append(entity)

        if self.mouse_click_timer:
            self.mouse_click_timer.cancel()

    def on_mouse_down(self, event: MouseDown) -> None:
        # self.mouse_handler.handle_mouse_event(event)
        self.mouse_click_timer = threading.Timer(0.2, self.mouse_handler.handle_mouse_event, args=(event,))
        self.mouse_click_timer.start()

    def on_mount(self) -> None:
        self.switch_mode(self._init_target.name)

    def action_forward(self) -> None:
        self.nav_handler.forward()

    def action_back(self) -> None:
        self.nav_handler.back()

    def action_reload(self) -> None:
        self.screen.force_update()

    # def action_toggle_echo(self) -> None:
    #     self.fix = not self.fix
    #     self.notify(f"fix: {self.fix}")

    async def action_quit(self) -> None:
        await super().action_quit()

    def on_ros_entity_selected(self, e: RosEntitySelected) -> None:
        self.show_ros_entity(e.entity)


class RosCommandHelper:
    def execute_command(self, entity: RosEntity) -> None:
        command_map = {
            RosEntityType.Node: self.node_info,
            RosEntityType.Topic: self.topic_echo,
            RosEntityType.Action: self.action_info,
            RosEntityType.MsgType: self.msg_type,
            RosEntityType.SrvType: self.srv_type,
            RosEntityType.ActionType: self.action_type,
        }
        command = command_map.get(entity.type)
        if command:
            command(entity.name)
        else:
            print(f"Invalid entity type: {entity.type}")

    def topic_echo(self, topic_name: str) -> None:
        self._run_command(f'ros2 topic echo {topic_name}')

    def node_info(self, node_name: str) -> None:
        self._run_command(f'ros2 node info {node_name}')

    def action_info(self, action_name: str) -> None:
        self._run_command(f'ros2 action info {action_name}')

    def msg_type(self, msg_name: str) -> None:
        self._run_command(f'ros2 interface show {msg_name}')

    def srv_type(self, srv_name: str) -> None:
        self._run_command(f'ros2 service type {srv_name}')

    def action_type(self, action_name: str) -> None:
        self._run_command(f'ros2 action type {action_name}')

    def _run_command(self, command: str) -> None:
        title = f"{command}"
        terminal_cmd = f'gnome-terminal --title "{title}" -- bash -c "echo {command}; echo "---";{command}; read line"'
        subprocess.Popen(terminal_cmd, shell=True)


class MouseEventHandler:
    def __init__(self, app: InspectApp):
        self.app = app
        self.last_click_time = 0
        self.double_click_threshold = 0.2
        self.single_click_timer = None

    def handle_mouse_event(self, event: MouseDown) -> None:
        current_time = time.time()
        if event.button == 1:               # 左键触发
            if self.single_click_timer:
                self.single_click_timer.cancel()
            if current_time - self.last_click_time < self.double_click_threshold:
                self.on_double_click()
            else:
                self.single_click_timer = threading.Timer(self.double_click_threshold, self.on_single_click)
                self.single_click_timer.start()
            self.last_click_time = current_time
        elif event.button == 3:             # 右键触发
            self.app.notify(f"Prev Page")
            self.app.action_back()
        elif event.button == 2:             # 中间触发
            self.on_middle_click()

    def on_single_click(self) -> None:
        self.app.notify(f"Next Page")
        self.app.action_forward()

    def on_double_click(self) -> None:
        self.app.fix = not self.app.fix
        self.app.notify(f"fix: {self.app.fix}")

    def on_middle_click(self) -> None:
        self.app.notify(f"Reload Data")
        self.app.action_reload()

class NavigationHandler:
    def __init__(self, history: History[RosEntity], show_entity_callback):
        self._history = history
        self._show_entity = show_entity_callback

    def forward(self) -> None:
        if entity := self._history.forward():
            self._show_entity(entity, append_history=False)

    def back(self) -> None:
        if entity := self._history.back():
            self._show_entity(entity, append_history=False)
