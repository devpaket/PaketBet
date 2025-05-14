import os
import hashlib
import json

def calculate_hash(filepath):
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Ошибка при расчете хеша для {filepath}: {str(e)}")
        return None

def create_manifest():
    files = []
    excluded_files = []

    # Получаем все файлы в текущей директории
    print("Сканирование файлов в текущей директории...")
    for root, dirs, filenames in os.walk("."):
        for filename in filenames:
            if filename == 'manifest.json':  # Исключаем manifest.json
                continue

            file_path = os.path.join(root, filename)
            print(f"Обнаружен файл: {file_path}")
            files.append(file_path)

    # Запрос на исключение файлов
    print("\nВыберите файлы для исключения (через запятую):")
    for i, file in enumerate(files, 1):
        print(f"{i}. {file}")
    
    excluded_indices = input("\nВведите номера файлов для исключения (например, 1,3,5): ").split(",")
    excluded_indices = [int(i) - 1 for i in excluded_indices if i.strip().isdigit()]

    excluded_files = [files[i] for i in excluded_indices]

    # Генерация списка файлов и их хешей
    manifest_data = {"files": []}
    for file_path in files:
        if file_path not in excluded_files:
            file_hash = calculate_hash(file_path)
            if file_hash:
                manifest_data["files"].append({
                    "path": file_path,
                    "hash": file_hash
                })
            else:
                print(f"{file_path} не может быть добавлен в manifest.json из-за ошибки при расчете хеша.")

    # Добавляем сам manifest.json в файл
    manifest_file_hash = calculate_hash("manifest.json")
    if manifest_file_hash:
        manifest_data["files"].append({
            "path": "manifest.json",
            "hash": manifest_file_hash
        })

    # Сохраняем manifest.json
    with open("manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=4)

    print(f"\n{len(manifest_data['files'])} файлов было добавлено в manifest.json.")
    print("manifest.json успешно создан!")

if __name__ == "__main__":
    create_manifest()
