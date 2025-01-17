import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, input_dir: str = "data"):
        self.input_dir = input_dir
        self.data: List[Dict] = []
    
    def load_data(self, filename: str) -> bool:
        """
        Load data from a JSON file
        Returns True if successful, False otherwise
        """
        try:
            file_path = os.path.join(self.input_dir, filename)
            with open(file_path, 'r') as f:
                self.data = json.load(f)
            logger.info(f"Successfully loaded data from {filename}")
            return True
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            return False
    
    def process_records(self) -> Optional[Dict]:
        """
        Process loaded records and return summary statistics
        """
        if not self.data:
            logger.warning("No data to process")
            return None
        
        try:
            total_records = len(self.data)
            numeric_fields = sum(
                isinstance(record.get('value'), (int, float))
                for record in self.data
            )
            
            summary = {
                "total_records": total_records,
                "numeric_fields": numeric_fields,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("Data processing completed successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Error processing records: {str(e)}")
            return None

def run_pipeline(input_file: str) -> bool:
    """
    Main pipeline function
    """
    try:
        # Initialize processor
        processor = DataProcessor()
        
        # Load and process data
        if not processor.load_data(input_file):
            return False
            
        # Get summary
        summary = processor.process_records()
        if summary is None:
            return False
            
        # Write results
        output_file = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Pipeline completed successfully. Results saved to {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Test the pipeline
    test_data = [
        {"id": 1, "value": 100},
        {"id": 2, "value": "text"},
        {"id": 3, "value": 300}
    ]
    
    # Create test data file
    os.makedirs("data", exist_ok=True)
    with open("data/test_input.json", 'w') as f:
        json.dump(test_data, f)
    
    # Run pipeline
    success = run_pipeline("test_input.json")
    print(f"Pipeline test {'succeeded' if success else 'failed'}")
