# Changelog

## [Unreleased] - 2025-11-19

### Fixed Issues
1. **Missing Dependencies**: Added `werkzeug` and `click` to requirements.txt
2. **Duplicate Imports**: Removed duplicate import statements in `system.py`
3. **Database Path**: Fixed SQLite database path to use `instance/` folder consistently
4. **Entry Point Detection**: Improved Django/Flask entry point auto-detection logic
   - Now checks immediate subdirectories only for Django wsgi.py
   - Validates with manage.py presence
   - Added more Flask patterns (application.py)
5. **Error Handling**: Enhanced validation and error handling in routes
   - Port conflict detection
   - Path existence validation
   - Better try-catch blocks with rollback
   - Flash messages with appropriate categories

### New Features

#### 1. Free SSL Certificate Management (Let's Encrypt)
- Automatic SSL certificate request and installation
- Integration with Let's Encrypt via Certbot
- SSL certificate revocation support
- Auto-renewal setup via systemd timer
- Visual SSL status indicators in UI
- Email notifications for certificate expiry

**Files Added:**
- `app/utils/ssl_manager.py` - SSL certificate management functions

**Routes Added:**
- `/projects/<id>/request-ssl` - Request new SSL certificate
- `/projects/<id>/revoke-ssl` - Revoke SSL certificate

**UI Updates:**
- SSL management section in project settings
- SSL status badge in project details
- Interactive email input for certificate requests

#### 2. Project Folder Upload
- Upload entire project folders directly from browser
- Maintains directory structure
- Drag-and-drop support
- File list preview before upload
- Automatic entry point detection for uploaded projects
- Optional SSL configuration during upload

**Files Added:**
- `app/templates/upload_project.html` - Upload interface

**Routes Added:**
- `/upload-project` - Upload and deploy project folders

**UI Updates:**
- "Upload Project" button on dashboard
- Modern drag-and-drop file upload interface
- Real-time file count and listing
- Upload progress indication

### Improvements
1. **Code Organization**: Moved common imports to top level in routes.py
2. **Validation**: Added comprehensive input validation for all project operations
3. **User Feedback**: Improved flash messages with categories (success, error, warning, info)
4. **Documentation**: Updated README with detailed usage instructions
5. **UI/UX**: Enhanced visual feedback and status indicators

### Technical Details

#### SSL Certificate Flow
1. User provides domain and email
2. System installs certbot if needed (Linux only)
3. Certbot requests certificate from Let's Encrypt
4. Nginx config regenerated with SSL settings
5. Certificate auto-renewal configured

#### Upload Flow
1. User selects project folder in browser
2. Files uploaded maintaining relative paths
3. Project directory created in `uploads/` folder
4. Entry point auto-detected
5. Project added to database
6. Optional SSL certificate requested
7. Nginx config generated if domain provided

### Platform Compatibility
- **Linux**: Full functionality (Nginx, Supervisor, Certbot)
- **macOS/Windows**: Development mode with mocked system calls

### Database Schema
No changes to existing schema. All new features use existing `Project` model fields:
- `ssl_enabled` (Boolean)
- `domain` (String)
- `path` (String)

### Dependencies
No new dependencies added. Uses existing:
- Flask ecosystem
- Werkzeug (security utilities)
- Subprocess (system calls)
- OS utilities

### Security Considerations
1. Filename sanitization with `secure_filename()`
2. Path traversal prevention
3. Port conflict detection
4. Database transaction rollback on errors
5. SSL certificate validation via Let's Encrypt
6. User authentication required for all operations
