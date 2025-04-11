# import boto3
# import json
# from datetime import datetime
# from flask import Flask, request, render_template, jsonify

# app = Flask(__name__)

# # Initialize AWS clients
# lambda_client = boto3.client('lambda', region_name='eu-north-1')
# s3 = boto3.client('s3', region_name='eu-north-1')
# dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')

# # Configuration
# BUCKET_NAME = 'filesharingtool'
# LAMBDA_FUNCTION_NAME = 'sharingfunction'
# DYNAMODB_TABLE_NAME = 'sharingfile'

# @app.route('/')
# def index():
#     return render_template('upload.html')

# @app.route('/upload', methods=['POST'])
# def upload_file():
#     file = request.files['file']
#     emails = json.loads(request.form['emails'])

#     try:
#         # Upload the file to S3
#         s3_key = file.filename
#         s3.upload_fileobj(file, BUCKET_NAME, s3_key)

#         # Generate a pre-signed URL for the uploaded file
#         file_url = s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': s3_key})

#         # Send email via Lambda
#         email_payload = {
#             'file_url': file_url,
#             'emails': emails
#         }
#         lambda_client.invoke(
#             FunctionName=LAMBDA_FUNCTION_NAME,
#             InvocationType='Event',
#             Payload=json.dumps(email_payload)
#         )

#         # Store file information in DynamoDB
#         table = dynamodb.Table(DYNAMODB_TABLE_NAME)
#         table.put_item(
#             Item={
#                 'file_key': s3_key,
#                 'file_url': file_url,
#                 'upload_date': datetime.utcnow().isoformat(),
#                 'emails': json.dumps(emails)
#             }
#         )

#         return jsonify({'message': 'File uploaded successfully!'})

#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({'message': 'Error uploading file.'}), 500

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000,debug=True)
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import boto3
import json
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key

# Initialize AWS clients
lambda_client = boto3.client('lambda', region_name='eu-north-1')
s3 = boto3.client('s3', region_name='eu-north-1')
dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')

# Configuration
BUCKET_NAME = 'filesharingtool'
LAMBDA_FUNCTION_NAME = 'sharingfunction'
DYNAMODB_TABLE_NAME = 'sharingfile'

# Dummy in-memory database for example purposes
conn = sqlite3.connect(':memory:', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT
    )
''')

@app.route('/')
def index():
    if 'username' in session:
        return render_template('upload.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user[0], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials', 401
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password,method='pbkdf2:sha256')
        
        try:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', 
                           (username, email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return 'Username or email already exists', 400

    return render_template('signup.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    emails = json.loads(request.form['emails'])

    try:
        # Upload the file to S3
        s3_key = file.filename
        s3.upload_fileobj(file, BUCKET_NAME, s3_key)

        # Generate a pre-signed URL for the uploaded file
        file_url = s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': s3_key})

        # Send email via Lambda
        email_payload = {
            'file_url': file_url,
            'emails': emails
        }
        lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(email_payload)
        )

        # Store file information in DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        table.put_item(
            Item={
                'file_key': s3_key,
                'file_url': file_url,
                'upload_date': datetime.utcnow().isoformat(),
                'emails': json.dumps(emails)
            }
        )

        return jsonify({'message': 'File uploaded successfully!'})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Error uploading file.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
