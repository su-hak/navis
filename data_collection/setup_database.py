"""
Database Setup Script
데이터베이스 선택 및 초기화
"""

import sys
import os

def setup_sqlite():
    """SQLite 설정"""
    print("\n" + "="*60)
    print("SQLite Database Setup")
    print("="*60)

    from database.schema_sqlite import create_connection, create_tables

    try:
        connection = create_connection()
        create_tables(connection)
        connection.close()

        print("\n✓ SQLite database initialized successfully!")
        print(f"\nDatabase file: {os.path.join(os.getcwd(), 'trading.db')}")
        print("\nNext steps:")
        print("1. Set DATABASE_TYPE=sqlite in your .env file")
        print("2. Run: cd api && python main.py")

        return True

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return False


def setup_mysql():
    """MySQL 설정"""
    print("\n" + "="*60)
    print("MySQL Database Setup")
    print("="*60)

    # Check if MySQL is available
    try:
        import mysql.connector
    except ImportError:
        print("\n✗ mysql-connector-python not installed")
        print("Run: pip install mysql-connector-python")
        return False

    from dotenv import load_dotenv
    load_dotenv()

    # Get MySQL credentials
    host = os.getenv('MYSQL_HOST', 'localhost')
    port = int(os.getenv('MYSQL_PORT', 3306))
    user = os.getenv('MYSQL_USER', 'root')
    password = os.getenv('MYSQL_PASSWORD', '')
    database = os.getenv('MYSQL_DATABASE', 'trading_db')

    if not password:
        print("\n⚠ MYSQL_PASSWORD not set in .env file")
        print("\nPlease set your MySQL password in .env:")
        print(f"MYSQL_PASSWORD=your_password")
        return False

    print(f"\nConnecting to MySQL at {host}:{port}...")

    try:
        # Try to connect
        import mysql.connector
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )

        print("✓ Connected to MySQL successfully!")

        # Create tables
        from database.schema import create_tables
        create_tables(connection)

        connection.close()

        print("\n✓ MySQL database initialized successfully!")
        print("\nNext steps:")
        print("1. Ensure DATABASE_TYPE=mysql in your .env file (or not set)")
        print("2. Run: cd api && python main.py")

        return True

    except mysql.connector.Error as e:
        print(f"\n✗ MySQL Error: {str(e)}")
        print("\nPossible solutions:")
        print("1. Make sure MySQL is running")
        print("   - Windows: Start-Service MySQL80")
        print("   - Check services.msc")
        print("2. Verify credentials in .env file")
        print("3. Create database manually:")
        print(f"   mysql -u root -p -e 'CREATE DATABASE {database};'")
        print("\nFor detailed help, see: INSTALL_MYSQL.md")
        return False


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("Database Setup Wizard")
    print("="*60)
    print("\nChoose your database:")
    print("1. SQLite (Recommended for quick start, no installation)")
    print("2. MySQL (Recommended for production)")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == '1':
        success = setup_sqlite()
    elif choice == '2':
        success = setup_mysql()
    elif choice == '3':
        print("\nExiting...")
        sys.exit(0)
    else:
        print("\n✗ Invalid choice")
        sys.exit(1)

    if success:
        print("\n" + "="*60)
        print("Setup Complete!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("Setup Failed")
        print("="*60)
        print("\nFor help:")
        print("- SQLite: Just run this script again and choose option 1")
        print("- MySQL: See INSTALL_MYSQL.md for detailed instructions")
        sys.exit(1)


if __name__ == "__main__":
    main()
