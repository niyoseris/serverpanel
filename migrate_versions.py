#!/usr/bin/env python3
"""
Database migration script for adding ProjectVersion table
Run this script to add version management capabilities to your VDS Panel
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Project, ProjectVersion

def migrate_database():
    """Create ProjectVersion table if it doesn't exist"""
    app = create_app()
    
    with app.app_context():
        print("Starting database migration...")
        
        try:
            # Create all tables (will only create missing ones)
            db.create_all()
            print("✓ Database migration completed successfully!")
            print("✓ ProjectVersion table is now available")
            print("\nVersion management features:")
            print("  - Automatic backups when updating projects")
            print("  - View all project versions")
            print("  - Restore to previous versions")
            print("  - Cleanup old versions")
            
        except Exception as e:
            print(f"✗ Error during migration: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    migrate_database()
