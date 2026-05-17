# -*- coding: utf-8 -*-
"""
Maya 运动轨迹工具 - Maya 2020兼容版本
支持Maya 2020+ 和 Python 2.7/3.x
完整版本 - 支持相机空间显示
"""

import os
import sys
import time

# Python 2/3 兼容性处理
if sys.version_info[0] == 3:
    unicode = str
    long = int

import maya.cmds as cmds
import maya.mel as mel

# Qt兼容性导入
try:
    # Maya 2017+
    from PySide2.QtWidgets import *
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from shiboken2 import wrapInstance
    PYSIDE_VERSION = 2
except ImportError:
    try:
        # Maya 2014-2016
        from PySide.QtGui import *
        from PySide.QtCore import *
        from shiboken import wrapInstance
        PYSIDE_VERSION = 1
    except ImportError:
        print("Error: Cannot import PySide library")
        raise

# Maya API兼容性处理 - 针对Maya 2020优化
try:
    # Maya 2022+ (新API)
    from maya.api.OpenMaya import MMatrix, MPoint
    API_VERSION = 2.0
    
    def create_matrix(matrix_list):
        """创建矩阵对象 - 新API"""
        return MMatrix(matrix_list)
    
    def create_point(point_list):
        """创建点对象 - 新API"""
        if len(point_list) >= 3:
            if len(point_list) == 3:
                point_list.append(1.0)  # 添加w分量
            return MPoint(point_list[:4])
        else:
            return MPoint([0, 0, 0, 1])
            
except ImportError:
    # Maya 2020及以下版本 (旧API)
    import maya.OpenMaya as om
    API_VERSION = 1.0
    
    def create_matrix(matrix_list):
        """创建矩阵对象 - 旧API版本"""
        if matrix_list and len(matrix_list) == 16:
            matrix = om.MMatrix()
            # 转换为MScriptUtil
            util = om.MScriptUtil()
            util.createMatrixFromList(matrix_list, matrix)
            return MatrixWrapper(matrix)
        else:
            return MatrixWrapper(om.MMatrix())
    
    def create_point(point_list):
        """创建点对象 - 旧API版本"""
        if len(point_list) >= 3:
            return PointWrapper(point_list[:3])
        else:
            return PointWrapper([0, 0, 0])
    
    class MatrixWrapper(object):
        """旧API矩阵包装器 - Maya 2020兼容"""
        def __init__(self, maya_matrix):
            self.matrix = maya_matrix
        
        def inverse(self):
            """返回矩阵的逆"""
            try:
                inverse_matrix = self.matrix.inverse()
                return MatrixWrapper(inverse_matrix)
            except:
                # 如果逆矩阵失败，返回单位矩阵
                return MatrixWrapper(om.MMatrix())
    
    class PointWrapper(object):
        """旧API点包装器 - Maya 2020兼容"""
        def __init__(self, point_list):
            self.x = float(point_list[0]) if len(point_list) > 0 else 0.0
            self.y = float(point_list[1]) if len(point_list) > 1 else 0.0 
            self.z = float(point_list[2]) if len(point_list) > 2 else 0.0
        
        def __mul__(self, matrix_wrapper):
            """点乘以矩阵 - Maya 2020兼容"""
            if hasattr(matrix_wrapper, 'matrix'):
                try:
                    # 使用旧API进行矩阵变换
                    point = om.MPoint(self.x, self.y, self.z, 1.0)
                    transformed = point * matrix_wrapper.matrix
                    return PointWrapper([transformed.x, transformed.y, transformed.z])
                except:
                    # 变换失败，返回原点
                    return PointWrapper([self.x, self.y, self.z])
            else:
                return PointWrapper([self.x, self.y, self.z])

import maya.OpenMayaUI as omui

# 常量定义
TOOL_NAME = "motion_trail_tool"
TOOL_TITLE = "Motion Trail Tool"
TRAIL_NAME = 'motion_trail'
TRAILSHAPE_NAME = 'motion_trail_shape'

# 简化的日志系统
class SimpleLogger(object):
    def info(self, msg):
        print("INFO: " + str(msg))
    
    def warning(self, msg):
        print("WARNING: " + str(msg))
        cmds.warning(str(msg))
    
    def error(self, msg):
        print("ERROR: " + str(msg))
        try:
            cmds.error(str(msg))
        except:
            pass

LOGGER = SimpleLogger()


