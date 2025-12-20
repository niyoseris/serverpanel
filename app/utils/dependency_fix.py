"""
Auto-fix missing dependencies from import errors
"""
import re
import subprocess
import os

# Common package name mappings (import name -> pip package name)
PACKAGE_MAPPINGS = {
    'flask_sqlalchemy': 'flask-sqlalchemy',
    'flask_login': 'flask-login',
    'flask_cors': 'flask-cors',
    'flask_migrate': 'flask-migrate',
    'flask_wtf': 'flask-wtf',
    'werkzeug': 'werkzeug',
    'sqlalchemy': 'sqlalchemy',
    'bs4': 'beautifulsoup4',
    'PIL': 'pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'yaml': 'pyyaml',
    'dotenv': 'python-dotenv',
    'jwt': 'pyjwt',
    'redis': 'redis',
    'celery': 'celery',
    'selenium': 'selenium',
    'pymongo': 'pymongo',
    'psycopg2': 'psycopg2-binary',
    'MySQLdb': 'mysqlclient',
    'fake_useragent': 'fake-useragent',
    'requests': 'requests',
    'urllib3': 'urllib3',
    'lxml': 'lxml',
}

def extract_missing_modules(error_log_content):
    """
    Extracts missing module names from error log.
    Returns list of module names.
    """
    missing_modules = []
    
    # Pattern: ModuleNotFoundError: No module named 'xxx'
    pattern = r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
    matches = re.findall(pattern, error_log_content)
    if not matches:
        pattern_unquoted = r"ModuleNotFoundError: No module named ([^\s]+)"
        matches = re.findall(pattern_unquoted, error_log_content)
    
    for match in matches:
        # Get the top-level module name
        module = match.split('.')[0]
        if module not in missing_modules:
            missing_modules.append(module)
    
    # Also check for ImportError
    pattern2 = r"ImportError: cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]"
    matches2 = re.findall(pattern2, error_log_content)
    
    for name, module in matches2:
        module_name = module.split('.')[0]
        if module_name not in missing_modules:
            missing_modules.append(module_name)
    
    return missing_modules

def infer_venv_path_from_log(project_path, log_content):
    venv_names = r"(?:venv|\.venv|env)"
    patterns = [
        rf"(/[^\s]+?/{venv_names})/lib/python[0-9.]+/site-packages/",
        rf"(/[^\s]+?/{venv_names})/lib/python[0-9.]+/",
        rf"(/[^\s]+?/{venv_names})/bin/python",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, log_content)
        for match in matches:
            candidate = match.rstrip('/')
            if os.path.exists(os.path.join(candidate, 'bin', 'pip')):
                return candidate

    venv_candidates = ['venv', '.venv', 'env']
    for candidate in venv_candidates:
        candidate_path = os.path.join(project_path, candidate)
        if os.path.exists(os.path.join(candidate_path, 'bin', 'pip')):
            return candidate_path

    return None

def is_local_module(project_path, module_name):
    if not module_name:
        return False
    if os.path.exists(os.path.join(project_path, f"{module_name}.py")):
        return True
    if os.path.isdir(os.path.join(project_path, module_name)):
        return True
    return False

