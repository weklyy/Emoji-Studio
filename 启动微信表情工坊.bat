@echo off
chcp 65001 >nul
title 微信表情包创作与资产管理工坊
cd /d "%~dp0\WeChatEmojiStudio"
start "" python main.py
exit