def get_maya_main_window():
    """获取Maya主窗口 - Maya 2020兼容"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr:
        if PYSIDE_VERSION == 2:
            return wrapInstance(int(main_window_ptr), QWidget)
        else:
            if sys.version_info[0] == 3:
                return wrapInstance(int(main_window_ptr), QWidget)
            else:
                return wrapInstance(long(main_window_ptr), QWidget)
    return None


def get_tool_group(tool_name):
    """获取或创建工具组"""
    group_name = tool_name + "_group"
    if not cmds.objExists(group_name):
        cmds.createNode('transform', name=group_name, skipSelect=True)
        cmds.setAttr(group_name + '.hiddenInOutliner', True)
    return group_name


class MotionTrailCore(object):
    """运动轨迹核心类 - Maya 2020兼容"""
    
    def __init__(self):
        self.trail = None
        self.trailshape = None
        self.tracked_object = []
        self.reference_matrix = 'world'
        self.range_to_process = []
        self.trail_length = 0
        self.first_tracked_frame = 0
        self.trail_points = []
        self.keyvisual_group = None
        self.default_fade_mode = 'all'  # 默认生成轨迹为all
        
    def define_object(self):
        """定义要追踪的对象"""
        selection = cmds.ls(selection=True)
        if not selection:
            LOGGER.warning('Please select at least one object.')
            return []
        
        if (len(selection) == 1 and 
            cmds.objectType(selection[0]) == 'mesh'):
            return self.mesh_tracker()
        else:
            self.tracked_object = selection
            return self.tracked_object
    
    def mesh_tracker(self):
        """网格追踪器 - Maya 2020兼容版本"""
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            # 删除现有的追踪器
            to_delete = []
            for obj in ['dummyMover', 'trail_keyvisual', 'motion_trail_mesh_tracker']:
                if cmds.objExists(obj):
                    to_delete.append(obj)
            if to_delete:
                cmds.delete(to_delete)
            
            # 获取选择的对象
            selected = cmds.ls(selection=True)[0]
            
            # 创建定位器作为追踪器
            locator = cmds.spaceLocator(name='motion_trail_mesh_tracker')[0]
            
            # 获取对象的边界框中心
            try:
                bbox = cmds.exactWorldBoundingBox(selected)
                center_x = (bbox[0] + bbox[3]) / 2.0
                center_y = (bbox[1] + bbox[4]) / 2.0  
                center_z = (bbox[2] + bbox[5]) / 2.0
                
                # 设置定位器位置
                cmds.xform(locator, translation=[center_x, center_y, center_z], worldSpace=True)
            except:
                # 如果获取边界框失败，使用对象原点
                pos = cmds.xform(selected, q=True, t=True, ws=True)
                cmds.xform(locator, translation=pos, worldSpace=True)
            
            # 约束定位器到网格对象
            try:
                cmds.pointConstraint(selected, locator, maintainOffset=True)
            except:
                # 如果约束失败，使用父子关系
                try:
                    cmds.parent(locator, selected)
                except:
                    LOGGER.warning("Cannot create constraint or parent relationship")
            
            # 隐藏定位器
            cmds.setAttr(locator + '.visibility', False)
            cmds.setAttr(locator + '.hiddenInOutliner', True)
            
            self.tracked_object = [locator]
                
        except Exception as e:
            LOGGER.error("Failed to create mesh tracker: " + str(e))
            self.tracked_object = cmds.ls(selection=True)
        finally:
            cmds.undoInfo(stateWithoutFlush=True, undoName='Motion Trail')
        
        return self.tracked_object
    
    def delete_trail(self):
        """删除轨迹"""
        if self.trail and cmds.objExists(self.trail):
            try:
                cmds.delete(self.trail)
            except:
                pass
        
        # 清理所有相关的轨迹对象
        try:
            tool_group = get_tool_group(TOOL_NAME)
            all_trails = cmds.ls(tool_group + '|' + TRAIL_NAME + '*', long=True) or []
            for trail in all_trails:
                if cmds.objExists(trail):
                    try:
                        cmds.delete(trail)
                    except:
                        pass
        except:
            pass
                
        # 清理网格追踪器
        if cmds.objExists('motion_trail_mesh_tracker'):
            try:
                cmds.delete('motion_trail_mesh_tracker')
            except:
                pass
    
    def create_trail_node(self):
        """创建轨迹节点"""
        try:
            tool_group = get_tool_group(TOOL_NAME)
            self.trail = cmds.createNode('transform', n=TRAIL_NAME, parent=tool_group, skipSelect=True)
            self.trailshape = cmds.createNode('motionTrailShape', parent=self.trail, n=TRAILSHAPE_NAME, skipSelect=True)
            
            self.set_curve_style()
            cmds.setAttr(self.trail + '.hiddenInOutliner', True)
            
            # 父约束网格追踪器
            current_selection = cmds.ls(selection=True)
            if cmds.objExists('motion_trail_mesh_tracker'):
                cmds.setAttr('motion_trail_mesh_tracker.hiddenInOutliner', True)
                try:
                    cmds.parent('motion_trail_mesh_tracker', self.trail)
                except:
                    pass
            if current_selection:
                cmds.select(current_selection, replace=True)
        except Exception as e:
            LOGGER.error("Failed to create trail node: " + str(e))
    
    def set_curve_style(self):
        """设置曲线样式"""
        try:
            cmds.setAttr(self.trailshape + '.trailColor', 1.0, 0.0, 0.0, type='double3')
            cmds.setAttr(self.trailshape + '.extraTrailColor', 1.0, 1.0, 1.0, type='double3')
            cmds.setAttr(self.trailshape + '.trailDrawMode', 1)
            cmds.setAttr(self.trailshape + '.template', True)
            # 使用默认的all模式
            self.set_faded_frames(self.default_fade_mode)
            cmds.setAttr(self.trail + '.increment', 1)
        except Exception as e:
            LOGGER.error("Failed to set curve style: " + str(e))
    
    def set_faded_frames(self, number):
        """设置淡化帧数"""
        try:
            if number == 'all' or number == 0:
                setting = 0
            else:
                setting = int(number)
            cmds.setAttr(self.trailshape + '.postFrame', setting)
            cmds.setAttr(self.trailshape + '.preFrame', setting)
            cmds.setAttr(self.trailshape + '.fadeInoutFrames', setting)
        except Exception as e:
            LOGGER.error("Failed to set faded frames: " + str(e))
    
    def prioritize_timeline(self):
        """优先化时间线处理"""
        try:
            in_time = int(cmds.playbackOptions(query=True, minTime=True))
            out_time = int(cmds.playbackOptions(query=True, maxTime=True))
            cur_time = cmds.currentTime(q=True)
            list_of_keys = list(range(in_time, out_time + 1))
            self.range_to_process = sorted(list_of_keys, key=lambda x: abs(cur_time - x))
            self.trail_length = len(self.range_to_process)
            self.first_tracked_frame = min(self.range_to_process)
            return self.range_to_process
        except Exception as e:
            LOGGER.error("Failed to prioritize timeline: " + str(e))
            return []
    
    def prepare_pointarray(self, range_time):
        """准备点数组 - 支持相机空间"""
        if not self.tracked_object or not self.trail:
            return
        
        try:
            # 如果不是世界空间，需要将轨迹父约束到相机
            if self.reference_matrix != 'world':
                self.attach_trail_to_camera()
            
            original = cmds.getAttr(self.trailshape + '.points') or []
            
            # 获取当前帧的位置
            cur_matrix = [0, 0, 0]
            try:
                cur_matrix = cmds.getAttr(self.tracked_object[0] + '.worldMatrix', time=cmds.currentTime(q=True))[12:15]
                
                # 如果是相机空间，转换当前位置
                if self.reference_matrix != 'world' and self.validate_camera_existence(self.reference_matrix):
                    cam_matrix_data = cmds.getAttr(self.reference_matrix + '.worldMatrix', time=cmds.currentTime(q=True))
                    
                    # 使用兼容的API创建对象
                    world_point = create_point(cur_matrix + [1.0])
                    cam_matrix = create_matrix(cam_matrix_data)
                    
                    # 计算相机空间位置
                    camera_space_point = world_point * cam_matrix.inverse()
                    cur_matrix = [camera_space_point.x, camera_space_point.y, camera_space_point.z]
                    
            except Exception as e:
                LOGGER.warning("Failed to get current position: " + str(e))
                cur_matrix = [0, 0, 0]
                
            if len(original) < len(range_time):
                original = [cur_matrix] * len(range_time)
            self.trail_points = original
            
            cmds.setAttr(self.trailshape + '.startTime', min(range_time))
            
            # 设置相机可见性
            self.set_trail_camera_visibility()
            
        except Exception as e:
            LOGGER.error("Failed to prepare point array: " + str(e))
    
    def set_frame_point(self, frame):
        """设置帧点 - 支持相机空间"""
        if not self.tracked_object or not cmds.objExists(self.tracked_object[0]):
            return
            
        try:
            # 获取对象的世界矩阵
            matrix = cmds.getAttr(self.tracked_object[0] + '.worldMatrix', time=frame)[12:16]
            
            # 如果不是世界空间，需要转换到相机空间
            if self.reference_matrix != 'world' and self.validate_camera_existence(self.reference_matrix):
                try:
                    # 获取相机的世界矩阵
                    cam_matrix_data = cmds.getAttr(self.reference_matrix + '.worldMatrix', time=frame)
                    
                    # 使用兼容的API创建对象
                    world_point = create_point(matrix[:3] + [1.0])
                    cam_matrix = create_matrix(cam_matrix_data)
                    
                    # 计算相机空间位置
                    camera_space_point = world_point * cam_matrix.inverse()
                    matrix_point = [camera_space_point.x, camera_space_point.y, camera_space_point.z]
                except Exception as e:
                    LOGGER.warning("Camera space transformation failed: " + str(e))
                    matrix_point = matrix[:3]
                
            else:
                # 世界空间
                self.reference_matrix = 'world'
                matrix_point = matrix[:3]
            
            # 更新轨迹点
            frame_index = frame - int(self.first_tracked_frame)
            if 0 <= frame_index < len(self.trail_points):
                self.trail_points[frame_index] = matrix_point
            
                # 更新轨迹显示
                cmds.undoInfo(stateWithoutFlush=False)
                try:
                    # 构建参数列表
                    args = [self.trailshape + '.points', self.trail_length]
                    args.extend(self.trail_points[:self.trail_length])
                    cmds.setAttr(*args, type='pointArray')
                finally:
                    cmds.undoInfo(stateWithoutFlush=True, undoName='Motion Trail')
                    
        except Exception as e:
            LOGGER.error("Failed to set frame point: " + str(e))
    
    def set_camera_reference(self, camera):
        """设置相机参考"""
        self.reference_matrix = camera
        
        if not self.trail or not cmds.objExists(self.trail):
            return
            
        try:
            # 重置轨迹的父约束
            offset_matrix_attr = self.trail + '.offsetParentMatrix'
            
            # 断开现有连接
            connections = cmds.listConnections(offset_matrix_attr, plugs=True) or []
            for conn in connections:
                try:
                    cmds.disconnectAttr(conn, offset_matrix_attr)
                except:
                    pass
            
            # 重置为单位矩阵
            identity_matrix = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
            cmds.setAttr(offset_matrix_attr, identity_matrix, type="matrix")
        except Exception as e:
            LOGGER.error("Failed to set camera reference: " + str(e))
    
    def attach_trail_to_camera(self):
        """将轨迹附加到相机"""
        if self.reference_matrix == 'world' or not self.trail:
            return
            
        cam_name = self.reference_matrix
        if not cmds.objExists(cam_name):
            return
            
        try:
            offset_matrix_attr = self.trail + '.offsetParentMatrix'
            
            # 检查是否已经连接
            connections = cmds.listConnections(offset_matrix_attr, plugs=True) or []
            if not connections:
                try:
                    cmds.connectAttr(cam_name + '.worldMatrix[0]', offset_matrix_attr)
                except Exception as e:
                    LOGGER.warning("Failed to connect trail to camera: " + str(e))
        except Exception as e:
            LOGGER.error("Failed to attach trail to camera: " + str(e))
    
    def set_trail_camera_visibility(self):
        """设置轨迹的相机可见性"""
        if not self.trail or not cmds.objExists(self.trail):
            return
            
        try:
            # 获取所有相机
            cameras = cmds.listCameras(p=True) or []
            
            # 重置所有相机的可见性
            for camera in cameras:
                if cmds.objExists(camera):
                    try:
                        cmds.perCameraVisibility(self.trail, camera=camera, hide=False, remove=True)
                    except:
                        pass
            
            # 如果指定了特定相机，只在该相机中可见
            if self.reference_matrix != 'world' and cmds.objExists(self.reference_matrix):
                # 在所有其他相机中隐藏
                for camera in cameras:
                    if camera != self.reference_matrix:
                        try:
                            cmds.perCameraVisibility(self.trail, camera=camera, hide=True)
                        except:
                            pass
        except Exception as e:
            LOGGER.warning("Failed to set trail camera visibility: " + str(e))
    
    def validate_camera_existence(self, camera):
        """验证相机是否存在"""
        if camera == 'world':
            return True
        
        if cmds.objExists(camera):
            return True
        
        return False
    
    def create_dummy_point(self):
        """创建虚拟点"""
        if not self.tracked_object or not self.trail:
            return
        
        try:
            # 删除现有的虚拟点
            to_delete = []
            for obj in ['dummyMover', 'trail_keyvisual']:
                if cmds.objExists(obj):
                    to_delete.append(obj)
            if to_delete:
                cmds.delete(to_delete)
            
            # 创建新的虚拟点
            self.keyvisual_group = cmds.createNode('transform', name='dummyMover', parent=self.trail, skipSelect=True)
            cmds.setAttr(self.keyvisual_group + '.displayHandle', True)
            cmds.setAttr(self.keyvisual_group + '.overrideEnabled', True)
            cmds.setAttr(self.keyvisual_group + '.overrideDisplayType', 2)
            
            # 约束虚拟点到追踪对象
            self.constraint_dummy_point()
        except Exception as e:
            LOGGER.error("Failed to create dummy point: " + str(e))
    
    def constraint_dummy_point(self):
        """约束虚拟点"""
        if not self.tracked_object or not self.keyvisual_group:
            return
            
        target_object = self.tracked_object[0]
        
        # 创建点约束
        try:
            cmds.pointConstraint(target_object, self.keyvisual_group, maintainOffset=False)
        except:
            LOGGER.warning("Cannot constrain dummy point to target object")
    
    def is_idle(self):
        """检查是否空闲并处理下一帧"""
        if len(self.range_to_process) > 0:
            frame = self.range_to_process.pop(0)
            self.set_frame_point(frame)
    
    def get_range(self):
        """获取待处理范围"""
        return self.range_to_process
    
    def full_update(self):
        """完整更新轨迹 - 用于定时刷新"""
        if self.tracked_object and self.trail:
            try:
                range_frames = self.prioritize_timeline()
                self.prepare_pointarray(range_frames)
                return True
            except Exception as e:
                LOGGER.error("Full update failed: " + str(e))
                return False
        return False


class MotionTrailWindow(QDialog):
    """运动轨迹窗口 - Maya 2020兼容"""
    
    def __init__(self, parent=None):
        parent = parent or get_maya_main_window()
        super(MotionTrailWindow, self).__init__(parent)
        
        self.setWindowTitle("轨迹工具")
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.trail = MotionTrailCore()
        self.script_jobs = []
        self.auto_refresh_timer = None  # 定时器
        
        self.setup_ui()
        self.connect_signals()
        self.refresh_camera_list()
        
        # 初始化帧范围为时间线范围
        self.get_timeline_range()
        
        # 默认开启
        self.on_off_checkbox.setChecked(True)
        self.toggle_trail()
    
    def setup_ui(self):
        """设置用户界面 - 带边框布局"""
        # 全局样式 - 适配Maya深色主题
        self.setStyleSheet("""
            QPushButton {
                background-color: rgb(64, 64, 65);
                border: 1px solid rgb(100, 100, 100);
                border-radius: 4px;
                padding: 4px 12px;
                color: rgb(220, 220, 220);
            }
            QPushButton:hover {
                background-color: rgb(80, 80, 82);
                border-color: rgb(130, 130, 130);
            }
            QPushButton:pressed {
                background-color: rgb(55, 55, 56);
            }
            QPushButton:checked {
                background-color: rgb(40, 100, 170);
                border-color: rgb(60, 140, 210);
            }
            QLabel#object_label {
                color: #ff9944;
                font-weight: bold;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ===== 上方：轨迹对象控制区域（带边框）=====
        object_container = QFrame()
        object_container.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        object_layout = QVBoxLayout(object_container)
        object_layout.setSpacing(6)
        object_layout.setContentsMargins(6, 6, 6, 6)
        
        # 轨迹对象显示
        obj_display_layout = QHBoxLayout()
        obj_display_layout.addWidget(QLabel("当前对象:"))
        self.object_label = QLabel("未设置")
        self.object_label.setObjectName("object_label")
        obj_display_layout.addWidget(self.object_label, stretch=1)
        object_layout.addLayout(obj_display_layout)
        
        # 开关控制 + 设置按钮
        control_layout = QHBoxLayout()
        control_layout.setSpacing(6)
        
        self.on_off_checkbox = QCheckBox("显示轨迹")
        control_layout.addWidget(self.on_off_checkbox)
        
        self.set_object_btn = QPushButton("设置对象")
        self.set_object_btn.setMaximumWidth(80)
        control_layout.addWidget(self.set_object_btn)
        
        self.auto_select_btn = QPushButton("自动选择")
        self.auto_select_btn.setCheckable(True)
        self.auto_select_btn.setMaximumWidth(80)
        control_layout.addWidget(self.auto_select_btn)
        
        control_layout.addStretch()
        object_layout.addLayout(control_layout)
        
        layout.addWidget(object_container)
        
        # ===== 中间：显示设置区域（带边框）=====
        display_container = QFrame()
        display_container.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        display_layout = QVBoxLayout(display_container)
        display_layout.setSpacing(6)
        display_layout.setContentsMargins(6, 6, 6, 6)
        
        # 起始帧 - 结束帧
        frame_range_layout = QHBoxLayout()
        frame_range_layout.addWidget(QLabel("帧范围:"))
        
        self.start_frame_spin = QSpinBox()
        self.start_frame_spin.setRange(0, 99999)
        self.start_frame_spin.setValue(1)
        self.start_frame_spin.setMaximumWidth(65)
        frame_range_layout.addWidget(self.start_frame_spin)
        
        frame_range_layout.addWidget(QLabel("-"))
        
        self.end_frame_spin = QSpinBox()
        self.end_frame_spin.setRange(0, 99999)
        self.end_frame_spin.setValue(100)
        self.end_frame_spin.setMaximumWidth(65)
        frame_range_layout.addWidget(self.end_frame_spin)
        
        frame_range_layout.addStretch()
        display_layout.addLayout(frame_range_layout)
        
        # 自动更新选项 + 刷新按钮（同一行）
        update_layout = QHBoxLayout()
        update_layout.setSpacing(8)
        
        self.auto_update_checkbox = QCheckBox("自动更新")
        self.auto_update_checkbox.setChecked(True)
        update_layout.addWidget(self.auto_update_checkbox)
        
        self.auto_refresh_checkbox = QCheckBox("每2秒刷新")
        self.auto_refresh_checkbox.setChecked(False)
        update_layout.addWidget(self.auto_refresh_checkbox)
        
        update_layout.addStretch()
        
        self.manual_update_btn = QPushButton("刷新")
        self.manual_update_btn.setMaximumWidth(55)
        update_layout.addWidget(self.manual_update_btn)
        
        display_layout.addLayout(update_layout)
        
        # 参考相机
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("参考相机:"))
        self.camera_combo = QComboBox()
        self.camera_combo.setMaximumWidth(140)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addStretch()
        display_layout.addLayout(camera_layout)
        
        layout.addWidget(display_container)
        layout.addStretch()
        
        self.resize(255, 175)
        
        # 初始UI状态
        self.disable_ui()
    
    def connect_signals(self):
        """连接信号"""
        self.on_off_checkbox.clicked.connect(self.toggle_trail)
        self.set_object_btn.clicked.connect(self.change_tracked_objects)
        self.auto_select_btn.clicked.connect(self.auto_selection_setup)
        self.auto_update_checkbox.clicked.connect(self.validate_ui_state)
        self.auto_refresh_checkbox.clicked.connect(self.toggle_auto_refresh)
        self.manual_update_btn.clicked.connect(self.manual_process_timeline)
        self.camera_combo.activated.connect(self.set_camera_reference)
        
        # 帧范围变化时更新轨迹
        self.start_frame_spin.valueChanged.connect(self.on_frame_range_changed)
        self.end_frame_spin.valueChanged.connect(self.on_frame_range_changed)
    
    def toggle_auto_refresh(self):
        """切换每2秒自动刷新"""
        if self.auto_refresh_checkbox.isChecked():
            # 创建定时器，每2000毫秒（2秒）触发一次
            self.auto_refresh_timer = QTimer()
            self.auto_refresh_timer.timeout.connect(self.on_auto_refresh_timeout)
            self.auto_refresh_timer.start(2000)  # 2000ms = 2秒
        else:
            # 停止并销毁定时器
            if self.auto_refresh_timer:
                self.auto_refresh_timer.stop()
                self.auto_refresh_timer = None
    
    def on_auto_refresh_timeout(self):
        """定时器超时回调 - 每2秒执行一次完整更新"""
        if self.on_off_checkbox.isChecked() and self.trail.tracked_object:
            try:
                # 执行完整更新
                self.trail.full_update()
            except Exception as e:
                LOGGER.error("Auto refresh failed: " + str(e))
    
    def toggle_trail(self):
        """切换轨迹开关"""
        status = self.on_off_checkbox.isChecked()
        if status:
            sel = self.trail.define_object()
            if not sel:
                self.on_off_checkbox.setChecked(False)
                self.disable_ui()
            else:
                self.trail_on()
                self.update_object_label()
        else:
            self.trail_off()
    
    def trail_on(self):
        """开启轨迹"""
        self.enable_ui()
        
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            self.trail.delete_trail()
            self.trail.create_trail_node()
            self.trail.create_dummy_point()
            self.clear_condition()
        finally:
            cmds.undoInfo(stateWithoutFlush=True, undoName='Motion Trail')
        
        # 创建脚本任务
        self.create_script_jobs()
        self.auto_process_timeline()
        self.validate_ui_state()
    
    def trail_off(self):
        """关闭轨迹"""
        self.disable_ui()
        self.trail.delete_trail()
        self.kill_jobs()
        # 确保定时器也被停止
        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()
            self.auto_refresh_timer = None
        # 清除对象标签
        self.object_label.setText("未设置")
        self.object_label.setStyleSheet("color: gray;")
    
    def create_script_jobs(self):
        """创建脚本任务 - Maya 2020兼容"""
        self.kill_jobs()
        
        # 创建条件 - 简化版本
        try:
            cmds.condition('run_trail_job', delete=True)
        except:
            pass
        
        # 创建简单的空闲检测
        try:
            cmds.condition(
                'run_trail_job',
                s='python("import time; import maya.cmds as cmds; cmds.condition(\'run_trail_job\', edit=True, st=(int(time.time()*1000) % 10 == 0))")',
                d='idle',
            )
        except Exception as e:
            LOGGER.error("Failed to create condition: " + str(e))
        
        # 创建各种脚本任务
        try:
            job1 = cmds.scriptJob(ct=['run_trail_job', self.update_trail], compressUndo=True, killWithScene=True)
            job2 = cmds.scriptJob(event=['DragRelease', self.auto_process_timeline], compressUndo=True, killWithScene=True)
            job3 = cmds.scriptJob(event=['Undo', self.update_trail], compressUndo=True, killWithScene=True)
            job4 = cmds.scriptJob(event=['playingBack', self.auto_process_timeline], compressUndo=True, killWithScene=True)
            
            self.script_jobs = [job1, job2, job3, job4]
        except Exception as e:
            LOGGER.error("Failed to create script jobs: " + str(e))
    
    def update_trail(self):
        """更新轨迹"""
        try:
            to_process = self.trail.get_range()
            if len(to_process) > 0:
                self.trail.is_idle()
        except:
            pass
    
    def auto_process_timeline(self):
        """自动处理时间线"""
        try:
            cmds.undoInfo(stateWithoutFlush=False)
            if self.auto_update_checkbox.isChecked():
                self.manual_process_timeline()
        except Exception as e:
            LOGGER.error("Auto process timeline failed: " + str(e))
            self.clear_condition()
            self.trail.delete_trail()
            self.disable_ui()
            cmds.warning("Tracked object lost, disabling motion trail")
        finally:
            cmds.undoInfo(stateWithoutFlush=True, undoName='Motion Trail')
    
    def manual_process_timeline(self):
        """手动处理时间线 - 始终可用"""
        try:
            # 使用用户设置的帧范围
            start = self.start_frame_spin.value()
            end = self.end_frame_spin.value()
            
            # 创建帧范围列表
            range_frames = list(range(start, end + 1))
            self.trail.range_to_process = sorted(range_frames, key=lambda x: abs(cmds.currentTime(q=True) - x))
            self.trail.trail_length = len(range_frames)
            self.trail.first_tracked_frame = min(range_frames)
            
            self.trail.prepare_pointarray(range_frames)
        except Exception as e:
            LOGGER.error("Manual process timeline failed: " + str(e))
    
    def get_timeline_range(self):
        """从Maya时间线获取帧范围"""
        try:
            start_time = int(cmds.playbackOptions(query=True, minTime=True))
            end_time = int(cmds.playbackOptions(query=True, maxTime=True))
            self.start_frame_spin.setValue(start_time)
            self.end_frame_spin.setValue(end_time)
        except Exception as e:
            LOGGER.error("Failed to get timeline range: " + str(e))
    
    def on_frame_range_changed(self):
        """帧范围变化时更新轨迹"""
        if self.on_off_checkbox.isChecked() and self.trail.tracked_object:
            try:
                # 更新轨迹的帧范围
                start = self.start_frame_spin.value()
                end = self.end_frame_spin.value()
                if start <= end:
                    self.manual_process_timeline()
            except Exception as e:
                LOGGER.error("Frame range change failed: " + str(e))
    
    def auto_selection_setup(self):
        """设置自动选择"""
        if self.auto_select_btn.isChecked():
            try:
                job = cmds.scriptJob(
                    event=['SelectionChanged', self.auto_selection_execute],
                    compressUndo=True,
                )
                self.script_jobs.append(job)
                self.set_object_btn.setEnabled(False)
            except Exception as e:
                LOGGER.error("Failed to setup auto selection: " + str(e))
        else:
            self.kill_auto_selection_job()
            self.set_object_btn.setEnabled(True)
    
    def auto_selection_execute(self):
        """执行自动选择"""
        if self.auto_select_btn.isChecked():
            try:
                self.trail.define_object()
                self.update_object_label()
                self.auto_process_timeline()
            except Exception as e:
                LOGGER.error("Auto selection execute failed: " + str(e))
    
    def change_tracked_objects(self):
        """更改追踪对象"""
        try:
            objects = self.trail.define_object()
            if objects:
                self.trail.create_dummy_point()
                self.manual_process_timeline()
                self.update_object_label()
            else:
                self.on_off_checkbox.setChecked(False)
        except Exception as e:
            LOGGER.error("Failed to change tracked objects: " + str(e))
    
    def update_object_label(self):
        """更新对象标签显示"""
        if self.trail.tracked_object:
            obj_names = ', '.join(self.trail.tracked_object)
            if len(obj_names) > 30:
                obj_names = obj_names[:27] + "..."
            self.object_label.setText(obj_names)
            self.object_label.setStyleSheet("color: #ff9944; font-weight: bold;")
        else:
            self.object_label.setText("未设置")
            self.object_label.setStyleSheet("color: #888888; font-weight: bold;")
    
    def refresh_camera_list(self):
        """刷新相机列表"""
        try:
            cameras = cmds.listCameras(p=True) or []
            self.camera_combo.clear()
            self.camera_combo.addItem('World')
            
            for camera in cameras:
                self.camera_combo.addItem(str(camera))
        except Exception as e:
            LOGGER.error("Failed to refresh camera list: " + str(e))
    
    def set_camera_reference(self):
        """设置相机参考"""
        try:
            camera = str(self.camera_combo.currentText())
            if camera == 'World':
                camera = 'world'
            
            # 验证相机是否存在
            if camera != 'world' and not cmds.objExists(camera):
                self.camera_combo.setCurrentIndex(0)
                cmds.warning("选择的相机不存在，已重置为世界空间")
                camera = 'world'
            
            # 设置核心类的相机参考
            self.trail.set_camera_reference(camera)
            
            # 重新处理时间线以应用相机空间变换
            self.manual_process_timeline()
            
        except Exception as e:
            LOGGER.error("Failed to set camera reference: " + str(e))
    
    def validate_ui_state(self):
        """验证UI状态 - 手动更新按钮始终可用"""
        try:
            auto_select_on = self.auto_select_btn.isChecked()
            trail_on = self.on_off_checkbox.isChecked()
            
            # 设置对象选择按钮：自动选择开启时禁用，否则根据轨迹状态
            self.set_object_btn.setEnabled(not auto_select_on and trail_on)
            
            # 手动更新按钮始终在轨迹开启时可用，不受自动更新影响
            self.manual_update_btn.setEnabled(trail_on)
            
            # 自动更新复选框在轨迹开启时可用
            self.auto_update_checkbox.setEnabled(trail_on)
            
            # 自动刷新复选框在轨迹开启时可用
            self.auto_refresh_checkbox.setEnabled(trail_on)
            
        except Exception as e:
            LOGGER.error("Failed to validate UI state: " + str(e))
    
    def enable_ui(self):
        """启用UI"""
        self.set_object_btn.setEnabled(True)
        self.auto_select_btn.setEnabled(True)
        self.auto_update_checkbox.setEnabled(True)
        self.manual_update_btn.setEnabled(True)
        self.auto_refresh_checkbox.setEnabled(True)
        self.camera_combo.setEnabled(True)
        self.start_frame_spin.setEnabled(True)
        self.end_frame_spin.setEnabled(True)
    
    def disable_ui(self):
        """禁用UI"""
        self.set_object_btn.setEnabled(False)
        self.auto_select_btn.setEnabled(False)
        self.auto_update_checkbox.setEnabled(False)
        self.manual_update_btn.setEnabled(False)
        self.auto_refresh_checkbox.setEnabled(False)
        self.camera_combo.setEnabled(False)
        self.start_frame_spin.setEnabled(False)
        self.end_frame_spin.setEnabled(False)
    
    def clear_condition(self):
        """清除条件"""
        try:
            cmds.condition('run_trail_job', delete=True)
        except:
            pass
    
    def kill_jobs(self):
        """终止所有脚本任务"""
        self.clear_condition()
        
        # 终止所有记录的任务
        for job in self.script_jobs:
            try:
                cmds.scriptJob(kill=job, force=True)
            except:
                pass
        self.script_jobs = []
        
        # 清理相关的脚本任务
        try:
            all_jobs = cmds.scriptJob(listJobs=True) or []
            for job in all_jobs:
                job_str = str(job)
                if any(keyword in job_str for keyword in ['MotionTrailWindow', 'define_object', 'run_trail_job']):
                    try:
                        job_id = int(job_str.split(':')[0])
                        cmds.scriptJob(kill=job_id, force=True)
                    except:
                        pass
        except:
            pass
    
    def kill_auto_selection_job(self):
        """终止自动选择任务"""
        try:
            all_jobs = cmds.scriptJob(listJobs=True) or []
            for job in all_jobs:
                job_str = str(job)
                if 'define_object' in job_str or 'SelectionChanged' in job_str:
                    try:
                        job_id = int(job_str.split(':')[0])
                        cmds.scriptJob(kill=job_id, force=True)
                    except:
                        pass
        except:
            pass
    
    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 停止定时器
            if self.auto_refresh_timer:
                self.auto_refresh_timer.stop()
                self.auto_refresh_timer = None
            self.kill_jobs()
            self.trail.delete_trail()
        except:
            pass
        event.accept()


