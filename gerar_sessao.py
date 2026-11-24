"""Gera a sessão do Telegram para o coletor ler os grupos. Rode no SEU computador, uma vez.

    pip install telethon==1.46.0
    python gerar_sessao.py

Você vai precisar do api_id e do api_hash (https://my.telegram.org → API development tools)
e do código que o Telegram manda no app. No fim, o script mostra uma sessão longa:
copie e cole no segredo TELEGRAM_SESSION do repositório. Ela dá acesso à conta:
não envie para ninguém, nem em chat. Para revogar: Telegram → Configurações →
Dispositivos → encerrar a sessão "MilhasFacilitadas".
"""
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

api_id = int(input("api_id: ").strip())
api_hash = input("api_hash: ").strip()
with TelegramClient(StringSession(), api_id, api_hash, device_model="MilhasFacilitadas") as cliente:
    print("\nSessão gerada. Copie a linha abaixo para o segredo TELEGRAM_SESSION:\n")
    print(cliente.session.save())
