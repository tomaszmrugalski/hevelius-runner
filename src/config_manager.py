import configparser
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path="config/config.ini"):
        self.config = configparser.ConfigParser()
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        self.config.read(config_path)

    def get_api_config(self):
        return dict(self.config["api"])

    def get_paths_config(self):
        return dict(self.config["paths"])

    def get_nina_config(self):
        return dict(self.config["nina"])

    def get_scripts_config(self):
        return dict(self.config["scripts"])
