import subprocess
import sys
import os
import json
import re
import yaml
import requests
from datetime import datetime
from typing import Dict, List, Set, Tuple
import glob

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

class KnativeImageManager:
    def __init__(self, version: str, registry: str = None, platform: str = 'linux/amd64', 
                 git_repo: str = None, git_branch: str = 'main'):
        self.version = version
        self.registry = registry or "harbor.idp.ecpk.ru/core/knative"
        self.platform = platform
        self.git_repo = git_repo or "https://github.com/scr112/my-eventing.git"
        self.git_branch = git_branch
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.manifests_dir = os.path.join(self.base_dir, f"manifests-{version}")
        self.images_dir = os.path.join(self.base_dir, f"knative-images-{version}")
        self.git_local_dir = os.path.join(self.base_dir, f"git-repo-{version.replace('v', '')}")
        
        self.found_images: Dict[str, List[str]] = {}
        self.downloaded_images: List[Dict] = []
        
        # Список репозиториев для скачивания манифестов
        self.repositories = [
            {
                'name': 'eventing',
                'url': f'https://api.github.com/repos/knative/eventing/releases/tags/knative-{version}',
            },
            {
                'name': 'eventing-kafka-broker',
                'url': f'https://api.github.com/repos/knative-extensions/eventing-kafka-broker/releases/tags/knative-{version}',
            }
        ]
        
        # Маппинг для преобразования путей в имена
        self.name_mapping = {
            'controller': 'eventing-controller',
            'webhook': 'eventing-webhook',
            'jobsink': 'job-sink',
            'mtping': 'pingsource-mt-adapter',
            'requestreply': 'request-reply',
            'channel_controller': 'imc-controller',
            'channel_dispatcher': 'imc-dispatcher',
            'mtchannel_broker': 'mt-broker-controller',
            'filter': 'mt-broker-filter',
            'ingress': 'mt-broker-ingress',
            'kafka-controller': 'kafka-controller',
            'webhook-kafka': 'kafka-webhook',
            'kafka-source-controller': 'kafka-source-controller',
            'post-install': 'post-install',
            'appender': 'appender',
            'event_display': 'event_display',
            'heartbeats': 'heartbeats',
            'knative-kafka-broker-dispatcher-loom': 'kafka-dispatcher',
            'knative-kafka-broker-receiver-loom': 'kafka-receiver',
        }
    
    def get_image_name(self, image: str) -> str:
        """Извлекает имя образа из digest или полного пути"""
        if '@' in image:
            image_without_digest = image.split('@')[0]
        else:
            image_without_digest = image
        
        parts = image_without_digest.split('/')
        last_part = parts[-1]
        
        # Прямое соответствие
        if last_part in self.name_mapping:
            return self.name_mapping[last_part]
        
        # Для длинных имен
        for key, value in self.name_mapping.items():
            if key in image_without_digest:
                return value
        
        if last_part == 'cmd' and len(parts) > 1:
            second_last = parts[-2]
            if second_last in self.name_mapping:
                return self.name_mapping[second_last]
        
        return last_part.replace('/', '-')
    
    def create_directories(self):
        """Создает необходимые директории"""
        os.makedirs(self.manifests_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        log_success("Директории созданы")
    
    def download_manifests_from_repo(self, repo_info: Dict) -> bool:
        """Скачивает манифесты из конкретного репозитория"""
        api_url = repo_info['url']
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "KnativeImageManager/1.0"
        }
        
        log_info(f"Загрузка из {repo_info['name']}...")
        
        try:
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                release_data = response.json()
                assets = release_data.get('assets', [])
                
                if not assets:
                    log_warning(f"Нет файлов в {repo_info['name']}")
                    return False
                
                downloaded_count = 0
                for asset in assets:
                    asset_name = asset['name']
                    
                    if not re.search(r'\.ya?ml$', asset_name):
                        continue
                    
                    target_path = os.path.join(self.manifests_dir, asset_name)
                    
                    if os.path.exists(target_path):
                        downloaded_count += 1
                        continue
                    
                    try:
                        file_response = requests.get(asset['browser_download_url'])
                        file_response.raise_for_status()
                        
                        with open(target_path, 'wb') as f:
                            f.write(file_response.content)
                        
                        log_success(f"  ✓ {asset_name}")
                        downloaded_count += 1
                    except Exception as e:
                        log_error(f"  ✗ {asset_name}: {e}")
                
                return downloaded_count > 0
            else:
                log_warning(f"Релиз не найден в {repo_info['name']}")
                return False
                
        except Exception as e:
            log_error(f"Ошибка: {e}")
            return False
    
    def download_all_manifests(self) -> bool:
        """Скачивает манифесты из всех репозиториев"""
        success_count = 0
        for repo in self.repositories:
            if self.download_manifests_from_repo(repo):
                success_count += 1
        return success_count > 0
    
    def extract_images_from_file(self, file_path: str) -> List[str]:
        """Извлекает все образы из файла"""
        images = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for line in content.split('\n'):
                if 'image:' in line:
                    match = re.search(r'image:\s*(.+)', line)
                    if match:
                        image = match.group(1).strip()
                        image = image.strip('"\'')
                        if image and not image.startswith('#'):
                            images.append(image)
                            
        except Exception as e:
            log_error(f"Ошибка при чтении {file_path}: {e}")
        
        return images
    
    def extract_all_images(self) -> Dict[str, List[str]]:
        """Извлекает все образы из скачанных манифестов"""
        log_info("Извлечение образов из манифестов...")
        
        if not os.path.exists(self.manifests_dir):
            log_error("Директория манифестов не существует")
            return {}
        
        all_files = [f for f in os.listdir(self.manifests_dir) 
                    if os.path.isfile(os.path.join(self.manifests_dir, f))]
        
        yaml_files = [f for f in all_files if re.search(r'\.ya?ml$', f)]
        
        if not yaml_files:
            log_warning("YAML файлы не найдены")
            return {}
        
        log_info(f"Найдено {len(yaml_files)} YAML файлов")
        
        for yaml_file in yaml_files:
            file_path = os.path.join(self.manifests_dir, yaml_file)
            images = self.extract_images_from_file(file_path)
            
            if images:
                self.found_images[yaml_file] = images
                log_success(f"  ✓ {yaml_file}: {len(images)} образов")
        
        unique_images = set()
        for images in self.found_images.values():
            unique_images.update(images)
        
        images_list_file = os.path.join(self.images_dir, f"images_list_{self.version}.txt")
        with open(images_list_file, 'w', encoding='utf-8') as f:
            for img in sorted(unique_images):
                f.write(f"{img}\n")
        
        log_success(f"Найдено {len(unique_images)} уникальных образов")
        return self.found_images
    
    def docker_pull(self, image: str) -> Tuple[bool, str]:
        """Загружает образ через docker pull"""
        try:
            cmd = ['docker', 'pull', '--platform', self.platform, image]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                cmd = ['docker', 'pull', image]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    return True, result.stdout
                else:
                    return False, result.stderr
                    
        except subprocess.TimeoutExpired:
            return False, "Timeout (600 seconds)"
        except Exception as e:
            return False, str(e)
    
    def docker_tag(self, source: str, target: str) -> bool:
        """Тегирует образ"""
        try:
            cmd = ['docker', 'tag', source, target]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            return False
    
    def docker_save(self, image: str, output_file: str) -> Tuple[bool, str]:
        """Сохраняет образ в tar архив"""
        try:
            cmd = ['docker', 'save', image, '-o', output_file]
            log_info(f"  Сохранение: {cmd}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True, ""
                else:
                    return False, "File is empty or does not exist"
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Timeout (300 seconds)"
        except Exception as e:
            return False, str(e)
    
    def save_image_with_fallback(self, name: str, image: str, local_tag: str) -> Tuple[bool, str, float, str]:
        """Сохраняет образ с fallback методами"""
        tar_file = os.path.join(self.images_dir, f"{name}.tar")
        
        # Удаляем старый файл если существует
        if os.path.exists(tar_file):
            os.remove(tar_file)
        
        # Метод 1: сохраняем по оригинальному digest
        log_info(f"  Метод 1: docker save {image[:80]}...")
        ok, error = self.docker_save(image, tar_file)
        
        if ok and os.path.exists(tar_file):
            size = os.path.getsize(tar_file) / (1024 * 1024)
            log_success(f"  ✓ Сохранен ({size:.1f} MB)")
            return True, tar_file, size, 'docker save (digest)'
        
        # Метод 2: сохраняем по локальному тегу
        log_info(f"  Метод 2: docker save {local_tag}")
        ok, error = self.docker_save(local_tag, tar_file)
        
        if ok and os.path.exists(tar_file):
            size = os.path.getsize(tar_file) / (1024 * 1024)
            log_success(f"  ✓ Сохранен ({size:.1f} MB)")
            return True, tar_file, size, 'docker save (tag)'
        
        # Метод 3: используем docker export через контейнер
        log_info(f"  Метод 3: docker export")
        container_name = f"temp-{name}-{os.urandom(4).hex()}"
        try:
            # Создаем контейнер
            subprocess.run(['docker', 'create', '--name', container_name, local_tag], 
                          capture_output=True, text=True, check=True)
            
            # Экспортируем
            result = subprocess.run(['docker', 'export', container_name, '-o', tar_file],
                                  capture_output=True, text=True, timeout=300)
            
            # Удаляем контейнер
            subprocess.run(['docker', 'rm', container_name], capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(tar_file):
                size = os.path.getsize(tar_file) / (1024 * 1024)
                log_success(f"  ✓ Сохранен через export ({size:.1f} MB)")
                return True, tar_file, size, 'docker export'
            else:
                log_error(f"  Export failed: {result.stderr}")
                return False, None, 0, result.stderr
                
        except Exception as e:
            log_error(f"  Export error: {e}")
            return False, None, 0, str(e)
    
    def process_image(self, original_image: str, index: int, total: int) -> Dict:
        """Обрабатывает один образ"""
        result = {
            'name': '',
            'original_image': original_image,
            'status': 'failed',
            'error': None
        }
        
        print(f"\n{'='*60}")
        log_info(f"[{index}/{total}] Обработка образа")
        
        image_name = self.get_image_name(original_image)
        result['name'] = image_name
        
        local_tag = f"{image_name}:{self.version}"
        registry_tag = f"{self.registry}/{image_name}:{self.version}"
        
        log_info(f"Имя: {image_name}")
        log_info(f"Тег: {local_tag}")
        
        # Загрузка образа
        ok, output = self.docker_pull(original_image)
        
        if not ok:
            log_error(f"✗ Ошибка загрузки: {output[:200]}")
            result['error'] = f"Pull failed: {output[:200]}"
            return result
        
        log_success("Образ загружен")
        
        # Тегирование
        if self.docker_tag(original_image, local_tag):
            log_success(f"Создан тег: {local_tag}")
        else:
            log_warning(f"Не удалось создать тег: {local_tag}")
        
        if self.docker_tag(original_image, registry_tag):
            log_success(f"Создан registry тег: {registry_tag}")
        else:
            log_warning(f"Не удалось создать registry тег: {registry_tag}")
        
        result['local_tag'] = local_tag
        result['registry_tag'] = registry_tag
        
        # Сохранение
        saved, tar_file, size_mb, method = self.save_image_with_fallback(image_name, original_image, local_tag)
        
        if saved:
            result.update({
                'status': 'success',
                'method': method,
                'tar_file': tar_file,
                'size_mb': size_mb
            })
            log_success(f"✓ {image_name} успешно сохранен ({size_mb:.1f} MB)")
        else:
            result['error'] = 'All save methods failed'
            log_error(f"✗ Не удалось сохранить {image_name}")
        
        return result
    
    def download_and_save_images(self):
        """Скачивает и сохраняет все найденные образы"""
        if not self.found_images:
            log_error("Нет образов для обработки")
            return 0, 0
        
        unique_images = set()
        for images in self.found_images.values():
            unique_images.update(images)
        
        total_images = len(unique_images)
        log_info(f"Всего уникальных образов: {total_images}")
        
        success_count = 0
        failed_count = 0
        
        for idx, image in enumerate(sorted(unique_images), 1):
            result = self.process_image(image, idx, total_images)
            
            if result['status'] == 'success':
                success_count += 1
                self.downloaded_images.append(result)
            else:
                failed_count += 1
        
        return success_count, failed_count
    
    def setup_git_lfs(self):
        """Настраивает Git LFS"""
        log_info("Настройка Git LFS...")
        
        try:
            subprocess.run(['git-lfs', '--version'], capture_output=True, check=True)
        except:
            log_error("Git LFS не установлен")
            return False
        
        if os.path.exists(self.git_local_dir):
            os.chdir(self.git_local_dir)
            subprocess.run(['git', 'pull', 'origin', self.git_branch], capture_output=True)
        else:
            subprocess.run(['git', 'clone', '--branch', self.git_branch, self.git_repo, self.git_local_dir], 
                          capture_output=True, check=True)
            os.chdir(self.git_local_dir)
        
        subprocess.run(['git', 'lfs', 'install'], capture_output=True)
        
        with open('.gitattributes', 'w') as f:
            f.write("*.tar filter=lfs diff=lfs merge=lfs -text\n")
        
        subprocess.run(['git', 'add', '.gitattributes'], capture_output=True)
        
        log_success("Git LFS настроен")
        return True
    
    def copy_and_push_to_git(self):
        """Копирует файлы в git и пушит"""
        log_info("Копирование в Git репозиторий...")
        
        # Копируем манифесты
        manifests_target = os.path.join(self.git_local_dir, f"manifests-{self.version}")
        os.makedirs(manifests_target, exist_ok=True)
        
        for file in glob.glob(os.path.join(self.manifests_dir, '*.yaml')):
            if os.path.isfile(file):
                dest = os.path.join(manifests_target, os.path.basename(file))
                subprocess.run(['cp', file, dest], capture_output=True)
        
        # Копируем образы
        images_target = os.path.join(self.git_local_dir, f"images-{self.version}")
        os.makedirs(images_target, exist_ok=True)
        
        large_files = []
        for img in self.downloaded_images:
            tar_file = img['tar_file']
            dest = os.path.join(images_target, os.path.basename(tar_file))
            subprocess.run(['cp', tar_file, dest], capture_output=True)
            
            if img['size_mb'] > 50:
                large_files.append(img['name'])
        
        # Создаем README
        readme_file = os.path.join(self.git_local_dir, f"README-{self.version}.md")
        with open(readme_file, 'w') as f:
            f.write(f"# Knative Images {self.version}\n\n")
            f.write(f"## Images\n\n")
            for img in self.downloaded_images:
                f.write(f"- {img['name']}: {img['size_mb']:.1f} MB\n")
        
        os.chdir(self.git_local_dir)
        
        # Добавляем и пушим
        subprocess.run(['git', 'add', '.'], capture_output=True)
        subprocess.run(['git', 'commit', '-m', f"Add Knative {self.version} images"], capture_output=True)
        
        log_info("Пуш в репозиторий...")
        result = subprocess.run(['git', 'push', 'origin', self.git_branch], capture_output=True, text=True)
        
        if result.returncode == 0:
            log_success(f"✅ Успешно запушено")
            return True
        else:
            log_error(f"Ошибка пуша: {result.stderr}")
            return False
    
    def create_metadata(self, success_count: int, failed_count: int):
        """Создает метаданные"""
        metadata_file = os.path.join(self.images_dir, f'metadata_{self.version}.json')
        upload_data = {
            'version': self.version,
            'registry': self.registry,
            'success_count': success_count,
            'failed_count': failed_count,
            'images': []
        }
        
        for r in self.downloaded_images:
            upload_data['images'].append({
                'name': r['name'],
                'original_image': r['original_image'],
                'local_tag': r['local_tag'],
                'registry_tag': r['registry_tag'],
                'tar_file': os.path.basename(r['tar_file']),
                'size_mb': r['size_mb']
            })
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(upload_data, f, indent=2, ensure_ascii=False)
        
        return metadata_file
    
    def run(self):
        """Основной метод"""
        print("=" * 80)
        log_info(f"KNATIVE IMAGE MANAGER v{self.version}")
        print("=" * 80)
        
        self.create_directories()
        self.download_all_manifests()
        self.extract_all_images()
        
        if not self.found_images:
            log_error("Не удалось извлечь образы")
            return False
        
        success, failed = self.download_and_save_images()
        
        if success == 0:
            log_error("Не удалось загрузить ни одного образа")
            return False
        
        self.create_metadata(success, failed)
        
        if self.setup_git_lfs():
            self.copy_and_push_to_git()
        
        print("\n" + "=" * 80)
        log_info("СТАТИСТИКА")
        print("=" * 80)
        log_info(f"Успешно: {success}")
        log_info(f"Ошибок: {failed}")
        
        total_size = sum(r.get('size_mb', 0) for r in self.downloaded_images)
        log_info(f"Общий размер: {total_size:.2f} MB")
        
        return True

def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1.21.1"
    registry = sys.argv[2] if len(sys.argv) > 2 else "harbor.idp.ecpk.ru/core/knative"
    git_repo = sys.argv[3] if len(sys.argv) > 3 else "https://github.com/scr112/my-eventing.git"
    git_branch = sys.argv[4] if len(sys.argv) > 4 else "main"
    
    manager = KnativeImageManager(version, registry, 'linux/amd64', git_repo, git_branch)
    success = manager.run()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()