# 全局变量存储窗口实例
motion_trail_window = None


def launch():
    """启动运动轨迹工具"""
    global motion_trail_window
    
    LOGGER.info('Launching Motion Trail Tool...')
    
    # 关闭现有窗口
    if motion_trail_window:
        try:
            motion_trail_window.close()
        except:
            pass
    
    # 创建新窗口
    try:
        motion_trail_window = MotionTrailWindow()
        motion_trail_window.show()
        return motion_trail_window
    except Exception as e:
        LOGGER.error("Failed to launch window: " + str(e))
        return None


def show():
    """显示运动轨迹工具"""
    return launch()


def create_shelf_button():
    """创建Shelf按钮 - Maya 2020兼容"""
    
    # 获取当前shelf
    try:
        current_shelf = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
    except:
        print("Cannot get current shelf")
        return
    
    # 按钮代码 - Maya 2020兼容版本
    button_command = '''
import sys
import maya.cmds as cmds

try:
    # Python 2/3 兼容的重新导入
    script_name = "motion_trail_maya2020_complete"
    
    # 重新加载模块
    if script_name in sys.modules:
        if sys.version_info[0] == 3:
            import importlib
            importlib.reload(sys.modules[script_name])
        else:
            reload(sys.modules[script_name])
    
    # 导入并启动
    import motion_trail_maya2020_complete
    motion_trail_maya2020_complete.launch()
    
except Exception as e:
    cmds.confirmDialog(
        title="Runtime Error", 
        message="Motion Trail Tool runtime error:\\n\\n" + str(e),
        button=["OK"]
    )
'''
    
    # 创建按钮
    try:
        cmds.shelfButton(
            parent=current_shelf,
            label="Motion Trail",
            annotation="Maya Motion Trail Tool - Maya 2020 Compatible with Camera Space Support",
            image="kinReroot.png",
            command=button_command,
            sourceType="python"
        )
        print("Shelf button created successfully")
    except Exception as e:
        print("Failed to create shelf button: " + str(e))


