import json
import os
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
from typing import Optional


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(
    os.environ.get("QINGYU_DATA_DIR")
    or str(Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())) / "QingYuReader")
)
SETTINGS_PATH = DATA_DIR / "reader_settings.json"
CHAPTER_PATTERN = re.compile(
    r"^\s*(第[0-9零一二三四五六七八九十百千万两〇]+[章节卷部篇集回幕折]\s*.*|"
    r"(正文\s*)?第\s*\d+\s*[章节卷部篇集回幕折]\s*.*|"
    r"(chapter|prologue|epilogue)\s+\d*.*|"
    r"(序章|楔子|引子|前言|后记|番外)\s*.*)$",
    re.IGNORECASE,
)


class NovelReaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("轻羽阅读器")
        self.root.geometry("1180x760")
        self.root.minsize(960, 640)

        self.settings = self.load_settings()
        self.current_file = None
        self.chapter_positions = []
        self.content_text = ""
        self.recent_books = self.settings.get("recent_books", [])

        self.base_font_size = self.settings.get("font_size", 18)
        self.is_night_mode = self.settings.get("night_mode", False)

        self.reader_font = font.Font(family="Microsoft YaHei UI", size=self.base_font_size)
        self.title_font = font.Font(family="Microsoft YaHei UI", size=18, weight="bold")

        self.configure_style()
        self.build_layout()
        self.bind_events()
        self.apply_theme()
        self.restore_last_file()

    def load_settings(self) -> dict:
        defaults = {
            "font_size": 18,
            "night_mode": False,
            "last_file": "",
            "window_geometry": "",
            "last_chapter_index": 0,
            "last_scroll_fraction": 0.0,
            "recent_books": [],
        }
        if not SETTINGS_PATH.exists():
            return defaults
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            defaults.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
        return defaults

    def save_settings(self) -> None:
        self.settings["font_size"] = self.base_font_size
        self.settings["night_mode"] = self.is_night_mode
        self.settings["window_geometry"] = self.root.geometry()
        if self.current_file:
            self.settings["last_file"] = str(self.current_file.resolve(strict=False))
        self.settings["recent_books"] = self.recent_books
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(self.settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def configure_style(self) -> None:
        self.style = ttk.Style()
        self.style.theme_use("clam")

    def build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=(12, 10))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(8, weight=1)
        self.toolbar = toolbar

        ttk.Button(toolbar, text="导入 TXT", command=self.open_file).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(toolbar, text="最近书单", command=self.toggle_recent_panel).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="A-", width=4, command=lambda: self.change_font_size(-1)).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(toolbar, text="A+", width=4, command=lambda: self.change_font_size(1)).grid(
            row=0, column=3, padx=4
        )

        self.font_size_var = tk.StringVar(value=f"字号 {self.base_font_size}")
        ttk.Label(toolbar, textvariable=self.font_size_var).grid(row=0, column=4, padx=(8, 12))

        self.progress_var = tk.StringVar(value="进度 0%")
        ttk.Label(toolbar, textvariable=self.progress_var).grid(row=0, column=5, padx=(0, 12))

        self.mode_var = tk.BooleanVar(value=self.is_night_mode)
        ttk.Checkbutton(toolbar, text="夜间模式", variable=self.mode_var, command=self.toggle_night_mode).grid(
            row=0, column=6, padx=(4, 12)
        )

        ttk.Button(toolbar, text="上一章", command=lambda: self.navigate_chapter(-1)).grid(
            row=0, column=7, padx=4
        )
        ttk.Button(toolbar, text="下一章", command=lambda: self.navigate_chapter(1)).grid(
            row=0, column=8, padx=4
        )

        self.file_label_var = tk.StringVar(value="未打开文件")
        ttk.Label(toolbar, textvariable=self.file_label_var).grid(row=0, column=9, sticky="e")

        content = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.content_pane = content

        sidebar = ttk.Frame(content, padding=(8, 8))
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(1, weight=1)
        self.sidebar = sidebar

        ttk.Label(sidebar, text="章节目录").grid(row=0, column=0, sticky="w", pady=(0, 8))

        toc_frame = ttk.Frame(sidebar)
        toc_frame.grid(row=1, column=0, sticky="nsew")
        toc_frame.columnconfigure(0, weight=1)
        toc_frame.rowconfigure(0, weight=1)

        self.chapter_listbox = tk.Listbox(
            toc_frame,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            font=("Microsoft YaHei UI", 11),
        )
        self.chapter_listbox.grid(row=0, column=0, sticky="nsew")

        toc_scrollbar = ttk.Scrollbar(toc_frame, orient="vertical", command=self.chapter_listbox.yview)
        toc_scrollbar.grid(row=0, column=1, sticky="ns")
        self.chapter_listbox.configure(yscrollcommand=toc_scrollbar.set)

        recent_frame = ttk.Frame(sidebar)
        recent_frame.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.rowconfigure(1, weight=1)
        self.recent_frame = recent_frame

        self.recent_label_var = tk.StringVar(value="最近打开")
        ttk.Label(recent_frame, textvariable=self.recent_label_var).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.recent_listbox = tk.Listbox(
            recent_frame,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            height=6,
            font=("Microsoft YaHei UI", 10),
        )
        self.recent_listbox.grid(row=1, column=0, sticky="nsew")
        self.recent_listbox.bind("<Double-Button-1>", self.on_recent_book_open)
        self.recent_listbox.bind("<Return>", self.on_recent_book_open)

        reader_shell = ttk.Frame(content, padding=(20, 20))
        reader_shell.columnconfigure(0, weight=1)
        reader_shell.rowconfigure(1, weight=1)
        self.reader_shell = reader_shell

        self.chapter_title_var = tk.StringVar(value="请导入 TXT 文件")
        ttk.Label(reader_shell, textvariable=self.chapter_title_var, font=self.title_font).grid(
            row=0, column=0, sticky="w", pady=(0, 16)
        )

        text_frame = ttk.Frame(reader_shell)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text_widget = tk.Text(
            text_frame,
            wrap="word",
            font=self.reader_font,
            relief="flat",
            borderwidth=0,
            undo=False,
            padx=34,
            pady=26,
            spacing1=8,
            spacing2=6,
            spacing3=10,
            insertwidth=0,
        )
        self.text_widget.grid(row=0, column=0, sticky="nsew")
        self.text_widget.configure(state="disabled")

        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_widget.yview)
        text_scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)

        content.add(sidebar, weight=1)
        content.add(reader_shell, weight=4)

        self.status_var = tk.StringVar(value="准备就绪")
        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w", padding=(12, 6))
        status.grid(row=2, column=0, sticky="ew")
        self.recent_panel_visible = True
        self.refresh_recent_books()

    def bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Control-o>", lambda _event: self.open_file())
        self.root.bind("<Control-plus>", lambda _event: self.change_font_size(1))
        self.root.bind("<Control-equal>", lambda _event: self.change_font_size(1))
        self.root.bind("<Control-minus>", lambda _event: self.change_font_size(-1))
        self.root.bind("<Control-d>", lambda _event: self.flip_night_mode())
        self.root.bind("<Control-r>", lambda _event: self.toggle_recent_panel())
        self.root.bind("<Left>", lambda _event: self.navigate_chapter(-1))
        self.root.bind("<Right>", lambda _event: self.navigate_chapter(1))
        self.root.bind("<Up>", lambda _event: self.navigate_page(-1))
        self.root.bind("<Down>", lambda _event: self.navigate_page(1))
        self.chapter_listbox.bind("<<ListboxSelect>>", self.on_chapter_select)
        self.text_widget.bind("<MouseWheel>", self.on_reader_scroll)
        self.text_widget.bind("<ButtonRelease-1>", self.on_reader_scroll)
        self.text_widget.bind("<KeyRelease-Up>", self.on_reader_scroll)
        self.text_widget.bind("<KeyRelease-Down>", self.on_reader_scroll)
        self.text_widget.bind("<KeyRelease-Prior>", self.on_reader_scroll)
        self.text_widget.bind("<KeyRelease-Next>", self.on_reader_scroll)

    def apply_theme(self) -> None:
        if self.is_night_mode:
            palette = {
                "bg": "#171a1f",
                "surface": "#20242b",
                "panel": "#232831",
                "text": "#e6e1d9",
                "muted": "#9aa3b2",
                "accent": "#c9985f",
                "list_select": "#324053",
            }
        else:
            palette = {
                "bg": "#f5efe2",
                "surface": "#fffdfa",
                "panel": "#efe7d7",
                "text": "#2e2a25",
                "muted": "#6c6258",
                "accent": "#8f5b2e",
                "list_select": "#d9c8b0",
            }

        self.root.configure(bg=palette["bg"])
        self.style.configure("TFrame", background=palette["bg"])
        self.style.configure("TPanedwindow", background=palette["bg"])
        self.style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
        self.style.configure("TButton", background=palette["panel"], foreground=palette["text"], borderwidth=0)
        self.style.map("TButton", background=[("active", palette["list_select"])])
        self.style.configure("TCheckbutton", background=palette["bg"], foreground=palette["text"])
        self.style.map("TCheckbutton", background=[("active", palette["bg"])])
        self.style.configure("Vertical.TScrollbar", background=palette["panel"], troughcolor=palette["bg"])

        self.toolbar.configure(style="TFrame")
        self.sidebar.configure(style="TFrame")
        self.reader_shell.configure(style="TFrame")
        self.content_pane.configure(style="TPanedwindow")

        self.chapter_listbox.configure(
            bg=palette["surface"],
            fg=palette["text"],
            selectbackground=palette["list_select"],
            selectforeground=palette["text"],
        )
        self.recent_listbox.configure(
            bg=palette["surface"],
            fg=palette["text"],
            selectbackground=palette["list_select"],
            selectforeground=palette["text"],
        )
        self.text_widget.configure(
            bg=palette["surface"],
            fg=palette["text"],
            insertbackground=palette["text"],
            selectbackground=palette["accent"],
            selectforeground=palette["surface"],
        )
        self.status_var.set("夜间模式已开启" if self.is_night_mode else "日间模式已开启")

    def toggle_night_mode(self) -> None:
        self.is_night_mode = self.mode_var.get()
        self.mode_var.set(self.is_night_mode)
        self.apply_theme()

    def flip_night_mode(self) -> None:
        self.mode_var.set(not self.mode_var.get())
        self.toggle_night_mode()

    def change_font_size(self, delta: int) -> None:
        new_size = max(12, min(32, self.base_font_size + delta))
        if new_size == self.base_font_size:
            return
        self.base_font_size = new_size
        self.reader_font.configure(size=self.base_font_size)
        self.font_size_var.set(f"字号 {self.base_font_size}")
        self.status_var.set(f"当前字号：{self.base_font_size}")

    def open_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择 TXT 小说",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if file_path:
            self.load_book(Path(file_path))

    def restore_last_file(self) -> None:
        geometry = self.settings.get("window_geometry")
        if geometry:
            self.root.geometry(geometry)

        last_file = self.settings.get("last_file", "")
        if last_file and Path(last_file).exists():
            self.load_book(
                Path(last_file),
                restore_index=self.settings.get("last_chapter_index", 0),
                scroll_fraction=float(self.settings.get("last_scroll_fraction", 0.0)),
            )

    def load_book(self, path: Path, restore_index: int = 0, scroll_fraction: float = 0.0) -> None:
        try:
            raw_text, encoding = self.read_text_file(path)
        except OSError as exc:
            messagebox.showerror("打开失败", f"无法读取文件：\n{exc}")
            return

        self.current_file = path.resolve(strict=False)
        self.content_text = self.normalize_text(raw_text)
        self.chapter_positions = self.extract_chapters(self.content_text)

        self.chapter_listbox.delete(0, tk.END)
        for title, _start, _end in self.chapter_positions:
            self.chapter_listbox.insert(tk.END, title)

        self.file_label_var.set(self.current_file.name)
        self.status_var.set(f"已载入 {self.current_file.name}，编码：{encoding}，共 {len(self.chapter_positions)} 章")

        if not self.chapter_positions:
            self.chapter_positions = [("正文", 0, len(self.content_text))]
            self.chapter_listbox.insert(tk.END, "正文")

        recent_state = self.get_book_state(self.current_file)
        if recent_state:
            restore_index = recent_state.get("chapter_index", restore_index)
            scroll_fraction = recent_state.get("scroll_fraction", scroll_fraction)

        target_index = min(max(restore_index, 0), len(self.chapter_positions) - 1)
        self.show_chapter(target_index, scroll_fraction=float(scroll_fraction))
        self.remember_current_book()

    def read_text_file(self, path: Path) -> tuple[str, str]:
        encodings = ("utf-8", "utf-8-sig", "gb18030", "utf-16", "big5")
        data = path.read_bytes()
        for encoding in encodings:
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        return data.decode("latin-1"), "latin-1"

    def normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        compacted = []
        blank_seen = False
        for line in lines:
            if line.strip():
                compacted.append(line)
                blank_seen = False
            elif not blank_seen:
                compacted.append("")
                blank_seen = True
        return "\n".join(compacted).strip()

    def extract_chapters(self, text: str) -> list[tuple[str, int, int]]:
        lines = text.split("\n")
        positions = []
        cursor = 0
        for line in lines:
            if CHAPTER_PATTERN.match(line.strip()):
                positions.append((line.strip(), cursor))
            cursor += len(line) + 1

        if not positions:
            return []

        chapters = []
        for index, (title, start) in enumerate(positions):
            end = positions[index + 1][1] if index + 1 < len(positions) else len(text)
            chapters.append((title, start, end))

        first_start = chapters[0][1]
        if first_start > 0:
            chapters.insert(0, ("开篇", 0, first_start))
        return chapters

    def show_chapter(self, index: int, scroll_fraction: float = 0.0) -> None:
        if not self.chapter_positions:
            return

        title, start, end = self.chapter_positions[index]
        chapter_text = self.content_text[start:end].strip()

        self.chapter_title_var.set(title)
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", chapter_text)
        self.text_widget.configure(state="disabled")
        self.root.after_idle(lambda: self.text_widget.yview_moveto(max(0.0, min(scroll_fraction, 1.0))))

        self.chapter_listbox.selection_clear(0, tk.END)
        self.chapter_listbox.selection_set(index)
        self.chapter_listbox.activate(index)
        self.chapter_listbox.see(index)

        self.settings["last_chapter_index"] = index
        self.settings["last_scroll_fraction"] = max(0.0, min(scroll_fraction, 1.0))
        self.update_current_book_state()
        self.update_progress_display()
        self.status_var.set(f"当前章节：{title}")

    def on_chapter_select(self, _event=None) -> None:
        selection = self.chapter_listbox.curselection()
        if selection:
            self.show_chapter(selection[0])

    def navigate_chapter(self, offset: int) -> None:
        if not self.chapter_positions:
            return
        current_index = self.settings.get("last_chapter_index", 0)
        target_index = min(max(current_index + offset, 0), len(self.chapter_positions) - 1)
        if target_index != current_index:
            self.show_chapter(target_index)

    def navigate_page(self, direction: int) -> None:
        if not self.chapter_positions or direction == 0:
            return

        current_index = self.settings.get("last_chapter_index", 0)
        start_fraction = self.text_widget.yview()[0]
        scroll_units = 1 if direction > 0 else -1
        self.text_widget.yview_scroll(scroll_units, "page")
        self.root.after_idle(
            lambda: self.finalize_page_navigation(current_index, start_fraction, direction)
        )

    def finalize_page_navigation(self, chapter_index: int, start_fraction: float, direction: int) -> None:
        end_fraction = self.text_widget.yview()[0]
        threshold = 1e-6

        if direction > 0 and abs(end_fraction - start_fraction) <= threshold:
            if chapter_index < len(self.chapter_positions) - 1:
                self.show_chapter(chapter_index + 1, scroll_fraction=0.0)
            return

        if direction < 0 and abs(end_fraction - start_fraction) <= threshold:
            if chapter_index > 0:
                self.show_chapter(chapter_index - 1, scroll_fraction=1.0)
            return

        self.persist_current_position()

    def update_progress_display(self) -> None:
        if not self.chapter_positions:
            self.progress_var.set("进度 0%")
            return
        chapter_index = self.settings.get("last_chapter_index", 0)
        chapter_total = max(len(self.chapter_positions), 1)
        scroll_fraction = self.text_widget.yview()[0] if self.chapter_positions else 0.0
        progress = ((chapter_index + scroll_fraction) / chapter_total) * 100
        self.progress_var.set(f"进度 {progress:.1f}%")

    def on_reader_scroll(self, _event=None) -> None:
        if not self.chapter_positions or not self.current_file:
            return
        self.root.after_idle(self.persist_current_position)

    def persist_current_position(self) -> None:
        if not self.chapter_positions or not self.current_file:
            return
        self.settings["last_scroll_fraction"] = self.text_widget.yview()[0]
        self.update_current_book_state()
        self.update_progress_display()

    def get_book_state(self, path: Path) -> Optional[dict]:
        path_str = str(path.resolve(strict=False))
        for item in self.recent_books:
            if item.get("path") == path_str:
                return item
        return None

    def remember_current_book(self) -> None:
        if not self.current_file:
            return
        path_str = str(self.current_file.resolve(strict=False))
        existing = self.get_book_state(self.current_file)
        if existing:
            existing["name"] = self.current_file.name
        else:
            self.recent_books.insert(
                0,
                {
                    "path": path_str,
                    "name": self.current_file.name,
                    "chapter_index": self.settings.get("last_chapter_index", 0),
                    "scroll_fraction": self.settings.get("last_scroll_fraction", 0.0),
                },
            )
        self.recent_books = [item for item in self.recent_books if Path(item.get("path", "")).exists()]
        seen = set()
        unique_books = []
        for item in self.recent_books:
            path_value = item.get("path")
            if path_value and path_value not in seen:
                seen.add(path_value)
                unique_books.append(item)
        self.recent_books = unique_books[:8]
        if self.recent_books:
            current = self.get_book_state(self.current_file)
            if current:
                self.recent_books.remove(current)
                self.recent_books.insert(0, current)
        self.refresh_recent_books()

    def update_current_book_state(self) -> None:
        if not self.current_file:
            return
        item = self.get_book_state(self.current_file)
        if not item:
            self.remember_current_book()
            item = self.get_book_state(self.current_file)
        if not item:
            return
        item["name"] = self.current_file.name
        item["chapter_index"] = self.settings.get("last_chapter_index", 0)
        item["scroll_fraction"] = self.settings.get("last_scroll_fraction", 0.0)
        self.refresh_recent_books()

    def refresh_recent_books(self) -> None:
        self.recent_listbox.delete(0, tk.END)
        valid_books = []
        for item in self.recent_books:
            if Path(item.get("path", "")).exists():
                valid_books.append(item)
                self.recent_listbox.insert(tk.END, item.get("name", "未命名"))
        self.recent_books = valid_books[:8]
        if not self.recent_books:
            self.recent_listbox.insert(tk.END, "暂无最近书籍")
            self.recent_listbox.itemconfigure(0, foreground="#888888")

    def toggle_recent_panel(self) -> None:
        self.recent_panel_visible = not self.recent_panel_visible
        if self.recent_panel_visible:
            self.recent_frame.grid()
        else:
            self.recent_frame.grid_remove()

    def on_recent_book_open(self, _event=None) -> None:
        selection = self.recent_listbox.curselection()
        if not selection or not self.recent_books:
            return
        index = selection[0]
        if index >= len(self.recent_books):
            return
        item = self.recent_books[index]
        path = Path(item["path"])
        if not path.exists():
            messagebox.showwarning("文件不存在", f"找不到文件：\n{path}")
            self.refresh_recent_books()
            return
        self.load_book(
            path,
            restore_index=item.get("chapter_index", 0),
            scroll_fraction=item.get("scroll_fraction", 0.0),
        )

    def on_close(self) -> None:
        self.settings["last_scroll_fraction"] = self.text_widget.yview()[0] if self.chapter_positions else 0.0
        self.update_current_book_state()
        self.save_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = NovelReaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
