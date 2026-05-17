import maya.cmds as cmds
import subprocess
import os
import sys
import datetime
import textwrap

class SVNCommitUI(object):
    def __init__(self):
        self.window_name = "svnCommitWindow"
        self.window_title = "SVN 提交工具"
        
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)
        
        self.window = cmds.window(
            self.window_name,
            title=self.window_title,
            widthHeight=(520, 540),
            sizeable=True,
            resizeToFitChildren=False
        )
        
        self.main_form = cmds.formLayout(numberOfDivisions=100)
        
        # 初始化实例变量
        self.current_file_text = None
        self.file_path_field = None
        self.commit_message_field = None
        self.log_field = None
        self.path_frame = None
        self.commit_frame = None
        self.btn_row1 = None
        self.btn_row2 = None
        self.log_frame = None
        
        self.build_ui()
        cmds.showWindow(self.window)
        self.tortoise_proc = self.find_tortoise_proc()
        self.update_file_info()
    
    def find_tortoise_proc(self):
        possible_paths = [
            r"C:\\Program Files\\TortoiseSVN\\bin\\TortoiseProc.exe",
            r"C:\\Program Files (x86)\\TortoiseSVN\\bin\\TortoiseProc.exe",
        ]
        
        try:
            import winreg
            for reg_path in [r"SOFTWARE\\TortoiseSVN", r"SOFTWARE\\WOW6432Node\\TortoiseSVN"]:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                    install_path = winreg.QueryValueEx(key, "Directory")[0]
                    if install_path:
                        proc_path = os.path.join(install_path, "bin", "TortoiseProc.exe")
                        if os.path.exists(proc_path):
                            possible_paths.insert(0, proc_path)
                    winreg.CloseKey(key)
                except:
                    pass
        except:
            pass
        
        for path in possible_paths:
            if os.path.exists(path):
                self.log_message("找到 TortoiseSVN: " + path)
                return path
        
        self.log_message("警告: 未找到TortoiseSVN", "warning")
        return None
    
    def build_ui(self):
        # 标题
        title_text = cmds.text(label="SVN 提交工具", font="boldLabelFont", height=24)
        sep_title = cmds.separator(height=8, style='in')
        
        # SVN操作路径框架
        self.path_frame = cmds.frameLayout(
            label="SVN 操作路径",
            collapsable=False,
            marginWidth=6,
            marginHeight=6,
            borderStyle='etchedIn',
            labelAlign='center'
        )
        
        cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
        
        # 当前文件显示
        self.current_file_text = cmds.text(
            label="当前文件: 未保存",
            align='left',
            font="smallPlainLabelFont",
            height=20,
            annotation="当前打开的Maya文件完整路径"
        )
        
        cmds.separator(height=3, style='none')
        
        # 路径行 - 文件目录贴右边
        cmds.rowLayout(numberOfColumns=5, 
                      columnAttach=[(1, 'left', 0), (2, 'both', 2), (3, 'left', 0), (4, 'left', 0), (5, 'right', 0)],
                      columnWidth5=(40, 260, 35, 45, 80),
                      adjustableColumn=2)
        cmds.text(label="路径:", align='left', height=24)
        self.file_path_field = cmds.textField(
            editable=True,
            height=24,
            backgroundColor=(0.2, 0.2, 0.2),
            annotation="可手动输入或使用右侧按钮快速设置SVN操作路径"
        )
        cmds.button(label="...", height=24, width=35,
                   backgroundColor=(0.35, 0.4, 0.5),
                   annotation="浏览选择目录",
                   command=lambda x: self.browse_folder())
        cmds.button(label="↑", height=24, width=45,
                   backgroundColor=(0.3, 0.3, 0.3),
                   annotation="上一级目录",
                   command=lambda x: self.set_path_to_parent())
        cmds.button(label="文件目录", height=24, width=80,
                   backgroundColor=(0.3, 0.3, 0.3),
                   annotation="设置为当前文件所在目录",
                   command=lambda x: self.set_path_to_file_dir())
        cmds.setParent('..')
        
        cmds.setParent('..')
        cmds.setParent('..')
        
        # 提交信息框架
        self.commit_frame = cmds.frameLayout(
            label="提交信息",
            collapsable=False,
            marginWidth=6,
            marginHeight=6,
            borderStyle='etchedIn',
            labelAlign='center'
        )
        
        commit_inner_form = cmds.formLayout(numberOfDivisions=100)
        
        self.commit_message_field = cmds.scrollField(
            wordWrap=True,
            height=70,
            text="",
            backgroundColor=(0.15, 0.15, 0.15),
            annotation="输入提交说明"
        )
        
        helper_form = cmds.formLayout(numberOfDivisions=100)
        btn_modify = cmds.button(label="修改内容", height=22, backgroundColor=(0.35, 0.38, 0.42),
                   command=lambda x: self.set_message("修改内容: "))
        btn_timestamp = cmds.button(label="时间戳", height=22, backgroundColor=(0.35, 0.38, 0.42),
                   command=lambda x: self.insert_timestamp())
        cmds.formLayout(helper_form, edit=True,
            attachForm=[(btn_timestamp, 'top', 0), (btn_timestamp, 'right', 0), (btn_timestamp, 'bottom', 0),
                        (btn_modify, 'top', 0), (btn_modify, 'bottom', 0)],
            attachPosition=[(btn_modify, 'left', 0, 60), (btn_modify, 'right', 0, 80),
                            (btn_timestamp, 'left', 0, 80)])
        cmds.setParent('..')
        
        cmds.formLayout(commit_inner_form, edit=True,
            attachForm=[(self.commit_message_field, 'top', 0), (self.commit_message_field, 'left', 0), (self.commit_message_field, 'right', 0),
                        (helper_form, 'left', 0), (helper_form, 'right', 0), (helper_form, 'bottom', 0)],
            attachControl=[(self.commit_message_field, 'bottom', 3, helper_form)])
        
        cmds.setParent('..')
        cmds.setParent('..')
        
        # SVN操作按钮行 - 等宽
        self.btn_row1 = cmds.formLayout(numberOfDivisions=100)
        
        btn_commit = cmds.button(label="SVN提交", height=26,
                   backgroundColor=(0.2, 0.55, 0.2),
                   annotation="提交更改到SVN仓库",
                   command=lambda x: self.svn_commit())
        btn_update = cmds.button(label="SVN更新", height=26,
                   backgroundColor=(0.3, 0.35, 0.5),
                   annotation="从SVN仓库更新文件",
                   command=lambda x: self.svn_update())
        btn_cleanup = cmds.button(label="清理", height=26,
                   backgroundColor=(0.5, 0.48, 0.25),
                   annotation="清理SVN工作副本",
                   command=lambda x: self.svn_cleanup())
        btn_log = cmds.button(label="查看日志", height=26,
                   backgroundColor=(0.5, 0.35, 0.15),
                   annotation="查看SVN提交日志",
                   command=lambda x: self.svn_log())
        btn_browse = cmds.button(label="浏览仓库", height=26,
                   backgroundColor=(0.35, 0.38, 0.42),
                   annotation="浏览SVN仓库",
                   command=lambda x: self.svn_browse())
        
        cmds.formLayout(self.btn_row1, edit=True,
            attachForm=[(btn_commit, 'top', 0), (btn_commit, 'left', 0), (btn_commit, 'bottom', 0),
                        (btn_update, 'top', 0), (btn_update, 'bottom', 0),
                        (btn_cleanup, 'top', 0), (btn_cleanup, 'bottom', 0),
                        (btn_log, 'top', 0), (btn_log, 'bottom', 0),
                        (btn_browse, 'top', 0), (btn_browse, 'right', 0), (btn_browse, 'bottom', 0)],
            attachPosition=[
                (btn_commit, 'right', 1, 20),
                (btn_update, 'left', 1, 20), (btn_update, 'right', 1, 40),
                (btn_cleanup, 'left', 1, 40), (btn_cleanup, 'right', 1, 60),
                (btn_log, 'left', 1, 60), (btn_log, 'right', 1, 80),
                (btn_browse, 'left', 1, 80)])
        
        cmds.setParent('..')
        
        # 底部操作按钮行 - 等宽
        self.btn_row2 = cmds.formLayout(numberOfDivisions=100)
        
        btn_open = cmds.button(label="打开文件所在目录", height=26,
                   backgroundColor=(0.3, 0.3, 0.3),
                   annotation="在资源管理器中打开文件目录",
                   command=lambda x: self.open_folder())
        btn_refresh = cmds.button(label="刷新状态", height=26,
                   backgroundColor=(0.3, 0.3, 0.3),
                   annotation="刷新文件信息",
                   command=lambda x: self.update_file_info())
        btn_history = cmds.button(label="历史版本工具", height=26,
                   backgroundColor=(0.35, 0.4, 0.5),
                   annotation="打开SVN历史版本查看工具",
                   command=lambda x: self.open_history_tool())
        btn_close = cmds.button(label="关闭窗口", height=26,
                   backgroundColor=(0.5, 0.25, 0.25),
                   annotation="关闭窗口",
                   command=lambda x: self.close_window())
        
        cmds.formLayout(self.btn_row2, edit=True,
            attachForm=[(btn_open, 'top', 0), (btn_open, 'left', 0), (btn_open, 'bottom', 0),
                        (btn_refresh, 'top', 0), (btn_refresh, 'bottom', 0),
                        (btn_history, 'top', 0), (btn_history, 'bottom', 0),
                        (btn_close, 'top', 0), (btn_close, 'right', 0), (btn_close, 'bottom', 0)],
            attachPosition=[(btn_open, 'right', 1, 25),
                            (btn_refresh, 'left', 1, 25), (btn_refresh, 'right', 1, 50),
                            (btn_history, 'left', 1, 50), (btn_history, 'right', 1, 75),
                            (btn_close, 'left', 1, 75)])
        
        cmds.setParent('..')
        
        # 操作日志框架
        self.log_frame = cmds.frameLayout(
            label="操作日志",
            collapsable=False,
            marginWidth=6,
            marginHeight=6,
            borderStyle='etchedIn',
            labelAlign='center'
        )
        
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        
        cmds.button(
            label="清空日志",
            command=lambda x: cmds.scrollField(self.log_field, edit=True, text=""),
            height=20,
            align='right',
            backgroundColor=(0.35, 0.35, 0.35)
        )
        
        self.log_field = cmds.scrollField(
            wordWrap=True,
            height=140,
            editable=False,
            backgroundColor=(0.1, 0.1, 0.1),
            text="初始化中...\n"
        )
        
        cmds.setParent('..')
        cmds.setParent('..')
        
        # 底部状态提示
        sep_bottom = cmds.separator(height=8, style='in')
        hint_text = cmds.text(label="提示: 可修改SVN操作路径以对任意父级目录进行版本控制操作", align='left',
                             height=16, font="smallPlainLabelFont")
        
        # 设置 formLayout 约束
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(title_text, 'top', 5), (title_text, 'left', 5), (title_text, 'right', 5),
                                  (sep_title, 'left', 5), (sep_title, 'right', 5)],
                       attachControl=[(sep_title, 'top', 3, title_text)])
        
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(self.path_frame, 'left', 5), (self.path_frame, 'right', 5)],
                       attachControl=[(self.path_frame, 'top', 3, sep_title)])
        
        # commit_frame 在 path_frame 和 btn_row1 之间，高度自适应
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(self.commit_frame, 'left', 5), (self.commit_frame, 'right', 5)],
                       attachControl=[(self.commit_frame, 'top', 5, self.path_frame),
                                     (self.commit_frame, 'bottom', 5, self.btn_row1)])
        
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(self.btn_row1, 'left', 10), (self.btn_row1, 'right', 10)],
                       attachControl=[(self.btn_row1, 'bottom', 5, self.btn_row2)])
        
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(self.btn_row2, 'left', 10), (self.btn_row2, 'right', 10)],
                       attachControl=[(self.btn_row2, 'bottom', 5, self.log_frame)])
        
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(self.log_frame, 'left', 5), (self.log_frame, 'right', 5)],
                       attachControl=[(self.log_frame, 'bottom', 3, sep_bottom)])
        
        cmds.formLayout(self.main_form, edit=True,
                       attachForm=[(sep_bottom, 'left', 5), (sep_bottom, 'right', 5),
                                  (hint_text, 'left', 5), (hint_text, 'right', 5), (hint_text, 'bottom', 3)],
                       attachControl=[(sep_bottom, 'bottom', 3, hint_text)])
    
    def open_history_tool(self):
        try:
            from svn_version_manager import SVNHistoryUI
            history_ui = SVNHistoryUI()
            history_ui.show()
            self.log_message("已打开历史版本工具")
        except ImportError:
            try:
                import maya.mel as mel
                mel.eval('python("from svn_version_manager import SVNHistoryUI; SVNHistoryUI().show()")')
            except:
                self.log_message("无法打开历史版本工具，请确保脚本已正确安装", "warning")
    
    def update_file_info(self):
        try:
            current_file = cmds.file(query=True, sceneName=True)
            
            if not current_file:
                self.log_message("场景文件未保存", "warning")
                if self.current_file_text:
                    cmds.text(self.current_file_text, edit=True, label="当前文件: 未保存")
                cmds.textField(self.file_path_field, edit=True, text="")
                return
            
            if self.current_file_text:
                display_path = current_file
                if len(display_path) > 80:
                    display_path = "..." + display_path[-77:]
                cmds.text(self.current_file_text, edit=True, label="当前文件: " + display_path)
            
            file_dir = os.path.dirname(os.path.normpath(current_file))
            cmds.textField(self.file_path_field, edit=True, text=file_dir)
            
            self.log_message("当前文件: " + os.path.basename(current_file))
            
            if self.is_svn_working_copy(current_file):
                self.log_message("SVN工作副本已检测到")
            else:
                self.log_message("未检测到SVN工作副本", "warning")
            
        except Exception as e:
            self.log_message("更新信息失败: " + str(e), "error")
    
    def browse_folder(self):
        try:
            current_path = cmds.textField(self.file_path_field, query=True, text=True)
            start_dir = current_path if current_path and os.path.exists(current_path) else None
            
            result = cmds.fileDialog2(
                fileMode=2,
                caption="选择SVN操作的目录",
                okCaption="选择",
                startingDirectory=start_dir
            )
            if result:
                selected_path = result[0]
                cmds.textField(self.file_path_field, edit=True, text=selected_path)
                self.log_message("已选择路径: " + selected_path)
        except Exception as e:
            self.log_message("浏览文件夹失败: " + str(e), "error")
    
    def set_path_to_file_dir(self):
        current_file = cmds.file(query=True, sceneName=True)
        if current_file:
            file_dir = os.path.dirname(os.path.normpath(current_file))
            cmds.textField(self.file_path_field, edit=True, text=file_dir)
            self.log_message("已设置为文件所在目录: " + file_dir)
    
    def set_path_to_parent(self, levels=1):
        current_path = cmds.textField(self.file_path_field, query=True, text=True)
        if current_path:
            path = os.path.normpath(current_path)
            for i in range(levels):
                path = os.path.dirname(path)
                if not path or path == os.path.dirname(path):
                    break
            cmds.textField(self.file_path_field, edit=True, text=path)
            self.log_message("已设置为上级目录: " + path)
    
    def is_svn_working_copy(self, file_path):
        try:
            file_dir = os.path.dirname(os.path.normpath(file_path))
            current_dir = file_dir
            
            while current_dir and os.path.exists(current_dir):
                svn_dir = os.path.join(current_dir, ".svn")
                if os.path.exists(svn_dir) and os.path.isdir(svn_dir):
                    return True
                
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:
                    break
                current_dir = parent_dir
            
            return False
        except:
            return False
    
    def get_current_path(self):
        custom_path = cmds.textField(self.file_path_field, query=True, text=True).strip()
        
        if not custom_path:
            return None, None
        
        custom_path = os.path.normpath(custom_path)
        
        if os.path.isfile(custom_path):
            file_dir = os.path.dirname(custom_path)
            return custom_path, file_dir
        elif os.path.isdir(custom_path):
            return None, custom_path
        else:
            parent_dir = os.path.dirname(custom_path)
            if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                return custom_path, parent_dir
            else:
                return None, None
    
    def svn_commit(self):
        current_file, file_dir = self.get_current_path()
        
        if not file_dir:
            self.log_message("错误: 无效的路径！", "error")
            cmds.confirmDialog(
                title="错误",
                message="请检查文件路径是否正确！",
                button="确定",
                icon="warning"
            )
            return
        
        if current_file and os.path.isfile(current_file):
            self.log_message("正在保存场景文件...")
            cmds.file(save=True, force=True)
            self.log_message("场景文件已保存")
        
        commit_message = cmds.scrollField(self.commit_message_field, query=True, text=True)
        self.run_tortoise_command('commit', file_dir, commit_message)
    
    def svn_update(self):
        current_file, file_dir = self.get_current_path()
        
        if not file_dir:
            self.log_message("错误: 无效的路径！", "error")
            return
        
        self.run_tortoise_command('update', file_dir)
    
    def svn_cleanup(self):
        current_file, file_dir = self.get_current_path()
        
        if not file_dir:
            self.log_message("错误: 无效的路径！", "error")
            return
        
        self.run_tortoise_command('cleanup', file_dir)
    
    def svn_log(self):
        current_file, file_dir = self.get_current_path()
        
        if not file_dir:
            self.log_message("错误: 无效的路径！", "error")
            return
        
        self.run_tortoise_command('log', file_dir)
    
    def svn_browse(self):
        current_file, file_dir = self.get_current_path()
        
        if not file_dir:
            self.log_message("错误: 无效的路径！", "error")
            return
        
        self.run_tortoise_command('repobrowser', file_dir)
    
    def run_tortoise_command(self, command, path, log_message=None):
        if not self.tortoise_proc or not os.path.exists(self.tortoise_proc):
            self.log_message("错误: 未找到TortoiseSVN", "error")
            self.log_message("请手动打开文件夹并使用右键菜单操作")
            self.open_folder_in_explorer(path)
            return
        
        try:
            if not os.path.exists(path):
                self.log_message("错误: 路径不存在 - " + path, "error")
                return
            
            path = os.path.abspath(path)
            
            cmd = [self.tortoise_proc]
            cmd.append('/command:' + command)
            cmd.append('/path:' + path)
            
            if command == 'commit' and log_message and log_message.strip():
                import tempfile
                temp_file = os.path.join(tempfile.gettempdir(), 'svn_commit_msg.txt')
                try:
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(log_message)
                    cmd.append('/logmsgfile:' + temp_file)
                except:
                    safe_msg = log_message.replace('"', '""')
                    cmd.append('/logmsg:"' + safe_msg + '"')
            
            cmd.append('/closeonend:0')
            
            self.log_message("执行命令: TortoiseProc /command:" + command)
            self.log_message("路径: " + path)
            
            subprocess.Popen(cmd, shell=False)
            
            command_names = {
                'commit': '提交',
                'update': '更新',
                'cleanup': '清理',
                'log': '日志',
                'repobrowser': '仓库浏览器'
            }
            
            self.log_message(command_names.get(command, command) + "窗口已打开")
            
        except Exception as e:
            self.log_message("执行失败: " + str(e), "error")
            self.log_message("尝试备用方法...")
            self.open_folder_in_explorer(path)
    
    def open_folder_in_explorer(self, path):
        try:
            if os.path.isfile(path):
                folder = os.path.dirname(path)
            else:
                folder = path
            
            if os.path.exists(folder):
                os.startfile(folder)
                self.log_message("已打开文件夹: " + folder)
                self.log_message("请使用右键菜单 -> TortoiseSVN 进行操作")
            else:
                self.log_message("无法打开文件夹", "error")
        except Exception as e:
            self.log_message("打开文件夹失败: " + str(e), "error")
    
    def open_folder(self):
        current_file, file_dir = self.get_current_path()
        if file_dir:
            self.open_folder_in_explorer(file_dir)
    
    def set_message(self, prefix):
        current_text = cmds.scrollField(self.commit_message_field, query=True, text=True)
        if current_text.strip():
            new_text = current_text + "\n" + prefix
        else:
            new_text = prefix
        cmds.scrollField(self.commit_message_field, edit=True, text=new_text)
    
    def insert_timestamp(self):
        current_text = cmds.scrollField(self.commit_message_field, query=True, text=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if current_text.strip():
            new_text = current_text + "\n" + timestamp
        else:
            new_text = timestamp
        cmds.scrollField(self.commit_message_field, edit=True, text=new_text)
    
    def log_message(self, message, msg_type="info"):
        if not hasattr(self, 'log_field') or not self.log_field:
            print("[SVN] " + message)
            return
        
        current_log = cmds.scrollField(self.log_field, query=True, text=True)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if msg_type == "error":
            log_entry = "[" + timestamp + "] X " + message
        elif msg_type == "warning":
            log_entry = "[" + timestamp + "] ! " + message
        elif msg_type == "success":
            log_entry = "[" + timestamp + "] V " + message
        else:
            log_entry = "[" + timestamp + "] " + message
        
        log_lines = current_log.split('\n')
        if len(log_lines) > 200:
            log_lines = log_lines[-150:]
            current_log = '\n'.join(log_lines)
        
        new_log = current_log + log_entry + "\n"
        cmds.scrollField(self.log_field, edit=True, text=new_log)
        cmds.scrollField(self.log_field, edit=True, insertionPosition=len(new_log))
    
    def close_window(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

def show_svn_commit_ui():
    global svn_commit_ui
    svn_commit_ui = SVNCommitUI()