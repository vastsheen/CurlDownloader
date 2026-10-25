"""cURL / 磁力链接 / 种子下载 GUI 入口。"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .bt_downloader import download_with_aria2, find_aria2c, is_magnet, is_torrent_file
from .curl_parser import build_jd_link, parse_download_inputs
from .downloader import build_batch_output_names, download_with_ytdlp, find_ffmpeg, find_ytdlp
from .har_parser import extract_m3u8_requests_from_har, extract_media_requests_from_har, to_curl_text
from .progress_parser import DownloadProgress
from .progress_ui import ProgressPanel, setup_app_theme


class CurlDownloaderApp(tk.Tk):
    """主窗口：粘贴 cURL / magnet，或选择种子后下载。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("资源下载器")
        self.geometry("920x760")
        self.minsize(760, 660)

        setup_app_theme(self)

        self.output_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.output_name = tk.StringVar(value="video")
        self.resume_enabled = tk.BooleanVar(value=True)
        self.input_mode = tk.StringVar(value="auto")
        self.parsed = None
        self._worker: threading.Thread | None = None

        self._build_ui()
        self._log_runtime_info()

    def _build_ui(self) -> None:
        """构建界面控件。"""
        page_frame = ttk.Frame(self)
        page_frame.pack(fill=tk.BOTH, expand=True)
        self.page_canvas = tk.Canvas(page_frame, highlightthickness=0, bg="#eef1f6")
        page_scrollbar = ttk.Scrollbar(page_frame, orient=tk.VERTICAL, command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=page_scrollbar.set)
        page_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.page_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        root = ttk.Frame(self.page_canvas, padding=14)
        self._page_window = self.page_canvas.create_window((0, 0), window=root, anchor=tk.NW)
        root.bind("<Configure>", self._update_page_scrollregion)
        self.page_canvas.bind("<Configure>", self._resize_page_content)

        title_row = ttk.Frame(root)
        title_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_row, text="资源下载器", font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(title_row, text="支持多个 cURL / m3u8、磁力链接和种子文件", style="Subtitle.TLabel").pack(
            side=tk.LEFT, padx=(12, 0), pady=(6, 0)
        )

        output_frame = ttk.LabelFrame(root, text="下载设置", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(output_frame, text="保存目录").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(output_frame, textvariable=self.output_dir, width=70).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 8)
        )
        ttk.Button(output_frame, text="浏览", style="Ghost.TButton", command=self.on_browse).grid(row=0, column=2)

        ttk.Label(output_frame, text="文件名").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Entry(output_frame, textvariable=self.output_name, width=30).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 8), pady=(8, 0)
        )
        ttk.Checkbutton(
            output_frame,
            text="断点续传（同目录 + 同文件名，失败后可继续）",
            variable=self.resume_enabled,
        ).grid(row=2, column=1, sticky=tk.W, padx=(8, 8), pady=(8, 0))
        output_frame.columnconfigure(1, weight=1)

        input_frame = ttk.LabelFrame(root, text="下载输入", padding=10)
        input_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        self.curl_input = scrolledtext.ScrolledText(
            input_frame,
            height=8,
            wrap=tk.WORD,
            bg="#ffffff",
            fg="#111827",
            insertbackground="#2563eb",
            relief=tk.FLAT,
            padx=8,
            pady=8,
        )
        self.curl_input.pack(fill=tk.BOTH, expand=True)
        self.curl_input.bind("<<Paste>>", self._on_paste)

        action_row = ttk.Frame(root)
        action_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(action_row, text="自动", variable=self.input_mode, value="auto").pack(side=tk.LEFT)
        ttk.Radiobutton(action_row, text="cURL", variable=self.input_mode, value="curl").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Radiobutton(action_row, text="BT", variable=self.input_mode, value="bt").pack(side=tk.LEFT, padx=(8, 12))
        ttk.Button(action_row, text="解析", style="Ghost.TButton", command=self.on_parse_button).pack(side=tk.LEFT)
        ttk.Button(
            action_row,
            text="解析并下载",
            style="Accent.TButton",
            command=self.on_parse_and_download,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_row, text="选择种子", style="Ghost.TButton", command=self.on_choose_torrent).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_row, text="选择 HAR", style="Ghost.TButton", command=self.on_choose_har).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(action_row, text="清空", style="Ghost.TButton", command=self.on_clear).pack(side=tk.LEFT, padx=(8, 0))

        self.progress_panel = ProgressPanel(root)
        self.progress_panel.pack(fill=tk.X, pady=(0, 10))

        parsed_frame = ttk.LabelFrame(root, text="解析结果", padding=10)
        parsed_frame.pack(fill=tk.X, pady=(0, 10))

        self.field_url = self._add_field(parsed_frame, "URL", 0)
        self.field_referer = self._add_field(parsed_frame, "Referer", 1)
        self.field_origin = self._add_field(parsed_frame, "Origin", 2)
        self.field_cookie = self._add_field(parsed_frame, "Cookie", 3)
        self.field_ua = self._add_field(parsed_frame, "User-Agent", 4)
        self.field_jd = self._add_field(parsed_frame, "JD 链接", 5)

        ttk.Button(root, text="开始下载", style="Accent.TButton", command=self.on_download).pack(
            anchor=tk.W, pady=(0, 8)
        )

        ttk.Label(root, text="日志").pack(anchor=tk.W)
        log_frame = ttk.Frame(root)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log_box = tk.Text(
            log_frame,
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#ffffff",
            fg="#334155",
            relief=tk.FLAT,
            padx=8,
            pady=8,
        )
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _update_page_scrollregion(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """根据页面内容更新窗口级滚动范围。"""
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _resize_page_content(self, event: tk.Event[tk.Misc]) -> None:
        """让可滚动页面始终与窗口可用宽度对齐。"""
        self.page_canvas.itemconfigure(self._page_window, width=event.width)

    def _add_field(self, parent: ttk.LabelFrame, label: str, row: int) -> ttk.Entry:
        """添加只读解析字段。"""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
        entry = ttk.Entry(parent, width=90)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=3)
        parent.columnconfigure(1, weight=1)
        return entry

    def _log_runtime_info(self) -> None:
        """启动时输出依赖信息。"""
        try:
            ytdlp = find_ytdlp()
            self.log(f"yt-dlp: {ytdlp}")
        except FileNotFoundError as exc:
            self.log(f"警告: {exc}")

        ffmpeg = find_ffmpeg()
        if ffmpeg:
            self.log(f"ffmpeg: {ffmpeg}")
        else:
            self.log("警告: 未找到 ffmpeg，部分 m3u8 可能无法合并为 mp4")

        try:
            aria2c = find_aria2c()
            self.log(f"aria2c: {aria2c}")
        except FileNotFoundError as exc:
            self.log(f"警告: {exc}")

    def log(self, message: str) -> None:
        """追加日志（线程安全）。"""
        def append() -> None:
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert(tk.END, message + "\n")
            self.log_box.see(tk.END)
            self.log_box.configure(state=tk.DISABLED)

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.after(0, append)

    def _update_progress(self, progress: DownloadProgress) -> None:
        """线程安全更新进度条。"""
        def apply() -> None:
            self.progress_panel.update_progress(progress.percent, progress.status, progress.detail)

        if threading.current_thread() is threading.main_thread():
            apply()
        else:
            self.after(0, apply)

    def on_browse(self) -> None:
        """选择下载目录。"""
        selected = filedialog.askdirectory(initialdir=self.output_dir.get())
        if selected:
            self.output_dir.set(selected)

    def _on_paste(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        """粘贴后稍等片刻再判断，避免拿到半截内容。"""
        self.after(150, self._auto_download_after_paste)

    def _auto_download_after_paste(self) -> None:
        """粘贴内容看起来可下载时，直接按当前保存目录开始下载。"""
        if self._worker and self._worker.is_alive():
            return
        raw = self.curl_input.get("1.0", tk.END).strip()
        if not raw or not self._looks_downloadable(raw):
            return
        if self.on_parse():
            self.on_download()

    @staticmethod
    def _looks_downloadable(raw: str) -> bool:
        """粗略判断输入是否可下载，避免误触发。"""
        text = raw.strip().lower()
        if text.startswith(("http://", "https://", "magnet:?", "curl ", "curl.exe")):
            return True
        return text.endswith(".torrent") or text.endswith(".har")

    @staticmethod
    def _collect_urls(parsed_items: list) -> list[str]:
        """展开每个任务的 URL 与音视频附加轨，供确认弹框展示。"""
        urls: list[str] = []
        for item in parsed_items:
            urls.append(item.url)
            urls.extend(item.extra_urls)
        return urls

    def _confirm_urls(self, urls: list[str]) -> bool:
        """弹窗列出全部待下载链接，点「确定」返回 True。"""
        dialog = tk.Toplevel(self)
        dialog.title("确认下载链接")
        dialog.transient(self)
        dialog.minsize(520, 300)

        ttk.Label(
            dialog,
            text=f"共解析到 {len(urls)} 条链接，点「确定」开始下载：",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, padx=14, pady=(14, 8))

        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=14)
        text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            height=12,
            relief=tk.FLAT,
            bg="#ffffff",
            fg="#111827",
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for index, url in enumerate(urls, start=1):
            text.insert(tk.END, f"{index}. {url}\n")
        text.configure(state=tk.DISABLED)

        result = {"ok": False}

        def confirm() -> None:
            result["ok"] = True
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.pack(fill=tk.X, padx=14, pady=14)
        ttk.Button(button_row, text="确定", style="Accent.TButton", command=confirm).pack(side=tk.RIGHT)
        ttk.Button(button_row, text="取消", style="Ghost.TButton", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.update_idletasks()
        width, height = 780, 420
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 2
        dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        dialog.grab_set()
        dialog.wait_window()
        return result["ok"]

    def on_choose_torrent(self) -> None:
        """选择种子文件并填入输入框。"""
        selected = filedialog.askopenfilename(
            title="选择种子文件",
            filetypes=[("Torrent", "*.torrent"), ("All files", "*.*")],
        )
        if selected:
            self.curl_input.delete("1.0", tk.END)
            self.curl_input.insert("1.0", selected)
            self.input_mode.set("bt")
            self.on_parse()

    def on_choose_har(self) -> None:
        """选择 HAR 文件并提取 m3u8 请求。"""
        selected = filedialog.askopenfilename(
            title="选择 HAR 文件",
            filetypes=[("HAR", "*.har"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return

        playlist_error: ValueError | None = None
        try:
            try:
                parsed_items = extract_m3u8_requests_from_har(Path(selected))
                self.log("HAR 检测到 m3u8 播放列表")
            except ValueError as exc:
                playlist_error = exc
                parsed_items = extract_media_requests_from_har(Path(selected))
                if parsed_items[0].merge_output_format and not find_ffmpeg():
                    raise ValueError("HAR 检测到分离的视频和音频轨，但未找到 ffmpeg。请安装 ffmpeg 并添加到 PATH 后重试。")
                self.log(f"HAR 检测到 {len(parsed_items[0].extra_urls) + 1} 条 MP4 媒体轨，将下载并合并")
        except ValueError as exc:
            hint = f"\n\n播放列表解析信息：{playlist_error}" if playlist_error else ""
            messagebox.showerror("HAR 解析失败", f"{exc}{hint}")
            return

        urls = self._collect_urls(parsed_items)
        self.log(f"HAR 解析完成，共 {len(urls)} 条链接，等待确认")
        if not self._confirm_urls(urls):
            self.log("已取消 HAR 下载")
            return

        self.input_mode.set("curl")
        self.curl_input.delete("1.0", tk.END)
        self.curl_input.insert("1.0", to_curl_text(parsed_items))
        self._set_parsed_items(parsed_items)
        self.log(f"HAR 解析成功: {selected}")
        self.on_download()

    def on_clear(self) -> None:
        """清空输入与解析结果。"""
        self.curl_input.delete("1.0", tk.END)
        for field in (
            self.field_url,
            self.field_referer,
            self.field_origin,
            self.field_cookie,
            self.field_ua,
            self.field_jd,
        ):
            field.delete(0, tk.END)
        self.parsed = None
        self.progress_panel.update_progress(None, "待命", "粘贴 cURL / 磁力链接，或选择种子文件")
        self.progress_panel.percent_text_var.set("—")

    def on_parse(self) -> bool:
        """解析输入并展示结果。"""
        raw = self.curl_input.get("1.0", tk.END).strip()
        if self._is_bt_input(raw):
            self.parsed = raw
            self.field_url.delete(0, tk.END)
            self.field_url.insert(0, raw)
            for field in (
                self.field_referer,
                self.field_origin,
                self.field_cookie,
                self.field_ua,
                self.field_jd,
            ):
                field.delete(0, tk.END)
            self.log("BT 输入已识别")
            self.progress_panel.update_progress(None, "已识别", "正在准备启动 BT 下载")
            self.progress_panel.percent_text_var.set("—")
            return True

        try:
            parsed_items = parse_download_inputs(raw)
        except ValueError as exc:
            messagebox.showerror("解析失败", str(exc))
            return False

        self._set_parsed_items(parsed_items)
        return True

    def _set_parsed_items(self, parsed_items: list) -> None:
        """展示一个或多个 HTTP 下载任务。"""
        self.parsed = parsed_items
        first = parsed_items[0]
        summary = first.url if len(parsed_items) == 1 else f"{len(parsed_items)} 个下载任务；首个: {first.url}"
        self.field_url.delete(0, tk.END)
        self.field_url.insert(0, summary)
        self.field_referer.delete(0, tk.END)
        self.field_referer.insert(0, first.referer)
        self.field_origin.delete(0, tk.END)
        self.field_origin.insert(0, first.origin)
        self.field_cookie.delete(0, tk.END)
        self.field_cookie.insert(0, first.cookie)
        self.field_ua.delete(0, tk.END)
        self.field_ua.insert(0, first.user_agent)
        self.field_jd.delete(0, tk.END)
        self.field_jd.insert(0, build_jd_link(first) if len(parsed_items) == 1 else "多任务模式不展示 JD 链接")

        self.log(f"解析成功，共 {len(parsed_items)} 个下载任务")
        self.progress_panel.update_progress(None, "已解析", f"共 {len(parsed_items)} 个任务，可以开始下载")
        self.progress_panel.percent_text_var.set("—")
        if not first.referer:
            self.log("提示: 未检测到 Referer，防盗链站点可能下载失败")

    def _is_bt_input(self, raw: str) -> bool:
        """根据模式和内容判断是否走 BT 后端。"""
        mode = self.input_mode.get()
        if mode == "bt":
            return True
        if mode == "curl":
            return False
        return is_magnet(raw) or is_torrent_file(raw)

    def on_parse_and_download(self) -> None:
        """解析后立即下载。"""
        if self.on_parse():
            self.on_download()

    def on_parse_button(self) -> None:
        """解析按钮：BT 输入识别后直接开始获取资源。"""
        if self.on_parse() and isinstance(self.parsed, str) and self._is_bt_input(self.parsed):
            self.on_download()

    def on_download(self) -> None:
        """后台线程执行下载，避免阻塞界面。"""
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("请稍候", "正在下载中，请等待当前任务完成")
            return

        if not self.parsed and not self.on_parse():
            return

        output_dir = Path(self.output_dir.get().strip())
        resume = self.resume_enabled.get()
        parsed = self.parsed
        assert parsed is not None
        is_bt = isinstance(parsed, str) and self._is_bt_input(parsed)
        parsed_items = [] if is_bt else list(parsed)
        if is_bt:
            try:
                find_aria2c()
            except FileNotFoundError as exc:
                self.progress_panel.set_error(str(exc))
                self.log(f"错误: {exc}")
                messagebox.showerror("缺少 aria2c", str(exc))
                return

        self.progress_panel.reset("获取资源中" if is_bt else "连接中", f"保存到 {output_dir}")
        self.log(f"开始下载到: {output_dir}")
        if is_bt:
            self.log("模式: BT / 磁力，已启用 DHT、PEX、LPD、内置 tracker 与 metadata 保存")
            self.log("正在启动 aria2c...")
        elif resume:
            self.log("模式: 断点续传已开启")
            self.log(f"任务数: {len(parsed_items)}")

        def task() -> None:
            try:
                if is_bt:
                    download_with_aria2(
                        parsed,
                        output_dir,
                        log=self.log,
                        on_progress=self._update_progress,
                    )
                else:
                    total = len(parsed_items)
                    task_names = build_batch_output_names(output_dir, total)
                    name_range = task_names[0] if total == 1 else f"{task_names[0]} - {task_names[-1]}"
                    self.log(f"本轮文件名: {name_range}")
                    for index, (request, task_name) in enumerate(zip(parsed_items, task_names), start=1):
                        task_label = f"{index}/{total}"
                        self.log(f"开始任务 {task_label}: {request.url}")
                        self.after(
                            0,
                            lambda label=task_label, name=task_name: self.progress_panel.update_progress(
                                None,
                                label,
                                f"正在下载 {name}",
                            ),
                        )

                        def update_task_progress(progress: DownloadProgress, label: str = task_label) -> None:
                            self._update_progress(
                                DownloadProgress(
                                    percent=progress.percent,
                                    status=f"{label} {progress.status}",
                                    detail=progress.detail,
                                )
                            )

                        download_with_ytdlp(
                            request,
                            output_dir,
                            task_name,
                            log=self.log,
                            on_progress=update_task_progress,
                            resume=resume,
                        )
                self.after(
                    0,
                    lambda: self.progress_panel.set_complete(f"已保存到 {output_dir}"),
                )
                self.after(0, lambda: messagebox.showinfo("完成", f"下载完成\n目录: {output_dir}"))
            except Exception as exc:
                self.after(0, lambda: self.progress_panel.set_error(str(exc)))
                self.after(0, lambda: messagebox.showerror("下载失败", str(exc)))
                self.after(0, lambda: self.log(f"错误: {exc}"))

        self._worker = threading.Thread(target=task, daemon=True)
        self._worker.start()


def main() -> None:
    """程序入口。"""
    app = CurlDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
