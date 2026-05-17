# -*- coding: utf-8 -*-
"""
SVN Maya Tool 安装器
拖入 Maya 视口即可安装 SVN提交工具 和 历史版本工具
"""

import maya.cmds as cmds
import maya.mel as mel
import os
import sys
import shutil


def install_svn_maya_tool():
    maya_app_dir = cmds.internalVar(userAppDir=True)
    target_dir = os.path.join(maya_app_dir, "scripts", "SVN_Maya_Tool")

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    installer_dir = os.path.dirname(os.path.abspath(__file__))

    commit_src = os.path.join(installer_dir, "svn_commit_tool.py")
    commit_dst = os.path.join(target_dir, "svn_commit_tool.py")

    if os.path.exists(commit_src):
        try:
            shutil.copy2(commit_src, commit_dst)
            print(u"[SVN_Maya_Tool] svn_commit_tool.py 已复制到: " + commit_dst)
        except Exception as e:
            cmds.warning(u"[SVN_Maya_Tool] 复制 svn_commit_tool.py 失败: " + str(e))
            return False
    else:
        cmds.warning(u"[SVN_Maya_Tool] 错误: 未找到 svn_commit_tool.py")
        return False

    version_manager_src = os.path.join(installer_dir, "svn_version_manager.py")
    version_manager_dst = os.path.join(target_dir, "svn_version_manager.py")

    if os.path.exists(version_manager_src):
        try:
            shutil.copy2(version_manager_src, version_manager_dst)
            print(u"[SVN_Maya_Tool] svn_version_manager.py 已复制到: " + version_manager_dst)
        except Exception as e:
            cmds.warning(u"[SVN_Maya_Tool] 复制 svn_version_manager.py 失败: " + str(e))
            return False
    else:
        cmds.warning(u"[SVN_Maya_Tool] 警告: 未找到 svn_version_manager.py 源文件，仅安装了 svn_commit_tool.py")

    icon_names = []
    for f in os.listdir(installer_dir):
        if f.lower().endswith('.png'):
            safe_name = f.replace('#', '_').replace(' ', '_')
            src = os.path.join(installer_dir, f)
            dst = os.path.join(target_dir, safe_name)
            try:
                shutil.copy2(src, dst)
                icon_names.append(safe_name)
                print(u"[SVN_Maya_Tool] 图标已复制: " + safe_name)
            except Exception as e:
                cmds.warning(u"[SVN_Maya_Tool] 复制图标失败: " + str(e))

    print(u"[SVN_Maya_Tool] 可用图标: " + str(icon_names))

    cache_dir = os.path.join(target_dir, "__pycache__")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
        except:
            pass

    sys.path.insert(0, target_dir)

    try:
        current_shelf = mel.eval('tabLayout -q -selectTab $gShelfTopLevel;')
        if not current_shelf:
            current_shelf = 'Custom'

        old_buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
        removed_count = 0
        for btn in old_buttons:
            try:
                btn_label = cmds.shelfButton(btn, query=True, label=True) or ""
                btn_annot = cmds.shelfButton(btn, query=True, annotation=True) or ""
                if "SVN" in str(btn_label) or "SVN" in str(btn_annot) or "提交" in str(btn_label) or "历史" in str(btn_label):
                    cmds.deleteUI(btn)
                    removed_count += 1
            except:
                pass
        if removed_count > 0:
            print(u"[SVN_Maya_Tool] 已删除 " + str(removed_count) + " 个旧按钮")

        commit_cmd = '''import sys
sys.path.insert(0, "{target_dir}")
import svn_commit_tool
try:
    reload(svn_commit_tool)
except NameError:
    import importlib
    importlib.reload(svn_commit_tool)
svn_commit_tool.show_svn_commit_ui()'''.format(target_dir=target_dir.replace('\\', '/'))

        commit_icon = "menuIconFile.png"
        if icon_names:
            target_dir_clean = os.path.normpath(target_dir)
            abs_icon_path = os.path.join(target_dir_clean, icon_names[0])
            if os.path.exists(abs_icon_path):
                commit_icon = abs_icon_path

        btn1 = cmds.shelfButton(
            parent=current_shelf,
            
            annotation=u"SVN提交工具 - 提交/更新/清理/日志/浏览仓库",
            image=commit_icon,
            imageOverlayLabel=u"提交",
            command=commit_cmd,
            sourceType="python",
            style="iconAndTextVertical"
        )

        history_cmd = '''import sys
sys.path.insert(0, "{target_dir}")
import svn_version_manager
try:
    reload(svn_version_manager)
except NameError:
    import importlib
    importlib.reload(svn_version_manager)
ui = svn_version_manager.SVNHistoryUI()
ui.show()'''.format(target_dir=target_dir.replace('\\', '/'))

        history_icon = "menuIconFile.png"
        if icon_names:
            target_dir_clean = os.path.normpath(target_dir)
            if len(icon_names) >= 2:
                abs_icon_path = os.path.join(target_dir_clean, icon_names[1])
            else:
                abs_icon_path = os.path.join(target_dir_clean, icon_names[0])
            if os.path.exists(abs_icon_path):
                history_icon = abs_icon_path

        btn2 = cmds.shelfButton(
            parent=current_shelf,
           
            annotation=u"SVN历史版本工具 - 查看/恢复历史版本",
            image=history_icon,
            imageOverlayLabel=u"历史",
            command=history_cmd,
            sourceType="python",
            style="iconAndTextVertical"
        )
        try:
            cmds.shelfLayout(current_shelf, edit=True)
        except:
            pass

        print(u"[SVN_Maya_Tool] 工具架按钮已创建:")
        print(u"  - SVN提交 (" + btn1 + ")")
        print(u"  - SVN历史 (" + btn2 + ")")
    except Exception as e:
        cmds.warning(u"[SVN_Maya_Tool] 创建工具架按钮失败: " + str(e))

    cmds.confirmDialog(
        title=u"SVN Maya Tool 安装完成",
        message=u"SVN Maya Tool 安装成功！\n\n安装路径:\n{0}\n\n包含脚本:\n- svn_commit_tool.py (SVN提交工具)\n- svn_version_manager.py (历史版本工具)\n\n已在当前工具架添加按钮".format(target_dir),
        button=[u"确定"],
        defaultButton=u"确定"
    )

    return True


def onMayaDroppedPythonFile(*args):
    main()


def main():
    print(u"========================================")
    print(u"  SVN Maya Tool 安装器")
    print(u"========================================")
    ok = install_svn_maya_tool()
    if ok:
        print(u"安装完成，可以点击工具架按钮启动工具。")
    else:
        print(u"安装失败，请检查 Script Editor 输出。")


if __name__ == "__main__":
    main()
