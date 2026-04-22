import contextlib
import io
import os
import queue
import time
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from .config import STATIONS


BG = "#f3f4f6"
CARD_BG = "#ffffff"
BORDER = "#d7dbe2"
TEXT = "#1f2937"
MUTED = "#6b7280"
RED = "#b91c1c"
RED_DARK = "#8f1717"
RED_LIGHT = "#fef2f2"
GRAY_BUTTON = "#e5e7eb"
GRAY_BUTTON_ACTIVE = "#d1d5db"


class QueueWriter(io.TextIOBase):
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def write(self, text):
        if text:
            self.output_queue.put(text)
        return len(text)

    def flush(self):
        return None


class RadioMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Radio Ad Detector")
        self.root.geometry("900x620")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.worker_finished = threading.Event()
        self.detector = None
        self.stop_requested = False
        self.session_started_at = None
        self.session_timer_after_id = None
        self.session_timer_running = False
        self.station_pause_events = {name: threading.Event() for name in STATIONS}
        self.station_enabled_vars = {name: tk.BooleanVar(value=True) for name in STATIONS}
        self.station_status_vars = {name: tk.StringVar(value="Ativa") for name in STATIONS}
        self.station_pause_buttons = {}
        self.station_checkbuttons = {}

        self.status_var = tk.StringVar(value="Pronto")
        self.detail_var = tk.StringVar(value="A interface está pronta para iniciar a captura.")
        self.station_count_var = tk.StringVar(value=str(len(STATIONS)))
        self.output_folder_path = os.path.abspath("radio_capture")
        self.report_path = os.path.abspath(os.path.join("radio_capture", "relatorio_anuncios.xlsx"))
        self.output_folder_var = tk.StringVar(value=self._shorten_path(self.output_folder_path, 34))
        self.report_var = tk.StringVar(value=self._shorten_path(self.report_path, 34))
        self.session_timer_var = tk.StringVar(value="00:00:00")

        self._configure_style()
        self._build_ui()
        self._append_log("[INFO] Interface pronta. Aguardando início da captura.\n")
        self.root.after(120, self._poll_logs)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Primary.TButton", padding=10, relief="flat", borderwidth=0)
        style.configure(
            "Primary.TButton",
            background=RED,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", RED_DARK), ("disabled", "#e5e7eb")],
            foreground=[("disabled", "#9ca3af")],
        )

        style.configure(
            "Neutral.TButton",
            padding=10,
            relief="flat",
            borderwidth=0,
            background=GRAY_BUTTON,
            foreground=TEXT,
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Neutral.TButton",
            background=[("active", GRAY_BUTTON_ACTIVE), ("disabled", "#e5e7eb")],
            foreground=[("disabled", "#9ca3af")],
        )

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = tk.Frame(self.root, bg=BG)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        hero = tk.Frame(outer, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        hero.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=0)

        top_strip = tk.Frame(hero, bg=RED, height=6)
        top_strip.grid(row=0, column=0, columnspan=2, sticky="ew")

        left = tk.Frame(hero, bg=CARD_BG, padx=14, pady=12)
        left.grid(row=1, column=0, sticky="ew")
        left.columnconfigure(0, weight=1)

        tk.Label(left, text="Radio Ad Detector", bg=CARD_BG, fg=TEXT, font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            left,
            text="Monitoramento de anúncios em rádio com capturas, logs e relatório em uma interface mais limpa.",
            bg=CARD_BG,
            fg=MUTED,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        status_card = tk.Frame(hero, bg=RED_LIGHT, padx=12, pady=10)
        status_card.grid(row=1, column=1, sticky="e", padx=12, pady=10)
        tk.Label(status_card, text="STATUS", bg=RED_LIGHT, fg=RED, font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="e"
        )
        tk.Label(status_card, textvariable=self.status_var, bg=RED_LIGHT, fg=TEXT, font=("Segoe UI", 13, "bold")).grid(
            row=1, column=0, sticky="e", pady=(2, 0)
        )
        tk.Label(
            status_card,
            textvariable=self.detail_var,
            bg=RED_LIGHT,
            fg=MUTED,
            font=("Segoe UI", 9),
            wraplength=220,
            justify="right",
        ).grid(row=2, column=0, sticky="e", pady=(6, 0))

        timer_row = tk.Frame(status_card, bg=RED_LIGHT)
        timer_row.grid(row=3, column=0, sticky="e", pady=(8, 0))
        tk.Label(timer_row, text="Sessão", bg=RED_LIGHT, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(
            row=0, column=0, sticky="e", padx=(0, 8)
        )
        tk.Label(
            timer_row,
            textvariable=self.session_timer_var,
            bg=RED_LIGHT,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, sticky="e")

        stats = tk.Frame(outer, bg=BG)
        stats.grid(row=1, column=0, sticky="ew", padx=12)
        stats.columnconfigure((0, 1, 2), weight=1)

        self._build_stat_card(stats, 0, "Rádios monitoradas", self.station_count_var)
        self._build_stat_card(stats, 1, "Pasta de saída", self.output_folder_var)
        self._build_stat_card(stats, 2, "Relatório Excel", self.report_var)

        controls = tk.Frame(outer, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        controls.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 6))
        controls.columnconfigure(0, weight=1)

        button_row = tk.Frame(controls, bg=CARD_BG, padx=10, pady=8)
        button_row.grid(row=0, column=0, sticky="w")

        self.start_button = ttk.Button(
            button_row,
            text="Iniciar captura",
            command=self.start_monitoring,
            style="Primary.TButton",
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10))

        self.stop_button = ttk.Button(
            button_row,
            text="Encerrar",
            command=self.stop_monitoring,
            style="Neutral.TButton",
            state="disabled",
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 10))

        ttk.Button(button_row, text="Abrir pasta", command=self.open_output_folder, style="Neutral.TButton").grid(
            row=0, column=2
        )

        tk.Label(
            controls,
            text="Selecione as rádios antes de iniciar ou pause/retome durante a execução.",
            bg=CARD_BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

        self._build_station_manager(controls)

        body = tk.Frame(outer, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        body.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)

        header = tk.Frame(body, bg=CARD_BG, padx=12, pady=10)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="Log de execução", bg=CARD_BG, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        log_frame = tk.Frame(body, bg=CARD_BG, padx=10, pady=8)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=8,
            borderwidth=0,
            padx=12,
            pady=10,
            bg="#fafafa",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            font=("Consolas", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _build_station_manager(self, parent):
        station_box = tk.Frame(parent, bg="#fafafa", highlightthickness=1, highlightbackground=BORDER)
        station_box.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        station_box.columnconfigure(0, weight=1)

        tk.Label(station_box, text="Rádios monitoradas", bg="#fafafa", fg=TEXT, font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(6, 2)
        )
        tk.Label(
            station_box,
            text="Desmarque antes de iniciar.",
            bg="#fafafa",
            fg=MUTED,
            font=("Segoe UI", 8),
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 4))

        list_holder = tk.Frame(station_box, bg="#fafafa")
        list_holder.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        list_holder.columnconfigure(0, weight=1)
        list_holder.columnconfigure(1, weight=0)
        list_holder.columnconfigure(2, weight=0)

        for idx, station in enumerate(STATIONS):
            chk = tk.Checkbutton(
                list_holder,
                text=station,
                variable=self.station_enabled_vars[station],
                bg="#fafafa",
                fg=TEXT,
                activebackground="#fafafa",
                selectcolor="#fafafa",
                font=("Segoe UI", 8),
                anchor="w",
            )
            chk.grid(row=idx, column=0, sticky="w", pady=1)
            self.station_checkbuttons[station] = chk

            status_label = tk.Label(
                list_holder,
                textvariable=self.station_status_vars[station],
                bg="#fafafa",
                fg=MUTED,
                font=("Segoe UI", 8, "bold"),
                width=9,
            )
            status_label.grid(row=idx, column=1, sticky="e", padx=(6, 6), pady=1)

            btn = ttk.Button(
                list_holder,
                text="Pausar",
                command=lambda s=station: self.toggle_station_pause(s),
                style="Neutral.TButton",
                state="disabled",
            )
            btn.grid(row=idx, column=2, sticky="e", pady=1)
            self.station_pause_buttons[station] = btn

    def _build_stat_card(self, parent, column, title, value_var):
        padx = (0, 10) if column < 2 else (0, 0)
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER, padx=16, pady=14)
        card.grid(row=0, column=column, sticky="ew", padx=padx)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text=title, bg=CARD_BG, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            card,
            textvariable=value_var,
            bg=CARD_BG,
            fg=TEXT,
            font=("Segoe UI", 11, "bold"),
            wraplength=220,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    def start_monitoring(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        active_names = [name for name, var in self.station_enabled_vars.items() if var.get()]
        if not active_names:
            messagebox.showwarning("Radio Ad Detector", "Selecione ao menos uma rádio para iniciar.")
            return

        self.stop_event = threading.Event()
        self.worker_finished.clear()
        self.stop_requested = False
        self.status_var.set("Iniciando")
        self.detail_var.set("Preparando o detector e os gravadores.")
        self._start_session_timer()
        for name, event in self.station_pause_events.items():
            event.clear()
            self.station_status_vars[name].set("Ativa" if name in active_names else "Inativa")
        self._set_buttons(running=True)

        self.active_stations = {name: STATIONS[name] for name in active_names}

        self.worker_thread = threading.Thread(target=self._run_detector, daemon=True)
        self.worker_thread.start()

    def stop_monitoring(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_requested = True
            self.status_var.set("Encerrando")
            self.detail_var.set("Aguardando o ciclo atual terminar.")
            self.stop_event.set()

    def open_output_folder(self):
        folder = os.path.abspath("radio_capture")
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception as exc:
            messagebox.showerror("Radio Ad Detector", f"Não foi possível abrir a pasta:\n{exc}")

    def _run_detector(self):
        try:
            from app import AdDetector

            writer = QueueWriter(self.log_queue)
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                self.detector = AdDetector()
                self.detector.run(
                    stop_event=self.stop_event,
                    active_stations=self.active_stations,
                    station_pause_events=self.station_pause_events,
                )
            self.log_queue.put("\n[INFO] Execução finalizada.\n")
        except Exception:
            self.log_queue.put(traceback.format_exc())
            self.log_queue.put("\n[ERRO] Falha ao iniciar ou executar o detector.\n")
        finally:
            self.worker_finished.set()

    def _mark_stopped(self):
        self.stop_requested = False
        self._stop_session_timer()
        self.status_var.set("Encerrado")
        self.detail_var.set("A execução terminou de fato.")
        for name in STATIONS:
            self.station_status_vars[name].set("Ativa" if self.station_enabled_vars[name].get() else "Inativa")
        self._set_buttons(running=False)

    def _set_buttons(self, running: bool):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        for name, chk in self.station_checkbuttons.items():
            chk.configure(state="disabled" if running else "normal")
        for name, btn in self.station_pause_buttons.items():
            enabled = running and name in getattr(self, "active_stations", {})
            btn.configure(state="normal" if enabled else "disabled")
            if not enabled:
                btn.configure(text="Pausar")

    def toggle_station_pause(self, station_name):
        if station_name not in self.station_pause_events:
            return

        pause_event = self.station_pause_events[station_name]
        if pause_event.is_set():
            pause_event.clear()
            self.station_status_vars[station_name].set("Ativa")
            self.station_pause_buttons[station_name].configure(text="Pausar")
            self.log_queue.put(f"\n[UI] Rádio '{station_name}' retomada.\n")
        else:
            pause_event.set()
            self.station_status_vars[station_name].set("Pausada")
            self.station_pause_buttons[station_name].configure(text="Retomar")
            self.log_queue.put(f"\n[UI] Rádio '{station_name}' pausada.\n")

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _shorten_path(self, path, max_chars=34):
        normalized = os.path.normpath(path)
        if len(normalized) <= max_chars:
            return normalized

        drive, tail = os.path.splitdrive(normalized)
        tail_parts = tail.strip(os.sep).split(os.sep)
        if len(tail_parts) >= 2:
            shortened_tail = os.sep.join(tail_parts[-2:])
        else:
            shortened_tail = tail_parts[-1] if tail_parts else os.path.basename(normalized)

        candidate = f"{drive}{os.sep}...{os.sep}{shortened_tail}" if drive else f"...{os.sep}{shortened_tail}"
        if len(candidate) > max_chars:
            candidate = f"...{os.sep}{os.path.basename(normalized)}"
        return candidate

    def _format_elapsed(self, seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _cancel_session_timer(self):
        if self.session_timer_after_id is not None:
            try:
                self.root.after_cancel(self.session_timer_after_id)
            except Exception:
                pass
            self.session_timer_after_id = None

    def _start_session_timer(self):
        self._cancel_session_timer()
        self.session_started_at = time.monotonic()
        self.session_timer_running = True
        self.session_timer_var.set("00:00:00")
        self._update_session_timer()

    def _stop_session_timer(self):
        self.session_timer_running = False
        self._cancel_session_timer()

    def _update_session_timer(self):
        if not self.session_timer_running or self.session_started_at is None:
            return

        elapsed = time.monotonic() - self.session_started_at
        self.session_timer_var.set(self._format_elapsed(elapsed))
        self.session_timer_after_id = self.root.after(1000, self._update_session_timer)

    def _poll_logs(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self._append_log(text)
        except queue.Empty:
            pass

        if self.worker_finished.is_set() and self.status_var.get() != "Encerrado":
            self.root.after(0, self._mark_stopped)
        elif self.stop_requested and self.worker_thread and self.worker_thread.is_alive():
            self.status_var.set("Encerrando")
            self.detail_var.set("Aguardando finalização dos gravadores e exportações.")

        self.root.after(120, self._poll_logs)

    def _on_close(self):
        self.stop_monitoring()
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(250, self._on_close)
            return
        self._stop_session_timer()
        self.root.destroy()


def launch_app():
    root = tk.Tk()
    RadioMonitorApp(root)
    root.mainloop()