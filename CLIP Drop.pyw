"""Windows drag-and-drop entry point for CLIP Drop."""
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    from conversion import convert
except ImportError as error:
    messagebox.showerror('CLIP Drop', f'変換に必要な部品を読み込めませんでした。\n{error}')
    raise SystemExit(1)


PAPER = '#F6F3ED'
PANEL = '#EDE9E0'
INK = '#1D302A'
SUBTLE = '#45554F'
ACCENT = '#295B48'
EDGE = '#B2BEB3'


class DropWindow:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title('CLIP Drop · 習作・ベータ版')
        self.root.configure(background=PAPER)
        self.root.geometry('580x390')
        self.root.minsize(340, 350)
        self.pending = Queue()
        self.events = Queue()
        self.active = 0
        self.finished = 0
        self.failed = 0
        self.latest = None
        self.latest_error = None

        body = tk.Frame(self.root, background=PAPER, padx=22, pady=17)
        body.pack(fill='both', expand=True)
        header = tk.Frame(body, background=PAPER)
        header.pack(fill='x')
        name = tk.Frame(header, background=PAPER)
        name.pack(side='left', fill='x', expand=True)
        tk.Label(name, text='CLIP Drop', font=('Segoe UI', 21, 'bold'),
                 background=PAPER, foreground=INK, anchor='w').pack(fill='x')
        tk.Label(name, text='習作・ベータ版', font=('Yu Gothic UI', 10, 'bold'),
                 background=PAPER, foreground=ACCENT, anchor='w').pack(fill='x')
        tk.Button(header, text='マニュアル取得', command=self.open_manual,
                  font=('Yu Gothic UI', 10), foreground=ACCENT, background=PAPER,
                  activebackground=PANEL, relief='groove', padx=7, pady=2).pack(side='right')
        self.drop_area = tk.Frame(body, background=PANEL, highlightbackground=EDGE,
                                  highlightcolor=ACCENT, highlightthickness=1)
        self.drop_area.pack(fill='both', expand=True, pady=(12, 11))
        center = tk.Frame(self.drop_area, background=PANEL)
        center.pack(expand=True)
        title = tk.Label(center, text='.clip をここにドロップ',
                         font=('Yu Gothic UI', 15, 'bold'), background=PANEL, foreground=INK)
        title.pack()
        subtitle = tk.Label(center, text='SVG・PSD・PNG を自動で書き出し',
                            font=('Yu Gothic UI', 10), background=PANEL, foreground=SUBTLE)
        subtitle.pack(pady=(3, 8))
        select = tk.Button(center, text='ファイルを選ぶ…', command=self.select,
                           font=('Yu Gothic UI', 10), foreground=ACCENT, background=PANEL,
                           activebackground=PAPER, relief='flat', padx=8, pady=2)
        select.pack()
        self.drop_widgets = (body, self.drop_area, center, title, subtitle, select)
        for widget in self.drop_widgets:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<DropEnter>>', self.hover)
            widget.dnd_bind('<<DropLeave>>', self.leave)
            widget.dnd_bind('<<Drop>>', self.drop)

        self.status = tk.Label(body, text='元ファイルと同じ場所に結果フォルダーを作ります。',
                               font=('Yu Gothic UI', 10), foreground=SUBTLE, background=PAPER,
                               anchor='w', justify='left', wraplength=530)
        self.status.pack(fill='x')
        actions = tk.Frame(body, background=PAPER)
        actions.pack(fill='x', pady=(7, 0))
        self.folder = tk.Button(actions, text='結果フォルダーを開く', command=self.open_folder,
                                font=('Yu Gothic UI', 10), background=ACCENT, foreground='white',
                                padx=8, state='disabled', relief='flat')
        self.folder.pack(side='left')
        self.error = tk.Button(actions, text='エラーの詳細', command=self.show_error,
                               font=('Yu Gothic UI', 10), background=PAPER, foreground=INK,
                               state='disabled', relief='flat')
        self.error.pack(side='right')
        body.bind('<Configure>', lambda e: self.status.configure(wraplength=max(240, e.width - 44)))
        Thread(target=self.work, daemon=True).start()
        self.root.after(100, self.poll)

    def hover(self, event):
        self.drop_area.configure(highlightbackground=ACCENT, highlightthickness=2)
        return 'copy'

    def leave(self, event=None):
        self.drop_area.configure(highlightbackground=EDGE, highlightthickness=1)
        return 'copy'

    def drop(self, event):
        self.leave()
        self.enqueue(self.root.tk.splitlist(event.data))
        return 'copy'

    def select(self):
        paths = filedialog.askopenfilenames(
            parent=self.root, title='クリスタのファイルを選ぶ',
            filetypes=[('CLIP STUDIO PAINT', '*.clip'), ('すべてのファイル', '*.*')],
        )
        self.enqueue(paths)

    def enqueue(self, paths):
        if not paths:
            return
        if not self.active:
            self.finished = self.failed = 0
            self.latest_error = None
            self.error.configure(state='disabled')
        for path in paths:
            self.pending.put(Path(path))
            self.active += 1
        self.status.configure(text=f'{self.active} 件の変換を受け付けました。')

    def work(self):
        while True:
            path = self.pending.get()
            self.events.put(('running', path, None))
            try:
                self.events.put(('done', path, convert(path)))
            except Exception as error:
                self.events.put(('failed', path, str(error) or type(error).__name__))

    def poll(self):
        try:
            while True:
                state, path, payload = self.events.get_nowait()
                if state == 'running':
                    self.status.configure(text=f'{path.name}\n変換中…')
                    continue
                self.active -= 1
                if state == 'failed':
                    self.failed += 1
                    self.latest_error = f'{path.name}\n{payload}'
                    self.error.configure(state='normal')
                else:
                    self.finished += 1
                    self.latest = payload
                    self.folder.configure(state='normal')
                if self.active:
                    continue
                summary = f'{self.finished} 件完了' if self.finished else ''
                if self.failed:
                    summary += ('  ／  ' if summary else '') + f'{self.failed} 件失敗'
                detail = 'SVG・PSD・PNG と変換メモを保存しました。' if self.finished else '「エラーの詳細」で理由を確認できます。'
                self.status.configure(text=f'{summary}\n{detail}')
        except Empty:
            pass
        self.root.after(100, self.poll)

    def open_folder(self):
        if self.latest:
            try:
                os.startfile(self.latest.directory)
            except OSError as error:
                messagebox.showerror('CLIP Drop', str(error), parent=self.root)

    def open_manual(self):
        if getattr(sys, 'frozen', False):
            manual = Path(sys.executable).resolve().with_name('CLIP-Drop-manual.pdf')
        else:
            manual = Path(__file__).resolve().parent / 'docs' / 'CLIP-Drop-manual.pdf'
        try:
            os.startfile(manual)
        except FileNotFoundError:
            messagebox.showerror('CLIP Drop', 'マニュアルが見つかりません。配布ZIPをすべて展開してください。', parent=self.root)
        except OSError:
            messagebox.showerror('CLIP Drop', 'PDFを開けませんでした。WindowsでPDFを開くアプリを確認してください。', parent=self.root)

    def show_error(self):
        if self.latest_error:
            messagebox.showerror('CLIP Drop', self.latest_error, parent=self.root)


if __name__ == '__main__':
    app = DropWindow()
    app.enqueue(sys.argv[1:])
    app.root.mainloop()
