# check_logs.py
"""Check if logs are being written correctly to webdav_manager.log."""

import os
import sys


def check_logs():
    """Check log file location and content."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, 'logs')
    log_file = os.path.join(log_dir, 'webdav_manager.log')

    print(f"Base directory: {base_dir}")
    print(f"Log directory: {log_dir}")
    print(f"Log file: {log_file}")
    print(f"Log directory exists: {os.path.exists(log_dir)}")
    print(f"Log file exists: {os.path.exists(log_file)}")

    if os.path.exists(log_file):
        file_size = os.path.getsize(log_file)
        print(f"Log file size: {file_size} bytes")

        # Покажем последние 20 строк
        print("\n" + "=" * 60)
        print("LAST 20 LINES OF LOG:")
        print("=" * 60)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.strip())
    else:
        print("\n❌ Log file does not exist yet")
        print("Creating logs directory...")
        os.makedirs(log_dir, exist_ok=True)
        print(f"Created: {log_dir}")

        # Попробуем создать тестовый лог
        test_log = os.path.join(log_dir, 'test.log')
        with open(test_log, 'w') as f:
            f.write("Test write\n")
        print(
            f"Test write to {test_log}: {'✅' if os.path.exists(test_log) else '❌'}")
        if os.path.exists(test_log):
            os.remove(test_log)


if __name__ == "__main__":
    check_logs()