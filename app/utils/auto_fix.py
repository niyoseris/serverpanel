"""
Auto-fix utilities for self-healing project startup issues
"""
import os
import subprocess
import time

def detect_entry_point_error(log_content):
    """
    Detects if the error is related to entry point module not found.
    Returns True if entry point error detected.
    """
    error_patterns = [
        "ModuleNotFoundError: No module named",
        "ImportError: cannot import name",
        "No module named 'app'",
        "No module named 'run'",
        "cannot import name 'app'",
        "Worker failed to boot"
    ]
    
    for pattern in error_patterns:
        if pattern in log_content:
            return True
    return False

def scan_python_files_for_flask_app(project_path):
    """
    Scans all Python files in project to find Flask app instances.
    Returns list of (module_path, variable_name) tuples.
    """
    flask_apps = []
    
    try:
        # Walk through all Python files
        for root, dirs, files in os.walk(project_path):
            # Skip venv and common ignore dirs
            dirs[:] = [d for d in dirs if d not in ['venv', '.venv', 'env', '__pycache__', '.git', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            # Look for Flask app creation patterns
                            patterns = [
                                r'(\w+)\s*=\s*Flask\(',  # app = Flask(...)
                                r'(\w+)\s*=\s*create_app\(',  # app = create_app()
                                r'def\s+create_app\(',  # def create_app():
                                r'application\s*=\s*Flask\(',  # application = Flask(...)
                            ]
                            
                            for pattern in patterns:
                                import re
                                matches = re.findall(pattern, content)
                                if matches:
                                    # Get relative module path
                                    rel_path = os.path.relpath(file_path, project_path)
                                    module_path = rel_path.replace('.py', '').replace(os.sep, '.')
                                    
                                    if 'create_app' in content:
                                        flask_apps.append((module_path, 'create_app()'))
                                    
                                    for match in matches:
                                        if match:
                                            flask_apps.append((module_path, match))
                            
                    except Exception as e:
                        print(f"[AUTO-FIX] Could not read {file_path}: {e}")
                        continue
    
    except Exception as e:
        print(f"[AUTO-FIX] Error scanning project: {e}")
    
    return flask_apps

def get_all_possible_entry_points(project_path, project_type):
    """
    Returns a list of all possible entry points to try.
    Intelligently scans project structure and content.
    """
    entry_points = []
    
    print(f"[AUTO-FIX] Scanning project structure...")
    
    # First, scan for actual Flask apps in the code
    flask_apps = scan_python_files_for_flask_app(project_path)
    if flask_apps:
        print(f"[AUTO-FIX] Found {len(flask_apps)} Flask app instances in code")
        for module_path, var_name in flask_apps:
            entry_point = f"{module_path}:{var_name}"
            entry_points.append(entry_point)
            print(f"[AUTO-FIX]   - {entry_point}")
    
    # Check for common Python files in root
    common_files = ['app.py', 'run.py', 'wsgi.py', 'application.py', 'main.py', 'server.py', 'manage.py']
    common_callables = ['app', 'application', 'create_app()', 'main', 'server']
    
    # Find existing Python files in root
    existing_files = []
    try:
        for file in common_files:
            file_path = os.path.join(project_path, file)
            if os.path.exists(file_path):
                module_name = file.replace('.py', '')
                existing_files.append(module_name)
                print(f"[AUTO-FIX] Found root file: {file}")
    except Exception as e:
        print(f"[AUTO-FIX] Error scanning files: {e}")
    
    # Generate entry points for existing files
    for module in existing_files:
        for callable_name in common_callables:
            entry_point = f"{module}:{callable_name}"
            if entry_point not in entry_points:
                entry_points.append(entry_point)
    
    # Django specific
    if project_type == 'django':
        print(f"[AUTO-FIX] Scanning for Django structure...")
        try:
            for item in os.listdir(project_path):
                item_path = os.path.join(project_path, item)
                if os.path.isdir(item_path) and not item.startswith('.') and item not in ['venv', 'env', '__pycache__']:
                    wsgi_path = os.path.join(item_path, 'wsgi.py')
                    if os.path.exists(wsgi_path):
                        entry_points.insert(0, f"{item}.wsgi:application")
                        print(f"[AUTO-FIX] Found Django wsgi: {item}.wsgi:application")
        except:
            pass
    
    # Add some defaults at the end as fallback
    defaults = ['app:app', 'run:app', 'wsgi:application', 'application:app', 'main:app']
    for default in defaults:
        if default not in entry_points:
            entry_points.append(default)
    
    print(f"[AUTO-FIX] Total entry points to test: {len(entry_points)}")
    return entry_points

def test_entry_point(project_path, entry_point, port, venv_python):
    """
    Tests if an entry point works by trying to start gunicorn briefly.
    Returns True if successful, False otherwise.
    """
    print(f"[AUTO-FIX] Testing entry point: {entry_point}")
    
    gunicorn_path = os.path.join(os.path.dirname(venv_python), 'gunicorn')
    
    if not os.path.exists(gunicorn_path):
        print(f"[AUTO-FIX] Gunicorn not found: {gunicorn_path}")
        return False
    
    # Try to start gunicorn with this entry point
    # Use --check-config to validate without actually starting
    command = [
        gunicorn_path,
        '--bind', f'127.0.0.1:{port}',
        '--workers', '1',
        '--timeout', '5',
        entry_point
    ]
    
    try:
        # Start the process
        process = subprocess.Popen(
            command,
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit to see if it starts successfully
        time.sleep(2)
        
        # Check if process is still running
        poll_result = process.poll()
        
        if poll_result is None:
            # Process is running! Kill it and return success
            process.terminate()
            try:
                process.wait(timeout=2)
            except:
                process.kill()
            print(f"[AUTO-FIX] ✓ Entry point works: {entry_point}")
            return True
        else:
            # Process died, check stderr for specific errors
            stderr = process.stderr.read()
            if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
                print(f"[AUTO-FIX] ✗ Entry point failed (import error): {entry_point}")
            else:
                print(f"[AUTO-FIX] ✗ Entry point failed (exit code {poll_result}): {entry_point}")
            return False
            
    except Exception as e:
        print(f"[AUTO-FIX] ✗ Error testing entry point {entry_point}: {e}")
        return False

def auto_fix_entry_point(project_name, project_path, project_type, port, venv_python):
    """
    Automatically detects and fixes entry point issues.
    Returns (success, new_entry_point, message)
    """
    print(f"[AUTO-FIX] === Starting entry point auto-fix for {project_name} ===")
    
    # Get all possible entry points
    possible_entry_points = get_all_possible_entry_points(project_path, project_type)
    
    print(f"[AUTO-FIX] Found {len(possible_entry_points)} possible entry points to test")
    
    # Test each entry point
    for i, entry_point in enumerate(possible_entry_points, 1):
        print(f"[AUTO-FIX] Testing {i}/{len(possible_entry_points)}: {entry_point}")
        
        if test_entry_point(project_path, entry_point, port, venv_python):
            print(f"[AUTO-FIX] ✓✓✓ Found working entry point: {entry_point}")
            return True, entry_point, f"Auto-fixed: Found working entry point '{entry_point}'"
        
        # Small delay between tests
        time.sleep(0.5)
    
    # No working entry point found
    print(f"[AUTO-FIX] ✗ No working entry point found")
    return False, None, "Could not find a working entry point. Please check your application structure."

def should_attempt_auto_fix(error_log_path):
    """
    Checks if we should attempt auto-fix based on error log content.
    """
    if not os.path.exists(error_log_path):
        return False
    
    try:
        with open(error_log_path, 'r') as f:
            content = f.read()
            return detect_entry_point_error(content)
    except:
        return False
