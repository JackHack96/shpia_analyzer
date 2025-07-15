"""
SHPIA Location & Activity Analyzer - Dual Sensor Analysis

This script processes aggregated sensor data to determine both location and object interactions
by analyzing two types of sensors:
1. BLE Beacons (RSSI + basic accelerometer) - for location detection
2. Nordic Thingy (full sensors, no RSSI) - for object interaction detection

The script combines both sensor types to provide context-aware activity recognition.

Usage:
    python location_analyzer.py aggregated_data.json [-o output_file.json] [--time-window MINUTES] [--beacon-labels LABELS] [--object-labels LABELS]
"""

import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import statistics


def parse_timestamp(timestamp_str):
    """
    Parse timestamp string to datetime object.
    
    Args:
        timestamp_str (str): Timestamp in format "2025-07-14 11:42:58:448"
        
    Returns:
        datetime: Parsed datetime object
    """
    try:
        # Handle the microseconds part (last 3 digits)
        if ':' in timestamp_str:
            base_time, microseconds = timestamp_str.rsplit(':', 1)
            # Convert microseconds to proper format (pad with zeros if needed)
            microseconds = microseconds.ljust(6, '0')[:6]
            full_timestamp = f"{base_time}.{microseconds}"
        else:
            full_timestamp = timestamp_str
            
        return datetime.strptime(full_timestamp, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError as e:
        print(f"Error parsing timestamp {timestamp_str}: {e}")
        return None


def get_time_window_key(timestamp, window_minutes=1):
    """
    Generate a time window key for grouping timestamps.
    
    Args:
        timestamp (datetime): The timestamp to group
        window_minutes (int): Size of time window in minutes
        
    Returns:
        str: Time window key in format "2025-07-14 11:42:00"
    """
    # Round down to the nearest time window
    rounded_minute = (timestamp.minute // window_minutes) * window_minutes
    windowed_time = timestamp.replace(minute=rounded_minute, second=0, microsecond=0)
    return windowed_time.strftime("%Y-%m-%d %H:%M:%S")


def classify_sensors(aggregated_data):
    """
    Classify sensors into BLE Beacons and Nordic Thingy based on available data.
    
    BLE Beacons: Have RSSI + basic accelerometer (location sensors)
    Nordic Thingy: Have full sensor suite but no RSSI (object sensors)
    
    Args:
        aggregated_data (dict): Aggregated sensor data by MAC address
        
    Returns:
        tuple: (ble_beacons_dict, nordic_thingy_dict)
    """
    ble_beacons = {}
    nordic_thingy = {}
    
    print("Classifying sensors...")
    
    for mac, sensor_data in aggregated_data.items():
        has_rssi = 'rssiValues' in sensor_data
        has_quaternions = any(key.startswith('quaternion') for key in sensor_data.keys())
        has_gyroscope = any(key.startswith('gyroscope') for key in sensor_data.keys())
        has_compass = any(key.startswith('compass') for key in sensor_data.keys())
        has_accelerometer = any(key.startswith('accelerometer') for key in sensor_data.keys())
        
        # BLE Beacon: Has RSSI, basic accelerometer, but no advanced sensors
        if has_rssi and has_accelerometer and not (has_quaternions or has_gyroscope):
            ble_beacons[mac] = sensor_data
            sensor_type = "BLE Beacon (Location)"
        # Nordic Thingy: Has advanced sensors but no RSSI
        elif not has_rssi and (has_quaternions or has_gyroscope or has_compass):
            nordic_thingy[mac] = sensor_data
            sensor_type = "Nordic Thingy (Object)"
        # Ambiguous case - try to classify based on available sensors
        elif has_rssi:
            ble_beacons[mac] = sensor_data
            sensor_type = "BLE Beacon (Location) - assumed"
        else:
            nordic_thingy[mac] = sensor_data
            sensor_type = "Nordic Thingy (Object) - assumed"
        
        print(f"  {mac}: {sensor_type}")
        if has_rssi:
            print(f"    - RSSI readings: {len(sensor_data.get('rssiValues', {}))}")
        if has_accelerometer:
            accel_count = sum(len(sensor_data.get(key, {})) for key in sensor_data.keys() if key.startswith('accelerometer'))
            print(f"    - Accelerometer readings: {accel_count}")
        if has_quaternions:
            quat_count = sum(len(sensor_data.get(key, {})) for key in sensor_data.keys() if key.startswith('quaternion'))
            print(f"    - Quaternion readings: {quat_count}")
        if has_gyroscope:
            gyro_count = sum(len(sensor_data.get(key, {})) for key in sensor_data.keys() if key.startswith('gyroscope'))
            print(f"    - Gyroscope readings: {gyro_count}")
    
    print(f"\nSensor Classification Summary:")
    print(f"  BLE Beacons (Location sensors): {len(ble_beacons)}")
    print(f"  Nordic Thingy (Object sensors): {len(nordic_thingy)}")
    
    return ble_beacons, nordic_thingy


def assign_sensor_labels(mac_addresses, sensor_type):
    """
    Assign human-readable labels to MAC addresses based on sensor type.
    
    Args:
        mac_addresses (list): List of MAC addresses
        sensor_type (str): Either "beacon" or "object"
        
    Returns:
        dict: Mapping of MAC addresses to labels
    """
    if sensor_type == "beacon":
        # Location labels for BLE beacons
        default_labels = ["kitchen", "living_room", "bedroom", "bathroom", "office", "hallway", "balcony", "dining_room"]
    else:  # object
        # Object labels for Nordic Thingy
        default_labels = ["bottle", "toothbrush", "phone", "keys", "wallet", "book", "cup", "remote"]
    
    mac_to_label = {}
    for i, mac in enumerate(mac_addresses):
        if i < len(default_labels):
            mac_to_label[mac] = default_labels[i]
        else:
            mac_to_label[mac] = f"{sensor_type}_{i+1}"
    
    return mac_to_label


def detect_motion_from_accelerometer(sensor_data, time_window_minutes=1):
    """
    Detect motion periods from accelerometer data.
    
    Args:
        sensor_data (dict): Sensor data for a single device
        time_window_minutes (int): Time window size in minutes
        
    Returns:
        dict: Motion detection results by time window
    """
    motion_windows = defaultdict(list)
    
    # Get all accelerometer axes
    accel_axes = ['accelerometerValues_x', 'accelerometerValues_y', 'accelerometerValues_z']
    
    for axis in accel_axes:
        if axis in sensor_data:
            for timestamp_str, value in sensor_data[axis].items():
                timestamp = parse_timestamp(timestamp_str)
                if timestamp is None:
                    continue
                
                window_key = get_time_window_key(timestamp, time_window_minutes)
                motion_windows[window_key].append(abs(value))
    
    # Calculate motion metrics for each time window
    motion_analysis = {}
    for window_key, values in motion_windows.items():
        if values:
            motion_analysis[window_key] = {
                'average_motion': round(statistics.mean(values), 4),
                'max_motion': round(max(values), 4),
                'motion_variance': round(statistics.variance(values) if len(values) > 1 else 0, 4),
                'sample_count': len(values),
                'is_moving': statistics.mean(values) > 0.02  # Threshold for motion detection
            }
    
    return motion_analysis


def detect_object_interaction(sensor_data, time_window_minutes=1):
    """
    Detect object interactions from Nordic Thingy sensor data.
    
    Args:
        sensor_data (dict): Sensor data for a single Nordic Thingy device
        time_window_minutes (int): Time window size in minutes
        
    Returns:
        dict: Object interaction analysis by time window
    """
    time_windows = defaultdict(lambda: defaultdict(list))
    
    # Process all available sensor types
    sensor_types = ['accelerometerValues_x', 'accelerometerValues_y', 'accelerometerValues_z',
                   'gyroscopeValues_x', 'gyroscopeValues_y', 'gyroscopeValues_z',
                   'quaternionValues_w', 'quaternionValues_x', 'quaternionValues_y', 'quaternionValues_z']
    
    for sensor_type in sensor_types:
        if sensor_type in sensor_data:
            for timestamp_str, value in sensor_data[sensor_type].items():
                timestamp = parse_timestamp(timestamp_str)
                if timestamp is None:
                    continue
                
                window_key = get_time_window_key(timestamp, time_window_minutes)
                time_windows[window_key][sensor_type].append(value)
    
    # Analyze each time window
    interaction_analysis = {}
    for window_key, sensor_values in time_windows.items():
        window_analysis = {
            'accelerometer_activity': 0,
            'gyroscope_activity': 0,
            'orientation_change': 0,
            'total_activity_score': 0,
            'is_interacting': False,
            'interaction_type': None,
            'sensor_data': {}
        }
        
        # Calculate accelerometer activity (motion intensity)
        accel_values = []
        for axis in ['accelerometerValues_x', 'accelerometerValues_y', 'accelerometerValues_z']:
            if axis in sensor_values:
                accel_values.extend(sensor_values[axis])
        
        if accel_values:
            window_analysis['accelerometer_activity'] = round(statistics.variance(accel_values), 4)
            window_analysis['sensor_data']['accelerometer'] = {
                'mean': round(statistics.mean(accel_values), 4),
                'variance': round(statistics.variance(accel_values), 4),
                'sample_count': len(accel_values)
            }
        
        # Calculate gyroscope activity (rotation intensity)
        gyro_values = []
        for axis in ['gyroscopeValues_x', 'gyroscopeValues_y', 'gyroscopeValues_z']:
            if axis in sensor_values:
                gyro_values.extend(sensor_values[axis])
        
        if gyro_values:
            window_analysis['gyroscope_activity'] = round(statistics.variance(gyro_values), 4)
            window_analysis['sensor_data']['gyroscope'] = {
                'mean': round(statistics.mean(gyro_values), 4),
                'variance': round(statistics.variance(gyro_values), 4),
                'sample_count': len(gyro_values)
            }
        
        # Calculate orientation change (quaternion analysis)
        quat_values = []
        for axis in ['quaternionValues_w', 'quaternionValues_x', 'quaternionValues_y', 'quaternionValues_z']:
            if axis in sensor_values:
                quat_values.extend(sensor_values[axis])
        
        if quat_values:
            window_analysis['orientation_change'] = round(statistics.variance(quat_values), 4)
            window_analysis['sensor_data']['quaternion'] = {
                'mean': round(statistics.mean(quat_values), 4),
                'variance': round(statistics.variance(quat_values), 4),
                'sample_count': len(quat_values)
            }
        
        # Calculate total activity score and determine interaction
        activity_score = (window_analysis['accelerometer_activity'] * 1.0 + 
                         window_analysis['gyroscope_activity'] * 0.5 + 
                         window_analysis['orientation_change'] * 0.3)
        
        window_analysis['total_activity_score'] = round(activity_score, 4)
        
        # Determine interaction type based on sensor patterns
        if window_analysis['accelerometer_activity'] > 0.001:  # High motion
            if window_analysis['gyroscope_activity'] > 0.5:  # High rotation
                window_analysis['interaction_type'] = 'active_manipulation'
            else:
                window_analysis['interaction_type'] = 'gentle_movement'
        elif window_analysis['gyroscope_activity'] > 0.1:  # Rotation without much translation
            window_analysis['interaction_type'] = 'rotation_only'
        elif window_analysis['orientation_change'] > 0.01:  # Orientation change
            window_analysis['interaction_type'] = 'orientation_change'
        
        window_analysis['is_interacting'] = activity_score > 0.01  # Threshold for interaction
        
        interaction_analysis[window_key] = window_analysis
    
    return interaction_analysis


def analyze_location_and_activity(aggregated_data, time_window_minutes=1):
    """
    Analyze both location (from BLE beacons) and object interactions (from Nordic Thingy).
    
    Args:
        aggregated_data (dict): Aggregated sensor data by MAC address
        time_window_minutes (int): Time window size in minutes
        
    Returns:
        dict: Combined location and activity analysis results
    """
    # Classify sensors into BLE beacons and Nordic Thingy
    ble_beacons, nordic_thingy = classify_sensors(aggregated_data)
    
    # Assign labels to each sensor type
    beacon_addresses = list(ble_beacons.keys())
    object_addresses = list(nordic_thingy.keys())
    
    beacon_labels = assign_sensor_labels(beacon_addresses, "beacon")
    object_labels = assign_sensor_labels(object_addresses, "object")
    
    print(f"\nLocation Labels (BLE Beacons): {beacon_labels}")
    print(f"Object Labels (Nordic Thingy): {object_labels}")
    
    # Analyze location from BLE beacons (RSSI-based)
    location_analysis = {}
    if ble_beacons:
        location_analysis = analyze_location_by_rssi(ble_beacons, time_window_minutes, beacon_labels)
    
    # Analyze object interactions from Nordic Thingy
    object_interactions = {}
    object_summary = defaultdict(int)
    
    for mac, sensor_data in nordic_thingy.items():
        print(f"\nAnalyzing object interactions for {object_labels[mac]} ({mac})")
        interactions = detect_object_interaction(sensor_data, time_window_minutes)
        object_interactions[mac] = interactions
        
        # Count active interactions
        for window_key, interaction_data in interactions.items():
            if interaction_data['is_interacting']:
                object_summary[object_labels[mac]] += 1
    
    # Combine location and object analysis
    combined_analysis = {}
    all_time_windows = set()
    
    # Collect all time windows from both analyses
    if location_analysis:
        all_time_windows.update(location_analysis.get('time_windows', {}).keys())
    
    for mac_interactions in object_interactions.values():
        all_time_windows.update(mac_interactions.keys())
    
    # Create combined analysis for each time window
    for window_key in sorted(all_time_windows):
        window_analysis = {
            'location_info': None,
            'object_interactions': {},
            'context_inference': None
        }
        
        # Add location information
        if location_analysis and window_key in location_analysis.get('time_windows', {}):
            window_analysis['location_info'] = location_analysis['time_windows'][window_key]
        
        # Add object interactions
        for mac, interactions in object_interactions.items():
            if window_key in interactions:
                window_analysis['object_interactions'][object_labels[mac]] = interactions[window_key]
        
        # Infer context from location + object interactions
        context_inference = infer_activity_context(window_analysis)
        window_analysis['context_inference'] = context_inference
        
        combined_analysis[window_key] = window_analysis
    
    # Create final results structure
    results = {
        "analysis_settings": {
            "time_window_minutes": time_window_minutes,
            "beacon_labels": beacon_labels,
            "object_labels": object_labels,
            "total_beacons": len(ble_beacons),
            "total_objects": len(nordic_thingy),
            "total_time_windows": len(combined_analysis)
        },
        "location_analysis": location_analysis,
        "object_interactions": object_interactions,
        "combined_analysis": combined_analysis,
        "activity_summary": {
            "location_frequency": location_analysis.get('location_summary', {}),
            "object_interaction_frequency": dict(object_summary)
        }
    }
    
    return results


def analyze_location_by_rssi(ble_beacons, time_window_minutes=1, beacon_labels=None):
    """
    Analyze location based on RSSI values from BLE beacons.
    
    Args:
        ble_beacons (dict): BLE beacon sensor data by MAC address
        time_window_minutes (int): Time window size in minutes
        beacon_labels (dict): MAC to label mapping
        
    Returns:
        dict: Location analysis results
    """
    if not beacon_labels:
        beacon_labels = assign_sensor_labels(list(ble_beacons.keys()), "beacon")
    
    # Group RSSI data by time windows
    time_windows = defaultdict(lambda: defaultdict(list))
    
    print(f"Processing {len(ble_beacons)} BLE beacons for location analysis...")
    
    # Process each beacon and its RSSI values
    for mac, sensor_data in ble_beacons.items():
        if 'rssiValues' not in sensor_data:
            print(f"Warning: No RSSI data found for beacon {mac}")
            continue
            
        rssi_data = sensor_data['rssiValues']
        print(f"Processing {len(rssi_data)} RSSI readings for {beacon_labels[mac]} ({mac})")
        
        # Group RSSI values by time windows
        for timestamp_str, rssi_value in rssi_data.items():
            timestamp = parse_timestamp(timestamp_str)
            if timestamp is None:
                continue
                
            window_key = get_time_window_key(timestamp, time_window_minutes)
            time_windows[window_key][mac].append(rssi_value)
    
    # Analyze each time window to find the closest location
    results = {
        "time_windows": {},
        "location_summary": defaultdict(int)
    }
    
    print(f"Analyzing {len(time_windows)} time windows for location...")
    
    for window_key, mac_rssi_data in time_windows.items():
        window_analysis = {
            "closest_location": None,
            "closest_mac": None,
            "closest_rssi": None,
            "all_locations": {}
        }
        
        best_rssi = float('-inf')  # Start with very low RSSI
        best_mac = None
        
        # Calculate average RSSI for each beacon in this time window
        for mac, rssi_values in mac_rssi_data.items():
            if rssi_values:
                avg_rssi = statistics.mean(rssi_values)
                max_rssi = max(rssi_values)
                min_rssi = min(rssi_values)
                
                window_analysis["all_locations"][beacon_labels[mac]] = {
                    "mac": mac,
                    "average_rssi": round(avg_rssi, 2),
                    "max_rssi": max_rssi,
                    "min_rssi": min_rssi,
                    "sample_count": len(rssi_values)
                }
                
                # Higher RSSI (closer to 0) means stronger signal and closer proximity
                if avg_rssi > best_rssi:
                    best_rssi = avg_rssi
                    best_mac = mac
        
        if best_mac:
            window_analysis["closest_location"] = beacon_labels[best_mac]
            window_analysis["closest_mac"] = best_mac
            window_analysis["closest_rssi"] = round(best_rssi, 2)
            
            # Update location summary
            results["location_summary"][beacon_labels[best_mac]] += 1
        
        results["time_windows"][window_key] = window_analysis
    
    return results


def infer_activity_context(window_analysis):
    """
    Infer activity context from location and object interactions.
    
    Args:
        window_analysis (dict): Combined analysis for a time window
        
    Returns:
        dict: Context inference results
    """
    context = {
        'primary_location': None,
        'active_objects': [],
        'inferred_activities': [],
        'confidence_score': 0.0
    }
    
    # Extract location information
    location_info = window_analysis.get('location_info')
    if location_info and location_info.get('closest_location'):
        context['primary_location'] = location_info['closest_location']
    
    # Extract active objects
    object_interactions = window_analysis.get('object_interactions', {})
    for object_name, interaction_data in object_interactions.items():
        if interaction_data.get('is_interacting'):
            context['active_objects'].append({
                'object': object_name,
                'interaction_type': interaction_data.get('interaction_type'),
                'activity_score': interaction_data.get('total_activity_score', 0)
            })
    
    # Infer activities based on location + object combinations
    if context['primary_location'] and context['active_objects']:
        activities = []
        
        for obj_info in context['active_objects']:
            activity = infer_specific_activity(context['primary_location'], obj_info['object'], obj_info['interaction_type'])
            if activity:
                activities.append(activity)
        
        context['inferred_activities'] = activities
        context['confidence_score'] = min(1.0, len(activities) * 0.3)  # Simple confidence metric
    
    return context


def infer_specific_activity(location, object_name, interaction_type):
    """
    Infer specific activity based on location, object, and interaction type.
    
    Args:
        location (str): Location name
        object_name (str): Object name
        interaction_type (str): Type of interaction
        
    Returns:
        str: Inferred activity or None
    """
    # Activity inference rules
    activity_rules = {
        ('kitchen', 'bottle'): {
            'active_manipulation': 'drinking',
            'gentle_movement': 'handling_bottle',
            'rotation_only': 'opening_bottle'
        },
        ('bathroom', 'toothbrush'): {
            'active_manipulation': 'brushing_teeth',
            'gentle_movement': 'handling_toothbrush'
        },
        ('kitchen', 'cup'): {
            'active_manipulation': 'drinking',
            'gentle_movement': 'handling_cup'
        },
        ('living_room', 'remote'): {
            'active_manipulation': 'using_remote',
            'gentle_movement': 'handling_remote'
        },
        ('bedroom', 'phone'): {
            'active_manipulation': 'using_phone',
            'gentle_movement': 'handling_phone'
        }
    }
    
    # Check for specific location-object combinations
    location_object_key = (location, object_name)
    if location_object_key in activity_rules:
        activities = activity_rules[location_object_key]
        return activities.get(interaction_type, f'interacting_with_{object_name}')
    
    # Generic activity inference
    if interaction_type == 'active_manipulation':
        return f'actively_using_{object_name}'
    elif interaction_type == 'gentle_movement':
        return f'handling_{object_name}'
    elif interaction_type == 'rotation_only':
        return f'rotating_{object_name}'
    else:
        return f'interacting_with_{object_name}'


def generate_comprehensive_report(results):
    """
    Generate a comprehensive human-readable report for dual sensor analysis.
    
    Args:
        results (dict): Analysis results
        
    Returns:
        str: Comprehensive report
    """
    report = []
    report.append("=" * 70)
    report.append("SHPIA COMPREHENSIVE LOCATION & ACTIVITY ANALYSIS REPORT")
    report.append("=" * 70)
    
    settings = results["analysis_settings"]
    report.append(f"Time Window: {settings['time_window_minutes']} minute(s)")
    report.append(f"Total BLE Beacons (Location): {settings['total_beacons']}")
    report.append(f"Total Nordic Thingy (Objects): {settings['total_objects']}")
    report.append(f"Total Time Windows: {settings['total_time_windows']}")
    report.append("")
    
    # Sensor Labels
    report.append("SENSOR LABELS:")
    report.append("  BLE Beacons (Locations):")
    for mac, label in settings["beacon_labels"].items():
        report.append(f"    {label}: {mac}")
    report.append("  Nordic Thingy (Objects):")
    for mac, label in settings["object_labels"].items():
        report.append(f"    {label}: {mac}")
    report.append("")
    
    # Activity Summary
    report.append("ACTIVITY SUMMARY:")
    activity_summary = results["activity_summary"]
    
    report.append("  Location Frequency:")
    location_freq = activity_summary.get("location_frequency", {})
    total_location_windows = sum(location_freq.values())
    for location, count in sorted(location_freq.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_location_windows * 100) if total_location_windows > 0 else 0
        report.append(f"    {location}: {count} windows ({percentage:.1f}%)")
    
    report.append("  Object Interaction Frequency:")
    object_freq = activity_summary.get("object_interaction_frequency", {})
    total_object_windows = sum(object_freq.values())
    for obj, count in sorted(object_freq.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_object_windows * 100) if total_object_windows > 0 else 0
        report.append(f"    {obj}: {count} interactions ({percentage:.1f}%)")
    
    report.append("")
    
    # Sample Combined Analysis
    report.append("SAMPLE COMBINED ANALYSIS:")
    combined_analysis = results["combined_analysis"]
    sample_windows = sorted(combined_analysis.items())[:5]
    
    for window_key, window_data in sample_windows:
        report.append(f"  {window_key}:")
        
        # Location info
        location_info = window_data.get("location_info")
        if location_info and location_info.get("closest_location"):
            report.append(f"    Location: {location_info['closest_location']} (RSSI: {location_info.get('closest_rssi', 'N/A')} dBm)")
        else:
            report.append(f"    Location: Unknown")
        
        # Object interactions
        object_interactions = window_data.get("object_interactions", {})
        if object_interactions:
            report.append(f"    Object Interactions:")
            for obj_name, interaction_data in object_interactions.items():
                if interaction_data.get("is_interacting"):
                    interaction_type = interaction_data.get("interaction_type", "unknown")
                    activity_score = interaction_data.get("total_activity_score", 0)
                    report.append(f"      {obj_name}: {interaction_type} (score: {activity_score})")
        
        # Context inference
        context = window_data.get("context_inference", {})
        if context and context.get("inferred_activities"):
            report.append(f"    Inferred Activities:")
            for activity in context["inferred_activities"]:
                report.append(f"      - {activity}")
            report.append(f"    Confidence: {context.get('confidence_score', 0):.2f}")
        
        report.append("")
    
    # Detailed Activity Patterns
    report.append("ACTIVITY PATTERNS:")
    activity_patterns = analyze_activity_patterns(results)
    for pattern, description in activity_patterns.items():
        report.append(f"  {pattern}: {description}")
    
    return "\n".join(report)


def analyze_activity_patterns(results):
    """
    Analyze patterns in the combined data to identify common activities.
    
    Args:
        results (dict): Analysis results
        
    Returns:
        dict: Activity patterns and descriptions
    """
    patterns = {}
    combined_analysis = results["combined_analysis"]
    
    # Count location-object combinations
    location_object_combinations = defaultdict(int)
    activity_counts = defaultdict(int)
    
    for window_data in combined_analysis.values():
        location_info = window_data.get("location_info")
        if location_info and location_info.get("closest_location"):
            location = location_info["closest_location"]
            
            object_interactions = window_data.get("object_interactions", {})
            for obj_name, interaction_data in object_interactions.items():
                if interaction_data.get("is_interacting"):
                    location_object_combinations[f"{location}+{obj_name}"] += 1
                    
                    # Count inferred activities
                    context = window_data.get("context_inference", {})
                    for activity in context.get("inferred_activities", []):
                        activity_counts[activity] += 1
    
    # Generate pattern descriptions
    if location_object_combinations:
        most_common_combo = max(location_object_combinations.items(), key=lambda x: x[1])
        patterns["Most Common Location-Object Combination"] = f"{most_common_combo[0]} ({most_common_combo[1]} times)"
    
    if activity_counts:
        most_common_activity = max(activity_counts.items(), key=lambda x: x[1])
        patterns["Most Common Activity"] = f"{most_common_activity[0]} ({most_common_activity[1]} times)"
    
    # Calculate activity diversity
    unique_activities = len(activity_counts)
    patterns["Activity Diversity"] = f"{unique_activities} unique activities detected"
    
    return patterns


def main():
    """
    Main function to process aggregated data and analyze location and activity.
    """
    parser = argparse.ArgumentParser(
        description='Analyze location and activity from dual sensor data (BLE beacons + Nordic Thingy)',
        epilog='Example: python location_analyzer.py data/output.json -o analysis.json --time-window 5 --beacon-labels kitchen sofa --object-labels bottle cup'
    )
    
    parser.add_argument(
        'input_file',
        help='Input JSON file containing aggregated sensor data'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file path for analysis results (optional, prints to console if not specified)'
    )
    
    parser.add_argument(
        '--time-window',
        type=int,
        default=1,
        help='Time window size in minutes for grouping timestamps (default: 1)'
    )
    
    parser.add_argument(
        '--beacon-labels',
        nargs='+',
        help='Custom location labels for BLE beacons (space-separated)'
    )
    
    parser.add_argument(
        '--object-labels',
        nargs='+',
        help='Custom object labels for Nordic Thingy devices (space-separated)'
    )
    
    # Legacy support for --labels parameter
    parser.add_argument(
        '--labels',
        nargs='+',
        help='Legacy: Custom labels for all devices (deprecated, use --beacon-labels and --object-labels)'
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        exit(1)
    
    try:
        # Load aggregated data
        print(f"Loading aggregated data from '{args.input_file}'...")
        with open(args.input_file, 'r') as f:
            aggregated_data = json.load(f)
        
        # Analyze location and activity
        print("Analyzing location and activity from dual sensor data...")
        results = analyze_location_and_activity(aggregated_data, args.time_window)
        
        # Override labels if provided
        if args.beacon_labels:
            beacon_macs = list(results["analysis_settings"]["beacon_labels"].keys())
            if len(args.beacon_labels) != len(beacon_macs):
                print(f"Warning: Number of beacon labels ({len(args.beacon_labels)}) doesn't match number of beacons ({len(beacon_macs)})")
            else:
                # Update beacon labels
                new_beacon_labels = {}
                for i, mac in enumerate(beacon_macs):
                    new_beacon_labels[mac] = args.beacon_labels[i]
                results["analysis_settings"]["beacon_labels"] = new_beacon_labels
                update_labels_in_results(results, new_beacon_labels, "beacon")
        
        if args.object_labels:
            object_macs = list(results["analysis_settings"]["object_labels"].keys())
            if len(args.object_labels) != len(object_macs):
                print(f"Warning: Number of object labels ({len(args.object_labels)}) doesn't match number of objects ({len(object_macs)})")
            else:
                # Update object labels
                new_object_labels = {}
                for i, mac in enumerate(object_macs):
                    new_object_labels[mac] = args.object_labels[i]
                results["analysis_settings"]["object_labels"] = new_object_labels
                update_labels_in_results(results, new_object_labels, "object")
        
        # Legacy support for --labels parameter
        if args.labels and not args.beacon_labels and not args.object_labels:
            print("Warning: --labels parameter is deprecated. Use --beacon-labels and --object-labels instead.")
            all_macs = list(results["analysis_settings"]["beacon_labels"].keys()) + list(results["analysis_settings"]["object_labels"].keys())
            if len(args.labels) == len(all_macs):
                beacon_count = len(results["analysis_settings"]["beacon_labels"])
                if beacon_count > 0:
                    new_beacon_labels = {}
                    for i, mac in enumerate(list(results["analysis_settings"]["beacon_labels"].keys())):
                        new_beacon_labels[mac] = args.labels[i]
                    results["analysis_settings"]["beacon_labels"] = new_beacon_labels
                    update_labels_in_results(results, new_beacon_labels, "beacon")
                
                if len(args.labels) > beacon_count:
                    new_object_labels = {}
                    for i, mac in enumerate(list(results["analysis_settings"]["object_labels"].keys())):
                        new_object_labels[mac] = args.labels[beacon_count + i]
                    results["analysis_settings"]["object_labels"] = new_object_labels
                    update_labels_in_results(results, new_object_labels, "object")
        
        # Generate comprehensive report
        comprehensive_report = generate_comprehensive_report(results)
        
        # Output results
        if args.output:
            # Save detailed results to JSON file
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Analysis results saved to '{args.output}'")
            
            # Also save comprehensive report
            report_file = args.output.replace('.json', '_report.txt')
            with open(report_file, 'w') as f:
                f.write(comprehensive_report)
            print(f"Comprehensive report saved to '{report_file}'")
        else:
            # Print report to console
            print("\n" + comprehensive_report)
            
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


def update_labels_in_results(results, new_labels, label_type):
    """
    Update labels throughout the results structure.
    
    Args:
        results (dict): Analysis results
        new_labels (dict): New MAC to label mapping
        label_type (str): Either "beacon" or "object"
    """
    # Update activity summary
    if label_type == "beacon":
        # Update location frequency with new labels
        old_location_freq = results["activity_summary"].get("location_frequency", {})
        new_location_freq = {}
        old_beacon_labels = {v: k for k, v in results["analysis_settings"]["beacon_labels"].items()}
        
        for old_label, count in old_location_freq.items():
            # Find MAC for this old label
            for mac, new_label in new_labels.items():
                if old_beacon_labels.get(old_label) == mac:
                    new_location_freq[new_label] = count
                    break
        
        results["activity_summary"]["location_frequency"] = new_location_freq
        
        # Update location analysis
        if "location_analysis" in results and results["location_analysis"]:
            update_location_analysis_labels(results["location_analysis"], new_labels)
    
    else:  # object
        # Update object interaction frequency
        old_object_freq = results["activity_summary"].get("object_interaction_frequency", {})
        new_object_freq = {}
        old_object_labels = {v: k for k, v in results["analysis_settings"]["object_labels"].items()}
        
        for old_label, count in old_object_freq.items():
            # Find MAC for this old label
            for mac, new_label in new_labels.items():
                if old_object_labels.get(old_label) == mac:
                    new_object_freq[new_label] = count
                    break
        
        results["activity_summary"]["object_interaction_frequency"] = new_object_freq
    
    # Update combined analysis
    update_combined_analysis_labels(results["combined_analysis"], new_labels, label_type)


def update_location_analysis_labels(location_analysis, new_labels):
    """Update location analysis with new labels."""
    if "location_summary" in location_analysis:
        old_summary = location_analysis["location_summary"]
        new_summary = {}
        old_labels = {v: k for k, v in new_labels.items()}
        
        for old_label, count in old_summary.items():
            for mac, new_label in new_labels.items():
                if old_labels.get(old_label) == mac:
                    new_summary[new_label] = count
                    break
        
        location_analysis["location_summary"] = new_summary
    
    # Update time windows
    if "time_windows" in location_analysis:
        for window_data in location_analysis["time_windows"].values():
            if window_data.get("closest_mac") in new_labels:
                window_data["closest_location"] = new_labels[window_data["closest_mac"]]
            
            # Update all_locations
            if "all_locations" in window_data:
                new_all_locations = {}
                for old_label, location_data in window_data["all_locations"].items():
                    mac = location_data["mac"]
                    if mac in new_labels:
                        new_all_locations[new_labels[mac]] = location_data
                    else:
                        new_all_locations[old_label] = location_data
                window_data["all_locations"] = new_all_locations


def update_combined_analysis_labels(combined_analysis, new_labels, label_type):
    """Update combined analysis with new labels."""
    for window_data in combined_analysis.values():
        if label_type == "beacon":
            # Update location info
            location_info = window_data.get("location_info")
            if location_info and location_info.get("closest_mac") in new_labels:
                location_info["closest_location"] = new_labels[location_info["closest_mac"]]
            
            if location_info and "all_locations" in location_info:
                new_all_locations = {}
                for old_label, location_data in location_info["all_locations"].items():
                    mac = location_data["mac"]
                    if mac in new_labels:
                        new_all_locations[new_labels[mac]] = location_data
                    else:
                        new_all_locations[old_label] = location_data
                location_info["all_locations"] = new_all_locations
        
        else:  # object
            # Update object interactions
            object_interactions = window_data.get("object_interactions", {})
            new_object_interactions = {}
            old_object_labels = {v: k for k, v in new_labels.items()}
            
            for old_label, interaction_data in object_interactions.items():
                # Find new label for this old label
                found = False
                for mac, new_label in new_labels.items():
                    if old_object_labels.get(old_label) == mac:
                        new_object_interactions[new_label] = interaction_data
                        found = True
                        break
                
                if not found:
                    new_object_interactions[old_label] = interaction_data
            
            window_data["object_interactions"] = new_object_interactions
        
        # Update context inference
        context = window_data.get("context_inference", {})
        if context and "active_objects" in context:
            for obj_info in context["active_objects"]:
                old_obj_name = obj_info["object"]
                if label_type == "object":
                    # Find new object name
                    for mac, new_label in new_labels.items():
                        if old_object_labels.get(old_obj_name) == mac:
                            obj_info["object"] = new_label
                            break


if __name__ == "__main__":
    main()
