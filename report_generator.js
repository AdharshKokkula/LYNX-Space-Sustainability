/**
 * Collision Report Generator
 * Handles LLM-powered report generation and display
 */

// Global state for current collision data
let currentCollisionData = null;
let currentSatelliteId = null;

/**
 * Initialize report generation functionality
 * Call this after collision data is loaded
 */
function initializeReportGenerator(satelliteId, collisionData) {
    currentSatelliteId = satelliteId;
    currentCollisionData = collisionData;
    
    // Show report button
    const reportSection = document.getElementById('report-section');
    if (reportSection) {
        reportSection.style.display = 'block';
    }
    
    console.log('Report generator initialized for satellite:', satelliteId);
}

/**
 * Generate collision report
 */
async function generateCollisionReport() {
    if (!currentSatelliteId || !currentCollisionData) {
        showErrorMessage('No collision data available. Please select a satellite first.');
        return;
    }
    
    console.log('Generating report for satellite:', currentSatelliteId);
    
    // Show loading state
    showReportLoading(true);
    
    try {
        const url = 'http://127.0.0.1:5000/generate-collision-report';
        const payload = {
            target_norad_id: currentSatelliteId,
            collision_data: currentCollisionData
        };
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errorData = await response.json();
            handleReportError(errorData);
            return;
        }
        
        const data = await response.json();
        console.log('Report generated successfully:', data);
        
        // Hide loading, show report
        showReportLoading(false);
        displayReport(data.report);
        
    } catch (error) {
        console.error('Error generating report:', error);
        showReportLoading(false);
        
        if (error.name === 'AbortError') {
            showErrorMessage('Report generation timed out. Please try again.');
        } else if (error.message.includes('Failed to fetch')) {
            showErrorMessage('Backend server is not running. Please start the server.');
        } else {
            showErrorMessage('An error occurred while generating the report. Please try again.');
        }
    }
}

/**
 * Show/hide loading state
 */
