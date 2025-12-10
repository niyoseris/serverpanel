from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User, Project, SubRoute
import os
import json
import signal
import shutil
import tempfile
import zipfile
import time
from datetime import datetime

main = Blueprint('main', __name__)

# Upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'py', 'txt', 'html', 'css', 'js', 'json', 'yml', 'yaml', 'md', 'sh', 'env'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Helper function to stop a project process
def stop_project_process(project):
    """Stop a running project process and all its children"""
    if project.pid:
        try:
            import psutil
            # Get parent process
            parent = psutil.Process(project.pid)
            
            # Get all child processes
            children = parent.children(recursive=True)
            
            # Terminate parent first (gracefully)
            parent.terminate()
            
            # Terminate all children
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            # Wait for graceful termination
            gone, alive = psutil.wait_procs([parent] + children, timeout=3)
            
            # Force kill any remaining processes
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except psutil.NoSuchProcess:
            pass  # Already stopped
        except Exception as e:
            print(f'Error stopping project: {e}')
        
        project.pid = None
        project.status = 'stopped'
        db.session.commit()

@main.route('/')
@login_required
def dashboard():
    projects = Project.query.all()
    return render_template('dashboard.html', projects=projects)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid username or password')
    
    return render_template('login.html')

@main.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        name = request.form.get('name')
        domain = request.form.get('domain') # Optional now
        port = request.form.get('port')
        path = request.form.get('path')
        project_type = request.form.get('project_type') # flask, django
        entry_point = request.form.get('entry_point') # Optional custom entry point

        # Validation
        if not name or not port or not path:
            flash('Project name, port, and path are required')
            return redirect(url_for('main.new_project'))
        
        # Check if project exists
        if Project.query.filter_by(name=name).first():
            flash('Project name already exists')
            return redirect(url_for('main.new_project'))
        
        # Check if port is already in use
        if Project.query.filter_by(port=port).first():
            flash(f'Port {port} is already in use by another project')
            return redirect(url_for('main.new_project'))
        
        # Check if path exists
        if not os.path.exists(path):
            flash(f'Project path does not exist: {path}')
            return redirect(url_for('main.new_project'))
        
        # Create DB entry
        project = Project(name=name, domain=domain, port=port, path=path, project_type=project_type, status='stopped')
        db.session.add(project)
        db.session.commit()

        # System configurations
        from app.utils.system import generate_nginx_config, reload_nginx, generate_supervisor_config, reload_supervisor, detect_entry_point
        
        try:
            # Only generate Nginx config if domain is provided
            if domain:
                generate_nginx_config(name, domain, port)
                reload_nginx()
            
            # Auto-detect entry point if not provided
            if not entry_point:
                entry_point = detect_entry_point(path, project_type)
                
            project.entry_point = entry_point
            
            # Start the project
            pid = generate_supervisor_config(name, project_type, path, port, entry_point=entry_point)
            if pid:
                project.pid = pid
                project.status = 'running'
                db.session.commit()
                flash(f'Project {name} created and started (PID: {pid})!', 'success')
            else:
                reload_supervisor()
                flash(f'Project {name} created. Start it manually from the project page.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error configuring project: {str(e)}', 'error')
            
        return redirect(url_for('main.dashboard'))

    return render_template('project_wizard.html')

@main.route('/projects/<int:id>')
@login_required
def project_details(id):
    project = Project.query.get_or_404(id)
    
    # Verify process status
    if project.pid and project.status == 'running':
        from app.utils.system import check_process_status
        if not check_process_status(project.pid):
            project.status = 'stopped'
            project.pid = None
            db.session.commit()
            flash(f'Project {project.name} process died unexpectedly.', 'error')
    
    # Read logs - check multiple possible locations
    stdout_log = ""
    stderr_log = ""
    
    # Try project directory first (for local development)
    log_paths = [
        os.path.join(project.path, f"{project.name}.out.log"),
        os.path.join(project.path, project.name, f"{project.name}.out.log"),  # Nested structure
        f"{project.name}.out.log",  # Current directory (VDS Panel root)
        f"/var/log/{project.name}.out.log"  # Linux supervisor logs
    ]
    
    for log_path in log_paths:
        try:
            with open(log_path, "r") as f:
                stdout_log = f.read()[-10000:] # Last 10000 chars for better error visibility
                break
        except FileNotFoundError:
            continue
    
    if not stdout_log:
        stdout_log = "Log file not found. Start the project to generate logs."
    
    # Same for stderr
    err_log_paths = [
        os.path.join(project.path, f"{project.name}.err.log"),
        os.path.join(project.path, project.name, f"{project.name}.err.log"),  # Nested structure
        f"{project.name}.err.log",
        f"/var/log/{project.name}.err.log"
    ]
    
    for log_path in err_log_paths:
        try:
            with open(log_path, "r") as f:
                stderr_log = f.read()[-10000:]  # Last 10000 chars for better error visibility
                break
        except FileNotFoundError:
            continue
    
    if not stderr_log:
        stderr_log = "Log file not found. Start the project to generate logs."

    # Get sub-routes for this project
    sub_routes = SubRoute.query.filter_by(host_project_id=id).all()
    
    # Get all other projects for sub-route selection
    all_projects = Project.query.filter(Project.id != id).all()

    return render_template('project_details.html', 
                           project=project, 
                           stdout_log=stdout_log, 
                           stderr_log=stderr_log,
                           sub_routes=sub_routes,
                           all_projects=all_projects)

