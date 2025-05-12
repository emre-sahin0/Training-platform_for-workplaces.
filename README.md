# Occupational Health and Safety Training Platform

This project is a modern web application that enables online delivery of occupational health and safety training. It helps organizations manage and track their workplace safety training programs in a digital environment.

## 🌟 Features

- 👥 **Multi-User System**
  - Admin panel
  - User management
  - Role-based authorization

- 📚 **Training Management**
  - Video training upload and editing
  - Video forward prevention system
  - Test creation and management
  - Progress tracking

- 📊 **Reporting**
  - Detailed reports in Excel format
  - User-based progress tracking
  - Training completion statistics

- 🔒 **Security Features**
  - Video forward prevention
  - Right-click prevention
  - Keyboard shortcut prevention
  - Test passing criteria control

## 🚀 Installation

1. **Requirements**
   - Python 3.8 or higher
   - pip (Python package manager)
   - Git

2. **Clone the Repository**
   ```bash
   git clone https://github.com/username/occupational-safety-training.git
   cd occupational-safety-training
   ```

3. **Create Virtual Environment**
   ```bash
   # For Windows
   python -m venv venv
   venv\Scripts\activate

   # For Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Database Setup**
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. **Run the Application**
   ```bash
   python app.py
   ```

   image.png

## 💻 Usage
![image](https://github.com/user-attachments/assets/6481dcb0-a8f3-4642-86d7-5a4f31f45932)


1. Create an admin account
2. Upload courses and videos through the admin panel
3. Create user accounts
4. Users complete their training
5. View progress reports from the admin panel
![image](https://github.com/user-attachments/assets/78117b34-7ed5-43e5-bb58-cb7adf6d3515)


## 🛠️ Technologies

- **Backend**
  - Python 3.8+
  - Flask
  - SQLAlchemy
  - Flask-Login
  - Flask-Migrate

- **Frontend**
  - Bootstrap 5
  - HTML5 Video API
  - JavaScript
  - CSS3

## 📝 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Contact

For questions or suggestions, please open an issue or send an email. 
