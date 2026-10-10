@echo off
chcp 65001 >nul
title Emoji-Studio - 微信表情创作工坊
cd /d "%~dp0\WeChatEmojiStudio"
start "" python main.py
exit
