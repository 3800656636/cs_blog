#!/usr/bin/env python3
"""
MkDocs Blog Manager - 可视化博客管理工具
双击树节点编辑标题 | 右键操作 | 拖拽排序 | 一键提交
直接运行: python blog_manager.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import json
import os
import shutil
import subprocess
from pathlib import Path

# ============================================================
# BlogManager 主类
# ============================================================

class BlogManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MkDocs Blog Manager")
        self.root.geometry("1200x750")

        self.base_dir = Path(__file__).parent.resolve()
        self.docs_dir = self.base_dir / "docs"
        self.config_file = self.base_dir / "mkdocs.yml"
        self.meta_file = self.docs_dir / ".nav_meta.json"

        self.custom_titles = {}
        self._load_meta()
        self._preview_path = None

        self._setup_ui()
        self._refresh_tree()

    # ---------- meta 持久化 ----------
    def _load_meta(self):
        if self.meta_file.exists():
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    self.custom_titles = json.load(f).get('custom_titles', {})
            except Exception:
                self.custom_titles = {}

    def _save_meta(self):
        self.meta_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump({'custom_titles': self.custom_titles}, f, ensure_ascii=False, indent=2)

    # ---------- 标题提取 ----------
    def _extract_title(self, filepath):
        rel = str(filepath.relative_to(self.docs_dir)).replace('\\', '/')
        if rel in self.custom_titles:
            return self.custom_titles[rel]
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

    def _get_dir_display(self, rel_path):
        rel = rel_path.replace('\\', '/')
        if rel in self.custom_titles:
            return self.custom_titles[rel]
        return os.path.basename(rel_path)

    # ---------- 构建树 ----------
    def _refresh_tree(self):
        selected_path = None
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], 'values')
            if vals:
                selected_path = vals[0]

        self.tree.delete(*self.tree.get_children())

        if not self.docs_dir.exists():
            return

        self._populate("", self.docs_dir)

        if selected_path:
            self._select_by_path(selected_path)
        else:
            # 默认选中 index.md
            self._select_by_path('docs/index.md')

    def _populate(self, parent, dir_path):
        entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for entry in entries:
            name = entry.name
            if name.startswith('.') or name == 'CNAME':
                continue
            if entry.is_dir() and name in ('assets', 'javascripts', 'stylesheets'):
                continue

            if entry.is_dir():
                rel = str(entry.relative_to(self.docs_dir)).replace('\\', '/')
                display = self._get_dir_display(rel)
                iid = self.tree.insert(parent, 'end', text=display, open=True,
                                       values=[str(entry.relative_to(self.base_dir)).replace('\\', '/')])
                self._populate(iid, entry)
            elif entry.suffix == '.md':
                title = self._extract_title(entry)
                iid = self.tree.insert(parent, 'end', text=title,
                                       values=[str(entry.relative_to(self.base_dir)).replace('\\', '/')])

    def _select_by_path(self, path):
        def _search(item):
            vals = self.tree.item(item, 'values')
            if vals and vals[0] == path:
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

    # ---------- 获取选中信息 ----------
    def _get_sel_item(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _get_sel_path(self):
        item = self._get_sel_item()
        if not item:
            return None
        vals = self.tree.item(item, 'values')
        return vals[0] if vals else None

    def _get_sel_fullpath(self):
        p = self._get_sel_path()
        return self.base_dir / p if p else None

    def _get_sel_is_dir(self):
        item = self._get_sel_item()
        if not item:
            return False
        return self.tree.get_children(item) != ()

    # ---------- UI 搭建 ----------
    def _setup_ui(self):
        # 主分割面板
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # ---- 左侧：目录树 ----
        left = ttk.Frame(main_pane)
        main_pane.add(left, weight=1)

        # 工具栏
        tbar = ttk.Frame(left)
        tbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(tbar, text="+ 新文件", command=self._new_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(tbar, text="+ 新文件夹", command=self._new_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(tbar, text="重命名", command=self._rename).pack(side=tk.LEFT, padx=2)
        ttk.Button(tbar, text="删除", command=self._delete).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(tbar, text="↑", command=self._move_up).pack(side=tk.LEFT, padx=1)
        ttk.Button(tbar, text="↓", command=self._move_down).pack(side=tk.LEFT, padx=1)

        # 树
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.tree = ttk.Treeview(tree_frame, selectmode='browse', show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview).pack(fill=tk.Y, side=tk.RIGHT)
        self.tree.configure(yscrollcommand=self.tree.yview)

        # 右键菜单
        self._ctx = tk.Menu(self.root, tearoff=0)
        self._ctx.add_command(label="编辑标题", command=self._edit_title)
        self._ctx.add_separator()
        self._ctx.add_command(label="+ 新文件", command=self._new_file)
        self._ctx.add_command(label="+ 新文件夹", command=self._new_folder)
        self._ctx.add_separator()
        self._ctx.add_command(label="重命名文件", command=self._rename)
        self._ctx.add_command(label="删除", command=self._delete)
        self._ctx.add_separator()
        self._ctx.add_command(label="↑ 上移", command=self._move_up)
        self._ctx.add_command(label="↓ 下移", command=self._move_down)
        self._ctx.add_separator()
        self._ctx.add_command(label="在资源管理器中打开", command=self._open_in_explorer)

        self.tree.bind("<Button-3>", lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind("<Button-2>", lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self._edit_title())

        # ---- 右侧：预览 ----
        right = ttk.Frame(main_pane)
        main_pane.add(right, weight=2)
        ttk.Label(right, text="文件预览 (可直接编辑)", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self._preview = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Consolas", 10))
        self._preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._preview.bind("<FocusOut>", self._save_preview)

        # ---- 底部：Git 操作栏 ----
        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(bottom, text="提交信息:").pack(side=tk.LEFT)
        self._commit_msg = ttk.Entry(bottom, width=50)
        self._commit_msg.pack(side=tk.LEFT, padx=5)
        self._commit_msg.insert(0, "更新博客")

        ttk.Button(bottom, text="保存配置", command=self._save_config).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="提交并推送", command=self._commit_push).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="预览导航", command=self._preview_nav).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="刷新树", command=self._refresh_tree).pack(side=tk.RIGHT, padx=2)

    # ---------- 树操作 ----------
    def _on_select(self, event):
        """选中文件时显示预览"""
        self._save_preview()  # 先保存之前的编辑
        path = self._get_sel_fullpath()
        if not path or path.is_dir():
            self._preview.delete(1.0, tk.END)
            self._preview_path = None
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._preview.delete(1.0, tk.END)
            self._preview.insert(1.0, content)
            self._preview_path = path
        except Exception:
            self._preview_path = None

    def _save_preview(self, event=None):
        if self._preview_path and self._preview_path.exists():
            content = self._preview.get(1.0, 'end-1c')
            try:
                with open(self._preview_path, 'r', encoding='utf-8') as f:
                    old = f.read()
                if content != old:
                    with open(self._preview_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            except Exception:
                pass

    def _edit_title(self):
        """编辑树节点的显示标题"""
        item = self._get_sel_item()
        if not item:
            return
        old = self.tree.item(item, 'text')
        new = simpledialog.askstring("编辑标题", "输入导航中显示的标题:", initialvalue=old, parent=self.root)
        if not new or new == old:
            return
        self.tree.item(item, text=new)
        # 持久化自定义标题
        vals = self.tree.item(item, 'values')
        if vals:
            full = self.base_dir / vals[0]
            if full.is_dir():
                rel = str(full.relative_to(self.docs_dir)).replace('\\', '/')
            else:
                rel = str(full.relative_to(self.docs_dir)).replace('\\', '/')
            self.custom_titles[rel] = new
        self._save_meta()

    def _new_file(self):
        parent_item, parent_dir = self._get_target_dir()
        name = simpledialog.askstring("新建文件", "文件名 (不含 .md):", parent=self.root)
        if not name:
            return
        fpath = parent_dir / (name + '.md')
        if fpath.exists():
            messagebox.showerror("错误", f"文件已存在: {fpath.name}")
            return
        fpath.parent.mkdir(parents=True, exist_ok=True)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(f"# {name}\n\n")
        self._refresh_tree()
        self._select_by_path(str(fpath.relative_to(self.base_dir)).replace('\\', '/'))

    def _new_folder(self):
        parent_item, parent_dir = self._get_target_dir()
        name = simpledialog.askstring("新建文件夹", "文件夹名:", parent=self.root)
        if not name:
            return
        dpath = parent_dir / name
        if dpath.exists():
            messagebox.showerror("错误", f"文件夹已存在: {name}")
            return
        dpath.mkdir(parents=True)
        self._refresh_tree()
        self._select_by_path(str(dpath.relative_to(self.base_dir)).replace('\\', '/'))

    def _get_target_dir(self):
        item = self._get_sel_item()
        if item:
            vals = self.tree.item(item, 'values')
            path = self.base_dir / vals[0] if vals else self.docs_dir
            if path.is_file():
                parent_item = self.tree.parent(item)
                if parent_item:
                    pvals = self.tree.item(parent_item, 'values')
                    return parent_item, (self.base_dir / pvals[0] if pvals else self.docs_dir)
                return "", self.docs_dir
            return item, path
        return "", self.docs_dir

    def _rename(self):
        """重命名实际文件/文件夹"""
        item = self._get_sel_item()
        if not item:
            return
        vals = self.tree.item(item, 'values')
        old_path = self.base_dir / vals[0]

        if old_path == self.docs_dir / 'index.md':
            messagebox.showwarning("警告", "index.md 不可重命名")
            return

        if old_path.is_dir():
            old_name = old_path.name
            new_name = simpledialog.askstring("重命名", "新文件夹名:", initialvalue=old_name, parent=self.root)
            if not new_name or new_name == old_name:
                return
            new_path = old_path.parent / new_name
        else:
            old_name = old_path.stem
            new_name = simpledialog.askstring("重命名", "新文件名 (不含 .md):", initialvalue=old_name, parent=self.root)
            if not new_name or new_name == old_name:
                return
            new_path = old_path.parent / (new_name + '.md')

        if new_path.exists():
            messagebox.showerror("错误", "目标已存在")
            return
        old_path.rename(new_path)
        # 更新自定义标题映射
        old_rel = str(old_path.relative_to(self.docs_dir)).replace('\\', '/')
        new_rel = str(new_path.relative_to(self.docs_dir)).replace('\\', '/')
        if old_rel in self.custom_titles:
            self.custom_titles[new_rel] = self.custom_titles.pop(old_rel)
            self._save_meta()
        self._refresh_tree()

    def _delete(self):
        item = self._get_sel_item()
        if not item:
            return
        vals = self.tree.item(item, 'values')
        path = self.base_dir / vals[0]

        if path == self.docs_dir / 'index.md':
            messagebox.showwarning("警告", "不能删除首页 index.md")
            return

        name = self.tree.item(item, 'text')
        if not messagebox.askyesno("确认删除", f"确定删除 \"{name}\" 吗？\n\n此操作不可撤销！"):
            return

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
            # 清理自定义标题
            rel = str(path.relative_to(self.docs_dir)).replace('\\', '/')
            self.custom_titles.pop(rel, None)
            self._save_meta()
        self._refresh_tree()

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

    def _open_in_explorer(self):
        path = self._get_sel_fullpath()
        if path:
            subprocess.Popen(['explorer', '/select,', str(path)])

    # ---------- 导航生成 ----------
    def _generate_nav_lines(self, parent_item, indent):
        lines = []
        prefix = ' ' * indent
        for child in self.tree.get_children(parent_item):
            text = self.tree.item(child, 'text')
            vals = self.tree.item(child, 'values')
            grandchildren = self.tree.get_children(child)

            if grandchildren:
                # 有子节点 → 作为分组
                lines.append(f"{prefix}- {text}:")
                lines.extend(self._generate_nav_lines(child, indent + 4))
            else:
                # 叶子节点 → 文件
                if vals:
                    rel = vals[0]
                    if rel.startswith('docs/'):
                        rel = rel[5:]
                    rel = rel.replace('\\', '/')
                    lines.append(f"{prefix}- {text}: {rel}")
        return lines

    def _generate_nav(self):
        lines = ['nav:']
        lines.extend(self._generate_nav_lines("", 2))
        return '\n'.join(lines)

    # ---------- 配置保存 ----------
    def _save_config(self):
        self._save_preview()
        nav = self._generate_nav()
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                old = f.read()
        except Exception:
            messagebox.showerror("错误", "找不到 mkdocs.yml")
            return

        # 截断旧 nav 并追加新的
        lines = old.split('\n')
        new_lines = []
        skip = False
        for line in lines:
            if not skip and line.startswith('nav:'):
                skip = True
                continue
            if skip:
                if line and line[0] in (' ', '\t') or not line.strip():
                    continue
                skip = False
                new_lines.append(line)
                continue
            new_lines.append(line)

        # 去掉尾部空行，追加 nav
        while new_lines and not new_lines[-1].strip():
            new_lines.pop()
        new_lines.append('')
        new_lines.append(nav)
        new_lines.append('')

        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

        messagebox.showinfo("成功", "mkdocs.yml 已保存!")

    # ---------- Git 操作 ----------
    def _commit_push(self):
        self._save_config()

        msg = self._commit_msg.get().strip() or "更新博客"

        try:
            r = subprocess.run(['git', 'add', '-A'], cwd=self.base_dir, capture_output=True, text=True)
            if r.returncode != 0:
                messagebox.showerror("错误", f"git add 失败:\n{r.stderr}")
                return

            r = subprocess.run(['git', 'commit', '-m', msg], cwd=self.base_dir, capture_output=True, text=True)
            if r.returncode == 0:
                r = subprocess.run(['git', 'push'], cwd=self.base_dir, capture_output=True, text=True)
                if r.returncode == 0:
                    messagebox.showinfo("完成", "已保存 → 提交 → 推送成功!")
                else:
                    messagebox.showwarning("部分成功", f"已提交但推送失败:\n{r.stderr}")
            elif 'nothing to commit' in (r.stdout + r.stderr):
                # 尝试推送未推送的提交
                r = subprocess.run(['git', 'push'], cwd=self.base_dir, capture_output=True, text=True)
                if r.returncode == 0:
                    messagebox.showinfo("完成", "没有新更改，但已推送!")
                else:
                    messagebox.showinfo("提示", "没有需要提交的更改")
            else:
                messagebox.showerror("错误", f"提交失败:\n{r.stderr}")
        except Exception as e:
            messagebox.showerror("错误", f"Git 操作失败:\n{e}")

    def _preview_nav(self):
        nav = self._generate_nav()
        win = tk.Toplevel(self.root)
        win.title("导航预览")
        win.geometry("500x400")
        t = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10))
        t.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        t.insert(1.0, nav)
        t.configure(state='disabled')

    # ---------- 启动 ----------
    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    BlogManager().run()
