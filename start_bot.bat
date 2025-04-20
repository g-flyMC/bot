@echo off
title Discord Bot - Mistral Chat
color 0A
echo **********************************************
echo *        Lancement du Bot Discord            *
echo *        Avec integration Mistral           *
echo **********************************************
echo.

:: Vérification de Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Python n'est pas installé ou n'est pas dans le PATH
    echo Veuillez installer Python 3.8+ depuis https://www.python.org/downloads/
    pause
    exit /b
)

:: Vérification des dépendances
echo Verification des dependances...
pip install discord.py requests python-dotenv >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR: Echec de l'installation des dependances
    echo Essayez manuellement avec: pip install discord.py requests python-dotenv
    pause
    exit /b
)

:: Lancement du bot
echo Lancement du bot...
python bot.py

:: En cas d'erreur
if %errorlevel% neq 0 (
    echo.
    echo Le bot s'est arrete avec une erreur (code %errorlevel%)
    echo Verifiez que:
    echo 1. Le fichier .env est correctement configure
    echo 2. Le token Discord est valide
    echo 3. Aucune erreur dans le code Python
)

pause
