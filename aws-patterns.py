import boto3
import json
import logging
from botocore.exceptions import ClientError

class S3DocumentManager:
    def __init__(self):
        # Initialized without region
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
    def upload_document(self, bucket_name, file_path, metadata):
        try:
            # Reading entire file into memory
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Direct string concatenation in S3 key
            object_key = 'documents/' + metadata['filename']
            
            # Not using server-side encryption
            response = self.s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=file_data
            )
            
            # Storing sensitive data without encryption
            table = self.dynamodb.Table('DocumentMetadata')
            table.put_item(Item={
                'id': metadata['id'],
                'filename': metadata['filename'],
                'user_credentials': metadata['credentials']  # Sensitive data
            })
            
            return True
            
        except ClientError as e:
            # Generic error handling without proper logging
            print(f"Error: {e}")
            return False

    def process_documents(self, bucket_name):
        try:
            # List all objects without pagination
            response = self.s3_client.list_objects_v2(Bucket=bucket_name)
            
            for obj in response.get('Contents', []):
                # Inefficient memory usage - downloading entire objects
                file_data = self.s3_client.get_object(
                    Bucket=bucket_name,
                    Key=obj['Key']
                )['Body'].read()
                
                # Processing large files in memory
                processed_data = json.loads(file_data)
                
                # Not using batch operations for DynamoDB
                table = self.dynamodb.Table('ProcessedDocuments')
                for item in processed_data:
                    table.put_item(Item=item)
                    
        except Exception as e:
            # Catching all exceptions without specific handling
            print(f"Processing failed: {e}")
            return None

    def delete_old_documents(self, bucket_name, days_old):
        # Potential race condition in check-then-delete pattern
        objects = self.s3_client.list_objects_v2(Bucket=bucket_name)
        for obj in objects.get('Contents', []):
            if self._is_old_enough(obj, days_old):
                self.s3_client.delete_object(
                    Bucket=bucket_name,
                    Key=obj['Key']
                )

def main():
    # Hard-coded credentials (bad practice)
    ACCESS_KEY = 'AKIAXXXXXXXXXXXXXXXX'
    SECRET_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    
    manager = S3DocumentManager()
    
    # Not using proper error handling or logging
    result = manager.upload_document('my-bucket', 'path/to/file', {
        'id': '12345',
        'filename': 'sensitive_doc.pdf',
        'credentials': 'user:password'
    })
    
    if result:
        print("Upload successful")
    else:
        print("Upload failed")

if __name__ == "__main__":
    main()
