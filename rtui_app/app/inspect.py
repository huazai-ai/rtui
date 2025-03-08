from __future__ import annotations

import warnings

from textual.app import App
from textual.binding import Binding

from ..event import RosEntitySelected
from ..ros import RosClient, RosEntity, RosEntityType
from ..screens import RosEntityInspection
from ..utility import History

import subprocess

warnings.simplefilter("ignore", ResourceWarning)


class InspectApp(App):
    _ros: RosClient
    _init_target: RosEntityType
    _history: History[RosEntity] = History(20)
    
    TITLE = "ROS Inspect"
    BINDINGS = [
        Binding("b", "back", "Prev Page", key_display="b"),
        Binding("f", "forward", "Next Page", key_display="f"),
        Binding("r", "reload", "Reload", key_display="r"),
        Binding("e", "toggle_echo", "Toggle Echo", key_display="e"),
        Binding("q", "quit", "Quit", key_display="q"),
    ]

    def __init__(
        self,
        ros: RosClient,
        init_target: RosEntityType,
    ) -> None:
        super().__init__()

        self._ros = ros
        self._init_target = init_target

        for t in RosEntityType:
            if self._ros.available(t):
                self.add_mode(t.name, RosEntityInspection(ros, t))

    def show_ros_entity(self, entity: RosEntity, append_history: bool = True) -> None:
        self.switch_mode(entity.type.name)
        screen: RosEntityInspection = self.screen
        screen.set_entity_name(entity.name)

        if append_history:
            self._history.append(entity)

    def on_mount(self) -> None:
        self.switch_mode(self._init_target.name)

    def action_forward(self) -> None:
        if entity := self._history.forward():
            self.show_ros_entity(entity, append_history=False)

    def action_back(self) -> None:
        if entity := self._history.back():
            self.show_ros_entity(entity, append_history=False)

    def action_reload(self) -> None:
        self.screen.force_update()

    def action_toggle_echo(self) -> None:
        if entity := self._history.current():
            if entity.type == RosEntityType.Topic:
                """启动一个新的 GNOME 终端，并持续打印 self 的值，防止终端自动关闭。"""
                command = f'ros2 topic echo {entity.name}'
                title = f"{command}"
                
                # 先杀死可能存在的同名终端进程
                kill_command = f'pkill -f "{title}"'
                subprocess.run(kill_command, shell=True)

                # _ros: RosClient
                # _init_target: RosEntityType
                # _history: History[RosEntity] = History(20)
                terminal_cmd = f'gnome-terminal --title "{title}" -- bash -c "{command}; read line"'
                subprocess.Popen(terminal_cmd, shell=True)
                self.notify(f"Echo {command}")
            else:
                self.notify(f"不是一个话题")

    async def action_quit(self) -> None:
        await super().action_quit()

    def on_ros_entity_selected(self, e: RosEntitySelected) -> None:
        self.show_ros_entity(e.entity)
