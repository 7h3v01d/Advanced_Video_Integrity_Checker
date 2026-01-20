# Advanced Video Integrity Checker
A powerful, user-friendly desktop application for batch-verifying the integrity of video files using FFmpeg. Designed for media enthusiasts, archivists, and professionals to ensure their video library is free from corruption.

⚠️ **LICENSE & USAGE NOTICE — READ FIRST**

This repository is **source-available for private technical evaluation and testing only**.

- ❌ No commercial use  
- ❌ No production use  
- ❌ No academic, institutional, or government use  
- ❌ No research, benchmarking, or publication  
- ❌ No redistribution, sublicensing, or derivative works  
- ❌ No independent development based on this code  

All rights remain exclusively with the author.  
Use of this software constitutes acceptance of the terms defined in **LICENSE.txt**.

---

## Features
- **Batch Processing**: Add files, folders, or drag-and-drop them onto the application.
- **Concurrent Checking**: Multi-threaded processing with adjustable concurrent checks (default: half CPU cores).
- **Process Control**: Start, pause, resume, or cancel batch operations.
- **Enhanced Status Display**: Color-coded status icons (gray: Queued/Cancelled, yellow: Running, green: OK, red: Failed).
- **File Management**:
  - Move corrupt files to a designated folder.
  - Clear completed files from the list.
- **Queue Management**:
  - Save queues as JSON (including status/details) or text files.
  - Load queues to resume work.
- **Reporting**:
  - Export results to CSV with detailed FFmpeg output.
  - Copy FFmpeg output for any file to the clipboard.
- **Advanced Repair Commands**: Generate FFmpeg repair commands with options for stream copy or re-encoding (H.264/H.265).
- **Usability**:
  - Keyboard shortcuts (Ctrl+O, Ctrl+S, Ctrl+E, Ctrl+D, Ctrl+M, F1).
  - Visual drop zone and tooltips.
  - Summary dialog after batch completion.
  - Help dialog explaining features and status icons.

## Requirements
- **Python 3**: The script is written in Python.
- **PyQt6**: Install via `pip install PyQt6`.
- **FFmpeg**: Must be installed and accessible (checked at startup).

## Installation & Usage
1. **Install FFmpeg**:
   - Download from [ffmpeg.org](https://ffmpeg.org).
   - Place `ffmpeg.exe` (Windows) or `ffmpeg` (macOS/Linux) in the script's folder or add its path to your system's PATH.
2. **Save the Script**:
   - Save the code as `video_checker.py`.
3. **Run the Application**:
   ```bash
   python video_checker.py
   ```
   - If FFmpeg is missing, a dialog will guide you.

## How to Use
1. **Adding Files**:
   - Click "Add Files..." (Ctrl+O) or "Add Folder...".
   - Drag-and-drop files/folders onto the highlighted drop zone.
2. **Controlling the Process**:
   - Adjust concurrent checks via the spinbox.
   - Start, pause/resume, or cancel the process.
3. **Managing Results**:
   - **File Menu**: Load/save queues (Ctrl+S/Ctrl+O), export results (Ctrl+E).
   - **Tools Menu**: Clear completed files (Ctrl+D), move corrupt files (Ctrl+M).
   - **Details Pane**: View FFmpeg output, copy details, or generate repair commands for failed files.
4. **Viewing Results**:
   - Color-coded list items show status.
   - A summary dialog appears after processing.
   - Press F1 for help.

## Troubleshooting
- **'ffmpeg' not found**: Ensure FFmpeg is in the script's folder or PATH.
- **Slow folder scanning**: For large folders, scanning may take time; a progress indicator is planned for future updates.

## License
MIT License.
