# SHPIA JSON Parser - Sensor Data Processing Suite

This suite contains two Python scripts for processing sensor data collected using SHPIA (https://github.com/IoT4CareLab/SHPIA/tree/Versione2) and determining location based on RSSI (Received Signal Strength Indicator) values.

## Scripts Overview

### 1. `convert.py` - Data Aggregation Script
Aggregates sensor data from JSON files by MAC address, creating a unified view of all sensor readings for each device.

### 2. `location_analyzer.py` - Location Analysis Script
Processes aggregated sensor data to determine the closest location for each time slot based on RSSI values.

## Quick Start

### Step 1: Aggregate Raw Data
```bash
python convert.py data/data.json -o data/output.json
```

### Step 2: Analyze Location
```bash
python location_analyzer.py data/output.json --labels kitchen sofa office -o data/location_analysis.json --time-window 1
```

## Data Flow

```
Raw JSON Data → Aggregation → Location Analysis → Results
    ↓              ↓              ↓              ↓
data.json → convert.py → output.json → location_analyzer.py → analysis.json
```

## Usage Examples

### Basic Data Aggregation
```bash
# Aggregate data and print to console
python convert.py data/data.json

# Aggregate data and save to file
python convert.py data/data.json -o data/aggregated_output.json
```

### Location Analysis Options

#### Basic Analysis (Default Labels)
```bash
# Use default labels: kitchen, living_room, bedroom
python location_analyzer.py data/output.json --time-window 1
```

#### Custom Location Labels
```bash
# Use custom labels for each MAC address
python location_analyzer.py data/output.json --labels kitchen sofa office --time-window 1
```

#### Different Time Windows
```bash
# 5-minute time windows
python location_analyzer.py data/output.json --time-window 5

# 30-second time windows (0.5 minutes)
python location_analyzer.py data/output.json --time-window 0.5
```

#### Save Results to File
```bash
# Save detailed JSON results and summary report
python location_analyzer.py data/output.json --labels kitchen sofa office -o results/location_analysis.json --time-window 1
```

## Output Files

### From `convert.py`
- **Aggregated JSON**: Contains sensor data grouped by MAC address
- **Structure**: `{MAC_ADDRESS: {sensor_type: {timestamp: value}}}`

### From `location_analyzer.py`
- **Analysis JSON**: Detailed analysis results with time windows and location data
- **Summary Report**: Human-readable summary with location frequency and sample time windows

## Understanding RSSI Values

- **RSSI Range**: Typically from -100 dBm (weak) to -30 dBm (strong)
- **Higher Values**: Closer to 0 means stronger signal and closer proximity
- **Analysis Logic**: The location with the highest average RSSI in each time window is considered the closest

## Sample Data Structure

### Input Data (data.json)
```json
[
  {
    "_id": {"$oid": "..."},
    "address": "EA:1B:15:7E:DE:53",
    "rssiValues": {
      "2025-07-14 11:42:58:448": -67,
      "2025-07-14 11:43:00:156": -65
    },
    "accelerometerValues_x": {
      "2025-07-14 11:42:58:448": -0.020507812
    }
  }
]
```

### Aggregated Data (output.json)
```json
{
  "EA:1B:15:7E:DE:53": {
    "rssiValues": {
      "2025-07-14 11:42:58:448": -67,
      "2025-07-14 11:43:00:156": -65
    },
    "accelerometerValues_x": {
      "2025-07-14 11:42:58:448": -0.020507812
    }
  }
}
```

### Location Analysis Results
```json
{
  "analysis_settings": {
    "time_window_minutes": 1,
    "mac_to_label": {
      "EA:1B:15:7E:DE:53": "kitchen",
      "E0:9C:78:B3:E6:34": "sofa"
    }
  },
  "time_windows": {
    "2025-07-14 11:42:00": {
      "closest_location": "kitchen",
      "closest_rssi": -65.5,
      "all_locations": {
        "kitchen": {"average_rssi": -65.5, "sample_count": 10},
        "sofa": {"average_rssi": -75.2, "sample_count": 8}
      }
    }
  },
  "location_summary": {
    "kitchen": 12,
    "sofa": 5
  }
}
```

## Parameters

### `convert.py`
- `input_file`: Path to input JSON file
- `-o, --output`: Output file path (optional)

### `location_analyzer.py`
- `input_file`: Path to aggregated JSON file
- `-o, --output`: Output file path (optional)
- `--time-window`: Time window size in minutes (default: 1)
- `--labels`: Custom location labels (space-separated)

## Requirements

- Python 3.6+
- Standard library modules only (json, argparse, datetime, collections, pathlib, statistics)

## Error Handling

- **Missing Files**: Scripts check for file existence before processing
- **Invalid JSON**: Graceful error handling with informative messages
- **Missing RSSI Data**: Warnings for MAC addresses without RSSI data
- **Timestamp Parsing**: Robust timestamp parsing with error handling

## Tips for Best Results

1. **Time Windows**: Use appropriate time window sizes for your data frequency
2. **Location Labels**: Use meaningful labels that match your physical setup
3. **RSSI Quality**: Ensure sufficient RSSI readings for accurate location determination
4. **Data Validation**: Check the summary report to verify reasonable location distribution

## Troubleshooting

### Common Issues

1. **No RSSI Data Warning**: 
   - Check if the MAC address has `rssiValues` in the aggregated data
   - Verify the original data contains RSSI measurements

2. **Empty Results**:
   - Ensure the input file contains valid aggregated data
   - Check that RSSI values exist for the specified time range

3. **Incorrect Location Labels**:
   - Verify the number of labels matches the number of MAC addresses
   - Use the `--labels` parameter to specify custom names

### Debug Commands

```bash
# Check aggregated data structure
python -c "import json; data = json.load(open('data/output.json')); print(list(data.keys()))"

# Check RSSI availability
python -c "import json; data = json.load(open('data/output.json')); [print(f'{mac}: {\"rssiValues\" in sensors}') for mac, sensors in data.items()]"
```

## License

This project is part of the SHPIA (Smart Home Personal Indoor Assistant) system.
