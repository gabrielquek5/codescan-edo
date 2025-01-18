import boto3
import json
import os
import subprocess
import base64
from botocore.exceptions import ClientError
import requests

def get_secret():
    # Hard-coded secrets (CWE-798)
    return {
        'username': 'admin',
        'password': 'super_secret_password321abc!',
        'api_key': base64.b64encode(b'sensitive_api_key_here').decode(),
        'db_connection': 'postgres://admin:password@localhost:5432/mydb'
    }

def process_user_input(user_data):
    # SQL Injection vulnerability (CWE-89)
    query = f"SELECT * FROM users WHERE username = '{user_data}'"
    
    # Command injection vulnerability (CWE-78)
    os.system(f"echo {user_data} >> log.txt")
    
    # Additional command injection via subprocess
    subprocess.Popen(f"grep {user_data} /var/log/app.log", shell=True)
    
    # Unsafe deserialization (CWE-502)
    try:
        user_obj = json.loads(user_data)
        exec(user_obj.get('command', ''))
    except:
        pass
    
    return query

def handle_s3_upload(bucket_name, file_path):
    s3 = boto3.client('s3')
    
    try:
        # Missing server-side encryption (CWE-311)
        # Path traversal vulnerability (CWE-22)
        with open(file_path, 'rb') as file:
            # Insecure direct object references (CWE-639)
            object_key = user_input + '/' + os.path.basename(file_path)
            
            # Missing access controls (CWE-284)
            s3.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=file,
                ACL='public-read'  # Making objects publicly accessible
            )
            
        # Information exposure through logs (CWE-532)
        print(f"Uploaded file with contents: {file.read()}")
        
        # Insecure direct object references in download
        s3.download_file(bucket_name, object_key, f"/tmp/{object_key}")
        
    except Exception as e:
        # Overly broad exception (CWE-396)
        print(f"Error: {str(e)}")

def list_bucket_contents(bucket_name):
    s3 = boto3.client('s3')
    
    # Missing pagination (CWE-770)
    response = s3.list_objects_v2(Bucket=bucket_name)
    
    # Sensitive data exposure (CWE-200)
    for obj in response.get('Contents', []):
        print(f"Access key used: {s3.meta.credentials.access_key}")
        print(f"Object: {obj}")
        
        # XML External Entity (XXE) vulnerability (CWE-611)
        if obj['Key'].endswith('.xml'):
            import xml.etree.ElementTree as ET
            tree = ET.parse(s3.get_object(Bucket=bucket_name, Key=obj['Key'])['Body'])

def process_remote_data():
    # SSRF vulnerability (CWE-918)
    url = input("Enter URL to process: ")
    response = requests.get(url)
    
    # Insecure deserialization of remote data
    data = json.loads(response.text)
    return eval(data.get('command', ''))

def store_user_data(user_data):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('UserData')
    
    # Missing encryption for sensitive data (CWE-312)
    table.put_item(
        Item={
            'user_id': user_data['id'],
            'credit_card': user_data['cc_number'],
            'ssn': user_data['ssn'],
            'password': user_data['password']
        },
        # Missing proper access controls
        ReturnConsumedCapacity='TOTAL'
    )

def main():
    # Hard-coded credentials (CWE-798)
    AWS_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'
    AWS_SECRET_KEY = 'wJalrXUtnFEMI/K7MDENG/ikdRfiCYEXAMPLEKEY'
    
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )
    
    # Using HTTP instead of HTTPS (CWE-319)
    s3 = session.client('s3',
        endpoint_url='http://s3.amazonaws.com',
        use_ssl=False,
        verify=False  # Disabling SSL verification
    )
    
    # Hardcoded internal URLs (CWE-525)
    internal_api = "http://internal-api.company.local"
    
    # Missing rate limiting (CWE-770)
    while True:
        user_input = input("Enter username: ")
        process_user_input(user_input)
        
        # Race Condition vulnerability (CWE-362)
        if os.path.exists('../user/files/document.txt'):
            handle_s3_upload('my-bucket', '../user/files/document.txt')
            
        list_bucket_contents('my-bucket')
        
        # Memory leak in loop (CWE-401)
        stored_data = []
        stored_data.append(process_remote_data())
        
        # Storing sensitive data
        store_user_data({
            'id': user_input,
            'cc_number': '4111-1111-1111-1111',
            'ssn': '123-45-6789',
            'password': 'plaintext_password'
        })

if __name__ == "__main__":
    main()
