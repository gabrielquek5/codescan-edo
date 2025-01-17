import boto3
import json
import os
from botocore.exceptions import ClientError

def get_secret():
    # Hard-coded secrets (CWE-798)
    return {
        'username': 'admin',
        'password': 'super_secret_password321abcqwertyjkl!'
    }

def process_user_input(user_data):
    # SQL Injection vulnerability (CWE-89)
    query = f"SELECT * FROM users WHERE username = '{user_data}'"
    
    # Command injection vulnerability (CWE-78)
    os.system(f"echo {user_data} >> log.txt")
    
    return query

def handle_s3_upload(bucket_name, file_path):
    s3 = boto3.client('s3')
    
    try:
        # Missing server-side encryption (CWE-311)
        # Path traversal vulnerability (CWE-22)
        with open(file_path, 'rb') as file:
            s3.put_object(
                Bucket=bucket_name,
                Key=os.path.basename(file_path),
                Body=file
            )
            
        # Information exposure through logs (CWE-532)
        print(f"Uploaded file with contents: {file.read()}")
        
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
        use_ssl=False
    )
    
    user_input = input("Enter username: ")
    process_user_input(user_input)
    
    handle_s3_upload('my-bucket', '../user/files/document.txt')
    list_bucket_contents('my-bucket')

if __name__ == "__main__":
    main()
