import requests
import numpy as np
from sgp4.api import Satrec, jday
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from scipy.special import erfc
import logging
from queue import Queue
from threading import Lock

# Import new services
from services.llm_client import HuggingFaceLLMClient, LLMAPIError, LLMTimeoutError, LLMRateLimitError
from services.cache_manager import ReportCacheManager
from services.report_service import ReportGenerationService
from config.config_loader import get_config

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# N2YO.com API configuration
N2YO_API_KEY = "G8TU84-GHMZRS-NN8XDL-5KJ7"
N2YO_TLE_URL = "https://api.n2yo.com/rest/v1/satellite/tle/{}/{}"

# Development mode - prioritize local data over API calls
DEVELOPMENT_MODE = True

# Initialize LLM services
try:
    config = get_config()
    logger.info("Configuration loaded successfully")
    
    # Initialize LLM client
    llm_client = HuggingFaceLLMClient(
        api_key=config.get('api_key'),
        model_name=config.get('model_name', 'mistralai/Mistral-7B-Instruct-v0.2'),
        timeout=config.get('retry_config', {}).get('timeout_seconds', 30),
        max_retries=config.get('retry_config', {}).get('max_retries', 2),
        backoff_factor=config.get('retry_config', {}).get('backoff_factor', 2.0)
    )
    logger.info("LLM client initialized")
    
    # Initialize cache manager
    cache_config = config.get('cache_config', {})
    cache_manager = ReportCacheManager(
        max_size=cache_config.get('max_size', 100),
        ttl_seconds=cache_config.get('ttl_seconds', 3600)
    )
    logger.info("Cache manager initialized")
    
    # Initialize report service
    report_service = ReportGenerationService(llm_client, cache_manager, config)
    logger.info("Report service initialized")
    
    # Request queue for rate limiting
    report_queue = Queue(maxsize=10)
    queue_lock = Lock()
    
except Exception as e:
    logger.error(f"Failed to initialize LLM services: {e}")
    llm_client = None
    cache_manager = None
    report_service = None

