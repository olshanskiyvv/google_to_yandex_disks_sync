import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    google_credentials_file: str
    google_token_file: str
    google_folder_id: str
    yandex_token: str
    yandex_folder: str
    log_file: str
    log_level: str

    def __init__(self):
        self.google_credentials_file = os.getenv(
            "GOOGLE_CREDENTIALS_FILE", "credentials.json"
        )
        self.google_token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        self.google_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
        self.yandex_token = os.getenv("YANDEX_TOKEN", "")
        self.yandex_folder = os.getenv("YANDEX_FOLDER", "/backup/videos")
        self.log_file = os.getenv("LOG_FILE", "sync.log")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> list[str]:
        errors = []
        if not self.google_folder_id:
            errors.append("GOOGLE_FOLDER_ID не указан")
        if not self.yandex_token:
            errors.append("YANDEX_TOKEN не указан")
        return errors


config = Config()
