"""下载进度条 UI 组件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.Frame):
    """带状态文字与百分比的进度条面板。"""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame", padding=(14, 12))
        self.percent_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="待命")
        self.detail_var = tk.StringVar(value="粘贴 cURL 后点击解析并下载")
        self.percent_text_var = tk.StringVar(value="—")

        self.columnconfigure(0, weight=1)

        header = ttk.Frame(self, style="Card.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="下载进度", style="CardTitle.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(header, textvariable=self.percent_text_var, style="Percent.TLabel").grid(
            row=0, column=1, sticky=tk.E
        )

        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 4)
        )

        self.bar = ttk.Progressbar(
            self,
            style="Accent.Horizontal.TProgressbar",
            variable=self.percent_var,
            maximum=100,
            mode="determinate",
        )
        self.bar.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))

        ttk.Label(self, textvariable=self.detail_var, style="Muted.TLabel").grid(
            row=3, column=0, columnspan=2, sticky=tk.W
        )

        self._pulse_job: str | None = None
        self._pulse_value = 0.0

    def reset(self, status: str = "准备中", detail: str = "正在启动 yt-dlp…") -> None:
        """重置为初始状态并显示不确定动画。"""
        self._stop_pulse()
        self.percent_var.set(0)
        self.percent_text_var.set("…")
        self.status_var.set(status)
        self.detail_var.set(detail)
        self.bar.configure(mode="indeterminate")
        self.bar.start(12)

    def _stop_pulse(self) -> None:
        """停止等待动画。"""
        try:
            self.bar.stop()
        except tk.TclError:
            pass
        self.bar.configure(mode="determinate")
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None

    def update_progress(
        self,
        percent: float | None,
        status: str,
        detail: str,
    ) -> None:
        """更新进度条与文案。"""
        self._stop_pulse()
        self.status_var.set(status)
        self.detail_var.set(detail)

        if percent is None:
            self.percent_text_var.set("…")
            self.bar.configure(mode="indeterminate")
            self.bar.start(10)
            return

        clamped = max(0.0, min(100.0, percent))
        self.percent_var.set(clamped)
        self.percent_text_var.set(f"{clamped:.1f}%")

    def set_complete(self, detail: str = "文件已保存到目标目录") -> None:
        """标记下载完成。"""
        self._stop_pulse()
        self.percent_var.set(100)
        self.percent_text_var.set("100%")
        self.status_var.set("完成")
        self.detail_var.set(detail)

    def set_error(self, message: str) -> None:
        """标记下载失败。"""
        self._stop_pulse()
        self.status_var.set("失败")
        self.detail_var.set(message)
        self.percent_text_var.set("!")


def setup_app_theme(root: tk.Tk) -> ttk.Style:
    """配置应用主题与控件样式。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg="#eef1f6")

    style.configure(".", background="#eef1f6", foreground="#1f2937", font=("Segoe UI", 10))
    style.configure("TFrame", background="#eef1f6")
    style.configure("TLabel", background="#eef1f6", foreground="#1f2937")
    style.configure("TLabelframe", background="#eef1f6", foreground="#334155")
    style.configure("TLabelframe.Label", background="#eef1f6", foreground="#334155", font=("Segoe UI", 10, "bold"))
    style.configure("TCheckbutton", background="#eef1f6", foreground="#1f2937")
    style.configure("TEntry", fieldbackground="#ffffff", foreground="#111827")

    style.configure("Card.TFrame", background="#ffffff", relief="flat")
    style.configure("CardTitle.TLabel", background="#ffffff", foreground="#64748b", font=("Segoe UI", 9))
    style.configure("Status.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 11, "bold"))
    style.configure("Muted.TLabel", background="#ffffff", foreground="#64748b", font=("Segoe UI", 9))
    style.configure("Percent.TLabel", background="#ffffff", foreground="#2563eb", font=("Segoe UI", 16, "bold"))
    style.configure("Subtitle.TLabel", background="#eef1f6", foreground="#64748b", font=("Segoe UI", 10))

    style.configure(
        "Accent.TButton",
        background="#2563eb",
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        padding=(14, 8),
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", "#1d4ed8"), ("pressed", "#1e40af"), ("disabled", "#93c5fd")],
        foreground=[("disabled", "#eff6ff")],
    )

    style.configure(
        "Ghost.TButton",
        background="#ffffff",
        foreground="#334155",
        borderwidth=1,
        relief="solid",
        padding=(12, 8),
        font=("Segoe UI", 10),
    )
    style.map("Ghost.TButton", background=[("active", "#f8fafc")])

    style.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor="#e2e8f0",
        background="#2563eb",
        bordercolor="#e2e8f0",
        lightcolor="#3b82f6",
        darkcolor="#1d4ed8",
        thickness=14,
    )

    return style
