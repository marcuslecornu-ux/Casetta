"""
PythonAnywhere WSGI configuration file.

On PythonAnywhere, set the WSGI file path to this file in the Web tab.
Update the path below to match your PythonAnywhere username.
"""
import sys
import os

# Replace 'yourusername' with your actual PythonAnywhere username
path = '/home/yourusername/casetta-app'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import app as application

# Initialise DB on startup
from database import init_db
init_db()
