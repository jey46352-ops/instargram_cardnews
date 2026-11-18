@echo off
chcp 65001 >nul
title 인스타그램 카드뉴스 업로드
cd /d "%~dp0"
python -m src.web_upload %*
echo.
echo 이어서 맞팔 도우미를 엽니다 (좋아요·팔로우는 직접 클릭).
python -m src.engage
echo.
echo 끝났습니다. 이 창은 1분 뒤 닫힙니다.
timeout /t 60 >nul
