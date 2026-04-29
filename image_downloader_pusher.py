#!/usr/bin/env python3

import subprocess
import sys
import os
import json
import glob
from datetime import datetime
from typing import Dict, List, Tuple
import re

# Цвета для вывода
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'

def log_info(msg): print(f"{BLUE}[INFO]{NC} {msg}")
def log_success(msg): print(f"{GREEN}[SUCCESS]{NC} {msg}")
def log_warning(msg): print(f"{YELLOW}[WARNING]{NC} {msg}")
def log_error(msg): print(f"{RED}[ERROR]{NC} {msg}")

class HarborImagePusher:
    def __init__(self, version: str, target_registry: str = None, 
                 git_repo: str = None, git_branch: str = 'main'):
        self.version = version
        self.version_without_v = version.replace('v', '')
        self.target_registry = target_registry or "harbor.idp.ecpk.ru/core/knative"
        self.git_repo = git_repo or "https://github.com/scr112/my-eventing.git"
        self.git_branch = git_branch
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.git_local_dir = os.path.join(self.base_dir, f"git-repo-{self.version_without_v}")
        self.images_dir = os.path.join(self.git_local_dir, f"images-{self.version}")
        self.manifests_dir = os.path.join(self.git_local_dir, f"manifests-{self.version}")
        
        self.harbor_user = None
        self.harbor_password = None
        
    def get_credentials(self):
        """Запрашивает учетные данные для Harbor"""
        print("\n" + "=" * 60)
        log_info("АВТОРИЗАЦИЯ В HARBOR REGISTRY")
        print("=" * 60)
        
        self.harbor_user = os.environ.get('HARBOR_USER')
        self.harbor_password = os.environ.get('HARBOR_PASSWORD')
        
        if not self.harbor_user:
            self.harbor_user = input(f"{BLUE}[INPUT]{NC} Введите имя пользователя Harbor: ").strip()
        
        if not self.harbor_password:
            import getpass
            self.harbor_password = getpass.getpass(f"{BLUE}[INPUT]{NC} Введите пароль Harbor: ").strip()
        
        if not self.harbor_user or not self.harbor_password:
            log_error("Имя пользователя и пароль обязательны!")
            return False
        
        return True
    
    def docker_login(self) -> bool:
        """Выполняет логин в Harbor"""
        registry_server = self.target_registry.split('/')[0]
        
        try:
            log_info(f"Логин в {registry_server}...")
            cmd = ['docker', 'login', registry_server, '-u', self.harbor_user, '--password-stdin']
            result = subprocess.run(cmd, input=self.harbor_password, 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                log_success(f"✓ Успешный вход в {registry_server}")
                return True
            else:
                log_error(f"✗ Ошибка входа: {result.stderr}")
                return False
        except Exception as e:
            log_error(f"Ошибка: {e}")
            return False
    
    def import_image(self, tar_file: str, image_name: str) -> Tuple[bool, str]:
        """Импортирует образ из tar файла используя docker import"""
        try:
            log_info(f"  Импорт: docker import {os.path.basename(tar_file)}")
            
            # Импортируем образ
            cmd = ['docker', 'import', tar_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                image_id = result.stdout.strip()
                log_success(f"  ✓ Образ импортирован: {image_id[:20]}...")
                
                # Тегируем образ
                target_tag = f"{self.target_registry}/{image_name}:{self.version}"
                tag_cmd = ['docker', 'tag', image_id, target_tag]
                tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
                
                if tag_result.returncode == 0:
                    log_success(f"  ✓ Образ перетегирован: {target_tag}")
                    return True, target_tag
                else:
                    log_error(f"  ✗ Ошибка тегирования: {tag_result.stderr}")
                    return False, tag_result.stderr
            else:
                log_error(f"  ✗ Ошибка импорта: {result.stderr[:200]}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Timeout (300 seconds)"
        except Exception as e:
            return False, str(e)
    
    def process_images(self) -> List[Dict]:
        """Обрабатывает все tar файлы и импортирует образы"""
        log_info("Поиск и импорт Docker образов...")
        
        # Проверяем несколько возможных директорий
        possible_dirs = [
            self.images_dir,
            os.path.join(self.base_dir, f"images-{self.version}"),
            os.path.join(self.base_dir, f"knative-images-{self.version}"),
            self.base_dir
        ]
        
        images_dir = None
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                images_dir = dir_path
                log_info(f"Найдена директория с образами: {images_dir}")
                break
        
        if not images_dir:
            log_error("Директория с образами не найдена")
            return []
        
        # Ищем все tar файлы
        tar_files = glob.glob(os.path.join(images_dir, "*.tar"))
        
        if not tar_files:
            log_error("Tar файлы не найдены")
            return []
        
        log_info(f"Найдено {len(tar_files)} архивов")
        
        processed_images = []
        
        for tar_file in sorted(tar_files):
            file_name = os.path.basename(tar_file)
            image_name = file_name.replace('.tar', '')
            file_size = os.path.getsize(tar_file) / (1024 * 1024)
            
            print(f"\n{'='*60}")
            log_info(f"Обработка: {file_name} ({file_size:.1f} MB)")
            
            # Импортируем образ
            success, result = self.import_image(tar_file, image_name)
            
            if success:
                processed_images.append({
                    'name': image_name,
                    'tar_file': tar_file,
                    'loaded_image': result,
                    'size_mb': file_size,
                    'status': 'imported'
                })
            else:
                log_error(f"  ✗ Не удалось импортировать {image_name}")
        
        log_success(f"\nИмпортировано {len(processed_images)} из {len(tar_files)} образов")
        return processed_images
    
    def push_to_harbor(self, images: List[Dict]) -> Tuple[int, int]:
        """Пушит образы в Harbor"""
        log_info("\nПуш образов в Harbor...")
        
        success_count = 0
        failed_count = 0
        
        for idx, img in enumerate(images, 1):
            print(f"\n{'='*60}")
            log_info(f"[{idx}/{len(images)}] Пуш: {img['name']}")
            
            target_tag = f"{self.target_registry}/{img['name']}:{self.version}"
            log_info(f"Target: {target_tag}")
            
            # Проверяем существование образа
            check_cmd = ['docker', 'image', 'inspect', img['loaded_image']]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if check_result.returncode != 0:
                log_error(f"  ✗ Образ не найден: {img['loaded_image']}")
                failed_count += 1
                continue
            
            # Пушим образ
            log_info("  Выполнение: docker push...")
            push_cmd = ['docker', 'push', target_tag]
            push_result = subprocess.run(push_cmd, capture_output=True, text=True, timeout=600)
            
            if push_result.returncode == 0:
                log_success(f"  ✓ Успешно запушен")
                success_count += 1
            else:
                error_msg = push_result.stderr[:200]
                if "denied" in error_msg.lower():
                    log_error(f"  ✗ Доступ запрещен. Проверьте права в Harbor")
                elif "unauthorized" in error_msg.lower():
                    log_error(f"  ✗ Ошибка авторизации. Проверьте логин/пароль")
                else:
                    log_error(f"  ✗ Ошибка пуша: {error_msg}")
                failed_count += 1
        
        return success_count, failed_count
    
    def create_import_script(self, images: List[Dict]):
        """Создает скрипт для ручного импорта и пуша"""
        script_file = os.path.join(self.base_dir, f"import-and-push-{self.version}.sh")
        
        with open(script_file, 'w') as f:
            f.write("#!/bin/bash\n\n")
            f.write(f"# Script to import and push images to Harbor for Knative {self.version}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("# Login to Harbor\n")
            f.write(f"echo 'Login to Harbor...'\n")
            f.write(f"docker login {self.target_registry.split('/')[0]}\n\n")
            
            for img in images:
                f.write(f"# Process {img['name']}\n")
                f.write(f"echo 'Importing {img[\"name\"]}...'\n")
                f.write(f"cat {img['tar_file']} | docker import - {self.target_registry}/{img['name']}:{self.version}\n")
                f.write(f"docker push {self.target_registry}/{img['name']}:{self.version}\n")
                f.write(f"echo '  ✓ {img[\"name\"]} pushed'\n\n")
            
            f.write('echo "All images pushed successfully!"\n')
        
        os.chmod(script_file, 0o755)
        log_success(f"Скрипт для импорта и пуша создан: {script_file}")
    
    def create_report(self, images: List[Dict], success: int, failed: int):
        """Создает отчет"""
        report_file = os.path.join(self.base_dir, f"push-report-{self.version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
        
        with open(report_file, 'w') as f:
            f.write(f"# Harbor Push Report\n")
            f.write(f"# Version: {self.version}\n")
            f.write(f"# Target: {self.target_registry}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(images)}\n")
            f.write(f"# Success: {success}\n")
            f.write(f"# Failed: {failed}\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            for img in images:
                target_tag = f"{self.target_registry}/{img['name']}:{self.version}"
                f.write(f"✅ {img['name']}\n")
                f.write(f"   Size: {img['size_mb']:.1f} MB\n")
                f.write(f"   Target: {target_tag}\n\n")
        
        log_success(f"Отчет сохранен: {report_file}")
    
    def run(self):
        """Основной метод"""
        print("=" * 80)
        log_info(f"HARBOR IMAGE PUSHER - Knative {self.version}")
        print("=" * 80)
        log_info(f"Target Registry: {self.target_registry}")
        log_info(f"Version: {self.version}")
        print()
        
        # 1. Получаем учетные данные
        if not self.get_credentials():
            return False
        
        # 2. Обрабатываем и импортируем образы
        images = self.process_images()
        
        if not images:
            log_error("Не удалось импортировать ни одного образа")
            log_info("\nПроверьте:")
            log_info("  1. Что tar файлы находятся в правильной директории")
            log_info("  2. Что файлы не повреждены")
            log_info("  3. Что у вас есть права на чтение файлов")
            return False
        
        # 3. Логин в Harbor
        if not self.docker_login():
            return False
        
        # 4. Пуш в Harbor
        success, failed = self.push_to_harbor(images)
        
        # 5. Создаем вспомогательные файлы
        self.create_import_script(images)
        self.create_report(images, success, failed)
        
        # 6. Статистика
        print("\n" + "=" * 80)
        log_info("СТАТИСТИКА")
        print("=" * 80)
        log_info(f"Всего образов: {len(images)}")
        log_info(f"Успешно запушено: {success}")
        log_info(f"Ошибок: {failed}")
        
        total_size = sum(img['size_mb'] for img in images)
        log_info(f"Общий размер: {total_size:.2f} MB")
        
        if success == len(images):
            log_success("\n✅ Все образы успешно запушены в Harbor!")
        else:
            log_warning(f"\n⚠️ Не удалось запушнуть {failed} образов")
            log_info(f"Для повторной попытки выполните: ./import-and-push-{self.version}.sh")
        
        return success > 0

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Push Knative images to Harbor using docker import')
    parser.add_argument('version', default='v1.21.1', nargs='?',
                       help='Knative version (e.g., v1.21.1)')
    parser.add_argument('--registry', default='harbor.idp.ecpk.ru/core/knative',
                       help='Target Harbor registry')
    parser.add_argument('--git-repo', default='https://github.com/scr112/my-eventing.git',
                       help='Git repository with images')
    parser.add_argument('--git-branch', default='main',
                       help='Git branch')
    
    args = parser.parse_args()
    
    pusher = HarborImagePusher(
        version=args.version,
        target_registry=args.registry,
        git_repo=args.git_repo,
        git_branch=args.git_branch
    )
    
    success = pusher.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
