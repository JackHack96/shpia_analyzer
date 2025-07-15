"""
SHPIA JSON Parser - Sensor Data Aggregation Tool

This script aggregates sensor data from JSON files by MAC address, creating a unified
view of all sensor readings for each device. It's designed to process JSON arrays
containing sensor records with MAC addresses and various sensor measurements.

Usage:
    python conver.py input_file.json [-o output_file.json]

Example:
    python conver.py data.json -o aggregated_output.json
"""

import json
import argparse
from collections import defaultdict
from pathlib import Path


def merge_dicts(dest, src):
    """
    Merge two dictionaries with nested timestamp-value mappings.
    
    This function handles the aggregation of sensor data by merging source dictionary
    values into the destination dictionary. It preserves all existing data while
    adding new timestamp-value pairs from the source.
    
    Args:
        dest (dict): The destination dictionary to merge into
        src (dict): The source dictionary containing new data to merge
        
    Note:
        - Only processes dictionary values from src
        - Creates new keys in dest if they don't exist
        - Updates existing keys with new timestamp-value pairs
    """
    for key, sub_dict in src.items():
        if isinstance(sub_dict, dict):
            # Initialize the key in destination if it doesn't exist
            if key not in dest:
                dest[key] = {}
            # Merge the sub-dictionary (timestamp-value pairs)
            dest[key].update(sub_dict)

def aggregate_jsonl_by_mac(input_file, output_file=None):
    """
    Aggregate JSON sensor data by MAC address.
    
    This function reads a JSON file containing an array of sensor records,
    groups them by MAC address, and aggregates all sensor readings for each
    device. Non-sensor fields like '_id' and 'address' are filtered out.
    
    Args:
        input_file (str): Path to the input JSON file containing sensor data
        output_file (str, optional): Path to save the aggregated output.
                                   If None, prints to console.
    
    Returns:
        None: Results are either saved to file or printed to console
        
    Data Structure:
        Input: List of records with MAC addresses and sensor readings
        Output: Dictionary with MAC addresses as keys and aggregated sensor data as values
        
    Example:
        Input: [{"address": "AA:BB:CC", "temp": {"12:00": 25.5}, "_id": "123"}]
        Output: {"AA:BB:CC": {"temp": {"12:00": 25.5}}}
    """
    # Initialize aggregated data structure using defaultdict for automatic key creation
    aggregated_data = defaultdict(dict)

    # Read and parse the JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)  # Parse as JSON array instead of line-by-line

        # Process each record in the JSON array
        for record in data:
            # Extract MAC address from the record
            mac = record.get("address")
            if not mac:
                # Skip records without MAC address
                continue
                
            # Filter out non-sensor fields (metadata fields)
            # Keep only actual sensor data by removing administrative fields
            record = {k: v for k, v in record.items() if k not in ["_id", "address"]}
            
            # Merge the filtered record into the aggregated data for this MAC
            merge_dicts(aggregated_data[mac], record)

    # Handle output - either save to file or print to console
    if output_file:
        # Save aggregated data to specified output file
        with open(output_file, 'w') as out_f:
            json.dump(aggregated_data, out_f)
        print(f"Aggregated data saved to '{output_file}'")
    else:
        # Print aggregated data to console in JSON format
        print(json.dumps(aggregated_data))

if __name__ == "__main__":
    """
    Main execution block - Command line interface for the JSON aggregation tool.
    
    This section handles command-line argument parsing and input validation
    before calling the aggregation function.
    """
    # Set up command line argument parser
    parser = argparse.ArgumentParser(
        description='Aggregate JSON sensor data by MAC address',
        epilog='Example: python conver.py data.json -o aggregated_output.json'
    )
    
    # Define required positional argument for input file
    parser.add_argument(
        'input_file', 
        help='Input JSON file path containing sensor data array'
    )
    
    # Define optional argument for output file
    parser.add_argument(
        '-o', '--output', 
        help='Output file path (optional, prints to console if not specified)'
    )
    
    # Parse the command line arguments
    args = parser.parse_args()
    
    # Validate input file exists before processing
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        exit(1)
    
    # Execute the main aggregation function
    aggregate_jsonl_by_mac(args.input_file, output_file=args.output)
