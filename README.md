- Папка deleted - хранит удаленные файлы принтера с отчетом (удаленный файл целяком) ;
- Папка tosend - хранит отчеты на отправку (только сами отчеты, подготовленный к отправке)
- Лог автоматом удаляется когда становится больше 20 МБ
- config.json - JSON формат, для проверки правильности можно заюзать https://jsonformatter.curiousconcept.com/#
- Проверить, что-бы у config.json была читаемая кодировка в зависимости от OS
- consfig_example.json - только описание конфига, программа будет использовать config.json
- Кодировка всех файлов должна быть cp1251 (windows1251), в том числе и config файла
- Порядок установки клиента-отправлялки:
```bash
python -m pip install requests
python -m pip install -U pyinstaller
pyinstaller main.py --onefile
```

- Конфиг сервера - server.json
- БД сервера - users.json
- Порядок установки сервера и запуска сервера:
```bash
python -m pip install pyTelegramBotAPI
python -m pip intall Flask
python server.py
```
