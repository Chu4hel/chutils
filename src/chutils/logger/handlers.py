"""
Кастомные обработчики логов.
"""

import logging.handlers
import os


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Надежный обработчик ротации логов, адаптированный для Windows.

    Этот класс решает проблему `PermissionError` при ротации логов в Windows,
    гарантируя, что файл будет закрыт перед переименованием.
    Он явно закрывает файловый поток перед вызовом стандартной логики ротации.
    """

    def doRollover(self):
        """
        Выполняет ротацию, закрывая текущий поток перед операцией.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()


class CompressingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Обработчик ротации по размеру с поддержкой сжатия (gzip).

    Обеспечивает корректную работу с цепочкой сжатых бэкапов.
    """

    def doRollover(self):
        """
        Выполняет ротацию логов с последующим сжатием старого файла.

        Процесс:
        1. Закрытие текущего потока.
        2. Сдвиг существующих архивов (`log.1.gz` -> `log.2.gz`).
        3. Переименование текущего лога в `log.1`.
        4. Открытие нового файла для дальнейшей записи.
        5. Сжатие переименованного файла в фоне.
        """
        # Закрываем текущий поток
        if self.stream:
            self.stream.close()
            self.stream = None

        # 1. Сдвигаем существующие сжатые бэкапы
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn_gz = f"{self.baseFilename}.{i}.gz"
                dfn_gz = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(sfn_gz):
                    if os.path.exists(dfn_gz):
                        os.remove(dfn_gz)
                    os.rename(sfn_gz, dfn_gz)

        # 2. Ротируем текущий лог-файл в `basename.1`
        dfn_uncompressed = f"{self.baseFilename}.1"
        if os.path.exists(dfn_uncompressed):
            os.remove(dfn_uncompressed)

        dfn_compressed = f"{dfn_uncompressed}.gz"
        if os.path.exists(dfn_compressed):
            os.remove(dfn_compressed)

        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn_uncompressed)

        # 3. Открываем новый поток (создает новый пустой лог-файл)
        self.stream = self._open()

        # 4. Сжимаем новый бэкап `basename.1`
        if os.path.exists(dfn_uncompressed):
            try:
                import gzip
                with open(dfn_uncompressed, 'rb') as f_in:
                    with gzip.open(dfn_compressed, 'wb') as f_out:
                        f_out.writelines(f_in)

                import sys
                if sys.platform == "win32":
                    try:
                        import ctypes
                        ctypes.windll.kernel32.DeleteFileW(dfn_uncompressed)
                    except (ImportError, AttributeError):
                        os.remove(dfn_uncompressed)
                else:
                    os.remove(dfn_uncompressed)
            except Exception as e:
                self.handleError(f"Ошибка при сжатии или удалении {dfn_uncompressed}: {e}")


class CompressingTimedRotatingFileHandler(SafeTimedRotatingFileHandler):
    """
    Обработчик ротации по времени с поддержкой сжатия (gzip).
    """

    def doRollover(self):
        """
        Выполняет временную ротацию и сжимает полученные бэкапы.
        """
        # Вызываем стандартный doRollover, который переименует файлы
        super().doRollover()

        # Получаем список всех ротированных файлов, которые знает обработчик
        files_to_compress = self.getFilesToDelete()

        for source_file in files_to_compress:
            dest_file = f"{source_file}.gz"

            # Если исходный файл существует и сжатого еще нет
            if os.path.exists(source_file) and not os.path.exists(dest_file):
                try:
                    import gzip
                    with open(source_file, 'rb') as f_in:
                        with gzip.open(dest_file, 'wb') as f_out:
                            f_out.writelines(f_in)
                    os.remove(source_file)  # Удаляем исходный несжатый файл
                except Exception as e:
                    self.handleError(f"Ошибка при сжатии файла {source_file}: {e}")
