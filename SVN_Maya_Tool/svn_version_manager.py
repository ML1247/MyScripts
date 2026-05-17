import subprocess
import maya.cmds as cmds
import os
import re
from datetime import datetime
import threading
import json
import tempfile
import time
import shutil
import hashlib

# ==================== 路径配置 ====================
def get_script_dir():
    """获取当前脚本文件所在目录"""
    try:
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        if script_dir:
            return script_dir
    except NameError:
        pass
    
    # 在 Script Editor 中运行时，使用默认路径
    user_docs = os.path.expanduser("~")
    if user_docs.endswith("Documents"):
        maya_scripts = os.path.join(user_docs, "maya", "scripts", "SVN_Maya_Tool")
    else:
        maya_scripts = os.path.join(user_docs, "Documents", "maya", "scripts", "SVN_Maya_Tool")
    
    # 确保目录存在
    if not os.path.exists(maya_scripts):
        try:
            os.makedirs(maya_scripts)
        except:
            pass
    
    cmds.warning("=" * 50)
    cmds.warning("提示：请将脚本保存到 SVN_Maya_Tool 文件夹中")
    cmds.warning("路径: " + maya_scripts)
    cmds.warning("=" * 50)
    
    return maya_scripts

# 脚本所在目录
SCRIPT_DIR = get_script_dir()

# 缓存目录（脚本目录下的 .svn_cache）
CACHE_DIR = os.path.join(SCRIPT_DIR, ".svn_cache")

# 临时文件目录（脚本目录下的 .svn_temp）
TEMP_BASE_DIR = os.path.join(SCRIPT_DIR, ".svn_temp")

# 确保目录存在
for d in [CACHE_DIR, TEMP_BASE_DIR]:
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except:
            pass

# 打印路径信息
print("=" * 50)
print("SVN_Maya_Tool - SVN 历史版本工具")
print(f"工具目录: {SCRIPT_DIR}")
print(f"缓存目录: {CACHE_DIR}")
print(f"临时文件目录: {TEMP_BASE_DIR}")
print("=" * 50)

# ==================== 隐藏命令行窗口 ====================
STARTUP_INFO = None
if os.name == 'nt':
    STARTUP_INFO = subprocess.STARTUPINFO()
    STARTUP_INFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUP_INFO.wShowWindow = subprocess.SW_HIDE

def run_hidden(command, timeout=5):
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout, startupinfo=STARTUP_INFO)
        try:
            stdout = result.stdout.decode('gbk')
        except:
            stdout = result.stdout.decode('utf-8', errors='ignore')
        return stdout, ""
    except:
        return "", ""

