import os
import shutil
from pathlib import Path
from typing import Tuple

def cleanup_temp_files(temp_dir: str) -> Tuple[bool, str]:
    """
    Очистка временных файлов
    """
    try:
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Warning: Could not delete {item_path}: {e}")
        return True, "Cleanup completed"
    except Exception as e:
        return False, str(e)