#!/usr/bin/env python
# -*- coding: utf-8 -*-
import maya.cmds as mc
import math
from functools import partial
import sys

# Python 3 兼容性处理
if sys.version_info[0] >= 3:
    import importlib
    importlib.reload(sys)
else:
    reload(sys)
    sys.setdefaultencoding('utf-8')


class IkFkSwitchUI():
    def __init__(self):
        self.character_namespaces = []
        self.current_namespace = u""
        self.window_width = 300
        self.window_height = 400
        self.UI()

    def UI(self):
        if mc.window(u'ik_fk_switch', exists=1):
            mc.deleteUI(u'ik_fk_switch', window=True)

        main_window = mc.window(u'ik_fk_switch', title=u"IK-FK切换",
                                widthHeight=(self.window_width, self.window_height),
                                minimizeButton=True, maximizeButton=False, sizeable=True,
                                backgroundColor=[0.18, 0.18, 0.2])

        main_column = mc.columnLayout(adjustableColumn=True, rowSpacing=4,
                                      columnAttach=[u'both', 6])

        # 角色选择
        self.create_character_selection(main_column)

        # 选项卡
        tabs = mc.tabLayout(u'ik_fk_switch_tabs', innerMarginWidth=6, innerMarginHeight=6,
                            tabsVisible=True, backgroundColor=[0.2, 0.2, 0.22])

        # 单帧切换
        single_frame = mc.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.create_limb_section(single_frame, u"手臂", u"Arm", False)
        mc.separator(height=6, style="in")
        self.create_limb_section(single_frame, u"腿部", u"Leg", False)
        mc.setParent('..')

        # 批量切换 - 移除滚动条，直接显示（减小间距以收缩长度）
        batch_frame = mc.columnLayout(adjustableColumn=True, rowSpacing=2,
                                      backgroundColor=[0.16, 0.16, 0.18])
        self.create_frame_range(batch_frame)
        mc.separator(height=4, style="in")
        self.create_limb_section(batch_frame, u"手臂", u"Arm", True)
        mc.separator(height=4, style="in")
        self.create_limb_section(batch_frame, u"腿部", u"Leg", True)
        mc.setParent('..')

        mc.tabLayout(tabs, edit=True, tabLabel=((single_frame, u"单帧"), (batch_frame, u"批量")))

        # 状态栏
        self.create_status(main_column)

        mc.showWindow(main_window)
        self.refresh_character_list()

    def create_character_selection(self, parent):
        # 角色选择和刷新按钮放在一行
        row = mc.rowLayout(parent=parent, numberOfColumns=3, columnWidth3=(35, 170, 55),
                           columnAttach=[(1, 'right', 4), (2, 'both', 4), (3, 'both', 4)])
        mc.text(label=u"角色:", align="right")
        self.namespace_optionMenu = mc.optionMenu(changeCommand=self.on_namespace_changed,
                                                  backgroundColor=[0.25, 0.25, 0.27])
        mc.button(label=u"刷新", command=self.refresh_character_list,
                  backgroundColor=[0.3, 0.4, 0.5], height=26)
        mc.setParent('..')

    def create_frame_range(self, parent):
        frame = mc.frameLayout(parent=parent, label=u"帧范围", collapsable=False,
                               marginWidth=4, marginHeight=3,
                               backgroundColor=[0.18, 0.22, 0.18])
        mc.columnLayout(adjustableColumn=True, rowSpacing=2)

        # 开始、结束帧在一行
        row = mc.rowLayout(numberOfColumns=4, columnWidth4=(38, 82, 38, 82),
                           columnAttach=[(1, 'right', 2), (2, 'both', 2), (3, 'right', 2), (4, 'both', 2)])
        mc.text(label=u"开始:", align="right")
        self.start_frame_field = mc.intField(value=mc.playbackOptions(q=True, min=True))
        mc.text(label=u"结束:", align="right")
        self.end_frame_field = mc.intField(value=mc.playbackOptions(q=True, max=True))
        mc.setParent('..')

        # 时间滑块按钮和逐帧复选框放在同一行（逐帧更靠左，时间滑块更靠右）
        row2 = mc.rowLayout(numberOfColumns=2, columnWidth2=(70, 130),
                            columnAttach=[(1, 'left', 5), (2, 'right', -40)])
        self.frame_by_frame_checkbox = mc.checkBox(label=u"逐帧", value=False)
        mc.button(label=u"使用时间滑块", command=self.set_timeline_range,
                  backgroundColor=[0.25, 0.35, 0.25], height=26)
        mc.setParent('..')

        mc.setParent('..')
        mc.setParent('..')

    def create_limb_section(self, parent, title, limb_type, is_batch):
        frame = mc.frameLayout(parent=parent, label=title, collapsable=False,
                               marginWidth=4, marginHeight=4)
        mc.columnLayout(adjustableColumn=True, rowSpacing=3)

        row = mc.rowLayout(numberOfColumns=2, columnWidth2=(120, 120),
                           columnAttach=[(1, 'both', 4), (2, 'both', 4)])

        if limb_type == "Arm":
            left_label = u"右臂"      # 左侧按钮控制右臂
            right_label = u"左臂"     # 右侧按钮控制左臂
        else:
            left_label = u"右腿"      # 左侧按钮控制右腿
            right_label = u"左腿"     # 右侧按钮控制左腿

        # 左侧按钮控制角色右侧
        left_col = mc.columnLayout(adjustableColumn=True, rowSpacing=3)
        mc.text(label=left_label, align="center", font="boldLabelFont", height=22)
        # 左键切换，右键仅烘焙
        left_fk_cmd = partial(self.fk_to_ik_switch, limb_type, "R", is_batch, False)
        left_ik_cmd = partial(self.ik_to_fk_switch, limb_type, "R", is_batch, False)
        left_fk_bake_cmd = partial(self.fk_to_ik_switch, limb_type, "R", is_batch, True)
        left_ik_bake_cmd = partial(self.ik_to_fk_switch, limb_type, "R", is_batch, True)
        left_fk_btn = mc.button(label=u"FK→IK", command=left_fk_cmd, backgroundColor=[0.2, 0.5, 0.7], height=32)
        left_ik_btn = mc.button(label=u"IK→FK", command=left_ik_cmd, backgroundColor=[0.5, 0.2, 0.2], height=32)
        # 添加右键直接执行烘焙
        self.add_right_click_bake(left_fk_btn, left_fk_bake_cmd)
        self.add_right_click_bake(left_ik_btn, left_ik_bake_cmd)
        mc.setParent('..')

        # 右侧按钮控制角色左侧
        right_col = mc.columnLayout(adjustableColumn=True, rowSpacing=3)
        mc.text(label=right_label, align="center", font="boldLabelFont", height=22)
        # 左键切换，右键仅烘焙
        right_fk_cmd = partial(self.fk_to_ik_switch, limb_type, "L", is_batch, False)
        right_ik_cmd = partial(self.ik_to_fk_switch, limb_type, "L", is_batch, False)
        right_fk_bake_cmd = partial(self.fk_to_ik_switch, limb_type, "L", is_batch, True)
        right_ik_bake_cmd = partial(self.ik_to_fk_switch, limb_type, "L", is_batch, True)
        right_fk_btn = mc.button(label=u"FK→IK", command=right_fk_cmd, backgroundColor=[0.2, 0.5, 0.7], height=32)
        right_ik_btn = mc.button(label=u"IK→FK", command=right_ik_cmd, backgroundColor=[0.5, 0.2, 0.2], height=32)
        # 添加右键直接执行烘焙
        self.add_right_click_bake(right_fk_btn, right_fk_bake_cmd)
        self.add_right_click_bake(right_ik_btn, right_ik_bake_cmd)
        mc.setParent('..')

        mc.setParent('..')
        mc.setParent('..')
        mc.setParent('..')

    def add_right_click_bake(self, button, bake_command):
        """为按钮添加右键直接执行烘焙功能"""
        # 使用 scriptJob 或 popupMenu 的 postMenuCommand 来实现右键直接执行
        # 这里使用一个技巧：创建一个不可见的 popupMenu，点击后直接执行命令
        def execute_bake(*args):
            bake_command()
        
        popup = mc.popupMenu(parent=button, button=3)  # button=3 表示右键
        mc.menuItem(parent=popup, label=u"烘焙", command=execute_bake, visible=False)
        # 由于 menuItem 必须可见才能被点击，我们改用另一种方式
        # 使用 popupMenu 的 postMenuCommand 在菜单显示前执行命令
        mc.popupMenu(popup, e=True, postMenuCommand=execute_bake)

    def create_status(self, parent):
        mc.separator(parent=parent, height=3, style="in")
        self.status_text = mc.text(parent=parent, label=u"就绪", align="center",
                                   height=26, backgroundColor=[0.12, 0.12, 0.14])

    def refresh_character_list(self, *args):
        # 清空当前选项
        if mc.optionMenu(self.namespace_optionMenu, q=True, numberOfItems=True) > 0:
            mc.optionMenu(self.namespace_optionMenu, e=True, deleteAllItems=True)

        # 添加默认选项(无命名空间)
        mc.menuItem(label=u"无命名空间", parent=self.namespace_optionMenu)

        # 获取场景中的所有命名空间
        all_namespaces = mc.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        character_namespaces = []
        # 过滤出可能是角色的命名空间
        for namespace in all_namespaces:
            if namespace in [u'UI', u'shared']:
                continue

            # 检查是否包含IK/FK控制
            control_patterns = [
                u"{}:FKIKArm_L".format(namespace), u"{}:FKIKArm_R".format(namespace),
                u"{}:FKIKLeg_L".format(namespace), u"{}:FKIKLeg_R".format(namespace)
            ]

            for control in control_patterns:
                if mc.objExists(control):
                    character_namespaces.append(namespace)
                    break

        # 更新命名空间列表
        self.character_namespaces = character_namespaces

        # 添加找到的角色命名空间到下拉菜单
        for namespace in character_namespaces:
            mc.menuItem(label=namespace, parent=self.namespace_optionMenu)

        # 自动选择适当的命名空间
        selection = mc.ls(sl=True)
        if selection:
            selected_obj = selection[0]
            if ':' in selected_obj:
                namespace = selected_obj.split(':')[0]
                items = mc.optionMenu(self.namespace_optionMenu, q=True, itemListLong=True)
                if items:
                    for i, item in enumerate(items):
                        label = mc.menuItem(item, q=True, label=True)
                        if namespace == label:
                            mc.optionMenu(self.namespace_optionMenu, e=True, select=i+1)
                            self.current_namespace = namespace
                            self.update_status(u"角色: {}".format(namespace))
                            return

        # 如果没有选中对象，尝试选择第一个找到的角色
        if character_namespaces:
            first_namespace = character_namespaces[0]
            items = mc.optionMenu(self.namespace_optionMenu, q=True, itemListLong=True)
            if items:
                for i, item in enumerate(items):
                    label = mc.menuItem(item, q=True, label=True)
                    if first_namespace == label:
                        mc.optionMenu(self.namespace_optionMenu, e=True, select=i+1)
                        self.current_namespace = first_namespace
                        self.update_status(u"角色: {}".format(first_namespace))
                        return

        # 如果没有找到任何角色，设置为无命名空间
        self.current_namespace = u""
        self.update_status(u"角色: 无")

    def on_namespace_changed(self, namespace):
        self.current_namespace = u"" if namespace == u"无命名空间" else namespace
        self.update_status(u"角色: {}".format(self.current_namespace or u"无"))

    def set_timeline_range(self, *args):
        start = mc.playbackOptions(q=True, min=True)
        end = mc.playbackOptions(q=True, max=True)
        mc.intField(self.start_frame_field, e=True, value=start)
        mc.intField(self.end_frame_field, e=True, value=end)
        self.update_status(u"帧范围: {}-{}".format(int(start), int(end)))

    def update_status(self, message):
        mc.text(self.status_text, e=True, label=message)
        mc.inViewMessage(amg=message, pos='midCenter', fade=True, fadeOutTime=2.0)

    def get_limb_controllers(self, limb_type, side):
        if limb_type == "Arm":
            if side == "L":
                controllers = {
                    'fk_controls': ['FKShoulder_L', 'FKElbow_L', 'FKWrist_L'],
                    'ik_controls': ['IKArm_L', 'PoleArm_L'],
                    'switch_control': 'FKIKArm_L',
                    'fk_offset': ['Shoulder_L', 'Elbow_L', 'Wrist_L'],
                    'ik_joints': ['IKXShoulder_L', 'IKXElbow_L', 'IKXWrist_L'],
                    'wrist_bone': 'Wrist_L'
                }
            else:
                controllers = {
                    'fk_controls': ['FKShoulder_R', 'FKElbow_R', 'FKWrist_R'],
                    'ik_controls': ['IKArm_R', 'PoleArm_R'],
                    'switch_control': 'FKIKArm_R',
                    'fk_offset': ['Shoulder_R', 'Elbow_R', 'Wrist_R'],
                    'ik_joints': ['IKXShoulder_R', 'IKXElbow_R', 'IKXWrist_R'],
                    'wrist_bone': 'Wrist_R'
                }
        else:
            if side == "L":
                controllers = {
                    'fk_controls': ['FKHip_L', 'FKKnee_L', 'FKAnkle_L'],
                    'ik_controls': ['IKLeg_L', 'PoleLeg_L'],
                    'switch_control': 'FKIKLeg_L',
                    'fk_offset': ['Hip_L', 'Knee_L', 'Ankle_L'],
                    'ik_joints': ['IKXHip_L', 'IKXKnee_L', 'IKXAnkle_L'],
                    'wrist_bone': 'Ankle_L'
                }
            else:
                controllers = {
                    'fk_controls': ['FKHip_R', 'FKKnee_R', 'FKAnkle_R'],
                    'ik_controls': ['IKLeg_R', 'PoleLeg_R'],
                    'switch_control': 'FKIKLeg_R',
                    'fk_offset': ['Hip_R', 'Knee_R', 'Ankle_R'],
                    'ik_joints': ['IKXHip_R', 'IKXKnee_R', 'IKXAnkle_R'],
                    'wrist_bone': 'Ankle_R'
                }

        if self.current_namespace:
            prefix = u"{}:".format(self.current_namespace)
            for key, value in controllers.items():
                if isinstance(value, list):
                    controllers[key] = [prefix + v for v in value]
                else:
                    controllers[key] = prefix + value
        return controllers

    def get_keyframe_times(self, controllers, start_frame, end_frame):
        keyframe_times = set()
        for ctrl in controllers:
            if mc.objExists(ctrl):
                anim_curves = mc.listConnections(ctrl, type='animCurve') or []
                for curve in anim_curves:
                    key_times = mc.keyframe(curve, q=True, timeChange=True) or []
                    for time in key_times:
                        if start_frame <= time <= end_frame:
                            keyframe_times.add(int(time))
        return sorted(list(keyframe_times))

    def set_all_keyframes(self, controllers, frame_time, skip_switch_control=False):
        mc.currentTime(frame_time)
        keyframes_set = 0
        for ctrl in controllers:
            if mc.objExists(ctrl):
                try:
                    # 如果跳过切换控制器，则跳过包含FKIK的控制器
                    if skip_switch_control and 'FKIK' in ctrl:
                        continue
                    mc.setKeyframe(ctrl, at=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'])
                    if 'FKIK' in ctrl:
                        mc.setKeyframe(ctrl, at='FKIKBlend')
                    keyframes_set += 1
                except:
                    pass
        return keyframes_set

    def fk_to_ik_switch(self, limb_type, side, is_batch, bake_only=False, *args):
        try:
            controllers = self.get_limb_controllers(limb_type, side)

            if is_batch:
                start_frame = mc.intField(self.start_frame_field, q=True, value=True)
                end_frame = mc.intField(self.end_frame_field, q=True, value=True)
                frame_by_frame = mc.checkBox(self.frame_by_frame_checkbox, q=True, value=True)

                all_controllers = (controllers['fk_controls'] +
                                   controllers['ik_controls'] +
                                   [controllers['switch_control']])

                if frame_by_frame:
                    # 逐帧模式：从开始帧到结束帧每一帧都处理
                    keyframe_times = list(range(int(start_frame), int(end_frame) + 1))
                    self.update_status(u"逐帧模式：将处理 {} 帧".format(len(keyframe_times)))
                else:
                    # 关键帧模式：只在有关键帧的时间点处理
                    keyframe_times = self.get_keyframe_times(all_controllers, start_frame, end_frame)
                    if not keyframe_times:
                        keyframe_times = [mc.currentTime(q=True)]
                        self.update_status(u"未找到关键帧，将在当前帧进行切换")
                    else:
                        self.update_status(u"找到 {} 个关键帧进行批量切换".format(len(keyframe_times)))
            else:
                current_frame = mc.currentTime(q=True)
                keyframe_times = [current_frame]

            # 开始一个撤销块，实现整体撤销
            mc.undoInfo(openChunk=True, chunkName=u"FK→IK批量切换")

            # 暂停视口刷新以提高性能
            mc.refresh(suspend=True)

            total_keyframes_set = 0

            try:
                for i, frame_time in enumerate(keyframe_times):
                    if is_batch and len(keyframe_times) > 1:
                        progress = int((i + 1) / len(keyframe_times) * 100)
                        self.update_status(u"处理帧 {} ({}%)".format(int(frame_time), progress))

                    # 执行核心切换逻辑，传入 bake_only 参数
                    self.fk_to_ik_core(controllers, frame_time, bake_only)

                    # FK→IK：烘焙IK控制器
                    # 切换模式（非烘焙）时，还需要给切换控制器K帧
                    if bake_only:
                        # 仅烘焙：只烘焙IK控制器
                        ik_controllers = controllers['ik_controls']
                    else:
                        # 切换模式：烘焙IK控制器和切换控制器
                        ik_controllers = controllers['ik_controls'] + [controllers['switch_control']]
                    keyframes_set = self.set_all_keyframes(ik_controllers, frame_time)
                    total_keyframes_set += keyframes_set

            finally:
                # 恢复视口刷新
                mc.refresh(suspend=False)
                # 关闭撤销块
                mc.undoInfo(closeChunk=True)

            action_type = u"批量" if is_batch else u"单帧"
            bake_text = u"烘焙" if bake_only else u"切换"
            limb_name = u"手臂" if limb_type == u"Arm" else u"腿部"
            side_name = u"左" if side == u"L" else u"右"
            self.update_status(u"{} {} FK→IK {}{}成功".format(side_name, limb_name, action_type, bake_text))

        except Exception as e:
            mc.undoInfo(closeChunk=True)
            self.update_status(u"错误: {}".format(str(e)))
            mc.warning(u"切换失败: {}".format(str(e)))

    def ik_to_fk_switch(self, limb_type, side, is_batch, bake_only=False, *args):
        try:
            controllers = self.get_limb_controllers(limb_type, side)

            if is_batch:
                start_frame = mc.intField(self.start_frame_field, q=True, value=True)
                end_frame = mc.intField(self.end_frame_field, q=True, value=True)
                frame_by_frame = mc.checkBox(self.frame_by_frame_checkbox, q=True, value=True)

                all_controllers = (controllers['fk_controls'] +
                                   controllers['ik_controls'] +
                                   [controllers['switch_control']])

                if frame_by_frame:
                    # 逐帧模式：从开始帧到结束帧每一帧都处理
                    keyframe_times = list(range(int(start_frame), int(end_frame) + 1))
                    self.update_status(u"逐帧模式：将处理 {} 帧".format(len(keyframe_times)))
                else:
                    # 关键帧模式：只在有关键帧的时间点处理
                    keyframe_times = self.get_keyframe_times(all_controllers, start_frame, end_frame)
                    if not keyframe_times:
                        keyframe_times = [mc.currentTime(q=True)]
                        self.update_status(u"未找到关键帧，将在当前帧进行切换")
                    else:
                        self.update_status(u"找到 {} 个关键帧进行批量切换".format(len(keyframe_times)))
            else:
                current_frame = mc.currentTime(q=True)
                keyframe_times = [current_frame]

            # 开始一个撤销块，实现整体撤销
            mc.undoInfo(openChunk=True, chunkName=u"IK→FK批量切换")

            # 暂停视口刷新以提高性能
            mc.refresh(suspend=True)

            total_keyframes_set = 0

            try:
                for i, frame_time in enumerate(keyframe_times):
                    if is_batch and len(keyframe_times) > 1:
                        progress = int((i + 1) / len(keyframe_times) * 100)
                        self.update_status(u"处理帧 {} ({}%)".format(int(frame_time), progress))

                    # 执行核心切换逻辑，传入 bake_only 参数
                    self.ik_to_fk_core(controllers, frame_time, bake_only)

                    # IK→FK：烘焙FK控制器
                    # 切换模式（非烘焙）时，还需要给切换控制器K帧
                    if bake_only:
                        # 仅烘焙：只烘焙FK控制器
                        fk_controllers = controllers['fk_controls']
                    else:
                        # 切换模式：烘焙FK控制器和切换控制器
                        fk_controllers = controllers['fk_controls'] + [controllers['switch_control']]
                    keyframes_set = self.set_all_keyframes(fk_controllers, frame_time)
                    total_keyframes_set += keyframes_set

            finally:
                # 恢复视口刷新
                mc.refresh(suspend=False)
                # 关闭撤销块
                mc.undoInfo(closeChunk=True)

            action_type = u"批量" if is_batch else u"单帧"
            bake_text = u"烘焙" if bake_only else u"切换"
            limb_name = u"手臂" if limb_type == u"Arm" else u"腿部"
            side_name = u"左" if side == u"L" else u"右"
            self.update_status(u"{} {} IK→FK {}{}成功".format(side_name, limb_name, action_type, bake_text))

        except Exception as e:
            mc.undoInfo(closeChunk=True)
            self.update_status(u"错误: {}".format(str(e)))
            mc.warning(u"切换失败: {}".format(str(e)))

    def dtp(self, a=[0, 0, 0], b=[0, 0, 0]):
        distanceX = a[0] - b[0]
        distanceY = a[1] - b[1]
        distanceZ = a[2] - b[2]
        distance = math.sqrt((distanceX * distanceX) +
                             (distanceY * distanceY) + (distanceZ * distanceZ))
        return distance

    def fk_to_ik_core(self, controllers, frame_time, bake_only=False):
        mc.currentTime(frame_time)

        required_objects = (controllers['fk_offset'] +
                            controllers['ik_controls'] +
                            [controllers['switch_control'], controllers['wrist_bone']])

        for obj in required_objects:
            if not mc.objExists(obj):
                raise RuntimeError(u"对象 {} 不存在".format(obj))

        FK_Shoulder = mc.xform(controllers['fk_offset'][0], q=1, ws=1, t=1)
        FK_Elbow = mc.xform(controllers['fk_offset'][1], q=1, ws=1, t=1)
        FK_Wrist = mc.xform(controllers['fk_offset'][2], q=1, ws=1, t=1)

        # 记录当前的FKIKBlend值
        original_blend = mc.getAttr(controllers['switch_control'] + '.FKIKBlend')
        
        # 设置FKIKBlend，烘焙模式下不自动K帧
        mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 10)

        ik_arm = controllers['ik_controls'][0]
        pole_arm = controllers['ik_controls'][1]
        wrist_bone = controllers['wrist_bone']

        mc.select(ik_arm)
        mc.move(FK_Wrist[0], FK_Wrist[1], FK_Wrist[2], a=1, os=1, ws=1)

        fk_wrist_loc = mc.spaceLocator(name="temp_fk_wrist_loc")[0]
        ik_wrist_loc = mc.spaceLocator(name="temp_ik_wrist_loc")[0]

        mc.parentConstraint(wrist_bone, fk_wrist_loc, w=1, mo=0)
        mc.parentConstraint(ik_arm, ik_wrist_loc, w=1, mo=0)
        mc.parentConstraint(ik_arm, ik_wrist_loc, w=1, rm=1)

        constraint = mc.parentConstraint(fk_wrist_loc, ik_wrist_loc, w=1, mo=1)

        mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 0)
        mc.delete(constraint)
        mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 10)

        ik_wrist_pos = mc.xform(ik_wrist_loc, q=1, ws=1, t=1)
        ik_wrist_rot = mc.xform(ik_wrist_loc, q=1, ws=1, ro=1)

        mc.select(ik_arm)
        mc.move(ik_wrist_pos[0], ik_wrist_pos[1], ik_wrist_pos[2], a=1, os=1, ws=1)
        mc.rotate(ik_wrist_rot[0], ik_wrist_rot[1], ik_wrist_rot[2], a=1, fo=1, ws=1)

        mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 0)

        temp_nodes = []
        pole_loc1 = mc.spaceLocator(name="temp_pole_loc1")[0]
        temp_nodes.append(pole_loc1)
        pole_loc2 = mc.spaceLocator(name="temp_pole_loc2")[0]
        temp_nodes.append(pole_loc2)
        pole_loc3 = mc.spaceLocator(name="temp_pole_loc3")[0]
        pole_loc3_grp = mc.group(pole_loc3, name="temp_pole_loc3_grp")
        temp_nodes.append(pole_loc3_grp)
        pole_loc4 = mc.spaceLocator(name="temp_pole_loc4")[0]
        pole_loc4_grp = mc.group(pole_loc4, name="temp_pole_loc4_grp")
        temp_nodes.append(pole_loc4_grp)

        mc.delete(mc.parentConstraint(controllers['fk_offset'][0], pole_loc1, w=1, mo=0))
        mc.delete(mc.parentConstraint(controllers['fk_offset'][1], pole_loc2, w=1, mo=0))
        mc.delete(mc.parentConstraint(controllers['fk_offset'][1], pole_loc4_grp, w=1, mo=0))
        mc.delete(mc.parentConstraint(controllers['fk_offset'][2], pole_loc3_grp, w=1, mo=0))

        mc.delete(mc.aimConstraint(pole_loc1, pole_loc3_grp, aim=(1, 0, 0), u=(0, 1, 0), wut='scene'))

        mc.parent(pole_loc4_grp, pole_loc3)
        mc.setAttr(pole_loc3 + '.rx', 180)

        mc.delete(mc.aimConstraint(pole_loc2, pole_loc4_grp, aim=(1, 0, 0), u=(0, 1, 0), wut='scene'))
        mc.delete(mc.pointConstraint(pole_loc2, pole_loc4_grp, w=1, mo=0))

        dis = self.dtp(FK_Shoulder, FK_Elbow)
        mc.setAttr(pole_loc4 + '.tx', dis)

        pole_pos = mc.xform(pole_loc4, q=1, ws=1, t=1)
        mc.xform(pole_arm, t=[pole_pos[0], pole_pos[1], pole_pos[2]], ws=1)

        mc.delete(temp_nodes)
        mc.delete(fk_wrist_loc, ik_wrist_loc)

        if bake_only:
            # 仅烘焙模式：恢复原来的FKIKBlend值，并删除可能自动创建的关键帧
            mc.setAttr(controllers['switch_control'] + '.FKIKBlend', original_blend)
            # 删除切换控制器在当前帧的关键帧
            try:
                mc.cutKey(controllers['switch_control'], time=(frame_time, frame_time), attribute='FKIKBlend')
            except:
                pass
        else:
            # 正常切换模式：设置为IK
            mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 10)
            mc.select(controllers['switch_control'])

    def ik_to_fk_core(self, controllers, frame_time, bake_only=False):
        mc.currentTime(frame_time)

        required_objects = (controllers['ik_joints'] +
                            controllers['fk_controls'] +
                            [controllers['switch_control']])

        for obj in required_objects:
            if not mc.objExists(obj):
                raise RuntimeError(u"对象 {} 不存在".format(obj))

        # 记录当前的FKIKBlend值
        original_blend = mc.getAttr(controllers['switch_control'] + '.FKIKBlend')
        
        mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 10)

        ik_joints_data = []
        for joint in controllers['ik_joints']:
            pos = mc.xform(joint, q=1, ws=1, t=1)
            rot = mc.xform(joint, q=1, ws=1, ro=1)
            ik_joints_data.append({'pos': pos, 'rot': rot})

        for i, fk_ctrl in enumerate(controllers['fk_controls']):
            if i < len(ik_joints_data):
                data = ik_joints_data[i]
                mc.xform(fk_ctrl, ro=[data['rot'][0], data['rot'][1], data['rot'][2]], ws=1)
                mc.xform(fk_ctrl, t=[data['pos'][0], data['pos'][1], data['pos'][2]], ws=1)

        if bake_only:
            # 仅烘焙模式：恢复原来的FKIKBlend值，并删除可能自动创建的关键帧
            mc.setAttr(controllers['switch_control'] + '.FKIKBlend', original_blend)
            # 删除切换控制器在当前帧的关键帧
            try:
                mc.cutKey(controllers['switch_control'], time=(frame_time, frame_time), attribute='FKIKBlend')
            except:
                pass
        else:
            # 正常切换模式：设置为FK
            mc.setAttr(controllers['switch_control'] + '.FKIKBlend', 0)
            mc.select(controllers['switch_control'])


def onMayaDroppedPythonFile(*args, **kwargs):
    IkFkSwitchUI()


if __name__ == "__main__":
    IkFkSwitchUI()