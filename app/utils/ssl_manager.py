import os
import subprocess
import sys
import re
import glob

def is_linux():
    return os.name == 'posix' and os.uname().sysname == 'Linux'

def ensure_nginx_running():
    """
    Ensures nginx is running. Starts it if not active.
    Returns True if nginx is running after this call.
    """
    if not is_linux():
        print("[MOCK] Would ensure nginx is running")
        return True
    
    try:
        # Check if nginx is active
        result = subprocess.run(
            ['/usr/bin/systemctl', 'is-active', 'nginx'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip() == 'active':
            print("Nginx is already running")
            return True
        
        # Try to start nginx
        print("Starting nginx...")
        start_result = subprocess.run(
            ['/usr/bin/systemctl', 'start', 'nginx'],
            capture_output=True, text=True
        )
        
        if start_result.returncode == 0:
            print("Nginx started successfully")
            return True
        else:
            print(f"Failed to start nginx: {start_result.stderr}")
            return False
    except Exception as e:
        print(f"Error ensuring nginx is running: {e}")
        return False

def cleanup_broken_ssl_references(domain):
    """
    Removes broken SSL certificate references from nginx configs.
    This fixes the chicken-egg problem where nginx fails because SSL certs
    don't exist, but certbot can't run because nginx config test fails.
    Returns True if cleanup was successful or not needed.
    """
    if not is_linux():
        print("[MOCK] Would cleanup broken SSL references")
        return True
    
    try:
        print(f"Checking for broken SSL references for {domain}...")
        
        # First, test if nginx config is OK
        test_result = subprocess.run(
            ['/usr/sbin/nginx', '-t'],
            capture_output=True, text=True
        )
        
        if test_result.returncode == 0:
            print("Nginx config is valid, no cleanup needed")
            return True
        
        # Check if the error is about missing SSL cert for this domain
        error_output = test_result.stderr
        if domain not in error_output or 'ssl_certificate' not in error_output.lower():
            print(f"Nginx error not related to {domain} SSL: {error_output}")
            return False
        
        print(f"Found broken SSL reference for {domain}, cleaning up...")
        
        # Find nginx config files that reference this domain
        sites_available = '/etc/nginx/sites-available'
        sites_enabled = '/etc/nginx/sites-enabled'
        
        for config_dir in [sites_available, sites_enabled]:
            if not os.path.exists(config_dir):
                continue
                
            for config_file in os.listdir(config_dir):
                config_path = os.path.join(config_dir, config_file)
                
                # Skip symlinks in sites-enabled (we'll fix the source in sites-available)
                if config_dir == sites_enabled and os.path.islink(config_path):
                    continue
                
                if not os.path.isfile(config_path):
                    continue
                
                try:
                    with open(config_path, 'r') as f:
                        content = f.read()
                    
                    # Check if this config has broken SSL for our domain
                    if domain in content and f'/etc/letsencrypt/live/{domain}' in content:
                        # Check if the cert file actually exists
                        cert_path = f'/etc/letsencrypt/live/{domain}/fullchain.pem'
                        if not os.path.exists(cert_path):
                            print(f"Cleaning broken SSL from {config_path}")
                            
                            # Remove SSL-related server blocks for this domain
                            # Pattern to match server blocks with SSL for this domain
                            cleaned_content = remove_ssl_blocks(content, domain)
                            
                            if cleaned_content != content:
                                with open(config_path, 'w') as f:
                                    f.write(cleaned_content)
                                print(f"Cleaned {config_path}")
                except Exception as e:
                    print(f"Error processing {config_path}: {e}")
        
        # Test nginx config again
        test_result = subprocess.run(
            ['/usr/sbin/nginx', '-t'],
            capture_output=True, text=True
        )
        
        if test_result.returncode == 0:
            print("Nginx config is now valid after cleanup")
            # Reload nginx
            subprocess.run(['/usr/bin/systemctl', 'reload', 'nginx'], capture_output=True)
            return True
        else:
            print(f"Nginx config still invalid: {test_result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error during SSL cleanup: {e}")
        return False

def remove_ssl_blocks(content, domain):
    """
    Removes server blocks that have SSL configuration for a domain
    where the certificate doesn't exist.
    """
    lines = content.split('\n')
    result_lines = []
    in_ssl_server_block = False
    brace_count = 0
    skip_block = False
    temp_block = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect start of a server block
        if 'server' in line and '{' in line:
            # Look ahead to check if this block has SSL for our domain
            block_content = ''
            temp_brace = 0
            for j in range(i, len(lines)):
                block_content += lines[j] + '\n'
                temp_brace += lines[j].count('{') - lines[j].count('}')
                if temp_brace == 0 and j > i:
                    break
            
            # Check if this block has broken SSL for our domain
            has_domain = domain in block_content
            has_ssl_cert = f'/etc/letsencrypt/live/{domain}' in block_content
            has_listen_443 = 'listen 443' in block_content
            
            if has_domain and has_ssl_cert and has_listen_443:
                # Skip this entire server block
                skip_brace = 0
                while i < len(lines):
                    skip_brace += lines[i].count('{') - lines[i].count('}')
                    i += 1
                    if skip_brace == 0:
                        break
                continue
            
            # Also check for redirect blocks added by certbot
            if has_domain and 'managed by Certbot' in block_content and 'return 301' in block_content:
                # Skip certbot redirect blocks for this domain
                skip_brace = 0
                while i < len(lines):
                    skip_brace += lines[i].count('{') - lines[i].count('}')
                    i += 1
                    if skip_brace == 0:
                        break
                continue
        
        result_lines.append(line)
        i += 1
    
    return '\n'.join(result_lines)

def install_certbot():
    """
    Installs certbot if not already installed.
    """
    if is_linux():
        try:
            # Check if certbot exists
            result = subprocess.run(['/usr/bin/which', 'certbot'], capture_output=True)
            if result.returncode == 0:
                print("Certbot is already installed.")
                return True
            
            print("Installing certbot...")
            subprocess.run(['/usr/bin/apt-get', 'update'], check=True)
            subprocess.run(['/usr/bin/apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'], check=True)
            return True
        except Exception as e:
            print(f"Error installing certbot: {e}")
            return False
    else:
        print("[MOCK] Would install certbot on Linux")
        return True

def request_ssl_certificate(domain, email):
    """
    Requests an SSL certificate from Let's Encrypt for the given domain.
    Automatically cleans up broken SSL references and ensures nginx is running.
    Returns True if successful, False otherwise.
    """
    if not domain or not email:
        print("Domain and email are required for SSL certificate")
        return False
    
    if is_linux():
        try:
            print(f"Preparing to request SSL certificate for {domain}...")
            
            # Step 1: Clean up any broken SSL references
            cleanup_broken_ssl_references(domain)
            
            # Step 2: Ensure nginx is running
            if not ensure_nginx_running():
                print("Failed to ensure nginx is running")
                return False
            
            # Step 3: Verify nginx config is valid
            test_result = subprocess.run(
                ['/usr/sbin/nginx', '-t'],
                capture_output=True, text=True
            )
            if test_result.returncode != 0:
                print(f"Nginx config test failed: {test_result.stderr}")
                # Try one more cleanup attempt
                cleanup_broken_ssl_references(domain)
                test_result = subprocess.run(
                    ['/usr/sbin/nginx', '-t'],
                    capture_output=True, text=True
                )
                if test_result.returncode != 0:
                    print("Nginx config still invalid after cleanup")
                    return False
            
            print(f"Requesting SSL certificate for {domain}...")
            
            # Set up environment with proper PATH so certbot can find nginx
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
            
            # Using certbot with nginx plugin (app runs as root, no sudo needed)
            result = subprocess.run([
                '/usr/bin/certbot', '--nginx',
                '-d', domain,
                '-d', f'www.{domain}',
                '--non-interactive',
                '--agree-tos',
                '--email', email,
                '--redirect'
            ], capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                print(f"SSL certificate obtained successfully for {domain}")
                return True
            else:
                print(f"Failed to obtain SSL certificate: {result.stderr}")
                print(f"stdout: {result.stdout}")
                return False
        except Exception as e:
            print(f"Error requesting SSL certificate: {e}")
            return False
    else:
        print(f"[MOCK] Would request SSL certificate for {domain} with email {email}")
        print("[MOCK] On production Linux server, this would use Let's Encrypt via certbot")
        return True

def renew_ssl_certificates():
    """
    Renews all SSL certificates that are due for renewal.
    """
    if is_linux():
        try:
            print("Checking for SSL certificates to renew...")
            result = subprocess.run(['/usr/bin/certbot', 'renew', '--quiet'], capture_output=True)
            if result.returncode == 0:
                print("SSL certificates renewed successfully")
                return True
            else:
                print(f"SSL renewal check completed with warnings")
                return True
        except Exception as e:
            print(f"Error renewing SSL certificates: {e}")
            return False
    else:
        print("[MOCK] Would renew SSL certificates on Linux")
        return True

def check_ssl_status(domain):
    """
    Checks if a domain has a valid SSL certificate.
    """
    if is_linux():
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        if os.path.exists(cert_path):
            try:
                # Check certificate expiry
                result = subprocess.run([
                    'openssl', 'x509', '-in', cert_path,
                    '-noout', '-enddate'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {
                        'has_ssl': True,
                        'expiry_info': result.stdout.strip()
                    }
            except Exception as e:
                print(f"Error checking SSL status: {e}")
        
        return {'has_ssl': False}
    else:
        print(f"[MOCK] Would check SSL status for {domain}")
        return {'has_ssl': False, 'mock': True}

def revoke_ssl_certificate(domain):
    """
    Revokes an SSL certificate for a domain.
    """
    if is_linux():
        try:
            print(f"Revoking SSL certificate for {domain}...")
            result = subprocess.run([
                '/usr/bin/certbot', 'revoke',
                '--cert-name', domain,
                '--delete-after-revoke'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"SSL certificate revoked for {domain}")
                return True
            else:
                print(f"Failed to revoke SSL certificate: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error revoking SSL certificate: {e}")
            return False
    else:
        print(f"[MOCK] Would revoke SSL certificate for {domain}")
        return True

def setup_ssl_auto_renewal():
    """
    Sets up automatic SSL certificate renewal via cron.
    """
    if is_linux():
        try:
            print("Setting up SSL auto-renewal...")
            # Certbot usually installs a systemd timer or cron job automatically
            # We can verify it exists
            result = subprocess.run(['/usr/bin/systemctl', 'status', 'certbot.timer'], 
                                  capture_output=True, text=True)
            
            if 'active' in result.stdout.lower():
                print("SSL auto-renewal is already configured via systemd")
                return True
            else:
                # Try to enable it
                subprocess.run(['/usr/bin/systemctl', 'enable', 'certbot.timer'], check=True)
                subprocess.run(['/usr/bin/systemctl', 'start', 'certbot.timer'], check=True)
                print("SSL auto-renewal configured successfully")
                return True
        except Exception as e:
            print(f"Note: {e}. Manual renewal may be needed.")
            return False
    else:
        print("[MOCK] Would setup SSL auto-renewal on Linux")
        return True
