from cryptography.fernet import Fernet

# Загружаем ключ
with open("secret.key", "rb") as key_file:
    key = key_file.read()

cipher = Fernet(key)

# Вставь сюда свой реальный токен
token = "7846221293:AAHsoCzRSvQQocIreb9dWWd2kc2gjgF93tQ"

# Шифруем токен
encrypted = cipher.encrypt(token.encode())
print("🔐 Зашифрованный токен:")
print(encrypted.decode())
