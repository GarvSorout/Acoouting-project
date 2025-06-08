#!/bin/bash

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is required but not installed. Please install pip3 first."
    exit 1
fi

# Check if Tesseract is installed
if ! command -v tesseract &> /dev/null; then
    echo "Tesseract is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install tesseract
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update
        sudo apt-get install -y tesseract-ocr
    else
        echo "Unsupported operating system. Please install Tesseract manually."
        exit 1
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOL
# Email Settings
EMAIL_HOST=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-specific-password

# MongoDB Settings
MONGODB_URI=your-mongodb-uri
EOL
    echo "Please edit the .env file with your email and MongoDB credentials."
fi

echo """
Setup complete! To run the demo:

1. Edit the .env file with your credentials:
   - Create a Gmail account for testing
   - Generate an App Password in Gmail settings
   - Create a free MongoDB Atlas account and get the connection string

2. Run the demo script:
   python demo_setup.py

3. Start the application:
   python main.py

4. Access the web interface:
   http://localhost:8000/docs

Note: Make sure to use an App Password from Gmail, not your regular password!
""" 