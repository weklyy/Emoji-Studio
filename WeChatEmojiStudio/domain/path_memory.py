import os
from PySide6.QtCore import QSettings

class PathMemory:
    """
    用户文件选择路径记忆服务
    记录并持久化上传（选择原图/视频）与下载（另存为/批量导出）的历史目录。
    遵循现代桌面体验规范：只要用户选择过一次目录，下次立即默认打开相同目录。
    """
    _SETTINGS_ORG = "WeChatEmojiStudio"
    _SETTINGS_APP = "PathPreferences"

    KEY_LAST_UPLOAD = "history/last_upload_dir"
    KEY_LAST_DOWNLOAD = "history/last_download_dir"

    @classmethod
    def _settings(cls) -> QSettings:
        return QSettings(cls._SETTINGS_ORG, cls._SETTINGS_APP)

    @classmethod
    def get_upload_dir(cls, fallback: str = "") -> str:
        """获取最近一次上传/打开文件的文件夹"""
        s = cls._settings()
        val = s.value(cls.KEY_LAST_UPLOAD, "")
        if val and isinstance(val, str) and os.path.isdir(val):
            return val
        if fallback and os.path.isdir(fallback):
            return fallback
        return os.path.expanduser("~")

    @classmethod
    def set_upload_dir(cls, path_or_dir: str):
        """记录上传/打开文件的文件夹"""
        if not path_or_dir:
            return
        d = path_or_dir if os.path.isdir(path_or_dir) else os.path.dirname(path_or_dir)
        if os.path.isdir(d):
            s = cls._settings()
            s.setValue(cls.KEY_LAST_UPLOAD, os.path.abspath(d))

    @classmethod
    def get_download_dir(cls, fallback: str = "") -> str:
        """获取最近一次下载/保存文件的文件夹"""
        s = cls._settings()
        val = s.value(cls.KEY_LAST_DOWNLOAD, "")
        if val and isinstance(val, str) and os.path.isdir(val):
            return val
        if fallback and os.path.isdir(fallback):
            return fallback
        return os.path.expanduser("~")

    @classmethod
    def set_download_dir(cls, path_or_dir: str):
        """记录下载/保存文件的文件夹"""
        if not path_or_dir:
            return
        d = path_or_dir if os.path.isdir(path_or_dir) else os.path.dirname(path_or_dir)
        if os.path.isdir(d):
            s = cls._settings()
            s.setValue(cls.KEY_LAST_DOWNLOAD, os.path.abspath(d))
