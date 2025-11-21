# VDS Hosting Panel

A modern, **self-healing** web-based control panel to manage Python web projects on a VPS/VDS server.

> 🚀 **Open Source Project** - Feel free to contribute, fork, and improve! Report any bugs or issues you encounter.

## 🤖 Adaptive Features (NEW!)
- **🔧 Auto-Setup**: Automatically creates venv and installs dependencies
- **🧠 Smart Detection**: Detects and fixes missing packages automatically
- **⚡ Zero Config**: Just upload or start - panel handles everything
- **🔄 Self-Healing**: Automatically recovers from common issues
- **🎯 Auto-Fix Entry Point**: Detects and fixes wrong entry points automatically

## ✨ Core Features
- **Project Management**: Deploy multiple Flask/Django apps on different ports
- **Folder Upload**: Upload entire project folders directly from the admin panel (up to 1GB)
- **Free SSL Certificates**: Automatic SSL certificate management with Let's Encrypt
- **Nginx Integration**: Automatically generates Nginx reverse proxy configs
- **Supervisor Integration**: Manages application processes
- **Process Monitoring**: Real-time status monitoring with PID tracking
- **Environment Variables**: Manage environment variables per project
- **Log Viewing**: View stdout and stderr logs in real-time
- **Modern UI**: Beautiful dark theme built with TailwindCSS and Alpine.js

## Installation (Server)

1.  Upload the files to your server (e.g., `/opt/vdspanel`)
2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Create initial admin user:
    ```bash
    python run.py create-user admin yourpassword
    ```
5.  Run the panel:
    ```bash
    python run.py
    ```
6.  Access the panel at `http://your-server-ip:5001`

## Development (Local)

1.  Create and activate virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create admin user:
    ```bash
    python run.py create-user admin admin123
    ```
4.  Run the app:
    ```bash
    python run.py
    ```
5.  Access at `http://localhost:5001`

**Note**: On non-Linux systems (like macOS/Windows), system commands (Nginx/Supervisor/Certbot) are mocked and will just print to the console.

## Using the Panel

### Deploying Projects

**Option 1: Upload Project Folder**
1. Click "Upload Project" button on dashboard
2. Select your entire project folder (maintains directory structure)
3. Fill in project details (name, port, domain)
4. Optionally enable free SSL certificate with Let's Encrypt
5. Click "Upload & Deploy"

**Option 2: Use Existing Server Path**
1. Click "New Project" button on dashboard
2. Provide absolute path to existing project on server
3. Configure project settings
4. Deploy

### SSL Certificates

The panel includes free SSL certificate management via Let's Encrypt:

1. Add a domain to your project in Settings
2. Click "Get Free SSL Certificate" in the SSL section
3. Enter your email for renewal notifications
4. Certificate will be automatically obtained and configured
5. Auto-renewal is configured via systemd timer (on Linux)

### Managing Projects

- **Start/Stop**: Use action buttons on project details page
- **Edit Settings**: Update domain, port, path, entry point
- **Environment Variables**: Set environment variables in JSON format
- **View Logs**: Real-time stdout and stderr logs
- **Delete**: Remove project and stop all processes

## Requirements

- Python 3.8+
- Flask, Flask-SQLAlchemy, Flask-Login
- Nginx (for reverse proxy, Linux only)
- Supervisor or systemd (for process management, Linux only)
- Certbot (for SSL certificates, Linux only)

## Security Configuration

**Important**: Before deploying to production:

1. **Set a secure SECRET_KEY**:
   ```bash
   export SECRET_KEY="your-secure-random-key-here"
   ```

2. **Configure production database** (recommended for production):
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost/vdspanel"
   ```

3. **Copy and configure deployment script**:
   ```bash
   cp deploy_to_server.sh.example deploy_to_server.sh
   # Edit deploy_to_server.sh with your server details
   ```

4. **Use environment variables**: Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Contributing

Contributions are welcome! Feel free to:
- Report bugs and issues
- Submit feature requests
- Create pull requests
- Improve documentation

## License

MIT License - Feel free to use and modify for your needs.

## Support

If you encounter any issues or need help, please open an issue on GitHub.
