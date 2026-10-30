# Диктофон (Voice Recorder)

Простой диктофон для Windows на Python: запись с микрофона в WAV,
индикатор уровня звука, список записей с воспроизведением и выбор микрофона.

## Возможности

- ⏺ Запись звука с выбранного микрофона в формате WAV (44.1 кГц, 16 бит)
- 📊 Индикатор уровня звука в реальном времени
- ▶ Прослушивание записей прямо в приложении
- 🎙 Выбор микрофона из списка доступных устройств
- 🗑 Удаление записей и открытие папки с файлами

## Установка и запуск

Требуется Python 3.9+.

```bash
pip install -r requirements.txt
python main.py
```

Записи сохраняются в папку `recordings` рядом с программой.

## Сборка в .exe

Чтобы получить один исполняемый файл без необходимости ставить Python:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name VoiceRecorder main.py
```

Готовый файл появится в папке `dist\VoiceRecorder.exe`.

## Зависимости

- [sounddevice](https://python-sounddevice.readthedocs.io/) — захват и воспроизведение звука
- [soundfile](https://python-soundfile.readthedocs.io/) — чтение/запись WAV-файлов
- [numpy](https://numpy.org/) — обработка аудиоданных
