"""Простой диктофон для Windows.

Запись с выбранного микрофона в WAV, индикатор уровня звука,
список записей с воспроизведением.
"""

import datetime
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 44100
CHANNELS = 1
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"


class VoiceRecorderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Диктофон")
        self.geometry("460x420")
        self.resizable(False, False)

        # Состояние записи
        self._stream = None
        self._sound_file = None
        self._audio_queue = queue.Queue()
        self._writer_thread = None
        self._recording = False
        self._record_start = None
        self._level = 0.0

        # Состояние воспроизведения
        self._playing = False

        self._build_ui()
        self._refresh_devices()
        self._refresh_recordings()
        self._poll_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Интерфейс ----------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Микрофон:").pack(side="left")
        self.device_combo = ttk.Combobox(top, state="readonly", width=42)
        self.device_combo.pack(side="left", padx=(5, 0))

        mid = ttk.Frame(self)
        mid.pack(fill="x", **pad)
        self.record_btn = ttk.Button(mid, text="⏺ Запись", command=self._toggle_recording)
        self.record_btn.pack(side="left")
        self.time_label = ttk.Label(mid, text="00:00", font=("Consolas", 14))
        self.time_label.pack(side="left", padx=15)
        ttk.Label(mid, text="Уровень:").pack(side="left")
        self.level_bar = ttk.Progressbar(mid, length=150, maximum=100, mode="determinate")
        self.level_bar.pack(side="left", padx=5)

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, **pad)
        ttk.Label(bottom, text="Записи:").pack(anchor="w")
        list_frame = ttk.Frame(bottom)
        list_frame.pack(fill="both", expand=True, pady=(5, 5))
        self.recordings_list = tk.Listbox(list_frame, activestyle="dotbox")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.recordings_list.yview)
        self.recordings_list.configure(yscrollcommand=scrollbar.set)
        self.recordings_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btns = ttk.Frame(bottom)
        btns.pack(fill="x")
        self.play_btn = ttk.Button(btns, text="▶ Слушать", command=self._toggle_playback)
        self.play_btn.pack(side="left")
        ttk.Button(btns, text="Удалить", command=self._delete_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="Открыть папку", command=self._open_folder).pack(side="left")

        self.status_label = ttk.Label(self, text="Готов к записи", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", side="bottom")

    # ---------- Микрофоны ----------

    def _refresh_devices(self):
        self._devices = []
        names = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0:
                    self._devices.append(i)
                    names.append(dev["name"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ошибка", f"Не удалось получить список микрофонов:\n{exc}")
        self.device_combo["values"] = names
        if names:
            try:
                default_in = sd.default.device[0]
                pos = self._devices.index(default_in) if default_in in self._devices else 0
            except Exception:  # noqa: BLE001
                pos = 0
            self.device_combo.current(pos)

    # ---------- Запись ----------

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not self._devices:
            messagebox.showwarning("Нет микрофона", "Не найдено ни одного входного устройства.")
            return
        self._stop_playback()
        RECORDINGS_DIR.mkdir(exist_ok=True)

        device_index = self._devices[self.device_combo.current()]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = RECORDINGS_DIR / f"rec_{timestamp}.wav"

        try:
            self._sound_file = sf.SoundFile(
                path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS, subtype="PCM_16"
            )
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                device=device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001
            if self._sound_file is not None:
                self._sound_file.close()
                self._sound_file = None
            messagebox.showerror("Ошибка записи", f"Не удалось начать запись:\n{exc}")
            return

        self._recording = True
        self._record_start = datetime.datetime.now()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

        self.record_btn.configure(text="⏹ Стоп")
        self.device_combo.configure(state="disabled")
        self.status_label.configure(text=f"Запись: {path.name}")

    def _audio_callback(self, indata, frames, time_info, status):  # noqa: ARG002
        self._audio_queue.put(indata.copy())
        rms = float(np.sqrt(np.mean(indata ** 2))) if frames else 0.0
        # Примерное преобразование RMS в шкалу 0..1 для индикатора
        self._level = min(1.0, rms * 6)

    def _writer_loop(self):
        while self._recording or not self._audio_queue.empty():
            try:
                block = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._sound_file.write(block)

    def _stop_recording(self):
        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=2)
            self._writer_thread = None
        if self._sound_file is not None:
            self._sound_file.close()
            self._sound_file = None

        self._level = 0.0
        self.record_btn.configure(text="⏺ Запись")
        self.device_combo.configure(state="readonly")
        self.status_label.configure(text="Запись сохранена")
        self.time_label.configure(text="00:00")
        self._refresh_recordings()

    # ---------- Воспроизведение ----------

    def _selected_recording(self):
        selection = self.recordings_list.curselection()
        if not selection:
            return None
        # В списке отображается имя с размером файла — берём только имя
        filename = self.recordings_list.get(selection[0]).split("   (")[0]
        return RECORDINGS_DIR / filename

    def _toggle_playback(self):
        if self._playing:
            self._stop_playback()
            return
        path = self._selected_recording()
        if path is None:
            messagebox.showinfo("Выбор записи", "Сначала выберите запись в списке.")
            return
        try:
            data, samplerate = sf.read(path, dtype="float32")
            sd.play(data, samplerate)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Ошибка", f"Не удалось воспроизвести файл:\n{exc}")
            return
        self._playing = True
        self.play_btn.configure(text="⏹ Стоп")
        self.status_label.configure(text=f"Воспроизведение: {path.name}")

    def _stop_playback(self):
        if self._playing:
            sd.stop()
        self._playing = False
        self.play_btn.configure(text="▶ Слушать")

    # ---------- Список записей ----------

    def _refresh_recordings(self):
        self.recordings_list.delete(0, tk.END)
        if not RECORDINGS_DIR.exists():
            return
        for path in sorted(RECORDINGS_DIR.glob("*.wav"), reverse=True):
            size_kb = path.stat().st_size / 1024
            self.recordings_list.insert(tk.END, f"{path.name}   ({size_kb:.0f} КБ)")

    def _delete_selected(self):
        path = self._selected_recording()
        if path is None:
            messagebox.showinfo("Выбор записи", "Сначала выберите запись в списке.")
            return
        if messagebox.askyesno("Удаление", f"Удалить {path.name}?"):
            try:
                path.unlink()
            except OSError as exc:
                messagebox.showerror("Ошибка", f"Не удалось удалить файл:\n{exc}")
            self._refresh_recordings()

    def _open_folder(self):
        RECORDINGS_DIR.mkdir(exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(RECORDINGS_DIR)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(RECORDINGS_DIR)])

    # ---------- Служебное ----------

    def _poll_ui(self):
        self.level_bar["value"] = self._level * 100
        if self._recording and self._record_start is not None:
            elapsed = datetime.datetime.now() - self._record_start
            minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
            self.time_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        self.after(50, self._poll_ui)

    def _on_close(self):
        if self._recording:
            self._stop_recording()
        self._stop_playback()
        self.destroy()


if __name__ == "__main__":
    app = VoiceRecorderApp()
    app.mainloop()