@main.route('/projects/<int:id>/stop', methods=['POST'])
@login_required
def stop_project(id):
    project = Project.query.get_or_404(id)
    if project.pid:
        try:
            import psutil
            # Get parent process
            parent = psutil.Process(project.pid)
            
            # Get all child processes
            children = parent.children(recursive=True)
            
            # Terminate parent first (gracefully)
            parent.terminate()
            
            # Terminate all children
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            # Wait for graceful termination
            gone, alive = psutil.wait_procs([parent] + children, timeout=3)
            
            # Force kill any remaining processes
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
            
            flash(f'Project {project.name} stopped successfully (killed {len(children) + 1} processes).')
        except psutil.NoSuchProcess:
            flash(f'Project {project.name} was already stopped.')
        except Exception as e:
            flash(f'Error stopping project: {e}')
        
        project.pid = None
        project.status = 'stopped'
        db.session.commit()
    else:
        flash('Project is not running.')
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/start', methods=['POST'])
@login_required
def start_project(id):
    project = Project.query.get_or_404(id)
    from app.utils.system import generate_supervisor_config, get_project_venv_python, auto_setup_project, open_firewall_port
    
    # Check if path still exists
    if not os.path.exists(project.path):
        flash(f'Project path no longer exists: {project.path}', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # AUTO-SETUP: Check and fix project environment
    venv_python = get_project_venv_python(project.path)
    gunicorn_path = None
    
    if venv_python:
        gunicorn_path = os.path.join(os.path.dirname(venv_python), 'gunicorn')
    
    # If venv missing or gunicorn missing, run auto-setup
    if not venv_python or not os.path.exists(gunicorn_path):
        flash('🔧 Auto-setup: Preparing project environment...', 'info')
        
        try:
            success, message = auto_setup_project(project.path, project.name)
            if success:
                flash(f'✓ Auto-setup complete: {message}', 'success')
                # Re-check venv after setup
                venv_python = get_project_venv_python(project.path)
            else:
                flash(f'Auto-setup failed: {message}', 'error')
                flash('Please manually create venv and install dependencies', 'warning')
                return redirect(url_for('main.project_details', id=id))
        except Exception as e:
            flash(f'Auto-setup error: {str(e)}', 'error')
            return redirect(url_for('main.project_details', id=id))
    else:
        flash('✓ Project environment ready', 'success')
    
    # Parse environment variables
    env_vars = {}
    if project.env_vars:
        try:
            env_vars = json.loads(project.env_vars)
        except:
            pass
    
    try:
        # Start the project
        flash('🚀 Starting project...', 'info')
        pid = generate_supervisor_config(project.name, project.project_type, project.path, project.port, env_vars, project.entry_point)
        
        if pid:
            project.pid = pid
            project.status = 'running'
            db.session.commit()
            
            # Open firewall port
            if open_firewall_port(project.port):
                flash(f'✓ Firewall: Port {project.port} opened', 'success')
            
            flash(f'✓ Project {project.name} is now running (PID: {pid})', 'success')
            flash(f'Access at: http://localhost:{project.port}', 'info')
        else:
            # Startup failed - attempt auto-fix
            flash('⚠ Initial startup failed. Attempting auto-fix...', 'warning')
            
            # Wait a bit for error log to be written
            time.sleep(1)
            
            error_log_path = os.path.join(project.path, f"{project.name}.err.log")
            
            # PRIORITY 1: Check for missing dependencies (with retry loop for chain dependencies)
            from app.utils.dependency_fix import auto_fix_dependencies
            
            fixed = False
            max_dependency_retries = 3
            retry_count = 0
            all_installed = []
            
            while not fixed and retry_count < max_dependency_retries:
                retry_count += 1
                
                # Wait for fresh error log if this is a retry
                if retry_count > 1:
                    time.sleep(1)
                
                dep_success, dep_message, installed = auto_fix_dependencies(project.path, error_log_path)
                
                if dep_success and installed:
                    # Dependencies were missing and now installed
                    all_installed.extend(installed)
                    
                    if retry_count == 1:
                        flash(f'🔧 Detected missing dependencies. Auto-fixing...', 'info')
                    else:
                        flash(f'🔧 Found more missing dependencies (chain dependencies)...', 'info')
                    
                    flash(f'✓ Installed: {", ".join(installed)}', 'success')
                    flash(f'🔄 Retrying startup (attempt {retry_count}/{max_dependency_retries})...', 'info')
                    
                    # Retry startup
                    pid = generate_supervisor_config(project.name, project.project_type, project.path, project.port, env_vars, project.entry_point)
                    
                    if pid:
                        project.pid = pid
                        project.status = 'running'
                        db.session.commit()
                        
                        # Open firewall port
                        if open_firewall_port(project.port):
                            flash(f'✓ Firewall: Port {project.port} opened', 'success')
                        
                        total_installed = len(set(all_installed))
                        flash(f'✓✓ Project started successfully after installing {total_installed} packages! (PID: {pid})', 'success')
                        flash(f'Packages: {", ".join(set(all_installed))}', 'info')
                        fixed = True
                        break
                    else:
                        # Still failing, loop will continue if more retries available
                        if retry_count < max_dependency_retries:
                            flash(f'Still failing, checking for more missing dependencies...', 'warning')
                        else:
                            flash(f'Max retries ({max_dependency_retries}) reached. Checking entry point...', 'warning')
                else:
                    # No more dependencies to fix
                    break
            
            # PRIORITY 2: If dependencies OK or fix didn't work, check entry point
            if not fixed:
                from app.utils.auto_fix import should_attempt_auto_fix, auto_fix_entry_point
                
                if should_attempt_auto_fix(error_log_path):
                    flash('🔧 Checking entry point...', 'info')
                    
                    # Get venv python for testing
                    venv_python = get_project_venv_python(project.path)
                    if venv_python:
                        success, new_entry_point, message = auto_fix_entry_point(
                        project.name, 
                        project.path, 
                        project.project_type, 
                        project.port, 
                        venv_python
                        )
                        
                        if success and new_entry_point:
                            # Update entry point in database
                            project.entry_point = new_entry_point
                            db.session.commit()
                            
                            flash(f'✓ {message}', 'success')
                            flash('🔄 Retrying startup with corrected entry point...', 'info')
                            
                            # Try starting again with new entry point
                            pid = generate_supervisor_config(project.name, project.project_type, project.path, project.port, env_vars, new_entry_point)
                            
                            if pid:
                                project.pid = pid
                                project.status = 'running'
                                db.session.commit()
                                flash(f'✓✓ Project started successfully (PID: {pid})', 'success')
                                flash(f'Updated entry point: {new_entry_point}', 'info')
                            else:
                                flash('Entry point updated but startup still failed. Check logs.', 'error')
                        else:
                            flash(f'Auto-fix failed: {message}', 'error')
                    else:
                        flash('Cannot auto-fix: No virtual environment found', 'error')
                else:
                    flash('Failed to start project. Check logs tab for details.', 'error')
    except Exception as e:
        flash(f'Error starting project: {str(e)}', 'error')
        
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/delete', methods=['POST'])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    
    # Stop if running
    if project.pid:
        try:
            os.kill(project.pid, signal.SIGTERM)
        except:
            pass
    
    # Delete sub-routes where this project is mounted (as a child)
    mounted_routes = SubRoute.query.filter_by(mounted_project_id=id).all()
    for sr in mounted_routes:
        db.session.delete(sr)
    
    # Delete sub-routes where this project is the host (as a parent)
    host_routes = SubRoute.query.filter_by(host_project_id=id).all()
    for sr in host_routes:
        db.session.delete(sr)
    
    db.session.delete(project)
    db.session.commit()
    
    if mounted_routes or host_routes:
        flash(f'Project {project.name} and {len(mounted_routes) + len(host_routes)} related sub-route(s) deleted.')
    else:
        flash(f'Project {project.name} deleted.')
    return redirect(url_for('main.dashboard'))

@main.route('/projects/<int:id>/edit', methods=['POST'])
@login_required
def edit_project(id):
    project = Project.query.get_or_404(id)
    
    new_port = request.form.get('port')
    new_path = request.form.get('path')
    
    # Validate port if changed
    if new_port and int(new_port) != project.port:
        existing = Project.query.filter_by(port=new_port).first()
        if existing and existing.id != project.id:
            flash(f'Port {new_port} is already in use by another project', 'error')
            return redirect(url_for('main.project_details', id=id))
    
    # Validate path if changed
    if new_path and new_path != project.path:
        if not os.path.exists(new_path):
            flash(f'Project path does not exist: {new_path}', 'error')
            return redirect(url_for('main.project_details', id=id))
    
    try:
        project.domain = request.form.get('domain')
        project.port = new_port
        project.path = new_path
        project.entry_point = request.form.get('entry_point')
        project.ssl_enabled = 'ssl_enabled' in request.form
        
        db.session.commit()
        
        # Re-generate configs
        from app.utils.system import generate_nginx_config, reload_nginx
        if project.domain:
            generate_nginx_config(project.name, project.domain, project.port, project.ssl_enabled)
            reload_nginx()
            
        flash('Project settings updated. Restart project to apply changes.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating project: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/env', methods=['POST'])
@login_required
def update_env(id):
    project = Project.query.get_or_404(id)
    env_json = request.form.get('env_vars')
    
    try:
        # Validate JSON
        json.loads(env_json)
        project.env_vars = env_json
        db.session.commit()
        flash('Environment variables updated. Restart project to apply.')
    except ValueError:
        flash('Invalid JSON format for environment variables.')
        
    return redirect(url_for('main.project_details', id=id))

@main.route('/upload-project', methods=['GET', 'POST'])
@login_required
def upload_project():
    if request.method == 'POST':
        project_mode = request.form.get('project_mode', 'new')
        existing_project_id = request.form.get('existing_project')
        project_name = request.form.get('project_name')
        port = request.form.get('port')
        domain = request.form.get('domain')
        project_type = request.form.get('project_type', 'flask')
        enable_ssl = 'enable_ssl' in request.form
        ssl_email = request.form.get('ssl_email')
        
        # Handle project selection based on mode
        existing_project = None
        if project_mode == 'update' and existing_project_id:
            # Update mode - get project by ID
            existing_project = Project.query.get(int(existing_project_id))
            if not existing_project:
                flash('Selected project not found', 'error')
                return redirect(url_for('main.upload_project'))
            project_name = existing_project.name
        else:
            # New mode - check by name
            if not project_name:
                flash('Project name is required', 'error')
                return redirect(url_for('main.upload_project'))
            existing_project = Project.query.filter_by(name=project_name).first()
        
        is_update = existing_project is not None
        
        # Validation
        if not port:
            flash('Port is required', 'error')
            return redirect(url_for('main.upload_project'))
        
        # If updating, don't check port conflict with self
        if not is_update:
            # Check if port is in use
            if Project.query.filter_by(port=port).first():
                flash(f'Port {port} is already in use', 'error')
                return redirect(url_for('main.upload_project'))
        else:
            # Check if port is in use by another project
            port_conflict = Project.query.filter(
                Project.port == port,
                Project.id != existing_project.id
            ).first()
            if port_conflict:
                flash(f'Port {port} is already in use by another project', 'error')
                return redirect(url_for('main.upload_project'))
        
        # Handle file upload
        if 'files[]' not in request.files:
            flash('No files uploaded', 'error')
            return redirect(url_for('main.upload_project'))
        
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            flash('No files selected', 'error')
            return redirect(url_for('main.upload_project'))
        
        try:
            # If updating existing project, create backup first
            if is_update:
                from app.utils.version_manager import VersionManager
                vm = VersionManager()
                
                # Stop project if running
                if existing_project.status == 'running':
                    flash('🛑 Stopping running project for update...', 'info')
                    stop_project_process(existing_project)
                
                # Create backup
                try:
                    version = vm.create_backup(
                        existing_project,
                        description=f'Backup before update at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                    )
                    flash(f'✓ Backup created: Version {version.version_number}', 'success')
                except Exception as e:
                    flash(f'⚠ Warning: Could not create backup: {str(e)}', 'warning')
            
            # Create project directory
            project_path = os.path.join(UPLOAD_FOLDER, secure_filename(project_name))
            if os.path.exists(project_path):
                shutil.rmtree(project_path)
            os.makedirs(project_path)
            
            # Save uploaded files maintaining structure
            for file in files:
                if file and file.filename:
                    # Get relative path from the uploaded file
                    filename = file.filename
                    # Secure the filename but maintain directory structure
                    filepath = os.path.join(project_path, filename)
                    
                    # Create directories if needed
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    # Save the file
                    file.save(filepath)
            
            # Smart path detection: If upload created a single subdirectory containing the actual project, use it
            subdirs = [d for d in os.listdir(project_path) if os.path.isdir(os.path.join(project_path, d)) and not d.startswith('.')]
            if len(subdirs) == 1:
                # Check if this subdirectory contains Python files or common project files
                subdir_path = os.path.join(project_path, subdirs[0])
                has_python = any(f.endswith('.py') for f in os.listdir(subdir_path) if os.path.isfile(os.path.join(subdir_path, f)))
                if has_python:
                    print(f"[UPLOAD] Detected nested project structure, using subdirectory: {subdirs[0]}")
                    project_path = subdir_path
            
            # Create or update project in database
            from app.utils.system import detect_entry_point, auto_setup_project
            entry_point = detect_entry_point(project_path, project_type)
            
            if is_update:
                # Update existing project
                project = existing_project
                project.domain = domain or project.domain
                project.port = port
                project.path = project_path
                project.project_type = project_type
                project.entry_point = entry_point
                project.status = 'stopped'
                db.session.commit()
                flash(f'Project {project_name} updated successfully!', 'success')
            else:
                # Create new project
                project = Project(
                    name=project_name,
                    domain=domain,
                    port=port,
                    path=project_path,
                    project_type=project_type,
                    entry_point=entry_point,
                    ssl_enabled=False,
                    status='stopped'
                )
                db.session.add(project)
                db.session.commit()
            
            # AUTO-SETUP: Prepare project environment
            flash('🔧 Setting up project environment...', 'info')
            try:
                success, message = auto_setup_project(project_path, project_name)
                if success:
                    flash(f'✓ {message}', 'success')
                else:
                    flash(f'⚠ Auto-setup warning: {message}', 'warning')
            except Exception as e:
                flash(f'⚠ Auto-setup warning: {str(e)}', 'warning')
            
            # Setup SSL if requested
            if enable_ssl and domain and ssl_email:
                from app.utils.ssl_manager import request_ssl_certificate, install_certbot
                install_certbot()
                if request_ssl_certificate(domain, ssl_email):
                    project.ssl_enabled = True
                    db.session.commit()
                    flash(f'SSL certificate obtained for {domain}', 'success')
                else:
                    flash('SSL certificate request failed. You can try again later.', 'warning')
            
            # Configure nginx if domain provided
            if domain:
                from app.utils.system import generate_nginx_config, reload_nginx, open_firewall_port
                generate_nginx_config(project_name, domain, port, project.ssl_enabled)
                reload_nginx()
            else:
                # Open firewall port even without domain
                from app.utils.system import open_firewall_port
            
            # Open firewall port for direct access
            if open_firewall_port(port):
                flash(f'✓ Firewall: Port {port} opened', 'success')
            
            flash(f'Project {project_name} uploaded successfully! Start it from the project page.', 'success')
            return redirect(url_for('main.project_details', id=project.id))
            
        except Exception as e:
            db.session.rollback()
            if os.path.exists(project_path):
                shutil.rmtree(project_path)
            flash(f'Error uploading project: {str(e)}', 'error')
            return redirect(url_for('main.upload_project'))
    
    projects = Project.query.all()
    return render_template('upload_project.html', projects=projects)

@main.route('/projects/<int:id>/versions')
@login_required
def project_versions(id):
    """Proje versiyonlarını listeler"""
    project = Project.query.get_or_404(id)
    from app.utils.version_manager import VersionManager
    vm = VersionManager()
    
    versions = vm.get_project_versions(project.id)
    
    # Her versiyon için boyut bilgisini ekle
    version_data = []
    for version in versions:
        size = vm.get_version_size(version.id)
        size_mb = size / (1024 * 1024)
        version_data.append({
            'version': version,
            'size_mb': round(size_mb, 2)
        })
    
    return render_template('project_versions.html', project=project, version_data=version_data)

@main.route('/projects/<int:id>/versions/<int:version_id>/restore', methods=['POST'])
@login_required
def restore_version(id, version_id):
    """Belirtilen versiyonu geri yükler"""
    project = Project.query.get_or_404(id)
    from app.utils.version_manager import VersionManager
    vm = VersionManager()
    
    try:
        vm.restore_version(version_id, stop_project=True)
        flash(f'✓ Project restored to version {version_id} successfully!', 'success')
    except Exception as e:
        flash(f'Error restoring version: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/versions/<int:version_id>/delete', methods=['POST'])
@login_required
def delete_version(id, version_id):
    """Bir versiyonu siler"""
    project = Project.query.get_or_404(id)
    from app.utils.version_manager import VersionManager
    vm = VersionManager()
    
    try:
        vm.delete_version(version_id)
        flash('Version deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting version: {str(e)}', 'error')
    
    return redirect(url_for('main.project_versions', id=id))

@main.route('/projects/<int:id>/versions/cleanup', methods=['POST'])
@login_required
def cleanup_versions(id):
    """Eski versiyonları temizler"""
    project = Project.query.get_or_404(id)
    keep_count = int(request.form.get('keep_count', 5))
    
    from app.utils.version_manager import VersionManager
    vm = VersionManager()
    
    try:
        deleted = vm.cleanup_old_versions(project.id, keep_count)
        flash(f'✓ Cleaned up {deleted} old version(s). Kept {keep_count} most recent.', 'success')
    except Exception as e:
        flash(f'Error cleaning up versions: {str(e)}', 'error')
    
    return redirect(url_for('main.project_versions', id=id))

@main.route('/projects/<int:id>/request-ssl', methods=['POST'])
@login_required
def request_ssl(id):
    project = Project.query.get_or_404(id)
    
    if not project.domain:
        flash('Cannot request SSL: No domain configured', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    ssl_email = request.form.get('ssl_email')
    if not ssl_email:
        flash('Email address is required for SSL certificate', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    try:
        from app.utils.ssl_manager import request_ssl_certificate, install_certbot
        
        # Install certbot if needed
        install_certbot()
        
        # Request certificate
        if request_ssl_certificate(project.domain, ssl_email):
            project.ssl_enabled = True
            db.session.commit()
            
            # Regenerate nginx config with SSL
            from app.utils.system import generate_nginx_config, reload_nginx
            generate_nginx_config(project.name, project.domain, project.port, True)
            reload_nginx()
            
            flash(f'SSL certificate obtained successfully for {project.domain}!', 'success')
        else:
            flash('Failed to obtain SSL certificate. Check logs for details.', 'error')
    except Exception as e:
        flash(f'Error requesting SSL certificate: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/revoke-ssl', methods=['POST'])
@login_required
def revoke_ssl(id):
    project = Project.query.get_or_404(id)
    
    if not project.ssl_enabled:
        flash('No SSL certificate to revoke', 'warning')
        return redirect(url_for('main.project_details', id=id))
    
    try:
        from app.utils.ssl_manager import revoke_ssl_certificate
        from app.utils.system import generate_nginx_config, reload_nginx
        
        if revoke_ssl_certificate(project.domain):
            project.ssl_enabled = False
            db.session.commit()
            
            # Regenerate nginx config without SSL
            generate_nginx_config(project.name, project.domain, project.port, False)
            reload_nginx()
            
            flash('SSL certificate revoked successfully', 'success')
        else:
            flash('Failed to revoke SSL certificate', 'error')
    except Exception as e:
        flash(f'Error revoking SSL certificate: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/system-status')
@login_required
def system_status():
    import psutil
    import subprocess
    
    # Get system info
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Get network connections and listening ports
    listening_ports = []
    try:
        connections = psutil.net_connections(kind='inet')
        port_map = {}
        
        for conn in connections:
            if conn.status == 'LISTEN' and conn.laddr:
                port = conn.laddr.port
                if port not in port_map:
                    # Try to get process info
                    try:
                        if conn.pid:
                            proc = psutil.Process(conn.pid)
                            process_name = proc.name()
                            process_cmdline = ' '.join(proc.cmdline()[:3])  # First 3 args
                        else:
                            process_name = 'Unknown'
                            process_cmdline = ''
                    except:
                        process_name = 'Unknown'
                        process_cmdline = ''
                    
                    port_map[port] = {
                        'port': port,
                        'process': process_name,
                        'cmdline': process_cmdline,
                        'pid': conn.pid or 'N/A'
                    }
        
        listening_ports = sorted(port_map.values(), key=lambda x: x['port'])
    except:
        pass
    
    # Get all projects with their ports
    projects = Project.query.all()
    project_ports = {p.port: p.name for p in projects}
    
    # Add project info to ports
    for port_info in listening_ports:
        port_info['project'] = project_ports.get(str(port_info['port']), None)
    
    # System uptime
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_minutes = int((uptime_seconds % 3600) // 60)
    
    system_info = {
        'cpu_percent': cpu_percent,
        'cpu_count': psutil.cpu_count(),
        'memory_total': memory.total,
        'memory_used': memory.used,
        'memory_percent': memory.percent,
        'disk_total': disk.total,
        'disk_used': disk.used,
        'disk_percent': disk.percent,
        'uptime': f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
    }
    
    return render_template('system_status.html', 
                         system_info=system_info,
                         listening_ports=listening_ports,
                         projects=projects)

@main.route('/kill-process/<int:pid>', methods=['POST'])
@login_required
def kill_process(pid):
    try:
        import psutil
        process = psutil.Process(pid)
        process_name = process.name()
        process.kill()
        flash(f'Process {process_name} (PID: {pid}) terminated successfully', 'success')
    except psutil.NoSuchProcess:
        flash(f'Process with PID {pid} not found', 'error')
    except Exception as e:
        flash(f'Error killing process: {str(e)}', 'error')
    
    return redirect(url_for('main.system_status'))

@main.route('/execute-command', methods=['POST'])
@login_required
def execute_command():
    command = request.form.get('command', '')
    
    if not command:
        return jsonify({'success': False, 'error': 'No command provided'})
    
    try:
        import subprocess
        import os
        
        # Set up environment with proper PATH
        env = os.environ.copy()
        env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            executable='/bin/bash'
        )
        
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr,
            'returncode': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Command timeout (30s)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/terminal')
@login_required
def terminal():
    return render_template('terminal.html')

@main.route('/service-control/<action>/<service_name>', methods=['POST'])
@login_required
def service_control(action, service_name):
    if action not in ['start', 'stop', 'restart', 'status']:
        flash('Invalid action', 'error')
        return redirect(url_for('main.system_status'))
    
    try:
        import subprocess
        result = subprocess.run(
            ['systemctl', action, service_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            flash(f'Service {service_name} {action}ed successfully', 'success')
        else:
            flash(f'Failed to {action} {service_name}: {result.stderr}', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('main.system_status'))

@main.route('/api/services')
@login_required
def get_services():
    try:
        import subprocess
        result = subprocess.run(
            ['systemctl', 'list-units', '--type=service', '--all', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        services = []
        for line in result.stdout.split('\n')[1:]:
            if '.service' in line:
                parts = line.split()
                if len(parts) >= 4:
                    service_name = parts[0].replace('.service', '')
                    load_state = parts[1] if len(parts) > 1 else 'unknown'
                    active_state = parts[2] if len(parts) > 2 else 'unknown'
                    sub_state = parts[3] if len(parts) > 3 else 'unknown'
                    description = ' '.join(parts[4:]) if len(parts) > 4 else ''
                    
                    services.append({
                        'name': service_name,
                        'load': load_state,
                        'active': active_state,
                        'sub': sub_state,
                        'description': description
                    })
        
        return jsonify({'success': True, 'services': services})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/service-logs/<service_name>')
@login_required
def get_service_logs(service_name):
    try:
        import subprocess
        result = subprocess.run(
            ['journalctl', '-u', service_name, '-n', '100', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return jsonify({
            'success': True,
            'logs': result.stdout,
            'service': service_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/file-browser')
@login_required
def file_browser():
    import os
    path = request.args.get('path', '/opt/vdspanel')
    
    # Security: prevent directory traversal outside safe zones
    safe_paths = ['/opt/vdspanel', '/var/log', '/etc/nginx', '/home']
    is_safe = any(os.path.abspath(path).startswith(sp) for sp in safe_paths)
    
    if not is_safe:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        items = []
        if not os.path.exists(path):
            return jsonify({'success': False, 'error': f'Path does not exist: {path}'})
        
        if not os.path.isdir(path):
            return jsonify({'success': False, 'error': f'Not a directory: {path}'})
        
        try:
            dir_items = os.listdir(path)
        except PermissionError:
            return jsonify({'success': False, 'error': f'Permission denied: {path}'})
        
        for item in sorted(dir_items):
            item_path = os.path.join(path, item)
            try:
                stat = os.stat(item_path)
                items.append({
                    'name': item,
                    'path': item_path,
                    'is_dir': os.path.isdir(item_path),
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except (PermissionError, OSError):
                # Skip files we can't read
                continue
        
        parent = os.path.dirname(path) if path != '/' else None
        return jsonify({
            'success': True,
            'path': path,
            'parent': parent,
            'items': items
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/file-content')
@login_required
def get_file_content():
    import os
    filepath = request.args.get('path', '')
    
    # Security check
    safe_paths = ['/opt/vdspanel', '/var/log', '/etc/nginx']
    is_safe = any(os.path.abspath(filepath).startswith(sp) for sp in safe_paths)
    
    if not is_safe:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        if os.path.isfile(filepath):
            # Check file size (max 1MB)
            if os.path.getsize(filepath) > 1024 * 1024:
                return jsonify({'success': False, 'error': 'File too large (>1MB)'})
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return jsonify({
                'success': True,
                'content': content,
                'path': filepath
            })
        else:
            return jsonify({'success': False, 'error': 'Not a file'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/system-logs')
@login_required
def get_system_logs():
    log_type = request.args.get('type', 'syslog')
    lines = request.args.get('lines', '100')
    
    log_files = {
        'syslog': '/var/log/syslog',
        'auth': '/var/log/auth.log',
        'nginx-access': '/var/log/nginx/access.log',
        'nginx-error': '/var/log/nginx/error.log'
    }
    
    log_file = log_files.get(log_type)
    if not log_file:
        return jsonify({'success': False, 'error': 'Invalid log type'})
    
    try:
        import subprocess
        result = subprocess.run(
            ['tail', '-n', lines, log_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        return jsonify({
            'success': True,
            'logs': result.stdout,
            'type': log_type
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@main.route('/change-password', methods=['POST'])
@login_required
def change_password():
    from werkzeug.security import check_password_hash, generate_password_hash
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('main.settings'))
    
    user = User.query.filter_by(username=current_user.username).first()
    
    if not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('main.settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('main.settings'))
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long', 'error')
        return redirect(url_for('main.settings'))
    
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('main.settings'))

def generate_nginx_config(project, sub_routes=None):
    """Generate Nginx configuration for a project with domain and sub-routes"""
    if not project.domain:
        return None
    
    # Determine upstream based on project type
    if project.project_type == 'nodejs':
        upstream_port = project.port or 3000
    elif project.project_type == 'python':
        upstream_port = project.port or 5000
    elif project.project_type == 'php':
        upstream_port = 9000  # PHP-FPM
    else:
        upstream_port = project.port or 8000
    
    # Check SSL certificate availability
    ssl_available = False
    if project.ssl_enabled:
        cert_path = f"/etc/letsencrypt/live/{project.domain}/fullchain.pem"
        key_path = f"/etc/letsencrypt/live/{project.domain}/privkey.pem"
        ssl_available = os.path.exists(cert_path) and os.path.exists(key_path)
    
    # Generate sub-route location blocks
    sub_route_blocks = ""
    if sub_routes:
        for sr in sub_routes:
            mounted_port = sr.mounted_project.port
            route_path = sr.route_path
            
            if sr.strip_prefix:
                # Strip the prefix - rewrite URL before proxying
                sub_route_blocks += f"""
    # Sub-route: {route_path} -> {sr.mounted_project.name} (port {mounted_port})
    location {route_path}/ {{
        rewrite ^{route_path}/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:{mounted_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix {route_path};
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    # Exact match for {route_path} without trailing slash
    location = {route_path} {{
        return 301 {route_path}/;
    }}
"""
            else:
                # Keep the prefix - pass URL as-is
                sub_route_blocks += f"""
    # Sub-route: {route_path} -> {sr.mounted_project.name} (port {mounted_port})
    location {route_path} {{
        proxy_pass http://127.0.0.1:{mounted_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
"""
    
    # Build location block (reusable for both HTTP and HTTPS)
    location_block = f"""{sub_route_blocks}
    location / {{
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}"""
    
    if ssl_available:
        # SSL config with HTTP to HTTPS redirect
        config = f"""# Auto-generated by VDS Panel for {project.name}
# SSL Certificate: Active

# HTTP -> HTTPS redirect
server {{
    listen 80;
    server_name {project.domain} www.{project.domain};
    return 301 https://$server_name$request_uri;
}}

# HTTPS server
server {{
    listen 443 ssl http2;
    server_name {project.domain} www.{project.domain};
    
    ssl_certificate /etc/letsencrypt/live/{project.domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{project.domain}/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    
    access_log /var/log/nginx/{project.name}_access.log;
    error_log /var/log/nginx/{project.name}_error.log;
{location_block}
}}
"""
    else:
        # HTTP only config
        config = f"""# Auto-generated by VDS Panel for {project.name}
# SSL Certificate: Not available (HTTP only)

server {{
    listen 80;
    server_name {project.domain} www.{project.domain};
    
    access_log /var/log/nginx/{project.name}_access.log;
    error_log /var/log/nginx/{project.name}_error.log;
{location_block}
}}
"""
    return config

@main.route('/configure-nginx/<int:project_id>', methods=['POST'])
@login_required
def configure_nginx(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not project.domain:
        flash('Project does not have a domain configured', 'error')
        return redirect(url_for('main.project_details', id=project_id))
    
    try:
        import subprocess
        import os
        
        # Check SSL certificate availability
        ssl_available = False
        if project.ssl_enabled:
            cert_path = f"/etc/letsencrypt/live/{project.domain}/fullchain.pem"
            key_path = f"/etc/letsencrypt/live/{project.domain}/privkey.pem"
            ssl_available = os.path.exists(cert_path) and os.path.exists(key_path)
            
            if not ssl_available:
                # SSL enabled but certificate not found - disable SSL
                project.ssl_enabled = False
                db.session.commit()
                flash(f'⚠ SSL certificate not found for {project.domain}. SSL disabled. Configure HTTP only.', 'warning')
        
        # Get sub-routes for this project
        sub_routes = SubRoute.query.filter_by(host_project_id=project_id).all()
        
        # Generate config with sub-routes
        config_content = generate_nginx_config(project, sub_routes)
        
        # Write config file directly (Flask runs as root via systemd)
        config_path = f'/etc/nginx/sites-available/{project.name}'
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Create symlink to sites-enabled
        enabled_path = f'/etc/nginx/sites-enabled/{project.name}'
        if os.path.exists(enabled_path):
            os.remove(enabled_path)
        os.symlink(config_path, enabled_path)
        
        # Test nginx configuration
        test_result = subprocess.run(
            ['/usr/sbin/nginx', '-t'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if test_result.returncode != 0:
            flash(f'Nginx configuration test failed: {test_result.stderr}', 'error')
            return redirect(url_for('main.project_details', id=project_id))
        
        # Reload nginx
        reload_result = subprocess.run(
            ['/usr/bin/systemctl', 'reload', 'nginx'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if reload_result.returncode == 0:
            if ssl_available:
                flash(f'✓ Nginx configured with SSL for {project.domain}', 'success')
            else:
                flash(f'✓ Nginx configured for {project.domain} (HTTP only)', 'success')
            
            # Show sub-routes info
            if sub_routes:
                flash(f'✓ {len(sub_routes)} sub-route(s) configured', 'info')
        else:
            flash(f'Failed to reload Nginx: {reload_result.stderr}', 'error')
            
    except Exception as e:
        flash(f'Error configuring Nginx: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/remove-nginx/<int:project_id>', methods=['POST'])
@login_required
def remove_nginx(project_id):
    project = Project.query.get_or_404(project_id)
    
    try:
        import subprocess
        import os
        
        config_path = f'/etc/nginx/sites-available/{project.name}'
        enabled_path = f'/etc/nginx/sites-enabled/{project.name}'
        
        # Remove symlink
        if os.path.exists(enabled_path):
            os.remove(enabled_path)
        
        # Remove config file
        if os.path.exists(config_path):
            os.remove(config_path)
        
        # Reload nginx
        subprocess.run(['/usr/bin/systemctl', 'reload', 'nginx'], timeout=10)
        
        flash(f'Nginx configuration removed for {project.name}', 'success')
    except Exception as e:
        flash(f'Error removing Nginx config: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/update-domain/<int:project_id>', methods=['POST'])
@login_required
def update_domain(project_id):
    project = Project.query.get_or_404(project_id)
    
    domain = request.form.get('domain', '').strip()
    
    if domain:
        # Validate domain format
        import re
        domain_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, domain):
            flash('Invalid domain format', 'error')
            return redirect(url_for('main.project_details', id=project_id))
    
    old_domain = project.domain
    project.domain = domain if domain else None
    
    try:
        db.session.commit()
        
        if domain:
            flash(f'Domain updated to {domain}. Click "Configure Nginx" to activate.', 'success')
        else:
            flash('Domain removed', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating domain: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=project_id))

# ==================== PROJECT FILE MANAGEMENT ====================

@main.route('/projects/<int:id>/files')
@login_required
def project_files(id):
    """Proje dosyalarını görüntüleme sayfası"""
    project = Project.query.get_or_404(id)
    return render_template('project_files.html', project=project)

@main.route('/api/projects/<int:id>/files')
@login_required
def api_project_files(id):
    """Proje dosyalarını listele"""
    project = Project.query.get_or_404(id)
    path = request.args.get('path', '')
    
    # Base path
    base_path = project.path
    
    # Full path
    if path:
        full_path = os.path.normpath(os.path.join(base_path, path))
        # Güvenlik: Proje dizini dışına çıkılmasını engelle
        if not full_path.startswith(base_path):
            return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    else:
        full_path = base_path
    
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'Dizin bulunamadı'})
    
    try:
        items = []
        for item in sorted(os.listdir(full_path)):
            item_path = os.path.join(full_path, item)
            relative_path = os.path.relpath(item_path, base_path)
            
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                
                # Dosya uzantısı
                ext = os.path.splitext(item)[1].lower() if not is_dir else ''
                
                items.append({
                    'name': item,
                    'path': relative_path,
                    'is_dir': is_dir,
                    'size': stat.st_size if not is_dir else 0,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'extension': ext
                })
            except (PermissionError, OSError):
                continue
        
        # Dizinleri önce, sonra dosyaları sırala
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
        return jsonify({
            'success': True,
            'path': os.path.relpath(full_path, base_path) if full_path != base_path else '',
            'items': items,
            'base_path': base_path
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/projects/<int:id>/files/content')
@login_required
def api_project_file_content(id):
    """Dosya içeriğini oku"""
    project = Project.query.get_or_404(id)
    file_path = request.args.get('path', '')
    
    if not file_path:
        return jsonify({'success': False, 'error': 'Dosya yolu gerekli'})
    
    full_path = os.path.normpath(os.path.join(project.path, file_path))
    
    # Güvenlik kontrolü
    if not full_path.startswith(project.path):
        return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    
    if not os.path.isfile(full_path):
        return jsonify({'success': False, 'error': 'Dosya bulunamadı'})
    
    # Boyut kontrolü (max 2MB)
    if os.path.getsize(full_path) > 2 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'Dosya çok büyük (>2MB)'})
    
    try:
        # Binary dosyaları kontrol et
        binary_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.jpg', '.jpeg', '.png', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz'}
        ext = os.path.splitext(full_path)[1].lower()
        
        if ext in binary_extensions:
            return jsonify({'success': False, 'error': 'Binary dosyalar düzenlenemez', 'binary': True})
        
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content,
            'path': file_path,
            'name': os.path.basename(full_path)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/projects/<int:id>/files/save', methods=['POST'])
@login_required
def api_project_file_save(id):
    """Dosya içeriğini kaydet (Update)"""
    project = Project.query.get_or_404(id)
    data = request.get_json()
    
    file_path = data.get('path', '')
    content = data.get('content', '')
    
    if not file_path:
        return jsonify({'success': False, 'error': 'Dosya yolu gerekli'})
    
    full_path = os.path.normpath(os.path.join(project.path, file_path))
    
    # Güvenlik kontrolü
    if not full_path.startswith(project.path):
        return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'message': 'Dosya kaydedildi'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/projects/<int:id>/files/create', methods=['POST'])
@login_required
def api_project_file_create(id):
    """Yeni dosya veya dizin oluştur (Create)"""
    project = Project.query.get_or_404(id)
    data = request.get_json()
    
    name = data.get('name', '')
    parent_path = data.get('path', '')
    is_dir = data.get('is_dir', False)
    content = data.get('content', '')
    
    if not name:
        return jsonify({'success': False, 'error': 'İsim gerekli'})
    
    # Güvenlik: Tehlikeli karakterleri kontrol et
    if '..' in name or '/' in name or '\\' in name:
        return jsonify({'success': False, 'error': 'Geçersiz dosya adı'})
    
    full_parent = os.path.normpath(os.path.join(project.path, parent_path)) if parent_path else project.path
    full_path = os.path.join(full_parent, name)
    
    # Güvenlik kontrolü
    if not full_path.startswith(project.path):
        return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    
    if os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'Bu isimde bir dosya/dizin zaten var'})
    
    try:
        if is_dir:
            os.makedirs(full_path)
            return jsonify({'success': True, 'message': 'Dizin oluşturuldu'})
        else:
            # Parent dizinin var olduğundan emin ol
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify({'success': True, 'message': 'Dosya oluşturuldu'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/projects/<int:id>/files/delete', methods=['POST'])
@login_required
def api_project_file_delete(id):
    """Dosya veya dizin sil (Delete)"""
    project = Project.query.get_or_404(id)
    data = request.get_json()
    
    file_path = data.get('path', '')
    
    if not file_path:
        return jsonify({'success': False, 'error': 'Dosya yolu gerekli'})
    
    full_path = os.path.normpath(os.path.join(project.path, file_path))
    
    # Güvenlik kontrolü
    if not full_path.startswith(project.path):
        return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    
    # Proje kök dizininin silinmesini engelle
    if full_path == project.path:
        return jsonify({'success': False, 'error': 'Proje kök dizini silinemez'})
    
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'Dosya/dizin bulunamadı'})
    
    try:
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
            return jsonify({'success': True, 'message': 'Dizin silindi'})
        else:
            os.remove(full_path)
            return jsonify({'success': True, 'message': 'Dosya silindi'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/projects/<int:id>/files/rename', methods=['POST'])
@login_required
def api_project_file_rename(id):
    """Dosya veya dizini yeniden adlandır"""
    project = Project.query.get_or_404(id)
    data = request.get_json()
    
    old_path = data.get('old_path', '')
    new_name = data.get('new_name', '')
    
    if not old_path or not new_name:
        return jsonify({'success': False, 'error': 'Eski yol ve yeni isim gerekli'})
    
    # Güvenlik: Tehlikeli karakterleri kontrol et
    if '..' in new_name or '/' in new_name or '\\' in new_name:
        return jsonify({'success': False, 'error': 'Geçersiz dosya adı'})
    
    full_old_path = os.path.normpath(os.path.join(project.path, old_path))
    new_path = os.path.join(os.path.dirname(full_old_path), new_name)
    
    # Güvenlik kontrolü
    if not full_old_path.startswith(project.path) or not new_path.startswith(project.path):
        return jsonify({'success': False, 'error': 'Erişim reddedildi'})
    
    if not os.path.exists(full_old_path):
        return jsonify({'success': False, 'error': 'Dosya/dizin bulunamadı'})
    
    if os.path.exists(new_path):
        return jsonify({'success': False, 'error': 'Bu isimde bir dosya/dizin zaten var'})
    
    try:
        os.rename(full_old_path, new_path)
        return jsonify({
            'success': True,
            'message': 'Yeniden adlandırıldı',
            'new_path': os.path.relpath(new_path, project.path)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# =====================
# Sub-Route Management
# =====================

@main.route('/projects/<int:id>/sub-routes', methods=['GET'])
@login_required
def get_sub_routes(id):
    """Get all sub-routes for a project"""
    project = Project.query.get_or_404(id)
    sub_routes = SubRoute.query.filter_by(host_project_id=id).all()
    return jsonify({
        'success': True,
        'sub_routes': [{
            'id': sr.id,
            'route_path': sr.route_path,
            'mounted_project_id': sr.mounted_project_id,
            'mounted_project_name': sr.mounted_project.name,
            'mounted_project_port': sr.mounted_project.port,
            'strip_prefix': sr.strip_prefix
        } for sr in sub_routes]
    })

@main.route('/projects/<int:id>/sub-routes/add', methods=['POST'])
@login_required
def add_sub_route(id):
    """Add a sub-route to mount another project on a specific path"""
    host_project = Project.query.get_or_404(id)
    
    if not host_project.domain:
        flash('Please configure a domain for this project before adding sub-routes', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    mounted_project_id = request.form.get('mounted_project_id')
    route_path = request.form.get('route_path', '').strip()
    strip_prefix = 'strip_prefix' in request.form
    
    if not mounted_project_id or not route_path:
        flash('Project and route path are required', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    mounted_project = Project.query.get(mounted_project_id)
    if not mounted_project:
        flash('Selected project not found', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    if mounted_project.id == host_project.id:
        flash('A project cannot be mounted to itself', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Normalize route path
    if not route_path.startswith('/'):
        route_path = '/' + route_path
    route_path = route_path.rstrip('/')
    
    # Check for duplicate
    existing = SubRoute.query.filter_by(
        host_project_id=id,
        route_path=route_path
    ).first()
    if existing:
        flash(f'This path ({route_path}) is already in use', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    try:
        sub_route = SubRoute(
            host_project_id=id,
            mounted_project_id=mounted_project.id,
            route_path=route_path,
            strip_prefix=strip_prefix
        )
        db.session.add(sub_route)
        db.session.commit()
        
        flash(f'Sub-route added: {route_path} -> {mounted_project.name}', 'success')
        flash('Click "Configure Nginx" to apply changes', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding sub-route: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/sub-routes/<int:sub_route_id>/delete', methods=['POST'])
@login_required
def delete_sub_route(id, sub_route_id):
    """Delete a sub-route"""
    project = Project.query.get_or_404(id)
    sub_route = SubRoute.query.get_or_404(sub_route_id)
    
    if sub_route.host_project_id != id:
        flash('This sub-route does not belong to this project', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    try:
        route_path = sub_route.route_path
        db.session.delete(sub_route)
        db.session.commit()
        flash(f'Sub-route deleted: {route_path}', 'success')
        flash('Click "Configure Nginx" to apply changes', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting sub-route: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))

@main.route('/projects/<int:id>/sub-routes/add-with-new-project', methods=['POST'])
@login_required
def add_sub_route_with_new_project(id):
    """Create a new project and add it as a sub-route"""
    host_project = Project.query.get_or_404(id)
    
    if not host_project.domain:
        flash('Please configure a domain for this project before adding sub-routes', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Get form data for new project
    route_path = request.form.get('route_path', '').strip()
    new_project_name = request.form.get('new_project_name', '').strip()
    new_project_type = request.form.get('new_project_type', 'python')
    new_project_port = request.form.get('new_project_port', '').strip()
    new_project_entry = request.form.get('new_project_entry', '').strip()
    strip_prefix = 'new_strip_prefix' in request.form
    
    # Validate required fields
    if not route_path or not new_project_name or not new_project_port:
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    try:
        port = int(new_project_port)
        if port < 1024 or port > 65535:
            flash('Port must be between 1024 and 65535', 'error')
            return redirect(url_for('main.project_details', id=id))
    except ValueError:
        flash('Invalid port number', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Check if project name already exists
    existing_project = Project.query.filter_by(name=new_project_name).first()
    if existing_project:
        flash(f'A project named "{new_project_name}" already exists', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Check if port is already in use
    port_in_use = Project.query.filter_by(port=port).first()
    if port_in_use:
        flash(f'Port {port} is already in use by project "{port_in_use.name}"', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Normalize route path
    if not route_path.startswith('/'):
        route_path = '/' + route_path
    route_path = route_path.rstrip('/')
    
    # Check for duplicate route
    existing_route = SubRoute.query.filter_by(
        host_project_id=id,
        route_path=route_path
    ).first()
    if existing_route:
        flash(f'This path ({route_path}) is already in use', 'error')
        return redirect(url_for('main.project_details', id=id))
    
    # Auto-generate project path based on host project's directory
    host_project_dir = os.path.dirname(host_project.path.rstrip('/'))
    new_project_path = os.path.join(host_project_dir, new_project_name)
    
    try:
        # Create project directory
        os.makedirs(new_project_path, exist_ok=True)
        
        # Create the new project (without domain - it will be accessed via sub-route)
        new_project = Project(
            name=new_project_name,
            domain=None,  # No domain - accessed via parent's sub-route
            port=port,
            path=new_project_path,
            project_type=new_project_type,
            entry_point=new_project_entry if new_project_entry else None,
            ssl_enabled=False,
            status='stopped'
        )
        db.session.add(new_project)
        db.session.flush()  # Get the ID without committing
        
        # Create the sub-route
        sub_route = SubRoute(
            host_project_id=id,
            mounted_project_id=new_project.id,
            route_path=route_path,
            strip_prefix=strip_prefix
        )
        db.session.add(sub_route)
        db.session.commit()
        
        flash(f'Project created: {new_project_name}', 'success')
        flash(f'Sub-route added: {route_path} -> {new_project_name}', 'success')
        flash(f'Project directory: {new_project_path}', 'info')
        flash('Click "Configure Nginx" to apply changes', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating project: {str(e)}', 'error')
    
    return redirect(url_for('main.project_details', id=id))
