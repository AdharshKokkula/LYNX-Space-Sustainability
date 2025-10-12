"""
Report generation service for satellite collision analysis.
Orchestrates LLM-based report generation with caching and fallback.
"""
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)


class ReportGenerationService:
    """Service for generating collision risk reports using LLM."""
    
    def __init__(self, llm_client, cache_manager, config: Dict[str, Any]):
        """
        Initialize report generation service.
        
        Args:
            llm_client: LLM client instance
            cache_manager: Cache manager instance
            config: Configuration dict
        """
        self.llm_client = llm_client
        self.cache_manager = cache_manager
        self.config = config
        self.report_config = config.get('report_config', {})
        self.risk_thresholds = self.report_config.get('risk_thresholds', {'high': 10, 'medium': 100})
        
        logger.info("Report generation service initialized")
    
    def generate_report(self, norad_id: str, collision_data: Dict[str, Any], 
                       satellite_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate collision risk report.
        
        Args:
            norad_id: NORAD ID of target satellite
            collision_data: Collision probability data
            satellite_metadata: Satellite metadata
            
        Returns:
            Generated report dict
        """
        logger.info(f"Generating report for satellite {norad_id}")
        
        # Check cache first
        cached_report = self.cache_manager.get_report(norad_id)
        if cached_report:
            logger.info(f"Returning cached report for {norad_id}")
            cached_report['from_cache'] = True
            return cached_report
        
        try:
            # Classify risk level
            miss_distance = collision_data.get('miss_distance (km)', 0)
            risk_level = self._classify_risk_level(miss_distance)
            
            # Build prompt
            prompt = self._build_prompt(collision_data, satellite_metadata, risk_level)
            
            # Generate with LLM
            llm_params = self.config.get('parameters', {})
            generated_text = self.llm_client.generate_text(
                prompt,
                max_tokens=llm_params.get('max_tokens', 1500),
                temperature=llm_params.get('temperature', 0.7),
                top_p=llm_params.get('top_p', 0.9)
            )
            
            # Parse response
            report = self._parse_llm_response(
                generated_text, 
                collision_data, 
                satellite_metadata, 
                risk_level
            )
            
            # Cache the report
            self.cache_manager.store_report(norad_id, report, collision_data)
            
            report['from_cache'] = False
            logger.info(f"Report generated successfully for {norad_id}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Return fallback report
            return self._generate_fallback_report(collision_data, satellite_metadata, norad_id)
    
    def _build_prompt(self, collision_data: Dict[str, Any], 
                     satellite_metadata: Dict[str, Any], risk_level: str) -> str:
        """
        Build structured prompt for LLM.
        
        Args:
            collision_data: Collision data dict
            satellite_metadata: Satellite metadata dict
            risk_level: Risk classification (HIGH, MEDIUM, LOW)
            
        Returns:
            Formatted prompt string
        """
        # Sanitize data
        sat_name = self._sanitize_string(satellite_metadata.get('name', 'Unknown'))
        norad_id = satellite_metadata.get('norad_id', 'Unknown')
        country = self._sanitize_string(satellite_metadata.get('country', 'Unknown'))
        altitude = satellite_metadata.get('altitude', 0)
        period = satellite_metadata.get('period', 0)
        inclination = satellite_metadata.get('inclination', 0)
        
        # Collision data
        probability = collision_data.get('collision_probability', 0)
        miss_distance = collision_data.get('miss_distance (km)', 0)
        relative_velocity = collision_data.get('relative_speed (km/s)', 0)
        tca_time = collision_data.get('tca_time', 'Unknown')
        other_sat_name = self._sanitize_string(collision_data.get('satellite_name', 'Unknown'))
        other_norad_id = collision_data.get('norad_id', 'Unknown')
        
        # Mission context based on satellite type
        mission_context = self._get_mission_context(sat_name, satellite_metadata)
        
        prompt = f"""You are a space operations analyst generating a collision risk report for satellite operators.

SATELLITE INFORMATION:
- Name: {sat_name}
- NORAD ID: {norad_id}
- Country/Organization: {country}
- Orbital Altitude: {altitude:.1f} km
- Orbital Period: {period:.1f} minutes
- Inclination: {inclination:.1f} degrees

COLLISION RISK DATA:
- Risk Level: {risk_level}
- Collision Probability: {probability:.2e}
- Miss Distance: {miss_distance:.2f} km
- Relative Velocity: {relative_velocity:.2f} km/s
- Time to Closest Approach: {tca_time}
- Other Object: {other_sat_name} (NORAD {other_norad_id})

MISSION CONTEXT:
{mission_context}

Generate a comprehensive collision risk report with the following sections:

1. EXECUTIVE SUMMARY: Brief overview (2-3 sentences) of the collision risk situation and immediate concerns.

2. SATELLITE DETAILS: Detailed information about the target satellite, its mission, and operational status.

3. RISK ASSESSMENT: Analysis of the collision probability, miss distance, and contributing risk factors. Explain what the probability means in practical terms.

4. RECOMMENDATIONS: Specific actionable steps based on the {risk_level} risk level. Include monitoring requirements and potential maneuver considerations.

5. TECHNICAL DETAILS: Orbital mechanics information, trajectory analysis, and uncertainty factors.

Format the report in clear, professional language suitable for satellite operators and mission controllers. Use technical terminology appropriately but ensure accessibility."""

        return prompt
    
    def _classify_risk_level(self, miss_distance: float) -> str:
        """
        Classify risk level based on miss distance.
        
        Args:
            miss_distance: Miss distance in km
            
        Returns:
            Risk level string (HIGH, MEDIUM, LOW)
        """
        high_threshold = self.risk_thresholds.get('high', 10)
        medium_threshold = self.risk_thresholds.get('medium', 100)
        
        if miss_distance < high_threshold:
            return "HIGH"
        elif miss_distance < medium_threshold:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _parse_llm_response(self, generated_text: str, collision_data: Dict[str, Any],
                           satellite_metadata: Dict[str, Any], risk_level: str) -> Dict[str, Any]:
        """
        Parse and structure LLM response.
        
        Args:
            generated_text: Text generated by LLM
            collision_data: Original collision data
            satellite_metadata: Original satellite metadata
            risk_level: Risk classification
            
        Returns:
            Structured report dict
        """
        # Extract sections using regex
        sections = {
            'executive_summary': self._extract_section(generated_text, 'EXECUTIVE SUMMARY'),
            'satellite_details': self._extract_section(generated_text, 'SATELLITE DETAILS'),
            'risk_assessment': self._extract_section(generated_text, 'RISK ASSESSMENT'),
            'recommendations': self._extract_section(generated_text, 'RECOMMENDATIONS'),
            'technical_details': self._extract_section(generated_text, 'TECHNICAL DETAILS')
        }
        
        # Validate that we got meaningful content
        if not sections['executive_summary'] or len(sections['executive_summary']) < 50:
            logger.warning("LLM response appears incomplete, using fallback")
            raise ValueError("Incomplete LLM response")
        
        # Build structured report
        report = {
            'report_id': str(uuid.uuid4()),
            'generated_at': datetime.utcnow().isoformat(),
            'target_satellite': {
                'norad_id': satellite_metadata.get('norad_id', 'Unknown'),
                'name': satellite_metadata.get('name', 'Unknown'),
                'country': satellite_metadata.get('country', 'Unknown'),
                'altitude_km': satellite_metadata.get('altitude', 0),
                'period_minutes': satellite_metadata.get('period', 0),
                'inclination_deg': satellite_metadata.get('inclination', 0)
            },
            'collision_risk': {
                'probability': collision_data.get('collision_probability', 0),
                'risk_level': risk_level,
                'miss_distance_km': collision_data.get('miss_distance (km)', 0),
                'relative_velocity_km_s': collision_data.get('relative_speed (km/s)', 0),
                'tca_time': collision_data.get('tca_time', 'Unknown'),
                'tca_seconds': collision_data.get('tca_seconds', 0)
            },
            'other_satellite': {
                'norad_id': collision_data.get('norad_id', 'Unknown'),
                'name': collision_data.get('satellite_name', 'Unknown'),
                'altitude_km': collision_data.get('other_altitude (km)', 0)
            },
            'report_sections': sections,
            'full_text': generated_text,
            'metadata': {
                'model_used': self.config.get('model_name', 'Unknown'),
                'generation_method': 'llm'
            }
        }
        
        return report
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """
        Extract a section from the generated text.
        
        Args:
            text: Full generated text
            section_name: Name of section to extract
            
        Returns:
            Extracted section text
        """
        # Try to find section with number prefix (e.g., "1. EXECUTIVE SUMMARY")
        pattern = rf'\d+\.\s*{re.escape(section_name)}:?\s*(.*?)(?=\d+\.\s*[A-Z\s]+:|$)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        # Try without number prefix
        pattern = rf'{re.escape(section_name)}:?\s*(.*?)(?=[A-Z\s]+:|$)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _generate_fallback_report(self, collision_data: Dict[str, Any],
                                  satellite_metadata: Dict[str, Any], norad_id: str) -> Dict[str, Any]:
        """
        Generate fallback report when LLM fails.
        
        Args:
            collision_data: Collision data dict
            satellite_metadata: Satellite metadata dict
            norad_id: NORAD ID
            
        Returns:
            Fallback report dict
        """
        logger.info(f"Generating fallback report for {norad_id}")
        
        miss_distance = collision_data.get('miss_distance (km)', 0)
        risk_level = self._classify_risk_level(miss_distance)
        probability = collision_data.get('collision_probability', 0)
        
        # Create basic report sections
        executive_summary = f"Collision risk analysis for {satellite_metadata.get('name', 'Unknown')} " \
                          f"(NORAD {norad_id}). Risk level: {risk_level}. " \
                          f"Collision probability: {probability:.2e}. " \
                          f"Miss distance: {miss_distance:.2f} km."
        
        satellite_details = f"Target satellite: {satellite_metadata.get('name', 'Unknown')}\n" \
                          f"NORAD ID: {norad_id}\n" \
                          f"Altitude: {satellite_metadata.get('altitude', 0):.1f} km\n" \
                          f"Orbital period: {satellite_metadata.get('period', 0):.1f} minutes"
        
        risk_assessment = f"The collision probability is {probability:.2e} with a miss distance of " \
                        f"{miss_distance:.2f} km. This represents a {risk_level} risk scenario."
        
        if risk_level == "HIGH":
            recommendations = "IMMEDIATE ACTION REQUIRED: Monitor closely and prepare for potential collision avoidance maneuver."
        elif risk_level == "MEDIUM":
            recommendations = "Enhanced monitoring recommended. Assess maneuver options and continue tracking."
        else:
            recommendations = "Continue routine monitoring. No immediate action required."
        
        technical_details = f"Relative velocity: {collision_data.get('relative_speed (km/s)', 0):.2f} km/s\n" \
                          f"Time to closest approach: {collision_data.get('tca_time', 'Unknown')}\n" \
                          f"Other object: {collision_data.get('satellite_name', 'Unknown')}"
        
        report = {
            'report_id': str(uuid.uuid4()),
            'generated_at': datetime.utcnow().isoformat(),
            'target_satellite': {
                'norad_id': norad_id,
                'name': satellite_metadata.get('name', 'Unknown'),
                'country': satellite_metadata.get('country', 'Unknown'),
                'altitude_km': satellite_metadata.get('altitude', 0),
                'period_minutes': satellite_metadata.get('period', 0),
                'inclination_deg': satellite_metadata.get('inclination', 0)
            },
            'collision_risk': {
                'probability': probability,
                'risk_level': risk_level,
                'miss_distance_km': miss_distance,
                'relative_velocity_km_s': collision_data.get('relative_speed (km/s)', 0),
                'tca_time': collision_data.get('tca_time', 'Unknown'),
                'tca_seconds': collision_data.get('tca_seconds', 0)
            },
            'other_satellite': {
                'norad_id': collision_data.get('norad_id', 'Unknown'),
                'name': collision_data.get('satellite_name', 'Unknown')
            },
            'report_sections': {
                'executive_summary': executive_summary,
                'satellite_details': satellite_details,
                'risk_assessment': risk_assessment,
                'recommendations': recommendations,
                'technical_details': technical_details
            },
            'full_text': f"{executive_summary}\n\n{satellite_details}\n\n{risk_assessment}\n\n{recommendations}\n\n{technical_details}",
            'metadata': {
                'model_used': 'fallback_template',
                'generation_method': 'template'
            },
            'from_cache': False
        }
        
        return report
    
    def _get_mission_context(self, sat_name: str, metadata: Dict[str, Any]) -> str:
        """
        Generate mission context based on satellite type.
        
        Args:
            sat_name: Satellite name
            metadata: Satellite metadata
            
        Returns:
            Mission context string
        """
        name_upper = sat_name.upper()
        
        # Check for common satellite types
        if 'ISS' in name_upper or 'ZARYA' in name_upper:
            return "International Space Station - Crewed orbital laboratory and research facility."
        elif 'STARLINK' in name_upper:
            return "Starlink constellation satellite - Part of SpaceX's global broadband internet network."
        elif 'GPS' in name_upper or 'NAVSTAR' in name_upper:
            return "GPS navigation satellite - Critical infrastructure for global positioning and timing."
        elif 'GLONASS' in name_upper:
            return "GLONASS navigation satellite - Russian global navigation satellite system."
        elif 'COSMOS' in name_upper:
            return "Cosmos series satellite - Russian/Soviet space program satellite."
        elif 'DEB' in name_upper:
            return "Space debris - Fragmented satellite or rocket body component."
        elif 'R/B' in name_upper or 'ROCKET BODY' in name_upper:
            return "Rocket body - Spent rocket stage or booster."
        elif 'IRIDIUM' in name_upper:
            return "Iridium constellation satellite - Global satellite communications network."
        elif 'LANDSAT' in name_upper:
            return "Landsat Earth observation satellite - Environmental monitoring and remote sensing."
        elif 'HUBBLE' in name_upper:
            return "Hubble Space Telescope - Space-based astronomical observatory."
        else:
            # Generic based on altitude
            altitude = metadata.get('altitude', 0)
            if altitude < 600:
                return "Low Earth Orbit satellite - Operational satellite in LEO regime."
            elif altitude < 2000:
                return "Medium Earth Orbit satellite - Operational satellite in MEO regime."
            else:
                return "High altitude satellite - Operational satellite in high orbit regime."
    
    def _sanitize_string(self, text: str, max_length: int = 200) -> str:
        """
        Sanitize string for prompt safety.
        
        Args:
            text: Input text
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
        """
        if not text:
            return "Unknown"
        
        # Remove any potential injection attempts
        text = str(text).strip()
        text = text[:max_length]
        
        # Remove newlines and excessive whitespace
        text = ' '.join(text.split())
        
        return text
