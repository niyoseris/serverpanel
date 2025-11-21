import os
import subprocess
import sys
import shlex

def is_linux():
    return os.name == 'posix' and os.uname().sysname == 'Linux'

def generate_nginx_config(project_name, domain, port, ssl_enabled=False):
    if not domain:
        print(f"No domain provided for {project_name}. Skipping Nginx config (Access via Port {port}).")
        return

    listen_block = "listen 80;"
    ssl_block = ""
    
    if ssl_enabled:
        listen_block = """
    listen 80;
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    if ($scheme != "https") {
        return 301 https://$host$request_uri;
    }
        """.replace("{domain}", domain)

    config = f"""
server {{
    {listen_block}
    server_name {domain};

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""
    if is_linux():
        config_path = f"/etc/nginx/sites-available/{project_name}"
        print(f"Writing Nginx config to {config_path}")
        # subprocess.run(['sudo', 'tee', config_path], input=config.encode())
        # subprocess.run(['sudo', 'ln', '-s', config_path, f"/etc/nginx/sites-enabled/{project_name}"])
    else:
        print(f"[MOCK] Nginx Config for {project_name}:\n{config}")

def reload_nginx():
    if is_linux():
        # subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'])
        print("Reloading Nginx")
    else:
        print("[MOCK] Reloading Nginx")

def open_firewall_port(port):
    """
    Opens a port in UFW firewall if on Linux.
    """
    if is_linux():
        try:
            import subprocess
            import os
            
            # Try to find ufw in common locations
            ufw_paths = ['/usr/sbin/ufw', '/sbin/ufw', 'ufw']
            ufw_cmd = None
            
            for path in ufw_paths:
                if path.startswith('/'):
                    if os.path.exists(path):
                        ufw_cmd = path
                        break
                else:
                    # Try without full path
                    ufw_cmd = path
                    break
            
            if not ufw_cmd:
                print(f"[FIREWALL] ⚠ ufw not found, skipping firewall configuration")
                return True  # Don't fail, just skip
            
            result = subprocess.run(
                [ufw_cmd, 'allow', f'{port}/tcp'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"[FIREWALL] ✓ Port {port} opened in firewall")
                return True
            else:
                print(f"[FIREWALL] ✗ Failed to open port {port}: {result.stderr}")
                return False
        except FileNotFoundError as e:
            print(f"[FIREWALL] ⚠ ufw not found: {e}")
            return True  # Don't fail startup
        except Exception as e:
            print(f"[FIREWALL] Error opening port {port}: {e}")
            return False
    else:
        print(f"[FIREWALL] [MOCK] Would open port {port}")
        return True

def start_local_process(project_name, command, directory, env_vars=None):
    """
    Starts a local process for development (when not using Supervisor).
    Returns PID if successful, None otherwise.
    """
    import subprocess
    import os
    import time
    
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    
    # Open log files first
    stdout_log_path = os.path.join(directory, f"{project_name}.out.log")
    stderr_log_path = os.path.join(directory, f"{project_name}.err.log")
    
    try:
        stdout_log = open(stdout_log_path, "w", buffering=1)  # Line buffered
        stderr_log = open(stderr_log_path, "w", buffering=1)
        
        # Write startup info
        stderr_log.write(f"=== Starting {project_name} ===\n")
        stderr_log.write(f"Command: {command}\n")
        stderr_log.write(f"Directory: {directory}\n")
        stderr_log.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        stderr_log.write("=" * 50 + "\n\n")
        stderr_log.flush()
        
        print(f"[START] Command: {command}")
        print(f"[START] Working directory: {directory}")
        print(f"[START] Log files: {stdout_log_path}, {stderr_log_path}")
        
        # Parse command into list
        args = command.split()
        
        # Check if executable exists
        if not os.path.exists(args[0]):
            error_msg = f"ERROR: Executable not found: {args[0]}\n"
            stderr_log.write(error_msg)
            stderr_log.close()
            stdout_log.close()
            print(f"[START] {error_msg}")
            return None
        
        # Start process
        process = subprocess.Popen(
            args,
            cwd=directory,
            env=env,
            stdout=stdout_log,
            stderr=stderr_log,
            start_new_session=True  # Detach from parent
        )
        
        print(f"[START] ✓ Process started with PID: {process.pid}")
        
        # Wait a bit to see if it crashes immediately
        time.sleep(0.5)
        poll_result = process.poll()
        
        if poll_result is not None:
            # Process already died
            print(f"[START] ✗ Process died immediately (exit code: {poll_result})")
            stderr_log.write(f"\n\nERROR: Process died immediately (exit code: {poll_result})\n")
            stderr_log.write("Check the error output above for details.\n")
            stderr_log.close()
            stdout_log.close()
            return None
        
        # For gunicorn, wait a bit longer to check if workers boot successfully
        print(f"[START] Waiting for workers to boot...")
        time.sleep(3)
        poll_result = process.poll()
        
        if poll_result is not None:
            # Process died after workers failed
            print(f"[START] ✗ Process died after {poll_result} (workers failed to boot)")
            stderr_log.write(f"\n\nERROR: Process died with exit code {poll_result} (likely worker boot failure)\n")
            stderr_log.write("Check the error output above for worker errors.\n")
            stderr_log.close()
            stdout_log.close()
            return None
        
        print(f"[START] ✓ Process and workers running successfully")
        return process.pid
        
    except FileNotFoundError as e:
        error_msg = f"ERROR: Command not found: {e}\n"
        try:
            with open(stderr_log_path, "w") as f:
                f.write(error_msg)
                f.write(f"\nCommand: {command}\n")
                f.write(f"Working directory: {directory}\n")
                f.write("\nPossible issues:\n")
                f.write("1. Gunicorn not installed in venv\n")
                f.write("2. Wrong venv path\n")
                f.write("3. Entry point incorrect\n")
        except:
            pass
        print(f"[START] ✗ {error_msg}")
        return None
        
    except Exception as e:
        error_msg = f"ERROR: Failed to start process: {e}\n"
        try:
            with open(stderr_log_path, "w") as f:
                f.write(error_msg)
                import traceback
                f.write("\nFull traceback:\n")
                f.write(traceback.format_exc())
        except:
            pass
        print(f"[START] ✗ {error_msg}")
        import traceback
        traceback.print_exc()
        return None

def get_project_venv_python(path):
    """
    Attempts to find the python executable in the project's virtual environment.
    Returns path to python or None.
    """
    common_venvs = ['venv', '.venv', 'env']
    for venv in common_venvs:
        # Check for bin/python (Unix) or Scripts/python.exe (Windows - though we are on Mac/Linux)
        python_path = os.path.join(path, venv, 'bin', 'python')
        if os.path.exists(python_path):
            return python_path
    return None

def auto_setup_project(project_path, project_name):
    """
    Automatically sets up project environment if missing.
    Creates venv, installs dependencies, etc.
    Returns (success, message)
    """
    print(f"[AUTO-SETUP] Starting auto-setup for {project_name} at {project_path}")
    
    # Check if venv exists
    venv_path = os.path.join(project_path, 'venv')
    
    if not os.path.exists(venv_path):
        print(f"[AUTO-SETUP] Creating virtual environment...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', 'venv'],
                cwd=project_path,
                check=True,
                timeout=60
            )
            print(f"[AUTO-SETUP] ✓ Virtual environment created")
        except Exception as e:
            return False, f"Failed to create venv: {e}"
    else:
        print(f"[AUTO-SETUP] Virtual environment already exists")
    
    # Get pip path
    pip_path = os.path.join(venv_path, 'bin', 'pip')
    
    if not os.path.exists(pip_path):
        return False, "pip not found in venv"
    
    # Upgrade pip
    print(f"[AUTO-SETUP] Upgrading pip...")
    try:
        subprocess.run(
            [pip_path, 'install', '--upgrade', 'pip', '-q'],
            timeout=60
        )
    except Exception as e:
        print(f"[AUTO-SETUP] Warning: Could not upgrade pip: {e}")
    
    # Check for requirements.txt
    requirements_file = os.path.join(project_path, 'requirements.txt')
    
    if os.path.exists(requirements_file):
        print(f"[AUTO-SETUP] Installing dependencies from requirements.txt...")
        try:
            subprocess.run(
                [pip_path, 'install', '-r', 'requirements.txt', '-q'],
                cwd=project_path,
                timeout=300
            )
            print(f"[AUTO-SETUP] ✓ Dependencies installed")
        except Exception as e:
            print(f"[AUTO-SETUP] Warning: Some dependencies failed: {e}")
    else:
        # No requirements.txt, try to generate one
        print(f"[AUTO-SETUP] No requirements.txt found, attempting to generate...")
        try:
            from app.utils.requirements_generator import generate_requirements_txt
            success, message, packages = generate_requirements_txt(project_path)
            
            if success and packages:
                print(f"[AUTO-SETUP] ✓ Generated requirements.txt with {len(packages)} packages")
                print(f"[AUTO-SETUP] Installing generated dependencies...")
                subprocess.run(
                    [pip_path, 'install', '-r', 'requirements.txt', '-q'],
                    cwd=project_path,
                    timeout=300
                )
                print(f"[AUTO-SETUP] ✓ Dependencies installed")
            else:
                # Fallback: install basics
                print(f"[AUTO-SETUP] Could not generate requirements.txt, installing basic packages...")
                subprocess.run(
                    [pip_path, 'install', 'flask', 'gunicorn', '-q'],
                    timeout=120
                )
                print(f"[AUTO-SETUP] ✓ Basic packages installed (Flask, Gunicorn)")
        except Exception as e:
            print(f"[AUTO-SETUP] Warning during requirements generation: {e}")
            # Fallback: install basics
            try:
                subprocess.run(
                    [pip_path, 'install', 'flask', 'gunicorn', '-q'],
                    timeout=120
                )
                print(f"[AUTO-SETUP] ✓ Basic packages installed (Flask, Gunicorn)")
            except Exception as e2:
                return False, f"Failed to install basic packages: {e2}"
    
    # Ensure gunicorn is installed
    gunicorn_path = os.path.join(venv_path, 'bin', 'gunicorn')
    if not os.path.exists(gunicorn_path):
        print(f"[AUTO-SETUP] Installing gunicorn...")
        try:
            subprocess.run(
                [pip_path, 'install', 'gunicorn', '-q'],
                timeout=60
            )
            print(f"[AUTO-SETUP] ✓ Gunicorn installed")
        except Exception as e:
            return False, f"Failed to install gunicorn: {str(e)}"
    else:
        print(f"[AUTO-SETUP] ✓ Gunicorn found")
    
    print(f"[AUTO-SETUP] Setup complete!")
    return True, "Project setup completed successfully"

def detect_entry_point(path, project_type):
    """
    Attempts to detect the entry point file and callable.
    """
    if project_type == 'django':
        # Look for wsgi.py in immediate subdirectories (not deeply nested)
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                wsgi_path = os.path.join(item_path, 'wsgi.py')
                if os.path.exists(wsgi_path):
                    return f"{item}.wsgi:application"
        
        # Check for manage.py to confirm Django and try common patterns
        if os.path.exists(os.path.join(path, 'manage.py')):
            return 'config.wsgi:application' # Common Django pattern
        return 'config.wsgi:application' # Default fallback
    
    # Flask - check common patterns
    if os.path.exists(os.path.join(path, 'app.py')):
        return 'app:app'
    if os.path.exists(os.path.join(path, 'run.py')):
        return 'run:app'
    if os.path.exists(os.path.join(path, 'wsgi.py')):
        return 'wsgi:app'
    if os.path.exists(os.path.join(path, 'application.py')):
        return 'application:app'
        
    return 'app:app' # Default

def generate_supervisor_config(project_name, project_type, path, port, env_vars=None, entry_point=None):
    print(f"\n[CONFIG] === Generating configuration for {project_name} ===")
    print(f"[CONFIG] Project path: {path}")
    print(f"[CONFIG] Port: {port}")
    print(f"[CONFIG] Project type: {project_type}")
    
    # Auto-detect entry point if not provided
    if not entry_point:
        entry_point = detect_entry_point(path, project_type)
        print(f"[CONFIG] Auto-detected entry point: {entry_point}")
    else:
        print(f"[CONFIG] Using provided entry point: {entry_point}")

    # Auto-detect venv
    project_python = get_project_venv_python(path)
    
    if project_python:
        print(f"[CONFIG] ✓ Found project venv: {project_python}")
        # Try to find gunicorn in the project's venv
        gunicorn_path = os.path.join(os.path.dirname(project_python), 'gunicorn')
        if not os.path.exists(gunicorn_path):
            print(f"[CONFIG] ✗ Gunicorn not found in project venv: {gunicorn_path}")
            print(f"[CONFIG] This should not happen after auto-setup!")
            # Create error log
            error_log_path = os.path.join(path, f"{project_name}.err.log")
            try:
                with open(error_log_path, "w") as f:
                    f.write("ERROR: Gunicorn not found in project venv\n")
                    f.write(f"Expected location: {gunicorn_path}\n")
                    f.write("\nThis is a configuration error. Please check:\n")
                    f.write("1. Auto-setup completed successfully?\n")
                    f.write("2. venv/bin/gunicorn exists?\n")
                    f.write(f"3. Run: {os.path.dirname(project_python)}/pip install gunicorn\n")
            except:
                pass
            return None
    else:
        print(f"[CONFIG] ✗ No project venv found!")
        print(f"[CONFIG] Checked: venv/, .venv/, env/")
        # Create error log
        error_log_path = os.path.join(path, f"{project_name}.err.log")
        try:
            with open(error_log_path, "w") as f:
                f.write("ERROR: No virtual environment found\n")
                f.write(f"Project path: {path}\n")
                f.write("\nExpected folders: venv/, .venv/, or env/\n")
                f.write("Auto-setup should have created this.\n")
        except:
            pass
        return None
    
    # Verify gunicorn exists
    if not os.path.exists(gunicorn_path):
        print(f"[CONFIG] ✗ CRITICAL: Gunicorn executable not found: {gunicorn_path}")
        return None
    
    print(f"[CONFIG] ✓ Gunicorn found: {gunicorn_path}")
    
    # Build command with detailed logging
    command = f"{gunicorn_path} -w 4 -b 0.0.0.0:{port} --log-level info --capture-output --enable-stdio-inheritance {entry_point}"
    print(f"[CONFIG] Command: {command}")

    # Format env vars for Supervisor (KEY="VAL",KEY2="VAL2")
    env_string = ""
    if env_vars:
        env_list = [f'{k}="{v}"' for k, v in env_vars.items()]
        env_string = "environment=" + ",".join(env_list)
        print(f"[CONFIG] Environment variables: {len(env_vars)} vars")

    config = f"""
[program:{project_name}]
command={command}
directory={path}
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/{project_name}.err.log
stdout_logfile=/var/log/{project_name}.out.log
{env_string}
"""
    
    # For now, always use local process (not supervisor)
    # TODO: Add proper supervisor integration later
    print(f"[CONFIG] Starting as local process (PID-based management)...")
    pid = start_local_process(project_name, command, path, env_vars)
    
    if pid:
        print(f"[CONFIG] ✓ Process started successfully with PID: {pid}")
    else:
        print(f"[CONFIG] ✗ Failed to start process")
    
    return pid

def check_process_status(pid):
    """
    Checks if a process with the given PID is running.
    """
    if not pid:
        return False
    try:
        # Signal 0 does nothing but checks if process exists
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def reload_supervisor():
    if is_linux():
        # subprocess.run(['sudo', 'supervisorctl', 'reread'])
        # subprocess.run(['sudo', 'supervisorctl', 'update'])
        print("Reloading Supervisor")
    else:
        print("[MOCK] Reloading Supervisor")
