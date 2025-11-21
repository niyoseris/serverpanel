"""
Auto-generate requirements.txt by analyzing Python imports
"""
import os
import re
import ast

# Common import to package mappings
IMPORT_TO_PACKAGE = {
    'flask': 'Flask',
    'flask_sqlalchemy': 'Flask-SQLAlchemy',
    'flask_login': 'Flask-Login',
    'flask_cors': 'Flask-CORS',
    'flask_migrate': 'Flask-Migrate',
    'flask_wtf': 'Flask-WTF',
    'bs4': 'beautifulsoup4',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'jwt': 'PyJWT',
    'fake_useragent': 'fake-useragent',
    'requests': 'requests',
    'lxml': 'lxml',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'sqlalchemy': 'SQLAlchemy',
    'werkzeug': 'Werkzeug',
    'jinja2': 'Jinja2',
    'click': 'click',
    'itsdangerous': 'itsdangerous',
    'celery': 'celery',
    'redis': 'redis',
    'pymongo': 'pymongo',
    'psycopg2': 'psycopg2-binary',
    'MySQLdb': 'mysqlclient',
    'selenium': 'selenium',
    'scrapy': 'scrapy',
}

def extract_imports_from_file(filepath):
    """
    Extract all import statements from a Python file.
    Returns set of module names.
    """
    imports = set()
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse with AST
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        imports.add(module)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        imports.add(module)
        except SyntaxError:
            # Fallback to regex if AST fails
            pass
        
        # Also use regex as fallback/supplement
        import_patterns = [
            r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.update(matches)
    
    except Exception as e:
        print(f"[REQUIREMENTS] Error reading {filepath}: {e}")
    
    return imports

def get_local_packages(project_path):
    """
    Get list of local packages (folders with __init__.py) in project.
    These should be excluded from requirements.txt
    """
    local_packages = set()
    
    try:
        for item in os.listdir(project_path):
            item_path = os.path.join(project_path, item)
            if os.path.isdir(item_path) and item not in ['venv', '.venv', 'env', '__pycache__', '.git']:
                init_file = os.path.join(item_path, '__init__.py')
                if os.path.exists(init_file):
                    # This is a local package
                    local_packages.add(item)
    except Exception as e:
        print(f"[REQUIREMENTS] Error detecting local packages: {e}")
    
    return local_packages

def scan_project_imports(project_path):
    """
    Recursively scan all Python files in project and extract imports.
    Returns set of all imported modules.
    """
    all_imports = set()
    
    for root, dirs, files in os.walk(project_path):
        # Skip venv, __pycache__, etc.
        dirs[:] = [d for d in dirs if d not in ['venv', '.venv', 'env', '__pycache__', '.git', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                imports = extract_imports_from_file(filepath)
                all_imports.update(imports)
    
    return all_imports

def filter_standard_library(imports):
    """
    Filter out Python standard library modules.
    Returns only third-party packages.
    """
    # Common stdlib modules
    stdlib = {
        'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random',
        'collections', 'itertools', 'functools', 'operator', 'copy',
        'io', 'pathlib', 'glob', 'shutil', 'tempfile', 'subprocess',
        'threading', 'multiprocessing', 'queue', 'socket', 'urllib',
        'http', 'email', 'base64', 'hashlib', 'hmac', 'secrets',
        'logging', 'warnings', 'traceback', 'inspect', 'types',
        'typing', 'dataclasses', 'enum', 'abc', 'contextlib',
        'asyncio', 'concurrent', 'importlib', 'pkgutil', 'weakref',
        'gc', 'atexit', 'signal', 'errno', 'argparse', 'configparser',
        'csv', 'sqlite3', 'pickle', 'shelve', 'dbm', 'gzip', 'zipfile',
        'tarfile', 'xml', 'html', 'unittest', 'doctest', 'pdb',
    }
    
    return [imp for imp in imports if imp not in stdlib]

def convert_to_package_names(imports):
    """
    Convert import names to pip package names.
    Returns list of package names.
    """
    packages = set()
    
    for imp in imports:
        if imp in IMPORT_TO_PACKAGE:
            packages.add(IMPORT_TO_PACKAGE[imp])
        else:
            # Default: use import name with hyphens
            packages.add(imp.replace('_', '-'))
    
    return sorted(list(packages))

def generate_requirements_txt(project_path):
    """
    Main function to generate requirements.txt
    Returns (success, message, packages_list)
    """
    print(f"[REQUIREMENTS] Scanning project: {project_path}")
    
    # Check if requirements.txt already exists
    req_file = os.path.join(project_path, 'requirements.txt')
    if os.path.exists(req_file):
        print(f"[REQUIREMENTS] requirements.txt already exists")
        return True, "requirements.txt already exists", []
    
    # Get local packages to exclude
    local_packages = get_local_packages(project_path)
    print(f"[REQUIREMENTS] Detected {len(local_packages)} local packages: {local_packages}")
    
    # Scan project
    all_imports = scan_project_imports(project_path)
    print(f"[REQUIREMENTS] Found {len(all_imports)} imports")
    
    # Filter stdlib
    third_party = filter_standard_library(all_imports)
    
    # Filter local packages
    third_party = [imp for imp in third_party if imp not in local_packages]
    print(f"[REQUIREMENTS] Filtered to {len(third_party)} third-party imports (excluding local packages)")
    
    if not third_party:
        print(f"[REQUIREMENTS] No third-party dependencies detected")
        return False, "No third-party dependencies detected", []
    
    # Convert to package names
    packages = convert_to_package_names(third_party)
    print(f"[REQUIREMENTS] Resolved to {len(packages)} packages: {packages}")
    
    # Always include Flask and gunicorn
    if 'Flask' not in packages:
        packages.insert(0, 'Flask')
    if 'gunicorn' not in packages:
        packages.append('gunicorn')
    
    # Write requirements.txt
    try:
        with open(req_file, 'w') as f:
            for package in packages:
                f.write(f"{package}\n")
        
        print(f"[REQUIREMENTS] ✓ Created requirements.txt with {len(packages)} packages")
        return True, f"Generated requirements.txt with {len(packages)} packages", packages
    
    except Exception as e:
        print(f"[REQUIREMENTS] ✗ Failed to write requirements.txt: {e}")
        return False, f"Failed to write requirements.txt: {e}", []
