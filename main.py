import json
import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "languages.json"


def load_database():
    with DB_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("languages"), list):
        raise ValueError("languages.json の languages は配列である必要があります")
    return data


def detect_distro():
    """Return ('debian'|'arch'|None, display_name)."""
    info = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k] = v.strip().strip('"').strip("'")
    except OSError:
        return None, platform.system()
    ids = {info.get("ID", "").lower()}
    ids.update(x.lower() for x in info.get("ID_LIKE", "").split())
    if ids.intersection({"debian", "ubuntu", "linuxmint", "pop", "elementary"}):
        return "debian", info.get("PRETTY_NAME", "Debian系 Linux")
    if ids.intersection({"arch", "manjaro", "endeavouros", "garuda"}):
        return "arch", info.get("PRETTY_NAME", "Arch系 Linux")
    return None, info.get("PRETTY_NAME", "未対応のLinux")


class LanguageLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Langbox")
        self.root.geometry("1040x700")
        self.root.minsize(850, 560)
        self.root.configure(bg="#171a21")
        try:
            self.db = load_database()
        except Exception as exc:
            messagebox.showerror("データベースエラー", f"languages.json を読み込めません。\n{exc}")
            root.destroy()
            return

        self.distro, self.distro_name = detect_distro()
        self.manager = {"debian": "apt", "arch": "pacman"}.get(self.distro)
        self.languages = self.db["languages"]
        self.filtered = list(self.languages)
        self.selected = None
        self.busy = False
        self._build_style()
        self._build_ui()
        self._populate()
        self._set_status()

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#222733", foreground="#e8eaf0",
                        fieldbackground="#222733", rowheight=30, borderwidth=0)
        style.map("Treeview", background=[("selected", "#375a9e")],
                  foreground=[("selected", "#ffffff")])
        style.configure("TCombobox", fieldbackground="#252b38", background="#252b38",
                        foreground="#ffffff", arrowcolor="#ffffff")

    def _label(self, parent, text, size=10, color="#e8eaf0", bold=False):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Noto Sans CJK JP", size, "bold" if bold else "normal"))

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#202633", height=76)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="⌘  Langbox", bg="#202633", fg="#ffffff",
                 font=("Noto Sans CJK JP", 18, "bold")).pack(side="left", padx=22)
        self.os_label = tk.Label(top, text="OSを検出中…", bg="#202633", fg="#8fb5ff",
                                 font=("Noto Sans CJK JP", 10, "bold"))
        self.os_label.pack(side="right", padx=22)

        body = tk.Frame(self.root, bg="#171a21")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        left = tk.Frame(body, bg="#1e2430", width=300)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._label(left, "言語カタログ", 14, bold=True).pack(anchor="w", padx=14, pady=(14, 8))
        self.search_var = tk.StringVar()
        search = tk.Entry(left, textvariable=self.search_var, bg="#2a3140", fg="#ffffff",
                          insertbackground="white", relief="flat", font=("Noto Sans CJK JP", 10))
        search.pack(fill="x", padx=12, pady=(0, 10), ipady=8)
        search.insert(0, "")
        self.search_var.trace_add("write", lambda *_: self._populate())
        self.category_var = tk.StringVar(value="すべて")
        categories = ["すべて"] + self.db.get("categories", [])
        combo = ttk.Combobox(left, textvariable=self.category_var, values=categories,
                             state="readonly")
        combo.pack(fill="x", padx=12, pady=(0, 10))
        combo.bind("<<ComboboxSelected>>", lambda _e: self._populate())

        list_frame = tk.Frame(left, bg="#1e2430")
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(list_frame, columns=("category",), show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="言語 / ツール")
        self.tree.heading("category", text="カテゴリ")
        self.tree.column("#0", width=155, stretch=True)
        self.tree.column("category", width=115, stretch=False)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = tk.Frame(body, bg="#202633")
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.name_label = tk.Label(right, text="言語を選択してください", bg="#202633",
                                   fg="#ffffff", font=("Noto Sans CJK JP", 20, "bold"))
        self.name_label.pack(anchor="w", padx=20, pady=(20, 4))
        self.category_label = self._label(right, "カテゴリ", 9, "#8fb5ff")
        self.category_label.pack(anchor="w", padx=20)
        self.desc_label = tk.Label(right, text="左の一覧から言語を選ぶと詳細が表示されます。",
                                   bg="#202633", fg="#c4cad6", justify="left", anchor="w",
                                   wraplength=620, font=("Noto Sans CJK JP", 11))
        self.desc_label.pack(fill="x", padx=20, pady=(16, 12))
        self.status_label = tk.Label(right, text="状態：未確認", bg="#293242", fg="#d9e2f2",
                                     anchor="w", padx=12, pady=10,
                                     font=("Noto Sans CJK JP", 10, "bold"))
        self.status_label.pack(fill="x", padx=20, pady=8)

        self.package_label = tk.Label(right, text="パッケージ情報", bg="#202633", fg="#aeb8c9",
                                      justify="left", anchor="nw", font=("Noto Sans CJK JP", 10))
        self.package_label.pack(fill="x", padx=20, pady=8)
        buttons = tk.Frame(right, bg="#202633")
        buttons.pack(fill="x", padx=20, pady=12)
        self.install_btn = tk.Button(buttons, text="インストール", command=self.install_selected,
                                     bg="#3976d3", fg="white", activebackground="#2d62b3",
                                     activeforeground="white", relief="flat", padx=18, pady=10)
        self.install_btn.pack(side="left")
        self.remove_btn = tk.Button(buttons, text="アンインストール", command=self.remove_selected,
                                    bg="#9b4148", fg="white", activebackground="#7e3339",
                                    activeforeground="white", relief="flat", padx=18, pady=10)
        self.remove_btn.pack(side="left", padx=8)
        self.refresh_btn = tk.Button(buttons, text="状態を再確認", command=self.refresh_status,
                                     bg="#394354", fg="white", relief="flat", padx=14, pady=10)
        self.refresh_btn.pack(side="left")

        self._label(right, "実行ログ", 11, bold=True).pack(anchor="w", padx=20, pady=(10, 5))
        log_frame = tk.Frame(right, bg="#11151c")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        self.log = tk.Text(log_frame, bg="#11151c", fg="#b9d4c2", insertbackground="white",
                           relief="flat", wrap="word", font=("DejaVu Sans Mono", 9), height=10)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        log_scroll.pack(side="right", fill="y")

        bottom = tk.Frame(self.root, bg="#11151c", height=28)
        bottom.pack(fill="x", side="bottom")
        self.footer = tk.Label(bottom, text="準備完了", bg="#11151c", fg="#9aa6b8",
                               anchor="w", font=("Noto Sans CJK JP", 9))
        self.footer.pack(fill="x", padx=18, pady=5)

    def _set_status(self):
        if self.manager:
            self.os_label.config(text=f"{self.distro_name}  |  {self.manager.upper()}")
            self._log(f"OS検出: {self.distro_name} / パッケージ管理: {self.manager}")
        else:
            self.os_label.config(text=f"{self.distro_name}  |  未対応")
            self._log(f"未対応のOSです: {self.distro_name}")
            self.install_btn.config(state="disabled")
            self.remove_btn.config(state="disabled")

    def _log(self, text):
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")

    def _populate(self):
        query = self.search_var.get().strip().lower()
        category = self.category_var.get()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.filtered = []
        for lang in self.languages:
            haystack = " ".join([lang["name"], lang.get("category", ""), lang.get("description", "")]).lower()
            if query and query not in haystack:
                continue
            if category != "すべて" and lang.get("category") != category:
                continue
            self.filtered.append(lang)
            self.tree.insert("", "end", iid=str(len(self.filtered)-1),
                             text=lang["name"], values=(lang.get("category", ""),))
        if self.filtered:
            first = self.tree.get_children()[0]
            if not self.tree.selection():
                self.tree.selection_set(first)

    def _on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        try:
            lang = self.filtered[int(selection[0])]
        except (ValueError, IndexError):
            return
        self.selected = lang
        self.name_label.config(text=lang["name"])
        self.category_label.config(text=lang.get("category", ""))
        self.desc_label.config(text=lang.get("description", ""))
        packages = lang.get(self.distro, []) if self.distro else []
        self.package_label.config(text=f"このOSのパッケージ: {', '.join(packages) if packages else '標準リポジトリからの自動導入なし'}")
        note = lang.get("note")
        if note:
            self.package_label.config(text=self.package_label.cget("text") + "\n注意: " + note)
        self.refresh_status()

    def _installed(self, lang):
        check = lang.get("check")
        if not check or not shutil.which(check[0]):
            return False
        try:
            result = subprocess.run(check, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def refresh_status(self):
        if not self.selected:
            return
        lang = self.selected
        self.status_label.config(text="状態：確認中…")
        def worker():
            installed = self._installed(lang)
            self.root.after(0, lambda: self.status_label.config(
                text="状態：インストール済み（コマンド確認）" if installed else "状態：未検出（コマンド確認）",
                fg="#8fe0a4" if installed else "#e7c17b"))
        threading.Thread(target=worker, daemon=True).start()

    def _packages(self):
        if not self.selected or not self.distro:
            return []
        return self.selected.get(self.distro, [])

    def _run_command(self, command, title):
        if self.busy:
            return
        self.busy = True
        self._set_buttons("disabled")
        self.footer.config(text=title + "を実行中…")
        def worker():
            self.root.after(0, lambda: self._log("$ " + " ".join(command)))
            try:
                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
                for line in proc.stdout:
                    self.root.after(0, lambda s=line: self._log(s))
                code = proc.wait()
                result = (code == 0, f"終了コード: {code}")
            except Exception as exc:
                result = (False, str(exc))
            self.root.after(0, lambda: self._finish_command(*result, title=title))
        threading.Thread(target=worker, daemon=True).start()

    def _finish_command(self, success, detail, title):
        self._log(detail)
        self._log("完了" if success else "失敗")
        self.footer.config(text=title + ("が完了しました" if success else "に失敗しました"))
        self.busy = False
        self._set_buttons("normal")
        self.refresh_status()

    def _set_buttons(self, state):
        self.install_btn.config(state=state)
        self.remove_btn.config(state=state)
        self.refresh_btn.config(state=state)

    def install_selected(self):
        if not self.manager or not self.selected:
            return
        packages = self._packages()
        if not packages:
            messagebox.showinfo("自動インストール対象外", self.selected.get("note", "このOS向けのパッケージ情報がありません。"))
            return
        if not messagebox.askyesno("インストール確認",
                f"{self.selected['name']} をインストールします。\n\nパッケージ: {', '.join(packages)}\n\n管理者権限が必要です。続行しますか？"):
            return
        if self.manager == "apt":
            cmd = ["pkexec", "apt-get", "install", "-y", "--"] + packages
            if not shutil.which("pkexec"):
                cmd = ["sudo", "apt-get", "install", "-y", "--"] + packages
        else:
            cmd = ["pkexec", "pacman", "-S", "--needed", "--noconfirm", "--"] + packages
            if not shutil.which("pkexec"):
                cmd = ["sudo", "pacman", "-S", "--needed", "--noconfirm", "--"] + packages
        self._run_command(cmd, "インストール")

    def remove_selected(self):
        if not self.manager or not self.selected:
            return
        packages = self._packages()
        if not packages:
            messagebox.showinfo("削除対象外", "このOS向けのパッケージ情報がありません。")
            return
        if not messagebox.askyesno("アンインストール確認",
                f"{self.selected['name']} に関連する以下のパッケージを削除します。\n\n{', '.join(packages)}\n\n他のソフトが依存している可能性があります。続行しますか？"):
            return
        if self.manager == "apt":
            cmd = ["pkexec", "apt-get", "remove", "-y", "--"] + packages
            if not shutil.which("pkexec"):
                cmd = ["sudo", "apt-get", "remove", "-y", "--"] + packages
        else:
            cmd = ["pkexec", "pacman", "-R", "--noconfirm", "--"] + packages
            if not shutil.which("pkexec"):
                cmd = ["sudo", "pacman", "-R", "--noconfirm", "--"] + packages
        self._run_command(cmd, "アンインストール")


def main():
    root = tk.Tk()
    LanguageLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
