@echo off
echo 清理系统输入队列...
rundll32 user32.dll,SetCursorPos 0,0
timeout /t 1 /nobreak >nul
echo 重启图形子系统（释放GDI/句柄）...
taskkill /f /im dwm.exe
echo 清理完成！脚本可正常运行
pause