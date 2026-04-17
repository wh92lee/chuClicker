VERSION = "1.0.0"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys

try:
    import pyautogui
    import keyboard
    pyautogui.PAUSE = 0        # 클릭 후 자동 딜레이 제거
    pyautogui.FAILSAFE = False # 화면 모서리 이동 시 예외 방지
except ImportError:
    pass

# ────────── 설정 ──────────
DEFAULT_START_KEY = "f6"
DEFAULT_RECORD_KEY = "f7"
DEFAULT_INTERVAL_MS = 15

# ────────── 메인 앱 ──────────
class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title(f"chuClicker v{VERSION}")
        self.root.resizable(False, False)

        self.rows = []          # {"x": int, "y": int, "ms": int}
        self.running = False
        self.macro_thread = None
        self.start_key = DEFAULT_START_KEY
        self.record_key = DEFAULT_RECORD_KEY

        self._build_ui()
        self._register_hotkeys()

    def _build_ui(self):
        # ── 테이블 ──
        frame_table = tk.Frame(self.root)
        frame_table.pack(padx=10, pady=(10, 0), fill="both")

        columns = ("#", "X", "Y", "ms")
        self.tree = ttk.Treeview(frame_table, columns=columns, show="headings", height=10, selectmode="browse")
        for col, width in zip(columns, [40, 80, 80, 80]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")

        scrollbar = ttk.Scrollbar(frame_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both")
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)

        # ── 행 조작 버튼 ──
        frame_row = tk.Frame(self.root)
        frame_row.pack(padx=10, pady=5)

        tk.Button(frame_row, text="▲ 위로", width=8, command=self._move_up).pack(side="left", padx=2)
        tk.Button(frame_row, text="▼ 아래로", width=8, command=self._move_down).pack(side="left", padx=2)
        tk.Button(frame_row, text="삭제", width=8, command=self._delete_row).pack(side="left", padx=2)
        tk.Button(frame_row, text="전체삭제", width=8, command=self._clear_all).pack(side="left", padx=2)

        # ── 단축키 설정 ──
        frame_keys = tk.LabelFrame(self.root, text="단축키 설정")
        frame_keys.pack(padx=10, pady=5, fill="x")

        tk.Label(frame_keys, text="시작/종료:").grid(row=0, column=0, padx=5, pady=3)
        self.start_key_var = tk.StringVar(value=self.start_key.upper())
        self.start_key_entry = tk.Entry(frame_keys, textvariable=self.start_key_var, width=8)
        self.start_key_entry.grid(row=0, column=1, padx=5)

        tk.Label(frame_keys, text="위치 기록:").grid(row=0, column=2, padx=5)
        self.record_key_var = tk.StringVar(value=self.record_key.upper())
        self.record_key_entry = tk.Entry(frame_keys, textvariable=self.record_key_var, width=8)
        self.record_key_entry.grid(row=0, column=3, padx=5)

        tk.Button(frame_keys, text="적용", command=self._apply_keys).grid(row=0, column=4, padx=5)

        # ── 상태 표시 ──
        self.status_var = tk.StringVar(value="⏹ 대기 중")
        tk.Label(self.root, textvariable=self.status_var, font=("Arial", 11, "bold")).pack(pady=3)

        # ── 저장/불러오기/시작 버튼 ──
        frame_btns = tk.Frame(self.root)
        frame_btns.pack(padx=10, pady=(0, 10))

        tk.Button(frame_btns, text="💾 저장", width=10, command=self._save).pack(side="left", padx=3)
        tk.Button(frame_btns, text="📂 불러오기", width=10, command=self._load).pack(side="left", padx=3)
        self.toggle_btn = tk.Button(frame_btns, text="▶ 시작", width=10,
                                     bg="#4CAF50", fg="white", command=self._toggle)
        self.toggle_btn.pack(side="left", padx=3)

    def _register_hotkeys(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.start_key, self._toggle)
            keyboard.add_hotkey(self.record_key, self._record_position)
        except Exception as e:
            print(f"단축키 등록 실패: {e}")

    def _apply_keys(self):
        self.start_key = self.start_key_var.get().lower()
        self.record_key = self.record_key_var.get().lower()
        self._register_hotkeys()
        messagebox.showinfo("단축키", f"단축키가 적용되었습니다.\n시작/종료: {self.start_key.upper()}\n기록: {self.record_key.upper()}")

    def _record_position(self):
        pos = pyautogui.position()
        self.rows.append({"x": pos.x, "y": pos.y, "ms": DEFAULT_INTERVAL_MS})
        self._refresh_table()

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self.rows):
            self.tree.insert("", "end", values=(i + 1, row["x"], row["y"], row["ms"]))

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or col not in ("#3", "#4"):  # X, Y, ms 수정 가능
            return

        col_idx = int(col[1:]) - 1
        col_name = ["#", "X", "Y", "ms"][col_idx]
        idx = self.tree.index(item)

        win = tk.Toplevel(self.root)
        win.title(f"{col_name} 수정")
        win.grab_set()
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 50
        win.geometry(f"300x100+{x}+{y}")

        current = self.rows[idx][col_name.lower()]
        var = tk.StringVar(value=str(current))
        tk.Label(win, text=f"{col_name} 값 입력:").pack(padx=10, pady=5)
        entry = tk.Entry(win, textvariable=var)
        entry.pack(padx=10, pady=5)
        entry.focus()

        def apply():
            try:
                val = float(var.get()) if col_name == "ms" else int(var.get())
                self.rows[idx][col_name.lower()] = val
                self._refresh_table()
                win.destroy()
            except ValueError:
                messagebox.showerror("오류", "숫자를 입력해주세요.", parent=win)

        tk.Button(win, text="확인", command=apply).pack(pady=5)
        entry.bind("<Return>", lambda e: apply())

    def _move_up(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        if idx > 0:
            self.rows[idx], self.rows[idx - 1] = self.rows[idx - 1], self.rows[idx]
            self._refresh_table()
            self.tree.selection_set(self.tree.get_children()[idx - 1])

    def _move_down(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        if idx < len(self.rows) - 1:
            self.rows[idx], self.rows[idx + 1] = self.rows[idx + 1], self.rows[idx]
            self._refresh_table()
            self.tree.selection_set(self.tree.get_children()[idx + 1])

    def _delete_row(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        self.rows.pop(idx)
        self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("전체삭제", "모든 행을 삭제할까요?"):
            self.rows.clear()
            self._refresh_table()

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 파일", "*.json")],
            title="저장"
        )
        if path:
            data = {
                "start_key": self.start_key,
                "record_key": self.record_key,
                "rows": self.rows
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("저장", "저장되었습니다.")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON 파일", "*.json")],
            title="불러오기"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rows = data.get("rows", [])
            self.start_key = data.get("start_key", DEFAULT_START_KEY)
            self.record_key = data.get("record_key", DEFAULT_RECORD_KEY)
            self.start_key_var.set(self.start_key.upper())
            self.record_key_var.set(self.record_key.upper())
            self._register_hotkeys()
            self._refresh_table()
            messagebox.showinfo("불러오기", "불러왔습니다.")

    def _toggle(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self.rows:
            messagebox.showwarning("경고", "클릭할 위치가 없습니다.")
            return
        self.running = True
        self.status_var.set("▶ 실행 중...")
        self.toggle_btn.config(text="⏹ 종료", bg="#f44336")
        self.macro_thread = threading.Thread(target=self._run_macro, daemon=True)
        self.macro_thread.start()

    def _stop(self):
        self.running = False
        self.status_var.set("⏹ 대기 중")
        self.toggle_btn.config(text="▶ 시작", bg="#4CAF50")

    def _run_macro(self):
        try:
            while self.running:
                for row in self.rows:
                    if not self.running:
                        break
                    pyautogui.click(row["x"], row["y"])
                    time.sleep(row["ms"] / 1000)
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"오류: {e}"))
            self.root.after(0, self._stop)

    def on_close(self):
        self.running = False
        try:
            keyboard.unhook_all()
        except:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClicker(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