def install_requirements_if_present(venv_pip, project_path):
    requirements_file = os.path.join(project_path, 'requirements.txt')
    if not os.path.exists(requirements_file):
        return True, "requirements.txt not present"

    try:
        result = subprocess.run(
            [venv_pip, 'install', '-r', 'requirements.txt'],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return True, "requirements.txt installed"
        return False, result.stderr or result.stdout or "pip install -r requirements.txt failed"
    except Exception as e:
        return False, str(e)

def get_pip_package_name(module_name):
    """
    Converts Python module name to pip package name.
    """
    # Check if we have a known mapping
    if module_name in PACKAGE_MAPPINGS:
        return PACKAGE_MAPPINGS[module_name]
    
    # Otherwise, assume pip package name is same as module name
    # but with underscores replaced by hyphens
    return module_name.replace('_', '-')

def install_missing_packages(venv_path, missing_modules):
    """
    Installs missing packages using pip.
    Returns (success, message, installed_packages)
    """
    if not missing_modules:
        return True, "No missing modules detected", []
    
    print(f"[DEPENDENCY-FIX] Found {len(missing_modules)} missing modules: {missing_modules}")
    
    # Get pip executable
    venv_pip = os.path.join(venv_path, 'bin', 'pip')
    if not os.path.exists(venv_pip):
        return False, f"pip not found at {venv_pip}", []
    
    installed = []
    failed = []
    skipped = []
    
    for module in missing_modules:
        if is_local_module(os.path.dirname(venv_path), module) or is_local_module(os.path.dirname(os.path.dirname(venv_path)), module):
            skipped.append(module)
            continue
        package_name = get_pip_package_name(module)
        print(f"[DEPENDENCY-FIX] Installing {package_name} (for module '{module}')...")
        
        try:
            result = subprocess.run(
                [venv_pip, 'install', package_name],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # Verify installation
                verify_result = subprocess.run(
                    [venv_pip, 'show', package_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if verify_result.returncode == 0:
                    print(f"[DEPENDENCY-FIX] ✓ Installed and verified {package_name}")
                    installed.append(package_name)
                else:
                    print(f"[DEPENDENCY-FIX] ⚠ Installed {package_name} but verification failed")
                    installed.append(package_name)  # Still count it as installed
            else:
                print(f"[DEPENDENCY-FIX] ✗ Failed to install {package_name}")
                print(f"[DEPENDENCY-FIX]   stdout: {result.stdout}")
                print(f"[DEPENDENCY-FIX]   stderr: {result.stderr}")
                failed.append(package_name)
        
        except subprocess.TimeoutExpired:
            print(f"[DEPENDENCY-FIX] ✗ Timeout installing {package_name}")
            failed.append(package_name)
        except Exception as e:
            print(f"[DEPENDENCY-FIX] ✗ Error installing {package_name}: {e}")
            failed.append(package_name)
    
    if skipped:
        print(f"[DEPENDENCY-FIX] Skipped local modules (not pip-installable): {skipped}")

    if failed:
        return False, f"Installed {len(installed)} packages, {len(failed)} failed: {failed}", installed
    return True, f"Successfully installed {len(installed)} packages: {installed}", installed

def auto_fix_dependencies(project_path, error_log_path):
    """
    Main function to auto-fix missing dependencies.
    Returns (success, message, installed_packages)
    """
    print(f"[DEPENDENCY-FIX] === Starting dependency auto-fix ===")
    
    # Read error log
    if not os.path.exists(error_log_path):
        return False, "Error log not found", []
    
    try:
        with open(error_log_path, 'r') as f:
            log_content = f.read()
    except Exception as e:
        return False, f"Could not read error log: {e}", []
    
    # Extract missing modules
    missing_modules = extract_missing_modules(log_content)
    
    if not missing_modules:
        return False, "No missing modules detected in error log", []
    
    print(f"[DEPENDENCY-FIX] Detected missing modules: {missing_modules}")
    
    venv_path = infer_venv_path_from_log(project_path, log_content)
    
    if not venv_path:
        return False, "Virtual environment not found", []
    
    print(f"[DEPENDENCY-FIX] Using venv: {venv_path}")

    venv_pip = os.path.join(venv_path, 'bin', 'pip')
    req_ok, req_msg = install_requirements_if_present(venv_pip, project_path)
    if not req_ok:
        print(f"[DEPENDENCY-FIX] requirements.txt install failed: {req_msg}")
    
    # Install missing packages
    success, message, installed = install_missing_packages(venv_path, missing_modules)

    if req_msg:
        message = f"{req_msg}; {message}"
    
    if success:
        print(f"[DEPENDENCY-FIX] ✓ Auto-fix complete!")
    else:
        print(f"[DEPENDENCY-FIX] ✗ Auto-fix partial or failed")
    
    return success, message, installed
