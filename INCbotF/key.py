from cryptography.fernet import Fernet

key = Fernet.generate_key()
with open("secret.key", "wb") as key_file:
    key_file.write(key)

print("🔑 Ключ успешно создан и сохранён в файл secret.key.")
