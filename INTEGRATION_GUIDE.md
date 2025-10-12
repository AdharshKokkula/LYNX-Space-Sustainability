# LLM Collision Report Integration Guide

This guide explains how to integrate the LLM-powered collision report feature into your existing satellite collision detection system.

## Files Created

### Backend Files
- `backend/services/llm_client.py` - Hugging Face API client
- `backend/services/cache_manager.py` - Report caching system
- `backend/services/report_service.py` - Report generation orchestration
- `backend/config/config_loader.py` - Configuration management
- `backend/config/llm_config.json` - LLM configuration
- `.env.example` - Environment variable template

### Frontend Files
- `report_generator.js` - Report generation JavaScript
- `report_modal.html` - Report UI components and styles

## Installation Steps

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install the new dependencies:
- `huggingface-hub` - For Hugging Face API access
- `markdown` - For report formatting
- `python-dotenv` - For environment variable management

### 2. Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and add your Hugging Face API key (optional for free tier):

```
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxx
```

To get a free API key:
1. Go to https://huggingface.co/settings/tokens
2. Create a new token (read access is sufficient)
3. Copy and paste into `.env` file

**Note:** The system works without an API key but has lower rate limits.

### 3. Integrate Frontend Components

#### Option A: Add to existing HTML file

Add these lines to your `index.html` or `collision.html` file:

**In the `<head>` section:**
```html
<!-- Add report generator script -->
<script src="report_generator.js"></script>
```

**Before the closing `</body>` tag:**
```html
<!-- Include report modal HTML -->
<div id="report-modal-container"></div>
<script>
    // Load report modal HTML
    fetch('report_modal.html')
        .then(response => response.text())
        .then(html => {
            document.getElementById('report-modal-container').innerHTML = html;
        });
</script>
```

#### Option B: Direct HTML inclusion

Copy the contents of `report_modal.html` and paste it into your main HTML file before the closing `</body>` tag.

### 4. Integrate with Collision Probability Display

In your `index.js` file, find the section where collision probability data is displayed (around line 300-400 in the `updateCollisionProbabilityUI` function).

Add this code after the collision data is successfully displayed:

```javascript
// After displaying collision probability data
if (data.status === "success" && data.collision_data) {
    // Initialize report generator with collision data
    initializeReportGenerator(
        data.target_norad_id,
        data.collision_data
    );
}
```

### 5. Add Report Button to Collision Panel

Find the HTML element where collision probability is displayed (likely `#botton-right-probability` or similar).

Add the report section div inside that panel:

```html
<div id="report-section" style="display: none; margin-top: 15px;">
    <button id="generate-report-btn" class="btn-report" onclick="generateCollisionReport()">
        Generate Detailed Report
    </button>
    <div id="report-loading" style="display: none;">
        <div class="report-spinner"></div>
        <span>Generating report with AI...</span>
    </div>
</div>
```

Or use the complete HTML from `report_modal.html`.

### 6. Start the Enhanced Backend Server

```bash
cd backend
python server.py
```

You should see:
```
Starting satellite collision probability server...
Configuration loaded successfully
LLM client initialized
Cache manager initialized
Report service initialized
LLM-powered report generation enabled
 * Running on http://127.0.0.1:5000
```

## Usage

### For Users

1. **Select a Satellite**: Click on any satellite in the 3D view
2. **View Collision Data**: The collision probability panel will appear
3. **Generate Report**: Click the "Generate Detailed Report" button
4. **View Report**: The AI-generated report will appear in a modal
5. **Download**: Use the download buttons to save as TXT or MD format

### For Developers

#### Testing the API Directly

```bash
curl -X POST http://127.0.0.1:5000/generate-collision-report \
  -H "Content-Type: application/json" \
  -d '{
    "target_norad_id": "25544",
    "collision_data": {
      "collision_probability": 0.000001,
      "miss_distance (km)": 45.2,
      "relative_speed (km/s)": 14.3,
      "tca_time": "2024-01-20T14:22:00Z",
      "satellite_name": "COSMOS 2251 DEB",
      "norad_id": "12345"
    }
  }'
```

#### Check Cache Statistics

```bash
curl http://127.0.0.1:5000/cache-stats
```

#### Check LLM Statistics

```bash
curl http://127.0.0.1:5000/llm-stats
```

## Configuration

### LLM Model Selection

Edit `backend/config/llm_config.json` to change the model:

```json
{
    "model_name": "mistralai/Mistral-7B-Instruct-v0.2",
    "fallback_models": [
        "HuggingFaceH4/zephyr-7b-beta",
        "meta-llama/Llama-2-7b-chat-hf"
    ]
}
```

Available free models:
- `mistralai/Mistral-7B-Instruct-v0.2` (recommended, best quality)
- `HuggingFaceH4/zephyr-7b-beta` (good alternative)
- `meta-llama/Llama-2-7b-chat-hf` (requires approval)

### Cache Settings

Adjust cache behavior in `llm_config.json`:

```json
{
    "cache_config": {
        "enabled": true,
        "max_size": 100,
        "ttl_seconds": 3600
    }
}
```

- `max_size`: Maximum number of reports to cache
- `ttl_seconds`: How long reports stay cached (3600 = 1 hour)

### Report Generation Parameters

Customize LLM parameters:

```json
{
    "parameters": {
        "max_tokens": 1500,
        "temperature": 0.7,
        "top_p": 0.9
    }
}
```

- `max_tokens`: Maximum length of generated report
- `temperature`: Creativity (0.0 = deterministic, 2.0 = very creative)
- `top_p`: Nucleus sampling (0.9 recommended)

## Troubleshooting

### Backend Issues

**Error: "Failed to initialize LLM services"**
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify `backend/config/llm_config.json` exists and is valid JSON
- Check logs for specific error messages

**Error: "LLM API unavailable"**
- Check internet connection
- Verify Hugging Face API is accessible
- Try without API key (free tier)
- Check if model is loading (503 errors are normal initially)

**Error: "Rate limit exceeded"**
- Wait 60 seconds and try again
- Add a Hugging Face API key for higher limits
- Consider using a different model

### Frontend Issues

**Button doesn't appear**
- Check that `report_generator.js` is loaded
- Verify `initializeReportGenerator()` is called after collision data loads
- Check browser console for JavaScript errors

**Modal doesn't display**
- Verify `report_modal.html` content is loaded
- Check that modal HTML elements exist in DOM
- Look for CSS conflicts with existing styles

**Download doesn't work**
- Check browser console for errors
- Verify `window.currentReport` is set
- Try a different browser

### Common Issues

**"Backend server is not running"**
- Start the server: `python backend/server.py`
- Check that port 5000 is not in use
- Verify CORS is enabled

**"No collision data available"**
- Select a satellite first
- Wait for collision probability calculation to complete
- Check that collision data exists for the satellite

**Report generation is slow**
- First request may take 10-20 seconds (model loading)
- Subsequent requests should be faster (3-8 seconds)
- Cached reports return in < 1 second

## Advanced Features

### Custom Report Templates

Modify the prompt template in `backend/services/report_service.py`:

```python
def _build_prompt(self, collision_data, satellite_metadata, risk_level):
    # Customize the prompt here
    prompt = f"""Your custom prompt template..."""
    return prompt
```

### Adding New Report Sections

1. Update the prompt in `report_service.py` to request new sections
2. Update `_extract_section()` to parse new sections
3. Update `buildReportHTML()` in `report_generator.js` to display new sections

### Webhook Notifications

Add webhook support for high-risk collisions:

```python
# In report_service.py
if risk_level == "HIGH":
    send_webhook_notification(report)
```

## Performance Metrics

### Expected Performance

- **Cache Hit**: < 100ms
- **Cache Miss (LLM generation)**: 3-8 seconds
- **First Request (model loading)**: 10-20 seconds
- **Memory Usage**: ~50MB for cache
- **API Rate Limit**: ~1000 requests/day (free tier)

### Monitoring

Check statistics endpoints:
- `/cache-stats` - Cache hit rate, size, evictions
- `/llm-stats` - Request count, success rate, average time

## Security Notes

1. **API Keys**: Never commit `.env` file to version control
2. **HTTPS**: Production deployments should use HTTPS
3. **Rate Limiting**: Built-in queue limits concurrent requests
4. **Input Validation**: All inputs are sanitized before sending to LLM
5. **CORS**: Configured for localhost, update for production

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review server logs for error messages
3. Test API endpoints directly with curl
4. Check Hugging Face status: https://status.huggingface.co/

## License

This feature integrates with your existing satellite collision detection system and uses:
- Hugging Face Inference API (free tier)
- Open-source LLM models (Mistral, Zephyr, Llama-2)
- MIT-licensed Python packages