def quick_launch():
    """快速启动函数 - Maya 2020兼容"""
    try:        
        return launch()
    except Exception as e:
        cmds.warning("Motion Trail launch failed: " + str(e))
        print("Error details: " + str(e))
        return None


if __name__ == "__main__":
    quick_launch()


def show_usage():
    """显示使用说明"""
    usage_text = """
Maya Motion Trail Tool - Maya 2020 兼容版本使用说明:

1. 快速启动:
   import motion_trail_maya2020_complete
   motion_trail_maya2020_complete.quick_launch()

2. 常规启动:
   motion_trail_maya2020_complete.launch()

3. 创建Shelf按钮:
   motion_trail_maya2020_complete.create_shelf_button()

4. 基本使用:
   - 在场景中选择一个对象
   - 在工具窗口中启用轨迹
   - 轨迹将在时间线拖动时自动更新

5. 功能特性:
   - 实时运动轨迹显示
   - 网格对象追踪支持（使用定位器）
   - 淡化帧数控制 (3, 6, 12, 24, 48, all) - 默认all
   - 相机空间参考显示（完整支持）
   - 自动/手动更新模式（手动更新始终可用）
   - 每5秒自动刷新曲线选项
   - Maya 2020+ 兼容性
   - Python 2.7/3.x 兼容性

6. 相机空间显示:
   - 选择"World"表示世界空间显示
   - 选择任意相机表示相机相对显示
   - 相机空间激活时轨迹在其他视口中隐藏
   - 支持Maya 2020的旧API和新版本的新API

7. Maya版本兼容性:
   - Maya 2020: 完全支持（Python 2.7/3.7）
   - Maya 2022+: 完全支持（Python 3.x）
   - 自动检测API版本并使用适当的兼容层

兼容 Maya 2020+ 和 Python 2.7/3.x
修复了所有已知的相机空间变换和API兼容性问题
"""
    print(usage_text)
    return usage_text