def fetch_tle_data(norad_ids):
    """Fetch TLE data for given NORAD IDs from N2YO API with fallback to local data."""
    tle_data = {}
    
    # Try to load local TLE data
    local_tle_data = load_local_tle_data()
    
    for norad_id in norad_ids:
        try:
            # In development mode, prioritize local data
            if DEVELOPMENT_MODE and norad_id in local_tle_data:
                tle_data[norad_id] = local_tle_data[norad_id]
                print(f"Using local TLE data for NORAD ID {norad_id} (development mode)")
                continue
            
            # Try N2YO API if not in development mode or local data not available
            if not DEVELOPMENT_MODE:
                response = requests.get(N2YO_TLE_URL.format(norad_id, N2YO_API_KEY), timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'tle' in data and data['tle'] and len(data['tle'].strip().split('\n')) >= 2:
                        tle_lines = data['tle'].strip().split('\n')
                        if len(tle_lines) >= 2 and tle_lines[0].strip() and tle_lines[1].strip():
                            tle_data[norad_id] = tle_lines[:2]  # Only take first two lines
                            continue
            
            # Fallback to local TLE data if API fails or in development mode
            if norad_id in local_tle_data:
                tle_data[norad_id] = local_tle_data[norad_id]
                print(f"Using local TLE data for NORAD ID {norad_id}")
                
        except Exception as e:
            print(f"Error fetching TLE for NORAD ID {norad_id}: {e}")
            # Try local data as fallback
            if norad_id in local_tle_data:
                tle_data[norad_id] = local_tle_data[norad_id]
                print(f"Using local TLE data for NORAD ID {norad_id} after API error")
            continue
    
    return tle_data

def get_satellite_metadata(norad_id):
    """Get satellite metadata including size from OIO file."""
    try:
        with open("../data/oio.20171129.txt", "r") as f:
            lines = f.readlines()
        
        for line in lines:
            parts = line.strip().split(',')
            if len(parts) >= 9 and parts[2] == str(norad_id):
                return {
                    'name': parts[1],
                    'size': parts[8] if len(parts) > 8 else 'MEDIUM',
                    'period': float(parts[4]) if parts[4] else 90.0,
                    'altitude': (float(parts[6]) + float(parts[7])) / 2 if parts[6] and parts[7] else 500.0
                }
    except Exception as e:
        print(f"Error loading metadata for {norad_id}: {e}")
    
    # Default metadata
    return {
        'name': f'Satellite {norad_id}',
        'size': 'MEDIUM',
        'period': 90.0,
        'altitude': 500.0
    }

def load_local_tle_data():
    """Load TLE data from local file as fallback."""
    tle_data = {}
    try:
        with open("../data/tle.20171129.txt", "r") as f:
            lines = f.readlines()
            
        # Parse TLE data (every 2 lines represent one satellite)
        for i in range(0, len(lines) - 1, 2):
            if i + 1 < len(lines):
                line1 = lines[i].strip()
                line2 = lines[i + 1].strip()
                
                if line1 and line2 and len(line1) >= 7 and len(line2) >= 7:
                    # Extract NORAD ID from line 1 (characters 2-7)
                    try:
                        norad_id = line1[2:7].strip()
                        if norad_id.isdigit():
                            tle_data[norad_id] = [line1, line2]
                    except:
                        continue
    except Exception as e:
        print(f"Error loading local TLE data: {e}")
    
    return tle_data

def tle_to_position_velocity(line1, line2, current_time):
    """Converts TLE lines to position and velocity in ECI frame."""
    satellite = Satrec.twoline2rv(line1, line2)
    jd, fr = jday(current_time.year, current_time.month, current_time.day,
                  current_time.hour, current_time.minute, current_time.second)
    e, position, velocity = satellite.sgp4(jd, fr)

    if e == 0:  # No error
        return np.array(position), np.array(velocity)
    else:
        return None, None

def calculate_relative_metrics(pos1, vel1, pos2, vel2):
    """Calculates relative position, velocity, and speed."""
    relative_position = np.array(pos1) - np.array(pos2)
    relative_velocity = np.array(vel1) - np.array(vel2)
    distance = np.linalg.norm(relative_position)
    relative_speed = np.linalg.norm(relative_velocity)
    return distance, relative_speed

def calculate_tle_uncertainty(tle_age_days, satellite_altitude):
    """
    Calculate realistic TLE uncertainty based on age and altitude.
    TLE accuracy degrades over time, especially for low-altitude satellites.
    
    Args:
        tle_age_days: Age of TLE data in days
        satellite_altitude: Mean altitude in km
        
    Returns:
        position_sigma: Position uncertainty in km
        velocity_sigma: Velocity uncertainty in km/s
    """
    # Base uncertainties (typical for fresh TLE data)
    base_pos_sigma = 1.0  # km
    base_vel_sigma = 0.001  # km/s
    
    # Altitude factor - lower satellites have higher uncertainty due to drag
    if satellite_altitude < 600:
        altitude_factor = 2.0
    elif satellite_altitude < 1000:
        altitude_factor = 1.5
    else:
        altitude_factor = 1.0
    
    # Age factor - uncertainty grows with TLE age
    age_factor = 1.0 + (tle_age_days * 0.1)  # 10% increase per day
    
    position_sigma = base_pos_sigma * altitude_factor * age_factor
    velocity_sigma = base_vel_sigma * altitude_factor * age_factor
    
    return position_sigma, velocity_sigma

def predict_closest_approach(pos1, vel1, pos2, vel2, max_time_hours=24):
    """
    Predict the time of closest approach (TCA) between two satellites.
    
    Args:
        pos1, vel1: Position and velocity of satellite 1 (km, km/s)
        pos2, vel2: Position and velocity of satellite 2 (km, km/s)
        max_time_hours: Maximum time to search for TCA
        
    Returns:
        tca_seconds: Time to closest approach in seconds
        min_distance: Minimum distance at TCA in km
        relative_velocity: Relative velocity vector at TCA
    """
    # Relative position and velocity
    rel_pos = np.array(pos1) - np.array(pos2)
    rel_vel = np.array(vel1) - np.array(vel2)
    
    # Find TCA using quadratic approximation
    # Distance^2 = |rel_pos + rel_vel * t|^2
    # Minimize by taking derivative and setting to zero
    
    dot_pos_vel = np.dot(rel_pos, rel_vel)
    dot_vel_vel = np.dot(rel_vel, rel_vel)
    
    if abs(dot_vel_vel) < 1e-10:
        # Parallel trajectories - use current distance
        tca_seconds = 0
    else:
        tca_seconds = -dot_pos_vel / dot_vel_vel
    
    # Limit TCA to reasonable time window
    max_seconds = max_time_hours * 3600
    tca_seconds = max(0, min(tca_seconds, max_seconds))
    
    # Calculate position and distance at TCA
    rel_pos_tca = rel_pos + rel_vel * tca_seconds
    min_distance = np.linalg.norm(rel_pos_tca)
    
    return tca_seconds, min_distance, rel_vel

def calculate_combined_radius(sat1_type, sat2_type):
    """
    Calculate combined hard body radius based on satellite types.
    
    Args:
        sat1_type, sat2_type: Satellite size types ('SMALL', 'MEDIUM', 'LARGE')
        
    Returns:
        combined_radius: Combined hard body radius in km
    """
    # Typical satellite dimensions
    size_radius = {
        'SMALL': 0.001,   # 1 meter radius (CubeSats)
        'MEDIUM': 0.003,  # 3 meter radius (typical satellites)
        'LARGE': 0.008,   # 8 meter radius (large satellites/ISS)
        '': 0.002         # Default for unknown
    }
    
    radius1 = size_radius.get(sat1_type, 0.002)
    radius2 = size_radius.get(sat2_type, 0.002)
    
    # Combined radius with safety margin
    combined_radius = (radius1 + radius2) * 2.0  # 2x safety factor
    
    return combined_radius

def dynamic_collision_probability(miss_distance, position_uncertainty, combined_radius, 
                                relative_velocity_magnitude, altitude_factor, size_factor):
    """
    Calculate dynamic collision probability using enhanced Alfano-inspired method.
    Incorporates multiple factors for realistic probability variation.
    
    Args:
        miss_distance: Distance of closest approach (km)
        position_uncertainty: 1-sigma position uncertainty (km)
        combined_radius: Combined hard body radius (km)
        relative_velocity_magnitude: Relative velocity magnitude (km/s)
        altitude_factor: Factor based on orbital altitude (1.0-3.0)
        size_factor: Factor based on satellite sizes (1.0-2.0)
        
    Returns:
        collision_probability: Probability of collision (0-1)
    """
    from scipy.special import erfc
    
    # Enhanced collision cross-section considering velocity and size
    velocity_factor = 1.0 + (relative_velocity_magnitude / 15.0)  # Higher velocity = higher risk
    effective_collision_radius = combined_radius * size_factor * velocity_factor
    
    # Dynamic uncertainty scaling based on altitude and conditions
    enhanced_uncertainty = position_uncertainty * altitude_factor
    
    # Calculate probability using multiple approaches and combine them
    
    # 1. Direct geometric probability (for very close approaches)
    if miss_distance <= effective_collision_radius:
        geometric_prob = 1.0 - (miss_distance / effective_collision_radius)
        geometric_prob = max(0.0, geometric_prob)
    else:
        geometric_prob = 0.0
    
    # 2. Statistical probability using error function
    if enhanced_uncertainty > 0:
        # Normalized miss distance in terms of uncertainty
        sigma_distance = miss_distance / enhanced_uncertainty
        
        # Calculate collision probability using complementary error function
        # This represents the probability that position errors cause a collision
        collision_threshold = effective_collision_radius / enhanced_uncertainty
        
        if sigma_distance <= collision_threshold:
            # Close approach - high probability region
            erfc_prob = 0.5 * erfc((sigma_distance - collision_threshold) / np.sqrt(2))
        else:
            # Distant approach - decreasing probability
            erfc_prob = 0.5 * erfc((sigma_distance - collision_threshold) / np.sqrt(2))
        
        # Apply distance scaling for very far objects
        distance_scale = np.exp(-((sigma_distance / 50.0) ** 1.5))  # Softer exponential decay
        erfc_prob *= distance_scale
        
    else:
        erfc_prob = 1.0 if miss_distance <= effective_collision_radius else 0.0
    
    # 3. Velocity-dependent probability enhancement
    # Higher relative velocities increase collision cross-section uncertainty
    velocity_enhancement = 1.0 + (relative_velocity_magnitude / 20.0) * 0.1
    
    # 4. Altitude-dependent scaling
    # Lower altitudes have more atmospheric effects and orbital decay uncertainty
    altitude_enhancement = altitude_factor * 0.5
    
    # Combine all probability components
    base_probability = max(geometric_prob, erfc_prob)
    enhanced_probability = base_probability * velocity_enhancement * (1.0 + altitude_enhancement)
    
    # Add realistic baseline probability based on miss distance ranges
    if miss_distance < 1.0:  # Less than 1 km
        baseline_prob = 1e-4
    elif miss_distance < 10.0:  # 1-10 km
        baseline_prob = 1e-6
    elif miss_distance < 100.0:  # 10-100 km
        baseline_prob = 1e-8
    elif miss_distance < 1000.0:  # 100-1000 km
        baseline_prob = 1e-10
    else:  # Greater than 1000 km
        baseline_prob = 1e-12
    
    # Scale baseline by factors
    dynamic_baseline = baseline_prob * velocity_factor * altitude_factor * size_factor
    
    # Use the higher of calculated probability or dynamic baseline
    final_probability = max(enhanced_probability, dynamic_baseline)
    
    # Ensure realistic bounds with more variation
    min_prob = 1e-15  # Very small but not zero
    max_prob = 1e-2   # 1% maximum for extreme cases
    
    return max(min_prob, min(max_prob, final_probability))

def calculate_altitude_factor(altitude):
    """
    Calculate altitude-based risk factor.
    Lower altitudes have higher uncertainty due to atmospheric effects.
    """
    if altitude < 300:  # Very low orbit - high drag
        return 3.0
    elif altitude < 600:  # Low Earth Orbit - moderate drag
        return 2.0
    elif altitude < 1000:  # Medium LEO
        return 1.5
    elif altitude < 2000:  # High LEO
        return 1.2
    else:  # MEO/GEO - stable orbits
        return 1.0

def calculate_size_factor(size1, size2):
    """
    Calculate size-based risk factor.
    Larger satellites have higher collision cross-sections.
    """
    size_values = {'SMALL': 1.0, 'MEDIUM': 1.5, 'LARGE': 2.0, '': 1.2}
    factor1 = size_values.get(size1, 1.2)
    factor2 = size_values.get(size2, 1.2)
    return (factor1 + factor2) / 2.0

def monte_carlo_collision_assessment(pos1, vel1, pos2, vel2, sigma1, sigma2, 
                                   combined_radius, n_samples=1000):
    """
    Monte Carlo simulation for collision probability assessment.
    
    Args:
        pos1, vel1: Nominal position and velocity of satellite 1
        pos2, vel2: Nominal position and velocity of satellite 2
        sigma1, sigma2: Position uncertainties for satellites 1 and 2
        combined_radius: Combined hard body radius
        n_samples: Number of Monte Carlo samples
        
    Returns:
        probability: Collision probability
        stats: Dictionary with additional statistics
    """
    collision_count = 0
    min_distances = []
    
    for _ in range(n_samples):
        # Sample positions with uncertainties
        pos1_sample = pos1 + np.random.normal(0, sigma1, 3)
        pos2_sample = pos2 + np.random.normal(0, sigma2, 3)
        
        # Sample velocities (smaller uncertainty)
        vel1_sample = vel1 + np.random.normal(0, sigma1/1000, 3)
        vel2_sample = vel2 + np.random.normal(0, sigma2/1000, 3)
        
        # Calculate closest approach for this sample
        _, min_dist, _ = predict_closest_approach(pos1_sample, vel1_sample, 
                                                pos2_sample, vel2_sample)
        min_distances.append(min_dist)
        
        # Check if collision occurs
        if min_dist <= combined_radius:
            collision_count += 1
    
    probability = collision_count / n_samples
    
    stats = {
        'mean_miss_distance': np.mean(min_distances),
        'std_miss_distance': np.std(min_distances),
        'min_miss_distance': np.min(min_distances),
        'collision_samples': collision_count
    }
    
    return probability, stats

def eci_to_lat_lon(position):
    """Converts ECI coordinates to latitude and longitude."""
    r = np.linalg.norm(position)
    lat = np.arcsin(position[2] / r) * (180 / np.pi)  # Latitude in degrees
    lon = np.arctan2(position[1], position[0]) * (180 / np.pi)  # Longitude in degrees
    lon = (lon + 360) % 360  # Normalize longitude to [0, 360)
    return lat, lon

@app.route('/satellite-collision-probability', methods=['POST'])
def satellite_collision_probability():
    """API endpoint for satellite collision probability calculation."""
    data = request.get_json()

    if not data or 'target_norad_id' not in data:
        return jsonify({"error": "Missing target NORAD ID", "status": "failed"}), 400

    try:
        dataset_file = "data/satellites_norad_ids.txt"
        with open(dataset_file, "r") as f:
            norad_ids = [line.strip() for line in f.readlines()]

        target_norad_id = str(data['target_norad_id'])
        if target_norad_id not in norad_ids:
            return jsonify({"error": f"NORAD ID {target_norad_id} is not in the dataset", "status": "failed"}), 404

        tle_data = fetch_tle_data(norad_ids)

        if not tle_data:
            return jsonify({"error": "Failed to fetch TLE data from API", "status": "failed"}), 503

        current_time = datetime.utcnow()
        satellites = {}
        for norad_id, tle in tle_data.items():
            try:
                if len(tle) >= 2:
                    satellites[norad_id] = Satrec.twoline2rv(tle[0], tle[1])
            except Exception as e:
                print(f"Error processing TLE for NORAD ID {norad_id}: {e}")
                continue

        if target_norad_id not in satellites:
            return jsonify({"error": f"TLE data not available for NORAD ID {target_norad_id}", "status": "failed"}), 404

        target_sat = satellites[target_norad_id]
        target_metadata = get_satellite_metadata(target_norad_id)
        highest_collision = None
        tle_age_days = 1.0  # Assume TLE data is 1 day old

        # Calculate time window for conjunction analysis
        time_step_hours = 1.0  # Check every hour
        max_days = 7
        
        print(f"Analyzing collisions for {target_metadata['name']} (NORAD {target_norad_id})")

        # Iterate through time window with higher resolution
        for hour_offset in range(0, max_days * 24, int(time_step_hours)):
            time_to_check = current_time + timedelta(hours=hour_offset)
            jd, fr = jday(time_to_check.year, time_to_check.month, time_to_check.day,
                          time_to_check.hour, time_to_check.minute, time_to_check.second)

            target_error, target_pos, target_vel = target_sat.sgp4(jd, fr)
            if target_error != 0:
                continue

            # Calculate target satellite uncertainty
            target_pos_sigma, target_vel_sigma = calculate_tle_uncertainty(
                tle_age_days, target_metadata['altitude'])

            for norad_id, satellite in satellites.items():
                if norad_id == target_norad_id:
                    continue

                try:
                    error, pos, vel = satellite.sgp4(jd, fr)
                    if error != 0:
                        continue

                    # Validate position and velocity data
                    if (pos is None or vel is None or 
                        not all(np.isfinite(pos)) or not all(np.isfinite(vel)) or
                        not all(np.isfinite(target_pos)) or not all(np.isfinite(target_vel))):
                        continue

                    # Get satellite metadata for uncertainty calculation
                    sat_metadata = get_satellite_metadata(norad_id)
                    sat_pos_sigma, sat_vel_sigma = calculate_tle_uncertainty(
                        tle_age_days, sat_metadata['altitude'])

                    # Predict closest approach
                    tca_seconds, miss_distance, rel_velocity = predict_closest_approach(
                        target_pos, target_vel, pos, vel, max_time_hours=48)

                    # Calculate combined uncertainties
                    combined_pos_sigma = np.sqrt(target_pos_sigma**2 + sat_pos_sigma**2)
                    
                    # Calculate combined hard body radius
                    combined_radius = calculate_combined_radius(
                        target_metadata['size'], sat_metadata['size'])

                    # Calculate dynamic collision probability with multiple factors
                    altitude_factor = calculate_altitude_factor(
                        (target_metadata['altitude'] + sat_metadata['altitude']) / 2)
                    size_factor = calculate_size_factor(
                        target_metadata['size'], sat_metadata['size'])
                    rel_velocity_magnitude = np.linalg.norm(rel_velocity)
                    
                    dynamic_prob = dynamic_collision_probability(
                        miss_distance, combined_pos_sigma, combined_radius,
                        rel_velocity_magnitude, altitude_factor, size_factor)

                    # For very close approaches, use Monte Carlo for more accuracy
                    if miss_distance < (combined_radius * 50) and dynamic_prob > 1e-8:
                        mc_prob, mc_stats = monte_carlo_collision_assessment(
                            target_pos, target_vel, pos, vel,
                            target_pos_sigma, sat_pos_sigma, combined_radius, 
                            n_samples=500)
                        
                        # Use the more conservative (higher) probability
                        collision_prob = max(dynamic_prob, mc_prob)
                        analysis_method = "Monte Carlo + Dynamic"
                    else:
                        collision_prob = dynamic_prob
                        analysis_method = "Dynamic Algorithm"

                    # Calculate additional metrics
                    distance, relative_speed = calculate_relative_metrics(target_pos, target_vel, pos, vel)
                    lat, lon = eci_to_lat_lon(pos)
                    
                    # Calculate TCA time
                    tca_time = time_to_check + timedelta(seconds=tca_seconds)

                    # Validate calculated values
                    if not all(np.isfinite([collision_prob, distance, relative_speed, lat, lon])):
                        continue

                    # Only consider significant collision probabilities
                    # Include all probabilities above a meaningful threshold
                    if collision_prob < 1e-15:
                        continue

                    collision_data = {
                        "collision_probability": round(float(collision_prob), 8),
                        "miss_distance (km)": round(float(miss_distance), 2),
                        "current_distance (km)": round(float(distance), 2),
                        "latitude": round(float(lat), 4),
                        "longitude": round(float(lon), 4),
                        "norad_id": norad_id,
                        "satellite_name": sat_metadata['name'],
                        "relative_speed (km/s)": round(float(relative_speed), 3),
                        "tca_seconds": round(float(tca_seconds), 1),
                        "tca_time": tca_time.isoformat(),
                        "combined_radius (m)": round(float(combined_radius * 1000), 1),
                        "position_uncertainty (km)": round(float(combined_pos_sigma), 3),
                        "analysis_method": analysis_method,
                        "target_size": target_metadata['size'],
                        "other_size": sat_metadata['size'],
                        "altitude_factor": round(float(altitude_factor), 1),
                        "size_factor": round(float(size_factor), 1),
                        "velocity_magnitude (km/s)": round(float(rel_velocity_magnitude), 2),
                        "target_altitude (km)": round(float(target_metadata['altitude']), 1),
                        "other_altitude (km)": round(float(sat_metadata['altitude']), 1),
                        "day_offset": hour_offset // 24
                    }

                    # Update highest collision if this is more significant
                    if (highest_collision is None or 
                        collision_prob > highest_collision["collision_probability"]):
                        highest_collision = collision_data
                        print(f"New highest collision risk: {collision_prob:.2e} with {sat_metadata['name']} (NORAD {norad_id})")

                except Exception as calc_error:
                    print(f"Calculation error for satellites {target_norad_id} and {norad_id}: {calc_error}")
                    continue

        if not highest_collision:
            return jsonify({"status": "no_collisions_predicted", "target_norad_id": target_norad_id})

        return jsonify({
            "status": "success",
            "target_norad_id": target_norad_id,
            "target_satellite_name": target_metadata['name'],
            "timestamp": current_time.isoformat(),
            "analysis_summary": {
                "time_window_days": max_days,
                "time_resolution_hours": time_step_hours,
                "total_satellites_analyzed": len(satellites) - 1,
                "tle_age_days": tle_age_days
            },
            "collision_data": highest_collision
        })

    except Exception as e:
        return jsonify({"error": str(e), "status": "failed"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@app.route('/generate-collision-report', methods=['POST'])
def generate_collision_report():
    """API endpoint for generating LLM-powered collision reports."""
    try:
        # Check if services are initialized
        if report_service is None:
            return jsonify({
                "status": "error",
                "error_type": "service_unavailable",
                "message": "Report generation service is not available. Please check server configuration."
            }), 503
        
        # Get request data
        data = request.get_json()
        
        if not data or 'target_norad_id' not in data:
            return jsonify({
                "status": "error",
                "error_type": "invalid_request",
                "message": "Missing target_norad_id in request"
            }), 400
        
        target_norad_id = str(data['target_norad_id'])
        logger.info(f"Report generation requested for satellite {target_norad_id}")
        
        # Check queue size
        with queue_lock:
            if report_queue.qsize() >= 10:
                return jsonify({
                    "status": "error",
                    "error_type": "queue_full",
                    "message": "Too many pending requests. Please try again later."
                }), 429
        
        # Get collision data (either from request or recalculate)
        collision_data = data.get('collision_data')
        
        if not collision_data:
            # Need to calculate collision data first
            logger.info(f"Collision data not provided, calculating for {target_norad_id}")
            
            # Call existing collision probability endpoint logic
            dataset_file = "data/satellites_norad_ids.txt"
            try:
                with open(dataset_file, "r") as f:
                    norad_ids = [line.strip() for line in f.readlines()]
            except FileNotFoundError:
                return jsonify({
                    "status": "error",
                    "error_type": "data_not_found",
                    "message": "Satellite dataset not found"
                }), 404
            
            if target_norad_id not in norad_ids:
                return jsonify({
                    "status": "error",
                    "error_type": "satellite_not_found",
                    "message": f"NORAD ID {target_norad_id} not in dataset"
                }), 404
            
            # Fetch TLE data
            tle_data = fetch_tle_data(norad_ids)
            
            if not tle_data:
                return jsonify({
                    "status": "error",
                    "error_type": "tle_unavailable",
                    "message": "Failed to fetch TLE data"
                }), 503
            
            # Calculate collision probability (simplified - get from existing calculation)
            # In practice, this would reuse the collision calculation logic
            return jsonify({
                "status": "error",
                "error_type": "no_collision_data",
                "message": "Please calculate collision probability first before generating report"
            }), 400
        
        # Get satellite metadata
        satellite_metadata = get_satellite_metadata(target_norad_id)
        satellite_metadata['norad_id'] = target_norad_id
        
        # Generate report
        try:
            report = report_service.generate_report(
                target_norad_id,
                collision_data,
                satellite_metadata
            )
            
            logger.info(f"Report generated successfully for {target_norad_id}")
            
            return jsonify({
                "status": "success",
                "report": report
            })
            
        except LLMRateLimitError as e:
            logger.warning(f"Rate limit exceeded: {e}")
            return jsonify({
                "status": "error",
                "error_type": "rate_limit",
                "message": str(e),
                "retry_after": 60
            }), 429
            
        except LLMTimeoutError as e:
            logger.error(f"Request timeout: {e}")
            return jsonify({
                "status": "error",
                "error_type": "timeout",
                "message": "Report generation timed out. Please try again."
            }), 504
            
        except LLMAPIError as e:
            logger.error(f"LLM API error: {e}")
            # Try to return fallback report
            try:
                fallback_report = report_service._generate_fallback_report(
                    collision_data, satellite_metadata, target_norad_id
                )
                return jsonify({
                    "status": "success",
                    "report": fallback_report,
                    "warning": "Generated using fallback template due to LLM unavailability"
                })
            except Exception as fallback_error:
                logger.error(f"Fallback report generation failed: {fallback_error}")
                return jsonify({
                    "status": "error",
                    "error_type": "llm_unavailable",
                    "message": "Report generation service temporarily unavailable"
                }), 503
        
    except Exception as e:
        logger.error(f"Unexpected error in report generation: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "message": "An unexpected error occurred"
        }), 500

@app.route('/cache-stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics."""
    try:
        if cache_manager is None:
            return jsonify({"error": "Cache manager not initialized"}), 503
        
        stats = cache_manager.get_stats()
        return jsonify({
            "status": "success",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/llm-stats', methods=['GET'])
def get_llm_stats():
    """Get LLM client statistics."""
    try:
        if llm_client is None:
            return jsonify({"error": "LLM client not initialized"}), 503
        
        stats = llm_client.get_stats()
        return jsonify({
            "status": "success",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting LLM stats: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting satellite collision probability server...")
    print("LLM-powered report generation enabled" if report_service else "LLM services not available")
    app.run(debug=True, host='127.0.0.1', port=5000)
