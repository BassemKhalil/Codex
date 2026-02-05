@echo off
REM Transfer Notepad++ Replica from Codex to NotepadReplica repo
REM Run this script in a folder where you want to clone the repos

echo Cloning repositories...
git clone https://github.com/BassemKhalil/Codex
git clone https://github.com/BassemKhalil/NotepadReplica

echo.
echo Checking out the feature branch...
cd Codex
git checkout claude/notepad-replica-tab-recovery-yvkfK

echo.
echo Copying files to NotepadReplica...
cd ..
xcopy /E /I Codex\notepad_replica NotepadReplica\notepad_replica
copy Codex\notepad_replica.py NotepadReplica\
copy Codex\build.bat NotepadReplica\
copy Codex\build.sh NotepadReplica\
copy Codex\build_portable.py NotepadReplica\

echo.
echo Creating README and other files...
cd NotepadReplica

REM Create .gitignore
(
echo # Python
echo __pycache__/
echo *.py[cod]
echo *$py.class
echo *.so
echo .Python
echo env/
echo venv/
echo .venv/
echo.
echo # PyInstaller
echo build/
echo dist/
echo *.spec
echo.
echo # IDE
echo .idea/
echo .vscode/
echo *.swp
echo *.swo
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
) > .gitignore

REM Create requirements.txt
(
echo # Notepad++ Replica
echo # No dependencies required to run - uses Python standard library
echo.
echo # Build dependencies ^(optional - for creating portable .exe^)
echo pyinstaller^>=6.0.0
) > requirements.txt

echo.
echo Committing and pushing...
git add -A
git commit -m "Initial commit: Notepad++ Replica with session recovery"
git push

echo.
echo Done! Your NotepadReplica repo is ready.
echo You can now run: python notepad_replica.py --recover
pause
