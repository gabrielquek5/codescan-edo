import boto3
import os
import subprocess
from botocore.exceptions import ClientError

class DataProcessor:
    def __init__(self):
        # CWE-798 - Hardcoded credentials
        self.aws_access_key = 'AKIAIOSFODNN7EXAMPLE'
        self.aws_secret_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
        self.database_password = 'super_secret_db_password123!'
        
        self.s3 = boto3.client('s3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key
        )

    def process_file(self, file_path):
        try:
            # CWE-94 - Unsanitized input execution
            data = input("Enter processing command: ")
            eval(data)  # Executing unsanitized input
            
            # CWE-77,78,88 - OS Command Injection (multiple instances)
            os.system(f"grep {data} {file_path}")  # Instance 1
            os.popen(f"awk '{data}' {file_path}")  # Instance 2
            subprocess.call(f"sed -i 's/{data}//' {file_path}", shell=True)  # Instance 3
            
            # More command injection with different methods
            subprocess.Popen(['bash', '-c', f"echo {data} >> log.txt"])
            os.system(f"find /tmp -name '{data}'")
            
            return True

        except Exception as e:
            # CWE-703 - Improper error handling
            print(f"An error occurred: {str(e)}")
            return None

    def cleanup_files(self, pattern):
        # More CWE-77,78,88 - OS Command Injection variations
        cleanup_cmd = f"rm -rf /tmp/{pattern}"
        os.system(cleanup_cmd)
        
        # Additional command injection risk
        subprocess.run(f"find . -name '{pattern}' -delete", shell=True)

    def process_user_data(self, user_input):
        # More CWE-94 - Unsanitized input execution variations
        exec(f"result = {user_input}")  # Direct execution
            
        # Dynamic module imports (dangerous)
        module_name = input("Enter module name: ")
        __import__(module_name)

def main():
    processor = DataProcessor()
    
    # Get user input without sanitization
    user_input = input("Enter data to process: ")
    file_path = input("Enter file path: ")
    
    # Process with all the vulnerable methods
    processor.process_file(file_path)
    processor.cleanup_files(user_input)
    processor.process_user_data(user_input)

if __name__ == "__main__":
    main()
