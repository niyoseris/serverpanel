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

def get_node_path():
    """
    Attempts to find the node executable.
    Returns path to node or None.
    """
    import shutil
    
    # Check common locations
    node_paths = [
        '/usr/local/bin/node',
        '/usr/bin/node',
        os.path.expanduser('~/.nvm/current/bin/node'),
        os.path.expanduser('~/.volta/bin/node'),
    ]
    
    # Try shutil.which first
    node_path = shutil.which('node')
    if node_path:
        return node_path
    
    # Try common paths
    for path in node_paths:
        if os.path.exists(path):
            return path
    
    return None

def get_npm_path():
    """
    Attempts to find the npm executable.
    Returns path to npm or None.
    """
    import shutil
    
    # Check common locations
    npm_paths = [
        '/usr/local/bin/npm',
        '/usr/bin/npm',
        os.path.expanduser('~/.nvm/current/bin/npm'),
        os.path.expanduser('~/.volta/bin/npm'),
    ]
    
    # Try shutil.which first
    npm_path = shutil.which('npm')
    if npm_path:
        return npm_path
    
    # Try common paths
    for path in npm_paths:
        if os.path.exists(path):
            return path
    
    return None

def install_nodejs():
    """
    Automatically installs Node.js on the server.
    Returns (success, message)
    """
    import platform
    
    print("[AUTO-FIX] Node.js not found. Installing automatically...")
    
    # Detect OS
    if platform.system() == 'Linux':
        # Check if we have apt (Debian/Ubuntu)
        if os.path.exists('/usr/bin/apt-get'):
            try:
                # Install Node.js 20.x LTS using NodeSource
                print("[AUTO-FIX] Detected Debian/Ubuntu, installing Node.js 20.x...")
                
                # Download and run NodeSource setup script
                setup_cmd = "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"
                result = subprocess.run(setup_cmd, shell=True, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    print(f"[AUTO-FIX] NodeSource setup failed: {result.stderr}")
                    # Fallback to system nodejs
                    print("[AUTO-FIX] Trying system nodejs package...")
                    result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True, timeout=60)
                
                # Install nodejs
                result = subprocess.run(
                    ['apt-get', 'install', '-y', 'nodejs'],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    return False, f"apt-get install nodejs failed: {result.stderr[:300]}"
                
                # Verify installation
                node_path = get_node_path()
                npm_path = get_npm_path()
                
                if node_path and npm_path:
                    # Get versions
                    node_ver = subprocess.run([node_path, '--version'], capture_output=True, text=True)
                    npm_ver = subprocess.run([npm_path, '--version'], capture_output=True, text=True)
                    print(f"[AUTO-FIX] ✓ Node.js installed: {node_ver.stdout.strip()}, npm: {npm_ver.stdout.strip()}")
                    return True, f"Node.js {node_ver.stdout.strip()} installed successfully"
                else:
                    return False, "Node.js installation completed but binaries not found"
                    
            except subprocess.TimeoutExpired:
                return False, "Node.js installation timed out"
            except Exception as e:
                return False, f"Node.js installation error: {str(e)}"
        
        # Check if we have yum/dnf (RHEL/CentOS/Fedora)
        elif os.path.exists('/usr/bin/yum') or os.path.exists('/usr/bin/dnf'):
            try:
                pkg_manager = 'dnf' if os.path.exists('/usr/bin/dnf') else 'yum'
                print(f"[AUTO-FIX] Detected RHEL/CentOS, installing Node.js with {pkg_manager}...")
                
                # Install Node.js
                result = subprocess.run(
                    [pkg_manager, 'install', '-y', 'nodejs', 'npm'],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    return False, f"{pkg_manager} install nodejs failed: {result.stderr[:300]}"
                
                print("[AUTO-FIX] ✓ Node.js installed successfully")
                return True, "Node.js installed successfully"
                
            except Exception as e:
                return False, f"Node.js installation error: {str(e)}"
        else:
            return False, "Unsupported Linux distribution. Please install Node.js manually."
    else:
        return False, f"Automatic Node.js installation not supported on {platform.system()}. Please install manually."

def detect_nodejs_entry_point(path):
    """
    Detects the entry point for a Node.js project.
    Returns (script_name, command) tuple.
    """
    import json
    
    package_json_path = os.path.join(path, 'package.json')
    
    if not os.path.exists(package_json_path):
        return None, None
    
    try:
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)
    except:
        return None, None
    
    scripts = package_data.get('scripts', {})
    main_file = package_data.get('main', 'index.js')
    
    # Priority order for start scripts
    start_scripts = ['start', 'serve', 'dev', 'server', 'run']
    
    for script in start_scripts:
        if script in scripts:
            return script, scripts[script]
    
    # If no start script, use main file
    main_path = os.path.join(path, main_file)
    if os.path.exists(main_path):
        return 'main', f'node {main_file}'
    
    # Fallback - look for common entry files
    common_files = ['index.js', 'server.js', 'app.js', 'main.js']
    for file in common_files:
        if os.path.exists(os.path.join(path, file)):
            return 'main', f'node {file}'
    
    return None, None

def auto_setup_nodejs_project(project_path, project_name, package_json_changed=False, progress_callback=None):
    """
    Automatically sets up a Node.js project environment.
    Runs npm install to install dependencies.
    Auto-installs Node.js if not found.
    
    Args:
        project_path: Path to the project
        project_name: Name of the project
        package_json_changed: If True, runs incremental update (npm prune + npm install)
        progress_callback: Optional callback function for progress updates - progress_callback(step, message)
    
    Returns (success, message)
    """
    def report_progress(step, message):
        print(f"[AUTO-SETUP-NODEJS] {message}")
        if progress_callback:
            progress_callback(step, message)
    
    report_progress("init", f"Starting auto-setup for {project_name}")
    
    # Check for package.json
    package_json = os.path.join(project_path, 'package.json')
    if not os.path.exists(package_json):
        return False, "No package.json found"
    
    # Find npm - auto-install Node.js if not found
    npm_path = get_npm_path()
    if not npm_path:
        report_progress("nodejs", "Node.js/npm not found. Installing...")
        success, message = install_nodejs()
        if not success:
            return False, f"Node.js auto-install failed: {message}"
        
        # Re-check for npm after installation
        npm_path = get_npm_path()
        if not npm_path:
            return False, "Node.js installed but npm still not found"
    
    report_progress("npm_found", f"Using npm: {npm_path}")
    
    # Get node path for environment
    node_path = get_node_path()
    node_dir = os.path.dirname(node_path) if node_path else '/usr/bin'
    
    # Create environment with proper PATH for npm to find node
    env = os.environ.copy()
    env['PATH'] = f"{node_dir}:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"
    
    # Check if node_modules exists
    node_modules = os.path.join(project_path, 'node_modules')
    
    if not os.path.exists(node_modules):
        # Fresh install
        report_progress("npm_install", "Installing dependencies (npm install)...")
        try:
            result = subprocess.run(
                [npm_path, 'install'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            if result.returncode != 0:
                print(f"[AUTO-SETUP-NODEJS] npm install stderr: {result.stderr}")
                return False, f"npm install failed: {result.stderr[:500]}"
            report_progress("npm_done", "✓ Dependencies installed")
        except subprocess.TimeoutExpired:
            return False, "npm install timed out (>5 min)"
        except Exception as e:
            return False, f"npm install error: {str(e)}"
    elif package_json_changed:
        # Incremental update: prune unused + install new
        report_progress("npm_prune", "Removing unused packages (npm prune)...")
        try:
            result = subprocess.run(
                [npm_path, 'prune'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )
            if result.returncode != 0:
                print(f"[AUTO-SETUP-NODEJS] npm prune stderr: {result.stderr}")
            else:
                # Parse prune output to show what was removed
                if result.stdout.strip():
                    report_progress("npm_prune_done", f"Pruned: {result.stdout.strip()[:200]}")
                else:
                    report_progress("npm_prune_done", "✓ No unused packages to remove")
        except Exception as e:
            print(f"[AUTO-SETUP-NODEJS] npm prune error (non-fatal): {e}")
        
        report_progress("npm_install", "Installing/updating packages (npm install)...")
        try:
            result = subprocess.run(
                [npm_path, 'install'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            if result.returncode != 0:
                print(f"[AUTO-SETUP-NODEJS] npm install stderr: {result.stderr}")
                return False, f"npm install failed: {result.stderr[:500]}"
            
            # Parse output to show what changed
            added = result.stdout.count('added')
            updated = result.stdout.count('updated')
            if 'up to date' in result.stdout:
                report_progress("npm_done", "✓ All packages up to date")
            else:
                report_progress("npm_done", f"✓ Packages updated (added: {added}, updated: {updated})")
        except subprocess.TimeoutExpired:
            return False, "npm install timed out (>5 min)"
        except Exception as e:
            return False, f"npm install error: {str(e)}"
    else:
        report_progress("skip", "✓ node_modules already exists, no changes needed")
    
    # Check if project needs build (TypeScript, Next.js, NestJS, etc.)
    import json
    try:
        with open(package_json, 'r') as f:
            pkg_data = json.load(f)
        scripts = pkg_data.get('scripts', {})
        
        # Check if build script exists and if build output is missing
        if 'build' in scripts:
            needs_build = False
            
            # Check for common build output directories
            dist_path = os.path.join(project_path, 'dist')
            next_path = os.path.join(project_path, '.next')
            build_path = os.path.join(project_path, 'build')
            
            # For monorepo, check backend/dist and frontend/.next
            backend_dist = os.path.join(project_path, 'backend', 'dist')
            frontend_next = os.path.join(project_path, 'frontend', '.next')
            
            # Determine if build is needed
            if 'next' in str(scripts.get('build', '')).lower() or 'next' in str(pkg_data.get('dependencies', {})):
                needs_build = not os.path.exists(next_path)
            elif os.path.exists(os.path.join(project_path, 'backend')) and os.path.exists(os.path.join(project_path, 'frontend')):
                # Monorepo - check both
                needs_build = not os.path.exists(backend_dist) or not os.path.exists(frontend_next)
            elif 'tsc' in str(scripts.get('build', '')) or 'typescript' in str(pkg_data.get('devDependencies', {})):
                needs_build = not os.path.exists(dist_path)
            else:
                # Generic check
                needs_build = not os.path.exists(dist_path) and not os.path.exists(build_path) and not os.path.exists(next_path)
            
            if needs_build:
                print(f"[AUTO-SETUP-NODEJS] Build output missing, running npm run build...")
                try:
                    # Get node path for environment
                    node_path = get_node_path()
                    node_dir = os.path.dirname(node_path) if node_path else '/usr/bin'
                    build_env = os.environ.copy()
                    build_env['PATH'] = f"{node_dir}:/usr/local/bin:/usr/bin:/bin:{build_env.get('PATH', '')}"
                    
                    result = subprocess.run(
                        [npm_path, 'run', 'build'],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=600,  # 10 min for build
                        env=build_env
                    )
                    if result.returncode != 0:
                        print(f"[AUTO-SETUP-NODEJS] npm run build stderr: {result.stderr[-500:]}")
                        return False, f"npm run build failed: {result.stderr[-500:]}"
                    print(f"[AUTO-SETUP-NODEJS] ✓ Build completed successfully")
                except subprocess.TimeoutExpired:
                    return False, "npm run build timed out (>10 min)"
                except Exception as e:
                    return False, f"npm run build error: {str(e)}"
            else:
                print(f"[AUTO-SETUP-NODEJS] ✓ Build output already exists")
    except Exception as e:
        print(f"[AUTO-SETUP-NODEJS] Warning: Could not check build status: {e}")
    
    print(f"[AUTO-SETUP-NODEJS] Setup complete!")
    return True, "Node.js project setup completed successfully"

def start_nodejs_process(project_name, project_path, port, env_vars=None, start_script='start'):
    """
    Starts a Node.js process.
    Returns PID if successful, None otherwise.
    Automatically builds Next.js projects if .next folder is missing.
    """
    import time
    import json
    
    node_path = get_node_path()
    npm_path = get_npm_path()
    
    if not node_path:
        print(f"[START-NODEJS] ✗ Node.js not found")
        return None
    
    print(f"[START-NODEJS] Using Node: {node_path}")
    
    # Prepare environment with proper PATH for node
    node_dir = os.path.dirname(node_path) if node_path else '/usr/bin'
    env = os.environ.copy()
    env['PATH'] = f"{node_dir}:/usr/local/bin:/usr/bin:/bin:{env.get('PATH', '')}"
    env['NODE_ENV'] = 'production'
    
    if env_vars:
        env.update(env_vars)
    
    print(f"[START-NODEJS] PATH set to include: {node_dir}")
    
    # Check if this is a Next.js project that needs building
    next_build_path = os.path.join(project_path, '.next')
    frontend_next_path = os.path.join(project_path, 'frontend', '.next')
    package_json_path = os.path.join(project_path, 'package.json')
    frontend_package_json = os.path.join(project_path, 'frontend', 'package.json')
    
    def run_nextjs_build(build_path, pkg_json_path, build_cwd):
        """Helper to run Next.js build if .next folder is missing"""
        if not os.path.exists(pkg_json_path):
            return True  # No package.json, skip
        
        try:
            with open(pkg_json_path, 'r') as f:
                pkg_data = json.load(f)
            
            scripts = pkg_data.get('scripts', {})
            dependencies = pkg_data.get('dependencies', {})
            dev_dependencies = pkg_data.get('devDependencies', {})
            
            # Detect Next.js project
            is_nextjs = (
                'next' in dependencies or 
                'next' in dev_dependencies or
                'next start' in str(scripts.get('start', '')) or
                'next dev' in str(scripts.get('dev', ''))
            )
            
            if is_nextjs and not os.path.exists(build_path):
                print(f"[START-NODEJS] ⚠ Next.js project detected but .next folder missing at {build_path}")
                print(f"[START-NODEJS] Running npm run build in {build_cwd}...")
                
                if 'build' in scripts:
                    try:
                        build_result = subprocess.run(
                            [npm_path, 'run', 'build'],
                            cwd=build_cwd,
                            capture_output=True,
                            text=True,
                            timeout=600,  # 10 min timeout
                            env=env
                        )
                        
                        if build_result.returncode != 0:
                            print(f"[START-NODEJS] ✗ Build failed: {build_result.stderr[-500:]}")
                            # Write error to log file
                            stderr_log_path = os.path.join(project_path, f"{project_name}.err.log")
                            with open(stderr_log_path, 'w') as f:
                                f.write(f"=== Build Failed ===\n")
                                f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write(f"Build directory: {build_cwd}\n")
                                f.write(f"Exit code: {build_result.returncode}\n\n")
                                f.write(f"STDOUT:\n{build_result.stdout}\n\n")
                                f.write(f"STDERR:\n{build_result.stderr}\n")
                            return False
                        
                        print(f"[START-NODEJS] ✓ Build completed successfully")
                        return True
                        
                    except subprocess.TimeoutExpired:
                        print(f"[START-NODEJS] ✗ Build timed out (>10 min)")
                        return False
                    except Exception as e:
                        print(f"[START-NODEJS] ✗ Build error: {e}")
                        return False
                else:
                    print(f"[START-NODEJS] ✗ No build script found in package.json at {pkg_json_path}")
                    return False
            return True
        except Exception as e:
            print(f"[START-NODEJS] Warning: Could not check for Next.js: {e}")
            return True  # Continue anyway
    
    # Check root-level Next.js
    if not run_nextjs_build(next_build_path, package_json_path, project_path):
        return None
    
    # Check monorepo frontend folder
    if os.path.exists(frontend_package_json):
        if not run_nextjs_build(frontend_next_path, frontend_package_json, os.path.join(project_path, 'frontend')):
            return None
    
    # Open log files
    stdout_log_path = os.path.join(project_path, f"{project_name}.out.log")
    stderr_log_path = os.path.join(project_path, f"{project_name}.err.log")
    
    try:
        stdout_log = open(stdout_log_path, "w", buffering=1)
        stderr_log = open(stderr_log_path, "w", buffering=1)
        
        # Write startup info
        stderr_log.write(f"=== Starting Node.js project {project_name} ===\n")
        stderr_log.write(f"Port: {port}\n")
        stderr_log.write(f"Directory: {project_path}\n")
        stderr_log.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        stderr_log.write("=" * 50 + "\n\n")
        stderr_log.flush()
        
        # Determine command
        # Special handling for monorepo projects (backend + frontend) that use concurrently.
        # Those projects often rely on the PORT env var; if we set a single PORT for the root
        # process, both backend and frontend will try to bind to the same port.
        frontend_dir = os.path.join(project_path, 'frontend')
        backend_dir = os.path.join(project_path, 'backend')
        has_monorepo = os.path.exists(frontend_dir) and os.path.exists(backend_dir)
        
        if has_monorepo and os.path.exists(package_json_path):
            backend_port = None
            if env_vars:
                backend_port = env_vars.get('BACKEND_PORT') or env_vars.get('PORT_BACKEND')
            if not backend_port:
                backend_port = 5001
            backend_port = int(backend_port)
            frontend_port = int(port)

            # Build a wrapper command that starts frontend and backend with separate PORT values.
            # Keep a single parent PID so panel can manage it.
            wrapper = (
                'set -e; '
                f'echo "[MONOREPO] Starting frontend on {frontend_port}"; '
                f'PORT={frontend_port} npm run start --workspace=frontend & FRONT_PID=$!; '
                f'echo "[MONOREPO] Starting backend on {backend_port}"; '
                f'PORT={backend_port} npm run start:prod --workspace=backend & BACK_PID=$!; '
                'wait -n "$FRONT_PID" "$BACK_PID"; '
                'EXIT_CODE=$?; '
                'echo "[MONOREPO] One process exited, stopping the other..."; '
                'kill "$FRONT_PID" "$BACK_PID" 2>/dev/null || true; '
                'wait "$FRONT_PID" "$BACK_PID" 2>/dev/null || true; '
                'exit "$EXIT_CODE"'
            )

            command = ['bash', '-lc', wrapper]
            print(f"[START-NODEJS] Monorepo detected (frontend+backend). Starting with split ports: frontend={frontend_port}, backend={backend_port}")
        else:
            env['PORT'] = str(port)
            script_name, script_cmd = detect_nodejs_entry_point(project_path)
            
            if script_name and script_name != 'main':
                # Use npm run <script>
                command = [npm_path, 'run', script_name]
                print(f"[START-NODEJS] Running: npm run {script_name}")
            elif script_cmd:
                # Direct node command
                command = script_cmd.split()
                if command[0] == 'node':
                    command[0] = node_path
                print(f"[START-NODEJS] Running: {' '.join(command)}")
            else:
                # Fallback
                command = [node_path, 'index.js']
                print(f"[START-NODEJS] Running fallback: node index.js")
        
        stderr_log.write(f"Command: {' '.join(command)}\n\n")
        stderr_log.flush()
        
        # Start process
        process = subprocess.Popen(
            command,
            cwd=project_path,
            env=env,
            stdout=stdout_log,
            stderr=stderr_log,
            start_new_session=True
        )
        
        print(f"[START-NODEJS] ✓ Process started with PID: {process.pid}")
        
        # Wait a bit to see if it crashes immediately
        time.sleep(2)
        poll_result = process.poll()
        
        if poll_result is not None:
            print(f"[START-NODEJS] ✗ Process died immediately (exit code: {poll_result})")
            stderr_log.write(f"\n\nERROR: Process died immediately (exit code: {poll_result})\n")
            stderr_log.close()
            stdout_log.close()
            return None
        
        print(f"[START-NODEJS] ✓ Process running successfully")
        return process.pid
        
    except Exception as e:
        error_msg = f"ERROR: Failed to start Node.js process: {e}\n"
        try:
            with open(stderr_log_path, "w") as f:
                f.write(error_msg)
                import traceback
                f.write("\nFull traceback:\n")
                f.write(traceback.format_exc())
        except:
            pass
        print(f"[START-NODEJS] ✗ {error_msg}")
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

def auto_setup_project(project_path, project_name, package_json_changed=False, requirements_txt_changed=False, progress_callback=None):
    """
    Automatically sets up project environment if missing.
    Creates venv, installs dependencies, etc.
    
    Args:
        project_path: Path to the project
        project_name: Name of the project
        package_json_changed: If True, runs incremental npm update for Node.js
        requirements_txt_changed: If True, runs incremental pip update for Python
        progress_callback: Optional callback for progress updates - progress_callback(step, message)
    
    Returns (success, message)
    """
    def report_progress(step, message):
        print(f"[AUTO-SETUP] {message}")
        if progress_callback:
            progress_callback(step, message)
    
    report_progress("init", f"Starting auto-setup for {project_name}")
    
    # Check if this is a Node.js project
    package_json = os.path.join(project_path, 'package.json')
    if os.path.exists(package_json):
        report_progress("detect", "Detected Node.js project")
        return auto_setup_nodejs_project(project_path, project_name, package_json_changed, progress_callback)
    
    report_progress("detect", "Detected Python project")
    
    # Check if venv exists
    venv_path = os.path.join(project_path, 'venv')
    
    if not os.path.exists(venv_path):
        report_progress("venv_create", "Creating virtual environment...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', 'venv'],
                cwd=project_path,
                check=True,
                timeout=60
            )
            report_progress("venv_done", "✓ Virtual environment created")
        except Exception as e:
            return False, f"Failed to create venv: {e}"
    else:
        report_progress("venv_exists", "✓ Virtual environment already exists")
    
    # Get pip path
    pip_path = os.path.join(venv_path, 'bin', 'pip')
    
    if not os.path.exists(pip_path):
        return False, "pip not found in venv"
    
    # Check for requirements.txt
    requirements_file = os.path.join(project_path, 'requirements.txt')
    
    if os.path.exists(requirements_file):
        if requirements_txt_changed:
            # Incremental update: only install changed/new packages
            report_progress("pip_update", "Updating packages incrementally (pip install -r requirements.txt)...")
            try:
                result = subprocess.run(
                    [pip_path, 'install', '-r', 'requirements.txt'],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                # Parse output to count changes
                installed = result.stdout.count('Successfully installed')
                already = result.stdout.count('already satisfied')
                if installed > 0:
                    report_progress("pip_done", f"✓ Packages updated ({installed} new/updated)")
                else:
                    report_progress("pip_done", "✓ All packages already up to date")
            except Exception as e:
                report_progress("pip_error", f"Warning: Some dependencies failed: {e}")
        else:
            # No changes to requirements.txt, skip if packages already installed
            report_progress("pip_skip", "✓ requirements.txt unchanged, skipping pip install")
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
    if project_type == 'nodejs':
        script_name, script_cmd = detect_nodejs_entry_point(path)
        return script_cmd or 'node index.js'
    
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
    
    # Handle Node.js projects separately
    if project_type == 'nodejs':
        print(f"[CONFIG] Detected Node.js project")
        
        # Auto-setup Node.js project
        success, message = auto_setup_nodejs_project(path, project_name)
        if not success:
            print(f"[CONFIG] ✗ Node.js setup failed: {message}")
            # Create error log
            error_log_path = os.path.join(path, f"{project_name}.err.log")
            try:
                with open(error_log_path, "w") as f:
                    f.write(f"ERROR: Node.js setup failed\n")
                    f.write(f"{message}\n")
            except:
                pass
            return None
        
        # Start Node.js process
        pid = start_nodejs_process(project_name, path, port, env_vars)
        return pid
    
    # Auto-detect entry point if not provided (Python projects)
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
    # Use explicit log file paths and debug level to capture all errors including tracebacks
    stdout_log = os.path.join(path, f"{project_name}.out.log")
    stderr_log = os.path.join(path, f"{project_name}.err.log")
    command = f"{gunicorn_path} -w 4 -b 0.0.0.0:{port} --log-level debug --access-logfile {stdout_log} --error-logfile {stderr_log} --capture-output --enable-stdio-inheritance {entry_point}"
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