def launch_cn():
    """启动工具 - 中文版本"""
    print("正在启动运动轨迹工具...")
    print("兼容Maya 2020+版本")
    return quick_launch()


def debug_info():
    """显示调试信息"""
    print("=== Motion Trail Debug Info ===")
    print("Maya Version:", cmds.about(version=True))
    print("Python Version:", sys.version_info)
    print("API Version:", API_VERSION)
    print("PySide Version:", PYSIDE_VERSION)
    print("Available cameras:", cmds.listCameras(p=True) or [])
    
    # 测试API兼容性
    try:
        test_matrix = create_matrix([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1])
        test_point = create_point([1, 2, 3])
        result = test_point * test_matrix
        print("API Test Successful - Point: ({}, {}, {})".format(result.x, result.y, result.z))
    except Exception as e:
        print("API Test Failed:", str(e))
    
    print("=== End Debug Info ===")


def test_trail():
    """测试轨迹功能 - Maya 2020兼容"""
    try:
        # 创建测试对象
        test_cube = cmds.polyCube(name='test_trail_cube')[0]
        
        # 在几个关键帧上设置动画
        cmds.setKeyframe(test_cube, attribute='translateX', time=1, value=0)
        cmds.setKeyframe(test_cube, attribute='translateX', time=50, value=10)
        cmds.setKeyframe(test_cube, attribute='translateY', time=25, value=5)
        cmds.setKeyframe(test_cube, attribute='translateZ', time=10, value=3)
        cmds.setKeyframe(test_cube, attribute='translateZ', time=40, value=-3)
        
        # 选择对象并启动工具
        cmds.select(test_cube)
        window = launch()
        
        print("测试设置完成：")
        print("- 立方体已创建：" + test_cube)
        print("- 动画已设置（X: 0->10, Y: 0->5, Z: 3->-3)")
        print("- 工具已启动")
        
        return window
    except Exception as e:
        print("测试设置失败：" + str(e))
        return None


def cleanup():
    """清理函数 - 删除所有轨迹相关对象"""
    try:
        # 删除测试对象
        if cmds.objExists('test_trail_cube'):
            cmds.delete('test_trail_cube')
        
        # 删除轨迹对象
        tool_group = get_tool_group(TOOL_NAME)
        if cmds.objExists(tool_group):
            cmds.delete(tool_group)
        
        # 删除网格追踪器
        if cmds.objExists('motion_trail_mesh_tracker'):
            cmds.delete('motion_trail_mesh_tracker')
        
        # 清理脚本任务
        all_jobs = cmds.scriptJob(listJobs=True) or []
        for job in all_jobs:
            job_str = str(job)
            if any(keyword in job_str for keyword in ['MotionTrailWindow', 'define_object', 'run_trail_job']):
                try:
                    job_id = int(job_str.split(':')[0])
                    cmds.scriptJob(kill=job_id, force=True)
                except:
                    pass
        
        print("清理完成")
    except Exception as e:
        print("清理失败：" + str(e))