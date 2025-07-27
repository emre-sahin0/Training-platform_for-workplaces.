#!/usr/bin/env python3
"""
Startup script for the new professional structure
"""

import os
from migrate_data import migrate_database
from app import create_app

def main():
    print("🚀 TRT Eğitim Platformu - Professional Edition")
    print("=" * 50)
    
    # Run migration
    migrate_database()
    
    # Create app
    app = create_app()
    
    print("\n🌟 Platform başlatılıyor...")
    print("📍 Admin Login: http://localhost:5000/auth/login")
    print("👤 Username: admin")
    print("🔑 Password: admin123")
    print("=" * 50)
    
    # Start the application
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main() 