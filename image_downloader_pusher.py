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
    def __init__(self, version: str, target_registry: str = None):
        self.version = version
        self.target_registry = target_registry or "harbor.idp.ecpk.ru/core/knative"
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = os.path.join(self.base_dir, "images-v1.21.1")
        
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
    
    def import_and_push_image(self, tar_file: str, image_name: str) -> Tuple[bool, str]:
        """Импортирует и пушит образ"""
        try:
            target_tag = f"{self.target_registry}/{image_name}:{self.version}"
            
            # Импортируем образ
            log_info(f"  Импорт {image_name}...")
            with open(tar_file, 'rb') as f:
                import_cmd = ['docker', 'import', '-', target_tag]
                import_result = subprocess.run(import_cmd, stdin=f, capture_output=True, text=True, timeout=300)
            
            if import_result.returncode != 0:
                log_error(f"  ✗ Ошибка импорта: {import_result.stderr[:200]}")
                return False, import_result.stderr
            
            log_success(f"  ✓ Образ импортирован: {target_tag}")
            
            # Пушим образ
            log_info(f"  Пуш в Harbor...")
            push_cmd = ['docker', 'push', target_tag]
            push_result = subprocess.run(push_cmd, capture_output=True, text=True, timeout=600)
            
            if push_result.returncode == 0:
                log_success(f"  ✓ Образ запушен: {target_tag}")
                return True, target_tag
            else:
                log_error(f"  ✗ Ошибка пуша: {push_result.stderr[:200]}")
                return False, push_result.stderr
                
        except Exception as e:
            return False, str(e)
    
    def process_all_images(self) -> List[Dict]:
        """Обрабатывает все tar файлы"""
        log_info(f"Поиск tar файлов в {self.images_dir}...")
        
        if not os.path.exists(self.images_dir):
            log_error(f"Директория не найдена: {self.images_dir}")
            return []
        
        tar_files = glob.glob(os.path.join(self.images_dir, "*.tar"))
        
        if not tar_files:
            log_error("Tar файлы не найдены")
            return []
        
        log_info(f"Найдено {len(tar_files)} архивов")
        
        results = []
        
        for idx, tar_file in enumerate(sorted(tar_files), 1):
            file_name = os.path.basename(tar_file)
            image_name = file_name.replace('.tar', '')
            file_size = os.path.getsize(tar_file) / (1024 * 1024)
            
            print(f"\n{'='*60}")
            log_info(f"[{idx}/{len(tar_files)}] {image_name} ({file_size:.1f} MB)")
            
            success, result = self.import_and_push_image(tar_file, image_name)
            
            results.append({
                'name': image_name,
                'size_mb': file_size,
                'success': success,
                'message': result
            })
        
        return results
    
    def create_bash_script(self, results: List[Dict]):
        """Создает bash скрипт для ручного выполнения"""
        script_file = os.path.join(self.base_dir, f"push-to-harbor-{self.version}.sh")
        
        with open(script_file, 'w') as f:
            f.write("#!/bin/bash\n\n")
            f.write(f"# Script to push Knative {self.version} images to Harbor\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("echo 'Login to Harbor...'\n")
            f.write(f"docker login {self.target_registry.split('/')[0]}\n\n")
            
            for img in results:
                if not img['success']:
                    f.write(f"echo 'Processing {img['name']}...'\n")
                    f.write(f"cat {self.images_dir}/{img['name']}.tar | docker import - {self.target_registry}/{img['name']}:{self.version}\n")
                    f.write(f"docker push {self.target_registry}/{img['name']}:{self.version}\n")
                    f.write(f"echo '  ✓ {img['name']} pushed'\n\n")
            
            f.write("echo 'All images processed!'\n")
        
        os.chmod(script_file, 0o755)
        if os.path.getsize(script_file) > 100:  # Если есть что писать
            log_success(f"Bash скрипт создан: {script_file}")
    
    def create_report(self, results: List[Dict]):
        """Создает отчет"""
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        
        report_file = os.path.join(self.base_dir, f"push-report-{self.version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
        
        with open(report_file, 'w') as f:
            f.write(f"# Harbor Push Report\n")
            f.write(f"# Version: {self.version}\n")
            f.write(f"# Target: {self.target_registry}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(results)}\n")
            f.write(f"# Success: {success_count}\n")
            f.write(f"# Failed: {failed_count}\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            f.write("## SUCCESSFUL PUSHES\n\n")
            for r in results:
                if r['success']:
                    f.write(f"✅ {r['name']}\n")
                    f.write(f"   Size: {r['size_mb']:.1f} MB\n")
                    f.write(f"   Target: {self.target_registry}/{r['name']}:{self.version}\n\n")
            
            if failed_count > 0:
                f.write("\n## FAILED PUSHES\n\n")
                for r in results:
                    if not r['success']:
                        f.write(f"❌ {r['name']}\n")
                        f.write(f"   Error: {r['message'][:200]}\n\n")
        
        log_success(f"Отчет сохранен: {report_file}")
        return success_count, failed_count
    
    def run(self):
        """Основной метод"""
        print("=" * 80)
        log_info(f"HARBOR IMAGE PUSHER - Knative {self.version}")
        print("=" * 80)
        log_info(f"Target Registry: {self.target_registry}")
        log_info(f"Images Directory: {self.images_dir}")
        print()
        
        # 1. Получаем учетные данные
        if not self.get_credentials():
            return False
        
        # 2. Обрабатываем образы
        results = self.process_all_images()
        
        if not results:
            log_error("Не найдено образов для обработки")
            return False
        
        # 3. Создаем отчет
        success, failed = self.create_report(results)
        
        # 4. Создаем bash скрипт для повторных попыток
        if failed > 0:
            self.create_bash_script(results)
        
        # 5. Статистика
        print("\n" + "=" * 80)
        log_info("СТАТИСТИКА")
        print("=" * 80)
        log_info(f"Всего образов: {len(results)}")
        log_info(f"Успешно: {success}")
        log_info(f"Ошибок: {failed}")
        
        total_size = sum(r['size_mb'] for r in results)
        log_info(f"Общий размер: {total_size:.2f} MB")
        
        if success == len(results):
            log_success("\n✅ Все образы успешно запушены в Harbor!")
        else:
            log_warning(f"\n⚠️ Не удалось запушнуть {failed} образов")
            log_info(f"\nДля повторной попытки выполните:")
            log_info(f"  ./push-to-harbor-{self.version}.sh")
        
        return success > 0

def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1.21.1"
    registry = sys.argv[2] if len(sys.argv) > 2 else "harbor.idp.ecpk.ru/core/knative"
    
    pusher = HarborImagePusher(version, registry)
    success = pusher.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()