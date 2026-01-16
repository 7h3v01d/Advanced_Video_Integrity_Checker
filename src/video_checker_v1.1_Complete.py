import sys
import os
import subprocess
import base64
import csv
import shutil
import json
import shlex
from enum import Enum, auto
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTextEdit, QLabel, QListWidget, QListWidgetItem,
    QStyleFactory, QProgressBar, QSpinBox, QMessageBox, QDialog, QComboBox, QLineEdit,
    QCheckBox
)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt, QByteArray, QBuffer, QIODevice, QRunnable, QThreadPool, QTimer
from PyQt6.QtGui import QMovie, QAction, QIcon, QGuiApplication

# --- Constants & Enums ---
LOADING_GIF_B64 = b'R0lGODlhEAAQAPIAAP///wAAAMLCwkJCQgAAAGJiYoKCgpKSkiH/C05FVFNDQVBFMi4wAwEAAAAh/hpDcmVhdGVkIHdpdGggYWpheGxvYWQuaW5mbwAh+QQJCgAAACwAAAAAEAAQAAADMwi63P4wyklrE2MIOggZnAdOmGYJRbExwroUmcG2LmDEwnHQLVsYOd2mBzkYDAdKa+dIAAAh+QQJCgAAACwAAAAAEAAQAAADNAi63P5OjCEgG4QMu7DmikRxQlFUYDEZIGBMRVsaqHwctXXf7WEYB4Ag1axihOCsitegAAAIfkECQoAAAAsAAAAABAAEAAAAzYIujIjK8pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECQoAAAAsAAAAABAAEAAAAzMIumIlK8oyhpHsnFZvxvoCTORHolIKYsSoLwAI8A9G5sqDsdwaAyTTu7efvHYKxynWyAAAIfkECQoAAAAsAAAAABAAEAAAAzMIuiJijK6pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECQoAAAAsAAAAABAAEAAAAzYIujIjK8pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECQoAAAAsAAAAABAAEAAAAzMIumIlK8oyhpHsnFZvxvoCTORHolIKYsSoLwAI8A9G5sqDsdwaAyTTu7efvHYKxynWyAAAIfkECQoAAAAsAAAAABAAEAAAAzMIuiJijK6pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECAoAAAAsAAAAABAAEAAAAwYIujIjK8pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECAoAAAAsAAAAABAAEAAAAwYIujIjK8pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAIfkECAoAAAAsAAAAABAAEAAAAwYIujIjK8pByJDMlFYvBoVjHA70GU7xSUJhmKtwHPAKzLO9HMaoKwJZ7Rf8AYPDDzKpZBqfvwQAOwAAAAAAAAAAAA=='
MEDIA_EXTENSIONS = {ext.lower() for ext in ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.ts', '.m2ts', '.vob']}

class JobStatus(Enum):
    """Status of a file processing job."""
    QUEUED = auto()
    RUNNING = auto()
    OK = auto()
    FAILED = auto()
    CANCELLED = auto()

class AppState(Enum):
    """State of the application workflow."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    CANCELLING = auto()
    MOVING = auto()

class FileJob:
    def __init__(self, path, list_widget_item):
        self.path = path
        self.list_widget_item = list_widget_item
        self.status = JobStatus.QUEUED
        self.details = "Queued for processing..."

# --- Worker for QThreadPool ---
class WorkerSignals(QObject):
    started = pyqtSignal(int)
    finished = pyqtSignal(int, bool, str)

class RunnableFFmpegWorker(QRunnable):
    def __init__(self, job_index, job_path, fast_check, fast_duration):
        super().__init__()
        self.job_index = job_index
        self.job_path = job_path
        self.fast_check = fast_check
        self.fast_duration = fast_duration
        self.signals = WorkerSignals()

    def run(self):
        if not os.path.exists(self.job_path):
            self.signals.finished.emit(self.job_index, False, "Error: File not found at path.")
            return
        self.signals.started.emit(self.job_index)
        try:
            command = ['ffmpeg']
            if self.fast_check:
                command.extend(['-sseof', f'-{self.fast_duration}'])
            command.extend(['-v', 'error', '-i', self.job_path, '-f', 'null', '-'])
            process = subprocess.run(
                command, capture_output=True, text=True, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            is_success = process.returncode == 0 and not process.stderr
            details = process.stderr.strip() or "OK"
            self.signals.finished.emit(self.job_index, is_success, details)
        except Exception as e:
            self.signals.finished.emit(self.job_index, False, f"A critical error occurred: {e}")

class MoveWorkerSignals(QObject):
    file_moved = pyqtSignal(str, str)
    finished = pyqtSignal(str)

class RunnableMoveWorker(QRunnable):
    def __init__(self, jobs_to_move, dest_folder):
        super().__init__()
        self.jobs_to_move = jobs_to_move
        self.dest_folder = dest_folder
        self.signals = MoveWorkerSignals()

    def run(self):
        moved_count, errors = 0, []
        for job in self.jobs_to_move:
            try:
                dest_path = os.path.join(self.dest_folder, os.path.basename(job.path))
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(dest_path)
                    dest_path = f"{base}_copy{ext}"
                shutil.move(job.path, dest_path)
                self.signals.file_moved.emit(job.path, dest_path)
                moved_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(job.path)}: {e}")
        
        msg = f"Moved {moved_count} file(s)."
        if errors: msg += "\n\nErrors:\n" + "\n".join(errors)
        self.signals.finished.emit(msg)

# --- Repair Command Dialog ---
class RepairCommandDialog(QDialog):
    def __init__(self, input_file, parent=None):
        super().__init__(parent)
        self.input_file = input_file
        self.setWindowTitle("Generate Repair Command")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Input File: {os.path.basename(input_file)}"))
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output File:"))
        default_out = f"{os.path.splitext(input_file)[0]}_repaired{os.path.splitext(input_file)[1]}"
        self.output_file_edit = QLineEdit(default_out)
        out_layout.addWidget(self.output_file_edit); layout.addLayout(out_layout)
        codec_layout = QHBoxLayout(); codec_layout.addWidget(QLabel("Method:"))
        self.codec_option = QComboBox()
        self.codec_option.addItems(["Copy (Fastest, Stream Copy)", "Re-encode (H.264, Slow, More Compatible)", "Re-encode (H.265, Slower, Smaller File)"])
        codec_layout.addWidget(self.codec_option); layout.addLayout(codec_layout)
        self.command_preview = QTextEdit(); self.command_preview.setReadOnly(True)
        layout.addWidget(QLabel("Generated Command:")); layout.addWidget(self.command_preview)
        button_layout = QHBoxLayout()
        self.copy_button = QPushButton("Copy Command"); self.run_button = QPushButton("Run Repair...")
        self.run_button.setToolTip("Opens a dialog to confirm before running the command directly.")
        button_layout.addWidget(self.copy_button); button_layout.addWidget(self.run_button)
        layout.addLayout(button_layout)
        self.copy_button.clicked.connect(self.copy_and_close)
        self.run_button.clicked.connect(self.run_repair)
        self.codec_option.currentTextChanged.connect(self.update_command)
        self.output_file_edit.textChanged.connect(self.update_command)
        self.update_command()

    def update_command(self): self.command_preview.setText(" ".join(shlex.quote(arg) for arg in self.get_command(quoted=False)))

    def get_command(self, quoted=True):
        out_file = self.output_file_edit.text(); in_file = self.input_file
        codec = self.codec_option.currentText()
        if "Copy" in codec: return ['ffmpeg', '-i', in_file, '-c', 'copy', out_file]
        elif "H.264" in codec: return ['ffmpeg', '-i', in_file, '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-c:a', 'aac', out_file]
        else: return ['ffmpeg', '-i', in_file, '-c:v', 'libx265', '-preset', 'medium', '-crf', '28', '-c:a', 'aac', out_file]
        
    def copy_and_close(self): QGuiApplication.clipboard().setText(" ".join(shlex.quote(arg) for arg in self.get_command(quoted=False))); self.accept()
        
    def run_repair(self):
        command_list = self.get_command(quoted=False); command_str = " ".join(shlex.quote(arg) for arg in command_list)
        QGuiApplication.clipboard().setText(command_str)
        reply = QMessageBox.question(self, "Run Repair", f"This will execute the following command:\n\n{command_str}\n\nThis may take a long time and consume system resources. Are you sure?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        try:
            subprocess.run(command_list, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            QMessageBox.information(self, "Success", f"Repair command completed successfully for:\n{os.path.basename(self.output_file_edit.text())}"); self.accept()
        except subprocess.CalledProcessError as e: QMessageBox.critical(self, "Error", f"Repair command failed with exit code {e.returncode}.\n\nError Output:\n{e.stderr}")
        except Exception as e: QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

## NEW FEATURE: About Dialog
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Video Integrity Checker")
        self.setFixedSize(400, 250)

        layout = QVBoxLayout(self)
        
        title_label = QLabel("Advanced Video Integrity Checker")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        version_label = QLabel("Version 1.1 (September 2025)")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- EDIT YOUR INFO HERE ---
        author_label = QLabel("Developed by Leon Priest")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        link_label = QLabel("<a href='https://github.com'>Visit my GitHub/Website</a>")
        link_label.setOpenExternalLinks(True)
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # -------------------------

        description_label = QLabel("This application uses FFmpeg to perform robust, multi-threaded integrity checks on video files.")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addSpacing(20)
        layout.addWidget(description_label)
        layout.addStretch()
        layout.addWidget(author_label)
        layout.addWidget(link_label)

# --- Main Application Window ---
class VideoBatchCheckerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.jobs = []
        self.state = AppState.IDLE
        self.jobs_processed = 0
        
        self.thread_pool = QThreadPool()
        self.max_threads = max(1, os.cpu_count() or 1)
        self.thread_pool.setMaxThreadCount(max(1, self.max_threads // 2))

        self.setWindowTitle("Advanced Video Integrity Checker"); self.setGeometry(100, 100, 900, 700); self.setAcceptDrops(True)
        self._create_menus(); self._init_ui(); self._update_ui_for_state()
        self._initial_ffmpeg_check()

    def _check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError): return False

    def _initial_ffmpeg_check(self):
        if not self._check_ffmpeg():
            QMessageBox.critical(self, "FFmpeg Not Found", "FFmpeg could not be found. The application requires FFmpeg to function.\n\nPlease install it and ensure its location is in your system's PATH, or place it in the same folder as this script.")
            self.check_button.setEnabled(False); self.retry_failed_action.setEnabled(False)

    def _create_menus(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        load_action = QAction("&Load Queue...", self); load_action.triggered.connect(self.load_queue)
        save_action = QAction("&Save Queue...", self); save_action.triggered.connect(self.save_queue)
        export_action = QAction("&Export Results...", self); export_action.triggered.connect(self.export_results)
        exit_action = QAction("E&xit", self); exit_action.triggered.connect(self.close)
        file_menu.addActions([load_action, save_action, export_action]); file_menu.addSeparator(); file_menu.addAction(exit_action)
        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        self.retry_failed_action = QAction("&Retry Failed Files", self); self.retry_failed_action.triggered.connect(self.retry_failed)
        self.clear_verified_action = QAction("Clear &Verified Files", self); self.clear_verified_action.triggered.connect(self.clear_verified)
        self.move_corrupt_action = QAction("&Move Corrupt Files...", self); self.move_corrupt_action.triggered.connect(self.move_corrupt_files)
        tools_menu.addActions([self.retry_failed_action, self.clear_verified_action, self.move_corrupt_action])
        # Help Menu (NEW)
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About...", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)
    
    def _init_ui(self):
        # ... (UI Initialization is unchanged) ...
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget)
        top_controls_layout = QHBoxLayout(); self.add_files_button = QPushButton("Add Files..."); self.add_folder_button = QPushButton("Add Folder...")
        self.remove_selected_button = QPushButton("Remove Selected"); self.clear_button = QPushButton("Clear All")
        top_controls_layout.addWidget(self.add_files_button); top_controls_layout.addWidget(self.add_folder_button); top_controls_layout.addStretch(); top_controls_layout.addWidget(self.remove_selected_button); top_controls_layout.addWidget(self.clear_button)
        self.file_list_widget = QListWidget(); self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        proc_controls_layout = QHBoxLayout(); proc_controls_layout.addWidget(QLabel("Concurrent Checks:"))
        self.thread_spinbox = QSpinBox(); self.thread_spinbox.setMinimum(1); self.thread_spinbox.setMaximum(self.max_threads)
        self.thread_spinbox.setValue(self.thread_pool.maxThreadCount())
        proc_controls_layout.addWidget(self.thread_spinbox); proc_controls_layout.addStretch()
        self.fast_check_box = QCheckBox("Fast Check"); self.fast_check_box.setToolTip("Only checks the end of each file (duration adjustable).\nMay miss corruption in earlier parts of the file.")
        proc_controls_layout.addWidget(self.fast_check_box)
        self.fast_duration_spinbox = QSpinBox(); self.fast_duration_spinbox.setMinimum(10); self.fast_duration_spinbox.setMaximum(600)
        self.fast_duration_spinbox.setValue(60); self.fast_duration_spinbox.setSuffix("s"); self.fast_duration_spinbox.setEnabled(False)
        proc_controls_layout.addWidget(self.fast_duration_spinbox)
        self.check_button = QPushButton("Start Checking"); self.pause_button = QPushButton("Pause"); self.cancel_button = QPushButton("Cancel")
        proc_controls_layout.addWidget(self.check_button); proc_controls_layout.addWidget(self.pause_button); proc_controls_layout.addWidget(self.cancel_button)
        self.progress_bar = QProgressBar()
        details_header_layout = QHBoxLayout(); details_header_layout.addWidget(QLabel("Details:")); details_header_layout.addStretch()
        self.busy_indicator_label = QLabel(); self.copy_details_button = QPushButton("Copy Details"); self.repair_button = QPushButton("Repair...")
        self.repair_button.setToolTip("Open a dialog to generate and run an FFmpeg repair command (only for failed files)")
        details_header_layout.addWidget(self.repair_button); details_header_layout.addWidget(self.copy_details_button); details_header_layout.addWidget(self.busy_indicator_label)
        self.status_label = QLabel("Add files/folders or drag them onto the window to begin.")
        self.details_log = QTextEdit(); self.details_log.setReadOnly(True)
        self.gif_byte_array = QByteArray(base64.b64decode(LOADING_GIF_B64)); self.gif_buffer = QBuffer(self.gif_byte_array); self.gif_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.busy_movie = QMovie(self.gif_buffer, b'gif'); self.busy_indicator_label.setMovie(self.busy_movie); self.busy_indicator_label.setFixedSize(16, 16)
        main_layout.addLayout(top_controls_layout); main_layout.addWidget(QLabel("Files to Process:")); main_layout.addWidget(self.file_list_widget)
        main_layout.addLayout(proc_controls_layout); main_layout.addWidget(self.progress_bar); main_layout.addWidget(self.status_label)
        main_layout.addLayout(details_header_layout); main_layout.addWidget(self.details_log)
        self.add_files_button.clicked.connect(self.add_files); self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_selected_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_list); self.file_list_widget.currentItemChanged.connect(self.update_details_log)
        self.check_button.clicked.connect(self.start_batch_check); self.pause_button.clicked.connect(self.toggle_pause)
        self.cancel_button.clicked.connect(self.cancel_check); self.thread_spinbox.valueChanged.connect(self.thread_pool.setMaxThreadCount)
        self.copy_details_button.clicked.connect(self.copy_details); self.repair_button.clicked.connect(self.generate_repair_command)
        self.fast_check_box.toggled.connect(self.fast_duration_spinbox.setEnabled)
    
    def _update_ui_for_state(self):
        # ... (UI State management is unchanged) ...
        is_idle = self.state == AppState.IDLE; is_running = self.state == AppState.RUNNING
        is_paused = self.state == AppState.PAUSED; is_cancelling = self.state == AppState.CANCELLING; is_moving = self.state == AppState.MOVING
        is_processing = not is_idle and not is_moving; has_items = len(self.jobs) > 0
        has_completed = any(j.status in [JobStatus.OK, JobStatus.FAILED] for j in self.jobs)
        has_failed = any(j.status == JobStatus.FAILED for j in self.jobs)
        self.centralWidget().setEnabled(not is_moving)
        self.add_files_button.setEnabled(is_idle); self.add_folder_button.setEnabled(is_idle)
        self.clear_button.setEnabled(is_idle and has_items); self.remove_selected_button.setEnabled(is_idle and has_items)
        self.thread_spinbox.setEnabled(is_idle); self.fast_check_box.setEnabled(is_idle); self.fast_duration_spinbox.setEnabled(is_idle and self.fast_check_box.isChecked())
        self.file_list_widget.setEnabled(is_idle or is_paused)
        self.check_button.setVisible(is_idle); self.pause_button.setVisible(is_processing); self.cancel_button.setVisible(is_processing)
        self.check_button.setEnabled(is_idle and has_items)
        self.pause_button.setText("Resume" if is_paused else "Pause")
        self.pause_button.setEnabled(is_running or is_paused); self.cancel_button.setEnabled(not is_cancelling)
        self.progress_bar.setVisible(is_processing); self.busy_indicator_label.setVisible(is_running)
        if is_running: self.busy_movie.start() 
        else: self.busy_movie.stop()
        self.menuBar().setEnabled(is_idle or is_paused)
        self.clear_verified_action.setEnabled((is_idle or is_paused) and has_completed)
        self.move_corrupt_action.setEnabled((is_idle or is_paused) and has_failed)
        self.retry_failed_action.setEnabled((is_idle or is_paused) and has_failed)
        self.update_details_log()

    ## NEW FEATURE: Method to show the About Dialog
    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

    # ... (All other methods remain the same) ...
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if os.path.exists(url.toLocalFile())]
        files_to_process = [p for p in paths if os.path.isfile(p) and p.lower().endswith(tuple(MEDIA_EXTENSIONS))]
        for p in paths:
            if os.path.isdir(p):
                files_to_process.extend([os.path.join(r, f) for r, _, fs in os.walk(p) for f in fs if f.lower().endswith(tuple(MEDIA_EXTENSIONS))])
        if files_to_process: self.add_files(sorted(files_to_process))
    def add_files(self, files_to_add=None):
        if not files_to_add: files_to_add, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", f"Video Files (*{' *'.join(MEDIA_EXTENSIONS)});;All Files (*)")
        current_paths = {job.path for job in self.jobs}; duplicates = [f for f in files_to_add if f in current_paths]
        new_files = [f for f in files_to_add if f not in current_paths]
        for file in new_files:
            item = QListWidgetItem(f"🕒 {os.path.basename(file)}"); item.setToolTip(file)
            self.file_list_widget.addItem(item); self.jobs.append(FileJob(file, item))
        if duplicates:
            duplicate_names = "\n".join(f"- {os.path.basename(f)}" for f in duplicates[:5])
            if len(duplicates) > 5: duplicate_names += "\n...and more."
            QMessageBox.warning(self, "Duplicates Skipped", f"Skipped {len(duplicates)} duplicate file(s) already in the queue:\n{duplicate_names}")
        self._update_ui_for_state()
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder: self.add_files(sorted([os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs if f.lower().endswith(tuple(MEDIA_EXTENSIONS))]))
    def remove_selected(self):
        if self.state != AppState.IDLE: return
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return
        paths_to_remove = {job.path for job in self.jobs if job.list_widget_item in selected_items}
        self.jobs = [job for job in self.jobs if job.path not in paths_to_remove]
        for item in selected_items: self.file_list_widget.takeItem(self.file_list_widget.row(item))
        self._update_ui_for_state()
    def clear_list(self):
        if self.state != AppState.IDLE: return
        self.jobs.clear(); self.file_list_widget.clear(); self.status_label.setText("Add files/folders to begin."); self._update_ui_for_state()
    def start_batch_check(self):
        if not self.jobs: return
        self.state = AppState.RUNNING; self.jobs_processed = 0; jobs_to_run_count = 0
        for job in self.jobs:
            if job.status != JobStatus.OK:
                job.status = JobStatus.QUEUED; job.details = "Queued..."
                job.list_widget_item.setText(f"🕒 {os.path.basename(job.path)}"); jobs_to_run_count += 1
        self.progress_bar.setMaximum(jobs_to_run_count if jobs_to_run_count > 0 else 1)
        self.progress_bar.setValue(0); self._update_ui_for_state(); self._submit_jobs()
    def _submit_jobs(self):
        if self.state != AppState.RUNNING: return
        use_fast_check = self.fast_check_box.isChecked(); fast_duration = self.fast_duration_spinbox.value()
        for i, job in enumerate(self.jobs):
            if job.status == JobStatus.QUEUED:
                worker = RunnableFFmpegWorker(i, job.path, use_fast_check, fast_duration)
                worker.signals.started.connect(self.on_file_started); worker.signals.finished.connect(self.on_file_finished)
                self.thread_pool.start(worker)
    def toggle_pause(self):
        if self.state == AppState.RUNNING: self.state = AppState.PAUSED; self.status_label.setText("Paused.")
        elif self.state == AppState.PAUSED: self.state = AppState.RUNNING; self.status_label.setText("Resuming..."); self._submit_jobs()
        self._update_ui_for_state()
    def cancel_check(self):
        if self.state in [AppState.RUNNING, AppState.PAUSED]:
            self.state = AppState.CANCELLING; self.thread_pool.clear()
            self.status_label.setText("Cancelling... Waiting for active checks to finish.")
            self._update_ui_for_state()
            if self.thread_pool.activeThreadCount() == 0: self.on_batch_finished()
    def on_file_started(self, job_index):
        if self.state == AppState.CANCELLING: return
        job = self.jobs[job_index]; job.status = JobStatus.RUNNING
        job.details = "Status: In Progress...\n\nResult: Checking file, please wait."
        job.list_widget_item.setText(f"➡️ {os.path.basename(job.path)}"); self.update_details_log(job.list_widget_item)
    def on_file_finished(self, job_index, is_success, details):
        job = self.jobs[job_index]
        if job.status == JobStatus.RUNNING: self.jobs_processed += 1
        job.status = JobStatus.OK if is_success else JobStatus.FAILED
        icon = "✅" if is_success else "❌"; job.list_widget_item.setText(f"{os.path.basename(job.path)} {icon}")
        job.details = f"Status: {job.status.name} {icon}\n\n"
        if is_success: job.details += "Result: File integrity verified."
        else: job.details += f"Result: File may be corrupt.\n\nFFmpeg Details:\n------------------\n{details}"
        if self.file_list_widget.currentItem() == job.list_widget_item: self.update_details_log()
        self.progress_bar.setValue(self.jobs_processed)
        self.status_label.setText(f"Processed {self.jobs_processed}/{self.progress_bar.maximum()} files...")
        jobs_to_run_count = self.progress_bar.maximum()
        if self.jobs_processed >= jobs_to_run_count or (self.state == AppState.CANCELLING and self.thread_pool.activeThreadCount() == 0):
            self.on_batch_finished()
    def on_batch_finished(self):
        if self.state == AppState.CANCELLING:
            self.status_label.setText("Batch processing cancelled.")
            for job in self.jobs:
                if job.status == JobStatus.QUEUED: job.status = JobStatus.CANCELLED
        else:
            self.status_label.setText("Batch processing complete."); self._show_summary_dialog()
        if self.progress_bar.maximum() > 0: self.progress_bar.setValue(self.progress_bar.maximum())
        self.state = AppState.IDLE; self._update_ui_for_state()
    def _show_summary_dialog(self):
        counts = {status: 0 for status in JobStatus};
        for job in self.jobs: counts[job.status] += 1
        msg = f"Processing complete!\n\n✅ Verified: {counts[JobStatus.OK]}\n❌ Failed: {counts[JobStatus.FAILED]}\n🚫 Cancelled: {counts[JobStatus.CANCELLED]}"
        failed_files = [j.path for j in self.jobs if j.status == JobStatus.FAILED]
        dialog = QMessageBox(self); dialog.setWindowTitle("Summary"); dialog.setText(msg)
        if failed_files:
            failed_files_str = "\n".join(f"- {os.path.basename(f)}" for f in failed_files)
            dialog.setDetailedText(f"Failed Files:\n{failed_files_str}")
            copy_button = dialog.addButton("Copy Failed List", QMessageBox.ButtonRole.ActionRole)
            copy_button.clicked.connect(lambda: QGuiApplication.clipboard().setText('\n'.join(failed_files)))
        dialog.exec()
    def update_details_log(self, current_item=None):
        if current_item is None: current_item = self.file_list_widget.currentItem()
        if not current_item:
            self.details_log.clear(); self.copy_details_button.setEnabled(False); self.repair_button.setVisible(False); return
        job = next((j for j in self.jobs if j.list_widget_item == current_item), None)
        if job:
            self.details_log.setText(f"Full Path: {job.path}\n\n{job.details}"); self.copy_details_button.setEnabled(True)
            self.repair_button.setVisible(job.status == JobStatus.FAILED)
    def copy_details(self): QGuiApplication.clipboard().setText(self.details_log.toPlainText())
    def generate_repair_command(self):
        job = next((j for j in self.jobs if j.list_widget_item == self.file_list_widget.currentItem()), None)
        if job and job.status == JobStatus.FAILED: dialog = RepairCommandDialog(job.path, self); dialog.exec()
    def save_queue(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Queue", "", "JSON Queue File (*.json)")
        if path:
            queue_data = [{'path': j.path, 'status': j.status.name, 'details': j.details} for j in self.jobs]
            try:
                with open(path, 'w', encoding='utf-8') as f: json.dump(queue_data, f, indent=2)
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not save queue: {e}")
    def load_queue(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Queue", "", "JSON Files (*.json);;Text Files (*.txt)")
        if not path: return
        self.clear_list()
        try:
            if path.lower().endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f: queue_data = json.load(f)
                files_to_load = {item['path']:item for item in queue_data if os.path.exists(item['path'])}
                if len(files_to_load) < len(queue_data): QMessageBox.warning(self, "Warning", "Some files from the queue were not found on disk and have been skipped.")
                self.add_files(list(files_to_load.keys()))
                for job in self.jobs:
                    if job.path in files_to_load:
                        item_data = files_to_load[job.path]
                        job.status = JobStatus[item_data.get('status', 'QUEUED')]; job.details = item_data.get('details', 'Queued...')
                        icon = "✅" if job.status == JobStatus.OK else "❌" if job.status == JobStatus.FAILED else "🕒"
                        job.list_widget_item.setText(f"{icon} {os.path.basename(job.path)}")
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    files_to_load = [line.strip() for line in f if line.strip() and os.path.exists(line.strip()) and line.strip().lower().endswith(tuple(MEDIA_EXTENSIONS))]
                self.add_files(files_to_load)
        except Exception as e: QMessageBox.critical(self, "Error", f"Could not load queue: {e}")
        self._update_ui_for_state()
    def export_results(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Results", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f); writer.writerow(["File Path", "Status", "Details"])
                    for job in self.jobs: writer.writerow([job.path, job.status.name, job.details.replace('\n', ' | ')])
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not export results: {e}")
    def clear_verified(self):
        for i in range(len(self.jobs) - 1, -1, -1):
            if self.jobs[i].status == JobStatus.OK: self.file_list_widget.takeItem(i); del self.jobs[i]
        self._update_ui_for_state()
    def move_corrupt_files(self):
        dest_folder = QFileDialog.getExistingDirectory(self, "Select Destination for Corrupt Files")
        if not dest_folder: return
        failed_jobs = [j for j in self.jobs if j.status == JobStatus.FAILED]
        if not failed_jobs: QMessageBox.information(self, "No Files to Move", "No corrupt files found."); return
        self.state = AppState.MOVING
        self.status_label.setText(f"Moving {len(failed_jobs)} files...")
        self._update_ui_for_state()
        worker = RunnableMoveWorker(failed_jobs, dest_folder)
        worker.signals.file_moved.connect(self._update_moved_job_path)
        worker.signals.finished.connect(self._on_move_finished)
        self.thread_pool.start(worker)
    def _update_moved_job_path(self, old_path, new_path):
        job = next((j for j in self.jobs if j.path == old_path), None)
        if job:
            job.path = new_path; job.details += f"\n\nMOVED to {new_path}"
            job.list_widget_item.setToolTip(new_path)
    def _on_move_finished(self, summary_message):
        QMessageBox.information(self, "Move Complete", summary_message)
        self.state = AppState.IDLE
        self.status_label.setText("Move operation finished.")
        self._update_ui_for_state()
    def retry_failed(self):
        failed_jobs_to_retry = [j for j in self.jobs if j.status == JobStatus.FAILED]
        if not failed_jobs_to_retry: QMessageBox.information(self, "No Failed Files", "There are no failed files to retry."); return
        self.state = AppState.RUNNING; self.jobs_processed = 0
        self.progress_bar.setMaximum(len(failed_jobs_to_retry)); self.progress_bar.setValue(0)
        for job in failed_jobs_to_retry:
            job.status = JobStatus.QUEUED; job.details = "Queued for retry..."
            job.list_widget_item.setText(f"🕒 {os.path.basename(job.path)}")
        self._update_ui_for_state(); self._submit_jobs()
    def closeEvent(self, event):
        if self.state not in [AppState.IDLE, AppState.MOVING]:
            reply = QMessageBox.question(self, 'Exit Confirmation', "A batch process is running. Are you sure you want to exit?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: event.ignore(); return
        self.busy_movie.stop(); self.gif_buffer.close()
        self.thread_pool.clear(); self.thread_pool.waitForDone(-1)
        super().closeEvent(event)

# --- Run the Application ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    if "Fusion" in QStyleFactory.keys(): app.setStyle("Fusion")
    
    # Create an instance but don't show it yet
    main_window = VideoBatchCheckerApp()
    
    # If the __init__ returned early (e.g. FFmpeg check failed in a future version), 
    # we might need to handle it, but the current implementation shows a message box from within __init__.
    # The initial check is now at the end of __init__ so the window object exists.
    
    main_window.show()
    sys.exit(app.exec())