class SVNHistoryUI:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SVNHistoryUI, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.window = "svn_history_window"
        self.current_file = None
        self.current_open_file = None
        self.selected_revision = None
        self.cached_history = []
        self.table_content = None
        self.desc_text = None
        self.rev_input = None
        self.url_frame = None
        self.status_text = None
        self.cache_file = None
        self.window_created = False
        self.temp_files = []
        self.is_loading_temp = False
        self.temp_info_file = os.path.join(TEMP_BASE_DIR, "temp_files_info.json")
        self.temp_files_map = {}
        self.load_temp_files_info()
    
    def load_temp_files_info(self):
        if os.path.exists(self.temp_info_file):
            try:
                with open(self.temp_info_file, 'r', encoding='utf-8') as f:
                    self.temp_files_map = json.load(f)
            except:
                pass
    
    def save_temp_files_info(self):
        try:
            with open(self.temp_info_file, 'w', encoding='utf-8') as f:
                json.dump(self.temp_files_map, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def register_temp_file(self, temp_path, original_path, revision):
        self.temp_files_map[os.path.normpath(temp_path)] = {
            'original': os.path.normpath(original_path),
            'revision': revision,
            'created': time.time()
        }
        self.save_temp_files_info()
    
    def cleanup_old_temp_files(self, max_age_hours=24):
        current_time = time.time()
        to_delete = []
        for temp_path, info in self.temp_files_map.items():
            if current_time - info.get('created', 0) > max_age_hours * 3600:
                to_delete.append(temp_path)
        for temp_path in to_delete:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                del self.temp_files_map[temp_path]
            except:
                pass
        if to_delete:
            self.save_temp_files_info()
    
    def cleanup_all_temp_files(self):
        count = len(self.temp_files_map)
        for temp_path in list(self.temp_files_map.keys()):
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                del self.temp_files_map[temp_path]
            except:
                pass
        self.temp_files = []
        self.save_temp_files_info()
        cmds.warning(f"已清理 {count} 个临时文件")
    
    def cleanup_cache(self):
        count = 0
        if os.path.exists(CACHE_DIR):
            for f in os.listdir(CACHE_DIR):
                if f.endswith('.json'):
                    try:
                        os.remove(os.path.join(CACHE_DIR, f))
                        count += 1
                    except:
                        pass
        self.cached_history = []
        cmds.warning(f"已清理 {count} 个缓存文件")
    
    def open_temp_folder(self):
        """打开临时文件目录"""
        if os.path.exists(TEMP_BASE_DIR):
            os.startfile(TEMP_BASE_DIR)
        else:
            cmds.warning(f"临时文件目录不存在: {TEMP_BASE_DIR}")
    
    def open_cache_folder(self):
        """打开缓存目录"""
        if os.path.exists(CACHE_DIR):
            os.startfile(CACHE_DIR)
        else:
            cmds.warning(f"缓存目录不存在: {CACHE_DIR}")
    
    def get_current_open_file(self):
        current = cmds.file(q=True, sn=True)
        if not current:
            return None
        return os.path.normpath(current)
    
    def get_target_file(self):
        """获取目标文件（如果是临时文件，返回原始文件路径）"""
        open_file = self.get_current_open_file()
        if not open_file:
            return None
        
        # 首先检查是否在temp_files_map中
        if open_file in self.temp_files_map:
            return self.temp_files_map[open_file]['original']
        
        # 检查是否是临时文件（通过文件名模式匹配）
        pattern = r'(.+)_r(\d+)_[a-f0-9]+_temp(\.[^\.]+)$'
        match = re.match(pattern, open_file)
        if match:
            original_path = match.group(1) + match.group(3)
            # 如果原始路径存在，添加到temp_files_map中
            if os.path.exists(original_path):
                self.temp_files_map[open_file] = {
                    'original': original_path,
                    'revision': match.group(2),
                    'created': time.time()
                }
                self.save_temp_files_info()
                return original_path
        
        # 检查是否在临时文件目录中
        temp_base_norm = os.path.normpath(TEMP_BASE_DIR)
        if open_file.startswith(temp_base_norm):
            # 尝试从temp_files_map中找到匹配的原始文件
            for temp_path, info in self.temp_files_map.items():
                if os.path.normpath(temp_path) == open_file:
                    return info['original']
        
        return open_file
    
    def update_current_file(self):
        self.current_open_file = self.get_current_open_file()
        self.current_file = self.get_target_file()
        
        if self.current_file:
            file_hash = hashlib.md5(self.current_file.encode('utf-8')).hexdigest()
            self.cache_file = os.path.join(CACHE_DIR, "svn_cache_" + file_hash + ".json")
            return True
        return False
    
    def load_from_cache(self):
        if not self.cache_file or not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if time.time() - data.get('timestamp', 0) < 3600:
                return data.get('history', [])
        except:
            pass
        return None
    
    def save_to_cache(self, history):
        if not self.cache_file:
            return
        try:
            data = {'timestamp': time.time(), 'history': history}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def check_and_save_current(self, show_cancel=True):
        current_scene = cmds.file(q=True, sn=True)
        if not current_scene:
            return True
        
        is_modified = cmds.file(q=True, modified=True)
        
        if is_modified:
            if show_cancel:
                result = cmds.confirmDialog(
                    title='保存当前文件',
                    message='当前文件有未保存的修改，是否先保存？',
                    button=['保存', '不保存', '取消'],
                    defaultButton='保存',
                    cancelButton='取消'
                )
                if result == '保存':
                    cmds.file(save=True)
                    return True
                elif result == '不保存':
                    return True
                else:
                    return False
            else:
                result = cmds.confirmDialog(
                    title='保存当前文件',
                    message='当前文件有未保存的修改，临时查看前是否先保存？',
                    button=['保存', '不保存'],
                    defaultButton='保存'
                )
                if result == '保存':
                    cmds.file(save=True)
                return True
        return True
    
    def get_file_history_sync(self, force_refresh=False):
        if not force_refresh and self.cached_history:
            return self.cached_history
        
        if not force_refresh:
            cached = self.load_from_cache()
            if cached:
                self.cached_history = cached
                return cached
        
        if not self.current_file or not os.path.exists(self.current_file):
            return []
        
        try:
            output, _ = run_hidden(["svn", "log", self.current_file, "--xml", "-l", "50"])
            if not output:
                return []
            
            history_list = []
            entry_pattern = r'<logentry\s+revision="(\d+)">(.*?)</logentry>'
            entries = re.findall(entry_pattern, output, re.DOTALL)
            
            file_ext = os.path.splitext(self.current_file)[1].lower()
            if file_ext.startswith('.'):
                file_ext = file_ext[1:]
            
            for revision, content in entries:
                author_match = re.search(r'<author>(.*?)</author>', content)
                author = author_match.group(1) if author_match else "unknown"
                
                date_match = re.search(r'<date>(.*?)</date>', content)
                date_str = date_match.group(1) if date_match else ""
                if date_str:
                    try:
                        dt = datetime.strptime(date_str.replace('Z', ''), '%Y-%m-%dT%H:%M:%S.%f')
                        date_str = dt.strftime('%Y/%m/%d %H:%M:%S')
                    except:
                        date_str = date_str[:16].replace('T', ' ')
                
                msg_match = re.search(r'<msg>(.*?)</msg>', content)
                message = msg_match.group(1) if msg_match else "-"
                
                action = "添加" if revision == '1' else "编辑"
                
                history_list.append({
                    'revision': revision,
                    'author': author,
                    'date': date_str,
                    'message': message,
                    'action': action,
                    'file_type': file_ext
                })
            
            history_list.sort(key=lambda x: int(x['revision']), reverse=True)
            self.cached_history = history_list
            self.save_to_cache(history_list)
            return history_list
        except:
            return []
    
    def get_file_url_sync(self):
        try:
            output, _ = run_hidden(["svn", "info", self.current_file])
            if output:
                match = re.search(r'URL: (.*?)(?:\n|$)', output)
                if match:
                    url = match.group(1)
                    if len(url) > 80:
                        url = url[:40] + "..." + url[-37:]
                    return url
        except:
            pass
        return "未加入版本控制"
    
    def get_current_revision_sync(self):
        try:
            output, _ = run_hidden(["svn", "info", self.current_file, "--show-item", "revision"])
            if output and output.strip().isdigit():
                return output.strip()
        except:
            pass
        return "?"
    
    def check_and_save_for_overwrite(self):
        return self.check_and_save_current(show_cancel=True)
    
    def overwrite_with_version(self, revision):
        if not self.current_file:
            cmds.error("无法获取当前文件路径")
            return False
        
        if not self.check_and_save_for_overwrite():
            return False
        
        try:
            backup_file = self.current_file + ".backup"
            if os.path.exists(self.current_file):
                shutil.copy2(self.current_file, backup_file)
            
            result = subprocess.run(
                ["svn", "cat", self.current_file, "-r", revision], 
                capture_output=True,
                startupinfo=STARTUP_INFO
            )
            
            if result.returncode != 0:
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, self.current_file)
                cmds.error(f"获取版本 r{revision} 失败")
                return False
            
            with open(self.current_file, 'wb') as f:
                f.write(result.stdout)
            
            if os.path.exists(backup_file):
                os.remove(backup_file)
            
            cmds.file(self.current_file, open=True, force=True)
            cmds.warning(f"已用版本 r{revision} 覆盖当前文件\n现在可以修改后提交为新版本")
            
            self.cached_history = []
            return True
        except Exception as e:
            cmds.error(f"覆盖失败: {str(e)}")
            return False
    
    def open_current_version(self):
        target = self.get_target_file()
        if not target:
            cmds.warning("无法获取原始文件路径")
            return
        
        if not os.path.exists(target):
            cmds.warning(f"原始文件不存在: {target}")
            return
        
        current_scene = cmds.file(q=True, sn=True)
        is_modified = cmds.file(q=True, modified=True) if current_scene else False
        
        if is_modified:
            result = cmds.confirmDialog(
                title='保存当前文件',
                message='当前文件有未保存的修改，打开当前版本前是否先保存？',
                button=['保存', '不保存', '取消'],
                defaultButton='保存',
                cancelButton='取消'
            )
            if result == '保存':
                cmds.file(save=True)
            elif result == '取消':
                return
        
        try:
            cmds.file(target, open=True, force=True)
            cmds.warning(f"已打开当前版本: {os.path.basename(target)}")
            
            # 刷新当前文件状态
            self.update_current_file()
        except Exception as e:
            cmds.error(f"打开失败: {str(e)}")
    
    def temp_view_version(self, revision):
        if not self.current_file:
            cmds.error("无法获取当前文件路径")
            return
        
        if self.is_loading_temp:
            cmds.warning("正在加载中，请稍后再试")
            return
        
        current_scene = cmds.file(q=True, sn=True)
        is_modified = cmds.file(q=True, modified=True) if current_scene else False
        
        if is_modified:
            result = cmds.confirmDialog(
                title='保存当前文件',
                message='当前文件有未保存的修改，临时查看前是否先保存？',
                button=['保存', '不保存'],
                defaultButton='保存'
            )
            if result == '保存':
                cmds.file(save=True)
        
        load_window = cmds.window(title="加载中", widthHeight=(200, 80))
        cmds.columnLayout(adjustableColumn=True)
        cmds.text(label=f"正在加载版本 r{revision}...", align='center')
        cmds.text(label="请稍候", align='center')
        cmds.showWindow(load_window)
        cmds.refresh()
        
        def load_async():
            self.is_loading_temp = True
            try:
                file_name = os.path.basename(self.current_file)
                name, ext = os.path.splitext(file_name)
                unique_id = hashlib.md5(f"{self.current_file}_{revision}_{time.time()}".encode()).hexdigest()[:8]
                temp_file = os.path.join(TEMP_BASE_DIR, f"{name}_r{revision}_{unique_id}_temp{ext}")
                
                result = subprocess.run(
                    ["svn", "cat", self.current_file, "-r", str(revision)],
                    capture_output=True,
                    startupinfo=STARTUP_INFO
                )
                
                if result.returncode != 0:
                    cmds.evalDeferred(lambda: cmds.error(f"获取版本 r{revision} 失败"))
                    return
                
                with open(temp_file, 'wb') as f:
                    f.write(result.stdout)
                
                self.register_temp_file(temp_file, self.current_file, revision)
                self.temp_files.append(temp_file)
                cmds.evalDeferred(lambda: self._open_temp_file(temp_file, revision))
            except Exception as e:
                cmds.evalDeferred(lambda: cmds.error(f"打开失败: {str(e)}"))
            finally:
                self.is_loading_temp = False
                cmds.evalDeferred(lambda: cmds.deleteUI(load_window))
        
        threading.Thread(target=load_async, daemon=True).start()
    
    def _open_temp_file(self, temp_file, revision):
        try:
            cmds.file(temp_file, open=True, force=True)
            cmds.warning(f"临时查看版本 r{revision}")
            
            # 刷新当前文件状态，确保 current_file 指向原始文件
            self.update_current_file()
        except Exception as e:
            cmds.error(f"打开失败: {str(e)}")
    
    def on_version_click(self, revision, message):
        self.selected_revision = revision
        cmds.text(self.desc_text, e=True, label="描述：" + message)
        cmds.textField(self.rev_input, e=True, text=revision)
    
    def on_temp_view(self, revision):
        self.temp_view_version(revision)
    
    def on_overwrite(self):
        if not self.selected_revision:
            cmds.warning("请先点击选择一个版本号")
            return
        
        result = cmds.confirmDialog(
            title='确认覆盖',
            message=f'确定要用版本 r{self.selected_revision} 覆盖当前文件吗？\n\n⚠️ 此操作会替换当前文件内容！',
            button=['确定', '取消'],
            defaultButton='取消',
            cancelButton='取消'
        )
        
        if result == '确定':
            self.overwrite_with_version(self.selected_revision)
    
    def on_refresh(self):
        if not self.update_current_file():
            cmds.warning("请先保存当前文件")
            return
        
        self.cached_history = []
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except:
                pass
        
        if self.table_content:
            children = cmds.columnLayout(self.table_content, q=True, childArray=True) or []
            for child in children:
                try:
                    cmds.deleteUI(child)
                except:
                    pass
            cmds.text(label="正在加载历史记录...", align='center', parent=self.table_content, height=50)
        
        if self.current_file and self.url_frame:
            short_name = os.path.basename(self.current_file)
            cmds.frameLayout(self.url_frame, e=True, label="当前文件: " + short_name)
        
        def load_async():
            history = self.get_file_history_sync(force_refresh=True)
            url = self.get_file_url_sync()
            rev = self.get_current_revision_sync()
            cmds.evalDeferred(lambda: self.populate_table(history, url, rev))
        
        threading.Thread(target=load_async, daemon=True).start()
    
    def populate_table(self, history, file_url=None, current_rev=None):
        if not self.table_content:
            return
        
        children = cmds.columnLayout(self.table_content, q=True, childArray=True) or []
        for child in children:
            try:
                cmds.deleteUI(child)
            except:
                pass
        
        if file_url and self.url_frame:
            cmds.frameLayout(self.url_frame, e=True, label="当前文件: " + file_url)
        
        if current_rev and self.status_text:
            cmds.text(self.status_text, e=True, label="状态: 当前版本 r" + current_rev)
        
        if not history:
            cmds.text(label="暂无历史记录", align='center', parent=self.table_content, height=40)
            return
        
        for i, ver in enumerate(history):
            # 交替行颜色
            bg_color = (0.25, 0.25, 0.25) if i % 2 == 0 else (0.22, 0.22, 0.22)
            
            cmds.rowColumnLayout(numberOfColumns=7, parent=self.table_content,
                                columnWidth=[(1,70), (2,65), (3,150), (4,90), (5,60), (6,50), (7,280)],
                                backgroundColor=bg_color)
            
            # 版本号按钮 - 不显示r前缀
            cmds.button(label=ver['revision'], height=22,
                       backgroundColor=(0.4, 0.4, 0.5),
                       command=lambda x, rev=ver['revision'], msg=ver['message']: self.on_version_click(rev, msg))
            
            # 临时查看按钮
            cmds.button(label="临时查看", height=22, width=65,
                       backgroundColor=(0.35, 0.45, 0.35),
                       command=lambda x, rev=ver['revision']: self.on_temp_view(rev))
            
            cmds.text(label=ver['date'], align='center', height=22)
            cmds.text(label=ver['author'], align='center', height=22)
            cmds.text(label=ver['file_type'], align='center', height=22)
            cmds.text(label=ver['action'], align='center', height=22)
            
            desc = ver['message'][:35] + "..." if len(ver['message']) > 35 else ver['message']
            cmds.text(label=desc, align='left', height=22)
            
            cmds.setParent('..')
    
    def on_close_window(self):
        self.cleanup_old_temp_files(max_age_hours=24)
    
    def auto_refresh(self):
        """自动刷新历史记录（仅在文件已保存时执行）"""
        if self.update_current_file():
            self.cached_history = []
            if self.cache_file and os.path.exists(self.cache_file):
                try:
                    os.remove(self.cache_file)
                except:
                    pass
            
            if self.current_file and self.url_frame:
                short_name = os.path.basename(self.current_file)
                cmds.frameLayout(self.url_frame, e=True, label="当前文件: " + short_name)
            
            def load_async():
                history = self.get_file_history_sync(force_refresh=True)
                url = self.get_file_url_sync()
                rev = self.get_current_revision_sync()
                cmds.evalDeferred(lambda: self.populate_table(history, url, rev))
            
            threading.Thread(target=load_async, daemon=True).start()
    
    def show(self):
        self.update_current_file()
        self.cleanup_old_temp_files(max_age_hours=24)
        
        if cmds.window(self.window, exists=True):
            cmds.showWindow(self.window)
            return
        
        self.create_ui()
        # 窗口创建后自动刷新
        cmds.evalDeferred(lambda: self.auto_refresh())
    
    def create_ui(self):
        if self.window_created:
            return
        
        window = cmds.window(self.window, title="SVN 历史版本工具", widthHeight=(960, 600),
                             sizeable=True, resizeToFitChildren=False,
                             closeCommand=lambda x: self.on_close_window())
        
        # 使用 formLayout 实现自适应布局
        main_form = cmds.formLayout(numberOfDivisions=100)
        
        # 标题
        title_text = cmds.text(label="SVN 历史版本工具", font="boldLabelFont", height=24)
        sep1 = cmds.separator(height=8, style='in')
        
        # URL/文件信息框架
        display_file = self.current_file if self.current_file else "未保存"
        if display_file and display_file != "未保存":
            short_name = os.path.basename(display_file)
            self.url_frame = cmds.frameLayout(label="当前文件: " + short_name, collapsable=False, 
                                              marginWidth=8, marginHeight=6, 
                                              borderStyle='etchedIn', labelAlign='center')
        else:
            self.url_frame = cmds.frameLayout(label="当前文件: 未保存", collapsable=False, 
                                              marginWidth=8, marginHeight=6, 
                                              borderStyle='etchedIn', labelAlign='center')
        
        # 工具栏按钮行
        btn_row1 = cmds.rowLayout(numberOfColumns=5, 
                                  columnWidth5=(95, 145, 135, 115, 145),
                                  columnAttach=[(1, 'both', 3), (2, 'both', 3), (3, 'both', 3), (4, 'both', 3), (5, 'both', 3)])
        cmds.button(label="刷新", height=26, 
                   backgroundColor=(0.35, 0.4, 0.5),
                   annotation="刷新历史记录",
                   command=lambda x: self.on_refresh())
        cmds.button(label="打开当前版本", height=26, 
                   backgroundColor=(0.35, 0.45, 0.35),
                   annotation="打开当前工作区版本",
                   command=lambda x: self.open_current_version())
        cmds.button(label="清理临时文件", height=26, 
                   backgroundColor=(0.45, 0.38, 0.3),
                   annotation="清理所有临时文件",
                   command=lambda x: self.cleanup_all_temp_files())
        cmds.button(label="清理缓存", height=26, 
                   backgroundColor=(0.45, 0.38, 0.3),
                   annotation="清理历史记录缓存",
                   command=lambda x: self.cleanup_cache())
        cmds.button(label="打开临时目录", height=26, 
                   backgroundColor=(0.35, 0.38, 0.42),
                   annotation="打开临时文件所在目录",
                   command=lambda x: self.open_temp_folder())
        cmds.setParent('..')
        cmds.separator(height=6, style='none')
        
        # 表头
        header_row = cmds.rowColumnLayout(numberOfColumns=7,
                            columnWidth=[(1,70), (2,65), (3,150), (4,90), (5,60), (6,50), (7,280)],
                            backgroundColor=(0.28, 0.28, 0.32))
        headers = ["版本号", "操作", "修改日期", "提交者", "类型", "变更", "描述"]
        for h in headers:
            cmds.text(label=h, align='center', font="boldLabelFont", height=22)
        cmds.setParent('..')
        cmds.separator(height=3, style='none')
        
        cmds.setParent('..')  # 关闭 url_frame
        
        # 历史记录列表滚动区域 - 使用 adjustableColumn 让高度自适应
        scroll = cmds.scrollLayout(childResizable=True, backgroundColor=(0.2, 0.2, 0.2))
        self.table_content = cmds.columnLayout(adjustableColumn=True, rowSpacing=1, parent=scroll)
        
        # 初始显示加载提示
        cmds.text(label="正在自动加载历史记录...", align='center', parent=self.table_content, height=40)
        
        cmds.setParent('..')  # 关闭 table_content
        cmds.setParent('..')  # 关闭 scroll
        
        # 描述区域
        desc_frame = cmds.frameLayout(label="提交描述", collapsable=False, 
                        marginWidth=8, marginHeight=6, 
                        borderStyle='etchedIn')
        self.desc_text = cmds.text(label="点击版本号查看提交描述...", align='left', height=35, 
                                   wordWrap=True, font="smallPlainLabelFont")
        cmds.setParent('..')  # 关闭 desc_frame
        
        # 底部操作区域
        op_frame = cmds.frameLayout(label="版本操作", collapsable=False, 
                        marginWidth=8, marginHeight=6, 
                        borderStyle='etchedIn')
        
        # 输入行
        cmds.rowLayout(numberOfColumns=4, columnWidth4=(90, 120, 140, 140),
                      columnAttach=[(1, 'both', 3), (2, 'both', 3), (3, 'both', 3), (4, 'both', 3)])
        cmds.text(label="指定版本号:", align='right', height=26)
        self.rev_input = cmds.textField(height=26, annotation="输入SVN版本号")
        cmds.button(label="临时查看", height=26, 
                   backgroundColor=(0.35, 0.45, 0.35),
                   annotation="临时查看指定版本",
                   command=lambda x: self.temp_view_by_input())
        cmds.button(label="覆盖当前版本", height=26, 
                   backgroundColor=(0.55, 0.3, 0.3),
                   annotation="用指定版本覆盖当前文件（不可逆）",
                   command=lambda x: self.on_overwrite())
        cmds.setParent('..')
        
        cmds.setParent('..')  # 关闭 op_frame
        
        # 底部状态栏
        sep2 = cmds.separator(height=8, style='in')
        self.status_text = cmds.text(label="状态: 正在加载...", align='left', height=18, 
                                     font="smallPlainLabelFont")
        hint_text = cmds.text(label="提示：点击版本号选中，点击【覆盖当前版本】使用指定的版本替换为当前版本", align='left', 
                 height=16, font="smallPlainLabelFont")
        
        # 设置 formLayout 约束
        # title 固定在顶部
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(title_text, 'top', 5), (title_text, 'left', 5), (title_text, 'right', 5),
                                  (sep1, 'left', 5), (sep1, 'right', 5)],
                       attachControl=[(sep1, 'top', 3, title_text)])
        
        # url_frame 在 title 下方
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(self.url_frame, 'left', 5), (self.url_frame, 'right', 5)],
                       attachControl=[(self.url_frame, 'top', 3, sep1)])
        
        # scroll 在 url_frame 下方，且填充到 desc_frame 上方
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(scroll, 'left', 5), (scroll, 'right', 5)],
                       attachControl=[(scroll, 'top', 3, self.url_frame),
                                     (scroll, 'bottom', 3, desc_frame)])
        
        # desc_frame 固定在底部操作区上方
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(desc_frame, 'left', 5), (desc_frame, 'right', 5)],
                       attachControl=[(desc_frame, 'bottom', 3, op_frame)])
        
        # op_frame 固定在状态栏上方
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(op_frame, 'left', 5), (op_frame, 'right', 5)],
                       attachControl=[(op_frame, 'bottom', 3, sep2)])
        
        # 底部状态栏固定在底部
        cmds.formLayout(main_form, edit=True,
                       attachForm=[(sep2, 'left', 5), (sep2, 'right', 5),
                                  (self.status_text, 'left', 5), (self.status_text, 'right', 5),
                                  (hint_text, 'left', 5), (hint_text, 'right', 5), (hint_text, 'bottom', 5)],
                       attachControl=[(sep2, 'bottom', 3, self.status_text),
                                     (self.status_text, 'bottom', 2, hint_text)])
        
        cmds.showWindow(window)
        self.window_created = True
    
    def temp_view_by_input(self):
        rev = cmds.textField(self.rev_input, q=True, text=True)
        if rev and rev.isdigit():
            self.temp_view_version(rev)
        else:
            cmds.warning("请输入有效的版本号")


# 运行
svn_ui = SVNHistoryUI()
svn_ui.show()