function showReportLoading(show) {
    const button = document.getElementById('generate-report-btn');
    const loading = document.getElementById('report-loading');
    
    if (button) {
        button.disabled = show;
        button.style.opacity = show ? '0.6' : '1';
    }
    
    if (loading) {
        loading.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Handle report generation errors
 */
function handleReportError(errorData) {
    const errorMessages = {
        'service_unavailable': 'Report generation service is not available. Please check server configuration.',
        'invalid_request': 'Invalid request. Please try again.',
        'queue_full': 'Too many requests. Please wait a moment and try again.',
        'satellite_not_found': 'Satellite not found in database.',
        'no_collision_data': 'No collision data available. Please calculate collision probability first.',
        'rate_limit': `Rate limit exceeded. Please wait ${errorData.retry_after || 60} seconds.`,
        'timeout': 'Report generation took too long. Please try again.',
        'llm_unavailable': 'Report generation service temporarily unavailable.',
        'internal_error': 'An unexpected error occurred. Please try again.'
    };
    
    const message = errorMessages[errorData.error_type] || errorData.message || 'Unknown error occurred';
    showErrorMessage(message);
}

/**
 * Display generated report in modal
 */
function displayReport(report) {
    const modal = document.getElementById('report-modal');
    const content = document.getElementById('report-content');
    
    if (!modal || !content) {
        console.error('Report modal elements not found');
        return;
    }
    
    // Build report HTML
    const reportHTML = buildReportHTML(report);
    content.innerHTML = reportHTML;
    
    // Apply risk level styling
    applyRiskStyling(report.collision_risk.risk_level);
    
    // Show modal
    modal.style.display = 'flex';
    
    // Store report for download
    window.currentReport = report;
}

/**
 * Build HTML for report display
 */
function buildReportHTML(report) {
    const sections = report.report_sections;
    const riskLevel = report.collision_risk.risk_level;
    const riskClass = `risk-${riskLevel.toLowerCase()}`;
    
    let html = `
        <div class="report-header ${riskClass}">
            <h2>Collision Risk Report</h2>
            <div class="risk-badge ${riskClass}">
                ${riskLevel} RISK
            </div>
        </div>
        
        <div class="report-metadata">
            <div class="metadata-item">
                <strong>Satellite:</strong> ${report.target_satellite.name} (NORAD ${report.target_satellite.norad_id})
            </div>
            <div class="metadata-item">
                <strong>Generated:</strong> ${new Date(report.generated_at).toLocaleString()}
            </div>
            <div class="metadata-item">
                <strong>Collision Probability:</strong> ${report.collision_risk.probability.toExponential(2)}
            </div>
            <div class="metadata-item">
                <strong>Miss Distance:</strong> ${report.collision_risk.miss_distance_km.toFixed(2)} km
            </div>
            ${report.from_cache ? '<div class="metadata-item cache-indicator"><em>(Cached Report)</em></div>' : ''}
        </div>
        
        <div class="report-section">
            <h3>Executive Summary</h3>
            <p>${formatText(sections.executive_summary)}</p>
        </div>
        
        <div class="report-section">
            <h3>Satellite Details</h3>
            <p>${formatText(sections.satellite_details)}</p>
        </div>
        
        <div class="report-section">
            <h3>Risk Assessment</h3>
            <p>${formatText(sections.risk_assessment)}</p>
        </div>
        
        <div class="report-section recommendations ${riskClass}">
            <h3>Recommendations</h3>
            <p>${formatText(sections.recommendations)}</p>
        </div>
        
        <div class="report-section">
            <h3>Technical Details</h3>
            <p>${formatText(sections.technical_details)}</p>
        </div>
        
        <div class="report-footer">
            <small>Generated using ${report.metadata.model_used} | Method: ${report.metadata.generation_method}</small>
        </div>
    `;
    
    return html;
}

/**
 * Format text with line breaks
 */
function formatText(text) {
    if (!text) return '';
    return text.replace(/\n/g, '<br>');
}

/**
 * Apply risk level styling to modal
 */
function applyRiskStyling(riskLevel) {
    const modal = document.getElementById('report-modal');
    if (!modal) return;
    
    // Remove existing risk classes
    modal.classList.remove('risk-high', 'risk-medium', 'risk-low');
    
    // Add appropriate class
    modal.classList.add(`risk-${riskLevel.toLowerCase()}`);
}

/**
 * Close report modal
 */
function closeReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Download report as text file
 */
function downloadReportAsText() {
    if (!window.currentReport) {
        showErrorMessage('No report available to download');
        return;
    }
    
    const report = window.currentReport;
    const sections = report.report_sections;
    
    let text = `COLLISION RISK REPORT\n`;
    text += `${'='.repeat(80)}\n\n`;
    text += `Satellite: ${report.target_satellite.name} (NORAD ${report.target_satellite.norad_id})\n`;
    text += `Generated: ${new Date(report.generated_at).toLocaleString()}\n`;
    text += `Risk Level: ${report.collision_risk.risk_level}\n`;
    text += `Collision Probability: ${report.collision_risk.probability.toExponential(2)}\n`;
    text += `Miss Distance: ${report.collision_risk.miss_distance_km.toFixed(2)} km\n\n`;
    
    text += `EXECUTIVE SUMMARY\n${'-'.repeat(80)}\n${sections.executive_summary}\n\n`;
    text += `SATELLITE DETAILS\n${'-'.repeat(80)}\n${sections.satellite_details}\n\n`;
    text += `RISK ASSESSMENT\n${'-'.repeat(80)}\n${sections.risk_assessment}\n\n`;
    text += `RECOMMENDATIONS\n${'-'.repeat(80)}\n${sections.recommendations}\n\n`;
    text += `TECHNICAL DETAILS\n${'-'.repeat(80)}\n${sections.technical_details}\n\n`;
    
    text += `${'='.repeat(80)}\n`;
    text += `Generated using ${report.metadata.model_used}\n`;
    
    // Create download
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `collision_report_${report.target_satellite.norad_id}_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('Report downloaded as text');
}

/**
 * Download report as markdown file
 */
function downloadReportAsMarkdown() {
    if (!window.currentReport) {
        showErrorMessage('No report available to download');
        return;
    }
    
    const report = window.currentReport;
    const sections = report.report_sections;
    
    let markdown = `# Collision Risk Report\n\n`;
    markdown += `## Satellite Information\n\n`;
    markdown += `- **Name:** ${report.target_satellite.name}\n`;
    markdown += `- **NORAD ID:** ${report.target_satellite.norad_id}\n`;
    markdown += `- **Generated:** ${new Date(report.generated_at).toLocaleString()}\n`;
    markdown += `- **Risk Level:** **${report.collision_risk.risk_level}**\n`;
    markdown += `- **Collision Probability:** ${report.collision_risk.probability.toExponential(2)}\n`;
    markdown += `- **Miss Distance:** ${report.collision_risk.miss_distance_km.toFixed(2)} km\n\n`;
    
    markdown += `## Executive Summary\n\n${sections.executive_summary}\n\n`;
    markdown += `## Satellite Details\n\n${sections.satellite_details}\n\n`;
    markdown += `## Risk Assessment\n\n${sections.risk_assessment}\n\n`;
    markdown += `## Recommendations\n\n${sections.recommendations}\n\n`;
    markdown += `## Technical Details\n\n${sections.technical_details}\n\n`;
    
    markdown += `---\n\n`;
    markdown += `*Generated using ${report.metadata.model_used}*\n`;
    
    // Create download
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `collision_report_${report.target_satellite.norad_id}_${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('Report downloaded as markdown');
}

/**
 * Show error message
 */
function showErrorMessage(message) {
    // You can customize this to use your existing error display mechanism
    alert(message);
    console.error('Report error:', message);
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Close modal on click outside
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeReportModal();
            }
        });
    }
    
    // ESC key to close modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeReportModal();
        }
    });
});
