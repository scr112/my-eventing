#!/usr/bin/env python3

import subprocess
import sys
import os
import json
import glob
from datetime import datetime
from typing import Dict, List, Tuple

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
        self.target_registry = target_registry or "harbor.idp.ecpk.ru/core/knative"
        self.git_repo = git_repo or "https://github.com/scr112/my-eventing.git"
        self.git_branch = git_branch
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.git_local_dir = os.path.join(self.base_dir, f"git-repo-{version.replace('v', '')}")
        self.images_dir = os.path.join(self.git_local_dir, f"images-{version}")
        self.manifests_dir = os.path.join(self.git_local_dir, f"manifests-{version}")
        
        self.harbor_user = None
        self.harbor_password = None
        
    def get_credentials(self):
        """Запрашивает учетные данные для Harbor"""
        print("\n" + "=" * 60)
        log_info("АВТОРИЗАЦИЯ В HARBOR REGISTRY")
        print("=" * 60)
        
        # Проверяем переменные окружения
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
    
    def clone_repository(self) -> bool:
        """Клонирует репозиторий с образами"""
        log_info(f"Клонирование репозитория {self.git_repo}...")
        
        # Удаляем старую директорию если есть
        if os.path.exists(self.git_local_dir):
            import shutil
            shutil.rmtree(self.git_local_dir)
        
        try:
            cmd = ['git', 'clone', '--branch', self.git_branch, self.git_repo, self.git_local_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                log_success(f"✓ Репозиторий склонирован")
                return True
            else:
                log_error(f"✗ Ошибка клонирования: {result.stderr}")
                return False
        except Exception as e:
            log_error(f"Ошибка: {e}")
            return False
    
    def pull_lfs_files(self) -> bool:
        """Скачивает LFS файлы"""
        log_info("Скачивание LFS файлов...")
        
        os.chdir(self.git_local_dir)
        
        try:
            # Устанавливаем LFS если нужно
            subprocess.run(['git', 'lfs', 'install'], capture_output=True)
            
            # Скачиваем LFS файлы
            result = subprocess.run(['git', 'lfs', 'pull'], capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                log_success("✓ LFS файлы скачаны")
                return True
            else:
                log_error(f"✗ Ошибка LFS pull: {result.stderr}")
                return False
        except Exception as e:
            log_error(f"Ошибка: {e}")
            return False
    
    def load_docker_images(self) -> List[Dict]:
        """Загружает Docker образы из tar файлов"""
        log_info("Загрузка Docker образов из архивов...")
        
        if not os.path.exists(self.images_dir):
            log_error(f"Директория с образами не найдена: {self.images_dir}")
            return []
        
        tar_files = glob.glob(os.path.join(self.images_dir, "*.tar"))
        
        if not tar_files:
            log_error("Tar файлы не найдены")
            return []
        
        log_info(f"Найдено {len(tar_files)} архивов")
        
        loaded_images = []
        
        for tar_file in tar_files:
            image_name = os.path.basename(tar_file).replace('.tar', '')
            log_info(f"Загрузка {image_name}...")
            
            try:
                cmd = ['docker', 'load', '-i', tar_file]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # Извлекаем имя загруженного образа
                    loaded_image = None
                    for line in result.stdout.split('\n'):
                        if 'Loaded image:' in line:
                            loaded_image = line.split('Loaded image:')[1].strip()
                            break
                    
                    log_success(f"  ✓ Загружен: {loaded_image or image_name}")
                    loaded_images.append({
                        'name': image_name,
                        'tar_file': tar_file,
                        'loaded_image': loaded_image
                    })
                else:
                    log_error(f"  ✗ Ошибка загрузки: {result.stderr}")
                    
            except Exception as e:
                log_error(f"  ✗ Ошибка: {e}")
        
        return loaded_images
    
    def get_registry_tag(self, image_name: str) -> str:
        """Формирует тег для Harbor"""
        # Убираем суффиксы если есть
        clean_name = image_name.replace('-v1', '').replace('-v', '')
        return f"{self.target_registry}/{clean_name}:{self.version}"
    
    def tag_and_push_images(self, loaded_images: List[Dict]) -> Tuple[int, int]:
        """Тегирует и пушит образы в Harbor"""
        log_info("Тегирование и пуш образов в Harbor...")
        
        success_count = 0
        failed_count = 0
        
        for idx, img in enumerate(loaded_images, 1):
            print(f"\n{'='*60}")
            log_info(f"[{idx}/{len(loaded_images)}] Обработка: {img['name']}")
            
            # Определяем source image
            source_image = img['loaded_image'] if img['loaded_image'] else img['name']
            
            # Формируем target тег
            target_tag = self.get_registry_tag(img['name'])
            log_info(f"Target: {target_tag}")
            
            # Тегируем
            log_info("Тегирование...")
            tag_cmd = ['docker', 'tag', source_image, target_tag]
            tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
            
            if tag_result.returncode != 0:
                log_error(f"  ✗ Ошибка тегирования: {tag_result.stderr}")
                failed_count += 1
                continue
            
            log_success("  ✓ Образ перетегирован")
            
            # Пушим в Harbor
            log_info("Пуш в Harbor...")
            push_cmd = ['docker', 'push', target_tag]
            push_result = subprocess.run(push_cmd, capture_output=True, text=True, timeout=600)
            
            if push_result.returncode == 0:
                log_success(f"  ✓ Успешно запушен: {target_tag}")
                success_count += 1
            else:
                log_error(f"  ✗ Ошибка пуша: {push_result.stderr[:200]}")
                failed_count += 1
        
        return success_count, failed_count
    
    def create_deployment_script(self):
        """Создает скрипт для развертывания"""
        script_file = os.path.join(self.base_dir, f"deploy-knative-{self.version}.sh")
        
        with open(script_file, 'w') as f:
            f.write("#!/bin/bash\n\n")
            f.write(f"# Deploy Knative {self.version}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write('set -e\n\n')
            
            # Применяем манифесты
            f.write("# Apply Knative manifests\n")
            if os.path.exists(self.manifests_dir):
                for manifest in sorted(glob.glob(os.path.join(self.manifests_dir, "*.yaml"))):
                    manifest_name = os.path.basename(manifest)
                    f.write(f"kubectl apply -f {self.manifests_dir}/{manifest_name}\n")
            
            f.write('\necho "Knative deployed successfully!"\n')
        
        os.chmod(script_file, 0o755)
        log_success(f"Скрипт развертывания создан: {script_file}")
        
        return script_file
    
    def create_report(self, success_count: int, failed_count: int, loaded_images: List[Dict]):
        """Создает отчет о загрузке"""
        report_file = os.path.join(self.base_dir, f"harbor-upload-report-{self.version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
        
        with open(report_file, 'w') as f:
            f.write(f"# Harbor Upload Report\n")
            f.write(f"# Version: {self.version}\n")
            f.write(f"# Target Registry: {self.target_registry}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total images: {len(loaded_images)}\n")
            f.write(f"# Successful: {success_count}\n")
            f.write(f"# Failed: {failed_count}\n")
            f.write("\n" + "=" * 80 + "\n\n")
            
            f.write("## IMAGES PUSHED TO HARBOR\n\n")
            for img in loaded_images:
                target_tag = self.get_registry_tag(img['name'])
                f.write(f"✅ {img['name']}\n")
                f.write(f"   Source: {img['loaded_image']}\n")
                f.write(f"   Target: {target_tag}\n\n")
        
        log_success(f"Отчет сохранен: {report_file}")
    
    def run(self):
        """Основной метод"""
        print("=" * 80)
        log_info(f"HARBOR IMAGE PUSHER - Knative {self.version}")
        print("=" * 80)
        log_info(f"Target Registry: {self.target_registry}")
        log_info(f"Git Repo: {self.git_repo}")
        log_info(f"Branch: {self.git_branch}")
        print()
        
        # 1. Получаем учетные данные
        if not self.get_credentials():
            return False
        
        # 2. Клонируем репозиторий
        if not self.clone_repository():
            return False
        
        # 3. Скачиваем LFS файлы
        if not self.pull_lfs_files():
            log_warning("Продолжаем без LFS файлов...")
        
        # 4. Загружаем Docker образы
        loaded_images = self.load_docker_images()
        
        if not loaded_images:
            log_error("Не удалось загрузить ни одного образа")
            return False
        
        # 5. Логин в Harbor
        if not self.docker_login():
            return False
        
        # 6. Тегируем и пушим образы
        success, failed = self.tag_and_push_images(loaded_images)
        
        # 7. Создаем отчет
        self.create_report(success, failed, loaded_images)
        
        # 8. Создаем скрипт развертывания
        self.create_deployment_script()
        
        # 9. Статистика
        print("\n" + "=" * 80)
        log_info("СТАТИСТИКА")
        print("=" * 80)
        log_info(f"Всего образов: {len(loaded_images)}")
        log_info(f"Успешно запушено: {success}")
        log_info(f"Ошибок: {failed}")
        
        if success == len(loaded_images):
            log_success("✅ Все образы успешно запушены в Harbor!")
        else:
            log_warning(f"⚠️ Не удалось запушнуть {failed} образов")
        
        return success > 0

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Push Knative images to Harbor')
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
