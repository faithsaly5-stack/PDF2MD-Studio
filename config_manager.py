import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class ConfigManager:
    @staticmethod
    def load():
        default_config = {
            "theme": "Light",  # Default to Light theme as requested
            "chunk_size": "20",
            "quality": "Balanced (1.15x - 110 DPI)",
            "format": "JPG (Recommended)",
            "auto_open": True,
            "use_custom_out": False,
            "custom_out_dir": ""
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    default_config.update(data)
            except Exception:
                pass
        return default_config

    @staticmethod
    def save(config_data):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
        except Exception:
            pass
