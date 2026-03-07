@echo off
chcp 65001 >nul
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   CortexNodus  Build  (Go/Windows)   ║
echo  ╚══════════════════════════════════════╝
echo.

where go >nul 2>&1
if errorlevel 1 (
    echo  [错误] 未找到 Go，请从 https://go.dev 安装
    pause & exit /b 1
)

echo  [1/3] 下载依赖...
cd launcher
go mod tidy
if errorlevel 1 ( echo  [错误] go mod tidy 失败 & cd .. & pause & exit /b 1 )

echo  [2/3] 编译...
go build -ldflags "-H windowsgui -s -w" -o ..\CortexNodus.exe .
if errorlevel 1 ( echo  [错误] 编译失败 & cd .. & pause & exit /b 1 )
cd ..

echo  [3/3] 打包分发目录...
if not exist dist mkdir dist
copy /y CortexNodus.exe dist\
xcopy /e /i /y ml       dist\ml\
xcopy /e /i /y templates dist\templates\
xcopy /e /i /y static   dist\static\
if exist subgraphs xcopy /e /i /y subgraphs dist\subgraphs\
copy /y app.py              dist\
copy /y marketplace_server.py dist\
copy /y requirements.txt    dist\

echo.
echo  ✓ 完成！分发包位于 dist\
echo    运行：dist\CortexNodus.exe
echo.
pause
