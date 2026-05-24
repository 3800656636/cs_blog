#!/usr/bin/env python3
"""
MkDocs Blog Manager - 纯净大纲导航CMS版
大纲即单源信度 | 双击叶子改标题并自动重写文件H1 | 物理路径自动代管
直接运行: python blog_manager.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import re
import time
import os
import shutil
import subprocess
from pathlib import Path

# 尝试导入 pyyaml (因为 MkDocs 依赖它，使用此环境的用户本地必然已安装)
try:
    import yaml
except ImportError:
    import sys

    print("错误: 当前环境缺少 pyyaml 模块。请先在终端运行 'pip install pyyaml'。")
    sys.exit(1)

# ============================================================
# 配色与样式常量（现代轻量主题）
# ============================================================
BG_MAIN = "#F3F4F6"  # 浅灰背景
BG_WHITE = "#FFFFFF"  # 纯白卡片
TEXT_DARK = "#1F2937"  # 主要文字
TEXT_MUTED = "#6B7280"  # 辅助文字
COLOR_PRIMARY = "#2563EB"  # 现代科技蓝
COLOR_PRIMARY_ACT = "#1D4ED8"
COLOR_BORDER = "#E5E7EB"  # 边框
COLOR_SUCCESS = "#10B981"  # 成功绿
COLOR_WARN = "#EF4444"  # 警告红


# ============================================================
# 工具函数
# ============================================================
def create_flat_button(parent, text, command, bg="#E5E7EB", fg=TEXT_DARK, active_bg="#D1D5DB"):
    """创建扁平化按钮"""
    return tk.Button(parent, text=text, command=command, bd=0, bg=bg, fg=fg,
                     activebackground=active_bg, activeforeground=fg,
                     font=("Microsoft YaHei", 9), padx=12, pady=6, cursor="hand2")


def create_primary_button(parent, text, command):
    """创建主要动作按钮"""
    return tk.Button(parent, text=text, command=command, bd=0, bg=COLOR_PRIMARY, fg="#FFFFFF",
                     activebackground=COLOR_PRIMARY_ACT, activeforeground="#FFFFFF",
                     font=("Microsoft YaHei", 9, "bold"), padx=16, pady=6, cursor="hand2")


class BlogManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MkDocs Blog Manager (Outline CMS)")
        self.root.geometry("1150x700")
        self.root.configure(bg=BG_MAIN)

        self.base_dir = Path(__file__).parent.resolve()
        self.docs_dir = self.base_dir / "docs"
        self.config_file = self.base_dir / "mkdocs.yml"

        self.config_data = {}
        self._save_timer = None
        self._preview_path = None

        self._setup_styles()
        self._setup_ui()
        self._refresh_tree()

    # ---------- 样式配置 ----------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".", background=BG_MAIN, foreground=TEXT_DARK)
        style.configure("TFrame", background=BG_MAIN)
        style.configure("Treeview",
                        background=BG_WHITE,
                        foreground=TEXT_DARK,
                        rowheight=32,
                        fieldbackground=BG_WHITE,
                        borderwidth=0,
                        font=("Microsoft YaHei", 10))
        style.map("Treeview",
                  background=[('selected', COLOR_PRIMARY)],
                  foreground=[('selected', '#FFFFFF')])

    # ---------- Markdown 标题解析 ----------
    def _extract_title(self, filepath):
        """尝试读取 markdown 文件内的第一个 H1 标题做 fallback"""
        if not filepath.exists():
            return filepath.stem
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                in_front = False
                for line in f:
                    s = line.strip()
                    if s == '---':
                        in_front = not in_front
                        continue
                    if in_front:
                        continue
                    if s.startswith('# ') and not s.startswith('## '):
                        return s[2:].strip()
        except Exception:
            pass
        return filepath.stem

    def _clean_title(self, text):
        """去除树节点前方的 Emoji"""
        if text.startswith("📁 "):
            return text[2:]
        if text.startswith("📄 "):
            return text[2:]
        return text

    # ---------- 博客导航大纲解析（MkDocs YAML驱动） ----------
    def _load_nav_from_config(self):
        """直接从 mkdocs.yml 中读取 nav 配置"""
        if not self.config_file.exists():
            return []
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f) or {}

            nav = self.config_data.get('nav', [])
            if not nav:
                # 若完全不存在 nav 配置，则自动扫描 docs 物理文件生成默认初始大纲
                nav = self._auto_generate_default_nav()
            return nav
        except Exception as e:
            messagebox.showerror("解析失败", f"无法正确加载 mkdocs.yml: {e}")
            return []

    def _auto_generate_default_nav(self):
        """自动从物理目录发现并填充一套默认导航结构"""
        nav = []
        if (self.docs_dir / 'index.md').exists():
            nav.append({"首页": "index.md"})
        else:
            self.docs_dir.mkdir(parents=True, exist_ok=True)
            with open(self.docs_dir / 'index.md', 'w', encoding='utf-8') as f:
                f.write("# 欢迎来到我的博客\n\n这是您的首个页面。")
            nav.append({"首页": "index.md"})

        for entry in sorted(self.docs_dir.rglob('*.md')):
            if entry.name == 'index.md':
                continue
            rel = str(entry.relative_to(self.docs_dir)).replace('\\', '/')
            title = self._extract_title(entry)
            nav.append({title: rel})
        return nav

    # ---------- 构建大纲树 ----------
    def _refresh_tree(self):
        selected_path = None
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], 'values')
            if vals:
                selected_path = vals[1]

        self.tree.delete(*self.tree.get_children())

        # 核心：根据 nav 大纲而非本地文件系统填充树
        nav_list = self._load_nav_from_config()
        self._populate_from_nav("", nav_list)

        if selected_path:
            self._select_by_path(selected_path)
        else:
            self._select_by_path('index.md')

    def _populate_from_nav(self, parent_iid, nav_list):
        """递归解析 nav 数据结构并填入 Treeview"""
        for entry in nav_list:
            if isinstance(entry, str):
                # 如 "- index.md" (无显示标题的单项)
                title = self._extract_title(self.docs_dir / entry)
                self.tree.insert(parent_iid, 'end', text="📄 " + title, values=["file", entry])
            elif isinstance(entry, dict):
                # 键值对或分类目录
                for key, val in entry.items():
                    if isinstance(val, str):
                        # 如 "- 快速上手: guide/quickstart.md"
                        self.tree.insert(parent_iid, 'end', text="📄 " + key, values=["file", val])
                    elif isinstance(val, list):
                        # 如 "- 我的指南: [ ... ]"
                        iid = self.tree.insert(parent_iid, 'end', text="📁 " + key, open=True, values=["dir", ""])
                        self._populate_from_nav(iid, val)

    def _select_by_path(self, path):
        def _search(item):
            vals = self.tree.item(item, 'values')
            if vals and vals[0] == "file" and vals[1] == path:
                self.tree.selection_set(item)
                self.tree.see(item)
                return True
            for child in self.tree.get_children(item):
                if _search(child):
                    return True
            return False

        for item in self.tree.get_children(''):
            if _search(item):
                return

    # ---------- 获取选中大纲项 ----------
    def _get_sel_item(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _get_sel_is_dir(self):
        item = self._get_sel_item()
        if not item:
            return False
        vals = self.tree.item(item, 'values')
        return vals[0] == "dir" if vals else False

    # ---------- UI 搭建 ----------
    def _setup_ui(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # ---- 左侧栏 (Sidebar - 大纲视角) ----
        sidebar = tk.Frame(main_pane, bg=BG_WHITE)
        main_pane.add(sidebar, weight=1)

        sb_header = tk.Frame(sidebar, bg=BG_WHITE)
        sb_header.pack(fill=tk.X, padx=15, pady=(20, 10))
        tk.Label(sb_header, text="📚 BLOG OUTLINE", fg=COLOR_PRIMARY, bg=BG_WHITE,
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor=tk.W)
        tk.Label(sb_header, text="文章导航大纲", fg=TEXT_DARK, bg=BG_WHITE,
                 font=("Microsoft YaHei", 14, "bold")).pack(anchor=tk.W, pady=(2, 0))

        # 大纲树
        tree_container = tk.Frame(sidebar, bg=BG_WHITE)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.tree = ttk.Treeview(tree_container, selectmode='browse', show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        sb = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        sb.pack(fill=tk.Y, side=tk.RIGHT)
        self.tree.configure(yscrollcommand=sb.set)

        # 底部快捷键
        sb_footer = tk.Frame(sidebar, bg=BG_WHITE)
        sb_footer.pack(fill=tk.X, padx=15, pady=(10, 20))

        create_flat_button(sb_footer, "+ 新分类", self._new_folder).pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                         padx=(0, 2))
        create_flat_button(sb_footer, "+ 新文章", self._new_file).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        create_flat_button(sb_footer, "🗑️ 删除", self._delete, bg="#FEE2E2", fg=COLOR_WARN, active_bg="#FCA5A5").pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # ---- 右侧栏 (Editor - 沉浸式写作) ----
        editor_panel = tk.Frame(main_pane, bg=BG_MAIN)
        main_pane.add(editor_panel, weight=3)

        ep_header = tk.Frame(editor_panel, bg=BG_MAIN)
        ep_header.pack(fill=tk.X, padx=25, pady=(20, 10))

        self.editor_info_label = tk.Label(ep_header, text="请在左侧点击一个大纲节点", fg=TEXT_MUTED, bg=BG_MAIN,
                                          font=("Microsoft YaHei", 9))
        self.editor_info_label.pack(anchor=tk.W)

        self.editor_title_label = tk.Label(ep_header, text="无选中的大纲项", fg=TEXT_DARK, bg=BG_MAIN,
                                           font=("Microsoft YaHei", 16, "bold"))
        self.editor_title_label.pack(anchor=tk.W, pady=(4, 0))

        # 状态微调（防抖提示）
        self.status_label = tk.Label(ep_header, text="", bg=BG_MAIN, font=("Microsoft YaHei", 9, "bold"))
        self.status_label.pack(anchor=tk.E, side=tk.RIGHT, pady=(0, 5))

        # 极简卡片写作面板
        paper_border = tk.Frame(editor_panel, bg=COLOR_BORDER)
        paper_border.pack(fill=tk.BOTH, expand=True, padx=25, pady=(0, 20))

        paper = tk.Frame(paper_border, bg=BG_WHITE)
        paper.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._preview = scrolledtext.ScrolledText(
            paper, wrap=tk.WORD, font=("Consolas", 11),
            bg=BG_WHITE, fg=TEXT_DARK, bd=0, highlightthickness=0,
            insertbackground=COLOR_PRIMARY, padx=15, pady=15,
            spacing1=6, spacing2=4
        )
        self._preview.pack(fill=tk.BOTH, expand=True)
        self._preview.bind("<KeyRelease>", self._on_editor_key)

        # ---- 底部控制区 ----
        ep_footer = tk.Frame(editor_panel, bg=BG_MAIN)
        ep_footer.pack(fill=tk.X, padx=25, pady=(0, 20))

        # 左：Git 提交
        git_frame = tk.Frame(ep_footer, bg=BG_MAIN)
        git_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(git_frame, text="Git 提交信息:", fg=TEXT_MUTED, bg=BG_MAIN, font=("Microsoft YaHei", 9)).pack(
            side=tk.LEFT, padx=(0, 5))

        entry_border = tk.Frame(git_frame, bg=COLOR_BORDER, padx=1, pady=1)
        entry_border.pack(side=tk.LEFT)
        self._commit_msg = tk.Entry(entry_border, width=30, bd=0, bg=BG_WHITE, fg=TEXT_DARK,
                                    insertbackground=COLOR_PRIMARY, font=("Microsoft YaHei", 10), relief="flat")
        self._commit_msg.pack(padx=5, pady=3)
        self._commit_msg.insert(0, "更新博客")

        # 右：核心按钮
        create_primary_button(ep_footer, "🚀 发布并同步推送", self._commit_push).pack(side=tk.RIGHT, padx=(8, 0))
        create_flat_button(ep_footer, "👁️ 预览导航结构", self._preview_nav).pack(side=tk.RIGHT)

        # 快捷上下文菜单
        self._ctx = tk.Menu(self.root, tearoff=0)
        self._ctx.add_command(label="✏️ 编辑节点名称 (双击)", command=self._edit_title)
        self._ctx.add_command(label="📁 修改底层物理文件名 (高级)", command=self._rename_file)
        self._ctx.add_separator()
        self._ctx.add_command(label="➕ 新分类目录", command=self._new_folder)
        self._ctx.add_command(label="📝 新文章文件", command=self._new_file)
        self._ctx.add_separator()
        self._ctx.add_command(label="⬆️ 大纲上移", command=self._move_up)
        self._ctx.add_command(label="⬇️ 大纲下移", command=self._move_down)
        self._ctx.add_separator()
        self._ctx.add_command(label="🗑️ 大纲移除/删除", command=self._delete)
        self._ctx.add_separator()
        self._ctx.add_command(label="🔍 在本地资源管理器中定位", command=self._open_in_explorer)

        self.tree.bind("<Button-3>", lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind("<Button-2>", lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)

    # ---------- 交互逻辑 ----------
    def _on_select(self, event):
        """选中某个大纲项时的编辑器调度"""
        self._force_save_now()

        item = self._get_sel_item()
        if not item:
            self._preview.delete(1.0, tk.END)
            self._preview_path = None
            return

        vals = self.tree.item(item, 'values')
        item_type, file_path_rel = vals[0], vals[1]
        clean_title = self._clean_title(self.tree.item(item, 'text'))

        if item_type == "file":
            self._preview.configure(state='normal')
            path = self.docs_dir / file_path_rel
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._preview.delete(1.0, tk.END)
                self._preview.insert(1.0, content)
                self._preview_path = path

                self.editor_info_label.config(text=f"📄 大纲绑定路径: docs/{file_path_rel}")
                self.editor_title_label.config(text=clean_title)
                self.status_label.config(text="● 已加载", fg=TEXT_MUTED)
            except Exception as e:
                self._preview_path = None
                self.status_label.config(text=f"✗ 文章内容读取失败: {e}", fg=COLOR_WARN)
        else:
            # 点击分类，编辑器切换为提示界面
            self._preview.configure(state='normal')
            self._preview.delete(1.0, tk.END)
            self._preview.insert(1.0,
                                 "\n\n\n\n\n       📁 分类栏目 [ " + clean_title + " ]\n\n       大纲中此处为一个逻辑分组。请在左侧树状图中点击它的子节点，或为其添加具体的文章开始书写。")
            self._preview.configure(state='disabled')

            self.editor_info_label.config(text="📁 逻辑分类目录")
            self.editor_title_label.config(text=clean_title)
            self.status_label.config(text="")
            self._preview_path = None

    def _on_double_click(self, event):
        """双击非分类叶子（文章名称），直接进入大纲重命名流程"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        vals = self.tree.item(item, 'values')
        if vals and vals[0] == "file":
            self._edit_title()

    def _on_editor_key(self, event):
        """输入反馈与自动保存机制"""
        self.status_label.config(text="○ 正在编辑...", fg=COLOR_PRIMARY)
        if self._save_timer:
            self.root.after_cancel(self._save_timer)
        # 静默 1.5 秒后自动执行写入
        self._save_timer = self.root.after(1500, self._auto_save)

    def _auto_save(self):
        if self._preview_path and self._preview_path.exists():
            content = self._preview.get(1.0, 'end-1c')
            try:
                with open(self._preview_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status_label.config(text="✓ 已自动保存", fg=COLOR_SUCCESS)
            except Exception as e:
                self.status_label.config(text=f"✗ 写入失败: {e}", fg=COLOR_WARN)
        self._save_timer = None

    def _force_save_now(self):
        """在切换节点或发布前强行收尾保存"""
        if self._save_timer:
            self.root.after_cancel(self._save_timer)
            self._auto_save()

    # ---------- 纯大纲下的一键创建与管理 ----------
    def _generate_unique_filepath(self, title):
        """在后台自动规划并维护物理文件的放置（托管机制，避免用户介入）"""
        posts_dir = self.docs_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        # 将标题中的特殊字符替换
        clean_title = re.sub(r'[\\/*?:"<>| ]', '-', title)
        clean_title = re.sub(r'-+', '-', clean_title).strip('-')
        if not clean_title:
            clean_title = f"post_{int(time.time())}"

        filename = f"{clean_title}.md"
        filepath = posts_dir / filename

        # 避开重名物理文件
        counter = 1
        while filepath.exists():
            filename = f"{clean_title}_{counter}.md"
            filepath = posts_dir / filename
            counter += 1

        return str(filepath.relative_to(self.docs_dir)).replace('\\', '/')

    def _new_file(self):
        """大纲视角下的新建文章"""
        title = simpledialog.askstring("新建文章", "请输入博文大纲展示名称:", parent=self.root)
        if not title:
            return

        # 1. 物理层无感代管生成
        rel_path = self._generate_unique_filepath(title)
        full_path = self.docs_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n在这里开始写作博文内容...")

        # 2. 挂载到大纲树上
        sel = self._get_sel_item()
        if sel:
            vals = self.tree.item(sel, 'values')
            if vals[0] == "dir":
                new_item = self.tree.insert(sel, 'end', text="📄 " + title, values=["file", rel_path])
            else:
                parent = self.tree.parent(sel)
                siblings = list(self.tree.get_children(parent))
                idx = siblings.index(sel)
                new_item = self.tree.insert(parent, idx + 1, text="📄 " + title, values=["file", rel_path])
        else:
            new_item = self.tree.insert("", 'end', text="📄 " + title, values=["file", rel_path])

        # 3. 自动同步保存配置并焦点切换
        self._save_nav_and_config()
        self.tree.selection_set(new_item)
        self.tree.see(new_item)

    def _new_folder(self):
        """新建分类分组"""
        name = simpledialog.askstring("新建分类栏目", "请输入新导航分类的名称:", parent=self.root)
        if not name:
            return

        sel = self._get_sel_item()
        if sel:
            vals = self.tree.item(sel, 'values')
            if vals[0] == "dir":
                new_item = self.tree.insert(sel, 'end', text="📁 " + name, open=True, values=["dir", ""])
            else:
                parent = self.tree.parent(sel)
                siblings = list(self.tree.get_children(parent))
                idx = siblings.index(sel)
                new_item = self.tree.insert(parent, idx + 1, text="📁 " + name, open=True, values=["dir", ""])
        else:
            new_item = self.tree.insert("", 'end', text="📁 " + name, open=True, values=["dir", ""])

        self._save_nav_and_config()
        self.tree.selection_set(new_item)
        self.tree.see(new_item)

    def _edit_title(self):
        """编辑导航名称。如果是文章，会联动重写对应物理文件的 H1 标题"""
        item = self._get_sel_item()
        if not item:
            return
        old_text = self.tree.item(item, 'text')
        is_dir = self._get_sel_is_dir()
        old_clean = self._clean_title(old_text)

        new = simpledialog.askstring("编辑导航大纲名称", "请输入在网站菜单中显示的新名称:", initialvalue=old_clean,
                                     parent=self.root)
        if not new or new == old_clean:
            return

        emoji = "📁 " if is_dir else "📄 "
        self.tree.item(item, text=emoji + new)

        # 改完大纲后，联动去改磁盘文件的 H1
        vals = self.tree.item(item, 'values')
        if vals and vals[0] == "file":
            full_path = self.docs_dir / vals[1]
            self._update_md_title(full_path, new)
            if self._preview_path == full_path:
                self.editor_title_label.config(text=new)
        else:
            self.editor_title_label.config(text=new)

        self._save_nav_and_config()

    def _update_md_title(self, filepath, new_title):
        """在写作者改动导航栏名字后，静默、无感、智能地更新 Markdown 第一行的一级标题 (# 标题)"""
        try:
            if not filepath.exists():
                return
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            in_front = False
            replaced = False
            for i, line in enumerate(lines):
                s = line.strip()
                if s == '---':
                    in_front = not in_front
                    continue
                if in_front:
                    continue
                if s.startswith('# ') and not s.startswith('## '):
                    lines[i] = f"# {new_title}"
                    replaced = True
                    break

            if not replaced:
                lines = [f"# {new_title}", ""] + lines

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            # 刷新编辑器文本视图
            if self._preview_path == filepath:
                self._preview.delete(1.0, tk.END)
                self._preview.insert(1.0, '\n'.join(lines))
        except Exception as e:
            print(f"联动修改文件标题出错: {e}")

    def _delete(self):
        """从导航中安全删除项。将物理文件处置权交给用户"""
        item = self._get_sel_item()
        if not item:
            return
        vals = self.tree.item(item, 'values')
        item_type, file_path_rel = vals[0], vals[1]
        title = self._clean_title(self.tree.item(item, 'text'))

        if item_type == "file" and file_path_rel == "index.md":
            messagebox.showwarning("警告", "首页 index.md 无法从大纲中删除")
            return

        confirm = messagebox.askyesnocancel(
            "安全删除大纲项目",
            f"您确定要将大纲项 \"{title}\" 移除吗？\n\n"
            f"● 选择 [是(Y)]：移除导航，并【彻底物理删除】其在磁盘中的绑定文件（不可找回）。\n"
            f"● 选择 [否(N)]：仅移出导航结构，【保留】磁盘中的物理文件（变为孤儿文件）。\n"
            f"● 选择 [取消]：放弃移除操作。"
        )

        if confirm is None:
            return

        if confirm is True:
            # 用户选择一并粉碎底层物理文件
            if item_type == "file" and file_path_rel:
                fp = self.docs_dir / file_path_rel
                if fp.exists():
                    try:
                        fp.unlink()
                    except Exception as e:
                        messagebox.showwarning("警告", f"物理文件删除失败: {e}")
            elif item_type == "dir":
                self._delete_node_files_recursive(item)

        self.tree.delete(item)
        self._save_nav_and_config()
        self._preview_path = None
        self.editor_title_label.config(text="请在左侧点击一个大纲节点")
        self.editor_info_label.config(text="")

    def _delete_node_files_recursive(self, parent_item):
        for child in self.tree.get_children(parent_item):
            vals = self.tree.item(child, 'values')
            if vals:
                if vals[0] == "file" and vals[1]:
                    fp = self.docs_dir / vals[1]
                    if fp.exists():
                        try:
                            fp.unlink()
                        except Exception:
                            pass
                elif vals[0] == "dir":
                    self._delete_node_files_recursive(child)

    def _rename_file(self):
        """修改物理底层的英文文件名(高级玩家使用，普通操作一般不推荐修改)"""
        item = self._get_sel_item()
        if not item:
            return
        vals = self.tree.item(item, 'values')
        if vals[0] != "file":
            messagebox.showinfo("提示", "逻辑分组没有底层物理文件")
            return

        old_rel = vals[1]
        if old_rel == "index.md":
            messagebox.showwarning("提示", "首页物理文件 index.md 不可更改")
            return

        old_full = self.docs_dir / old_rel
        new_name = simpledialog.askstring("重命名物理文件",
                                          "高级：请指定新的磁盘物理文件名 (建议纯英文数字小写 - 并带 .md):",
                                          initialvalue=old_full.name, parent=self.root)
        if not new_name or new_name == old_full.name:
            return
        if not new_name.endswith('.md'):
            new_name += '.md'

        new_full = old_full.parent / new_name
        if new_full.exists():
            messagebox.showerror("错误", "新指定的磁盘文件名已被其他文章占用")
            return

        try:
            old_full.rename(new_full)
            new_rel_path = str(new_full.relative_to(self.docs_dir)).replace('\\', '/')
            self.tree.item(item, values=["file", new_rel_path])
            self._save_nav_and_config()
            self.editor_info_label.config(text=f"📄 大纲绑定路径: docs/{new_rel_path}")
        except Exception as e:
            messagebox.showerror("错误", f"更改物理文件路径失败: {e}")

    # ---------- 大纲顺序调整 ----------
    def _move_up(self):
        item = self._get_sel_item()
        if not item:
            return
        parent = self.tree.parent(item)
        siblings = list(self.tree.get_children(parent))
        idx = siblings.index(item)
        if idx > 0:
            self.tree.move(item, parent, idx - 1)
            self.tree.see(item)
            self._save_nav_and_config()

    def _move_down(self):
        item = self._get_sel_item()
        if not item:
            return
        parent = self.tree.parent(item)
        siblings = list(self.tree.get_children(parent))
        idx = siblings.index(item)
        if idx < len(siblings) - 1:
            self.tree.move(item, parent, idx + 1)
            self.tree.see(item)
            self._save_nav_and_config()

    def _open_in_explorer(self):
        item = self._get_sel_item()
        if not item:
            return
        vals = self.tree.item(item, 'values')
        if vals and vals[1]:
            full = self.docs_dir / vals[1]
            if full.exists():
                subprocess.Popen(['explorer', '/select,', str(full)])

    # ---------- 导航数据重新打包并重写 YAML ----------
    def _build_nav_from_tree(self, parent_iid=""):
        """递归扫描 Treeview，倒序还原 MkDocs YAML 的 nav 规范树"""
        nav_list = []
        for child in self.tree.get_children(parent_iid):
            text = self._clean_title(self.tree.item(child, 'text'))
            vals = self.tree.item(child, 'values')
            item_type, file_path = vals[0], vals[1]

            if item_type == "dir":
                sub_nav = self._build_nav_from_tree(child)
                nav_list.append({text: sub_nav})
            elif item_type == "file":
                nav_list.append({text: file_path})
        return nav_list

    def _save_nav_and_config(self):
        """自动重新解析左侧 UI 并更新写入 mkdocs.yml，安全无失真"""
        self._force_save_now()
        nav_list = self._build_nav_from_tree()
        self.config_data['nav'] = nav_list

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                # 使用安全、格式友好的 dump 方式，不干扰其他选项 (如 theme, plugins)
                yaml.safe_dump(self.config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            self.status_label.config(text="✓ 大纲导航已同步物理文件", fg=COLOR_SUCCESS)
        except Exception as e:
            messagebox.showerror("写入配置失败", f"无法写入 mkdocs.yml 配置文件:\n{e}")

    # ---------- 预览 & 同步流程 ----------
    def _preview_nav(self):
        """展示最终将要生成的 YAML 真实大纲结构"""
        nav_list = self._build_nav_from_tree()
        nav_str = yaml.safe_dump({'nav': nav_list}, allow_unicode=True, default_flow_style=False, sort_keys=False)

        win = tk.Toplevel(self.root)
        win.title("预览生成的导航结构 (mkdocs.yml nav)")
        win.geometry("450x450")
        win.configure(bg=BG_MAIN)

        t_border = tk.Frame(win, bg=COLOR_BORDER)
        t_border.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        t = scrolledtext.ScrolledText(t_border, wrap=tk.WORD, font=("Consolas", 10), bg=BG_WHITE, fg=TEXT_DARK, bd=0)
        t.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        t.insert(1.0, nav_str)
        t.configure(state='disabled')

    def _commit_push(self):
        """一键打包、提交并推送"""
        self._save_nav_and_config()
        msg = self._commit_msg.get().strip() or "更新博客内容和大纲"

        try:
            r = subprocess.run(['git', 'add', '-A'], cwd=self.base_dir, capture_output=True, text=True)
            if r.returncode != 0:
                messagebox.showerror("错误", f"git add 失败:\n{r.stderr}")
                return

            r = subprocess.run(['git', 'commit', '-m', msg], cwd=self.base_dir, capture_output=True, text=True)
            if r.returncode == 0:
                r = subprocess.run(['git', 'push'], cwd=self.base_dir, capture_output=True, text=True)
                if r.returncode == 0:
                    messagebox.showinfo("同步成功", "大纲导航配置、新文章和改动已全部发布！")
                else:
                    messagebox.showwarning("推送失败", f"文章已保存并成功录入 Git，但远程同步失败:\n{r.stderr}")
            elif 'nothing to commit' in (r.stdout + r.stderr):
                r = subprocess.run(['git', 'push'], cwd=self.base_dir, capture_output=True, text=True)
                if r.returncode == 0:
                    messagebox.showinfo("同步成功", "文章已推送到最新，大纲导航无实质更改。")
                else:
                    messagebox.showinfo("推送完毕", "目录及大纲内容已经是最新状态。")
            else:
                messagebox.showerror("提交失败", f"Git 提交异常:\n{r.stderr}")
        except Exception as e:
            messagebox.showerror("流程异常", f"无法调起本地 Git 命令链: {e}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    BlogManager().run()