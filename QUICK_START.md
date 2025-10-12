# Quick Start Guide - LLM Collision Reports

Get your AI-powered collision reports running in 5 minutes!

## 🚀 Installation (2 minutes)

### Step 1: Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `huggingface-hub` - For AI model access
- `markdown` - For report formatting  
- `python-dotenv` - For configuration

### Step 2: Start the Server
```bash
python server.py
```

You should see:
```
Configuration loaded successfully
LLM client initialized
Cache manager initialized
Report service initialized
LLM-powered report generation enabled
 * Running on http://127.0.0.1:5000
```

✅ **Backend is ready!**

## 🎨 Frontend Integration (3 minutes)

### Option 1: Quick Integration (Recommended)

Add these two lines to your HTML file (before `</body>`):

```html
<!-- Add report functionality -->
<script src="report_generator.js"></script>

<!-- Load report modal -->
<div id="report-modal-container"></div>
<script>
    fetch('report_modal.html')
        .then(response => response.text())
        .then(html => {
            document.getElementById('report-modal-container').innerHTML = html;
        });
</script>
```

### Option 2: Manual Integration

1. Copy contents of `report_modal.html` into your HTML file
2. Add `<script src="report_generator.js"></script>` to your HTML
3. Done!

## 🔌 Connect to Your Collision Data

Find where your collision probability is displayed (likely in `index.js`), and add:

```javascript
// After collision data is successfully loaded
if (data.status === "success" && data.collision_data) {
    // Initialize report generator
    initializeReportGenerator(
        data.target_norad_id,
        data.collision_data
    );
}
```

## ✅ Test It!

1. **Open your application** in a browser
2. **Click on a satellite** in the 3D view
3. **Wait for collision data** to load
4. **Click "Generate Detailed Report"** button
5. **View your AI-generated report!**

## 🎯 That's It!

You now have:
- ✅ AI-powered report generation
- ✅ Beautiful modal display
- ✅ Download functionality (TXT/MD)
- ✅ Smart caching (1-hour TTL)
- ✅ Risk-level color coding

## 🔧 Optional: Add API Key for Higher Limits

1. Create `.env` file in project root:
```bash
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxx
```

2. Get free API key from: https://huggingface.co/settings/tokens

3. Restart server

**Benefits:**
- Higher rate limits (more requests per day)
- Faster model loading
- Priority access

## 📊 Verify It's Working

### Check Backend Status
```bash
curl http://127.0.0.1:5000/health
```

Should return:
```json
{"status": "healthy", "timestamp": "..."}
```

### Check Cache Stats
```bash
curl http://127.0.0.1:5000/cache-stats
```

### Test Report Generation
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

## 🐛 Troubleshooting

### "Backend server is not running"
→ Start server: `python backend/server.py`

### "Button doesn't appear"
→ Check that `initializeReportGenerator()` is called after collision data loads

### "Report generation is slow"
→ First request takes 10-20 seconds (model loading). Subsequent requests are faster (3-8 seconds)

### "Rate limit exceeded"
→ Wait 60 seconds or add API key to `.env` file

## 📚 Need More Help?

- **Full Integration Guide**: See `INTEGRATION_GUIDE.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Configuration Options**: See `backend/config/llm_config.json`

## 🎉 Enjoy Your AI Reports!

Your satellite collision detection system now has professional, AI-generated risk analysis reports!

**Features:**
- 🤖 AI-powered analysis using Mistral-7B
- ⚡ Fast caching (< 100ms for cached reports)
- 🎨 Beautiful, responsive UI
- 📥 Download as TXT or Markdown
- 🚦 Automatic risk classification
- 🔒 Secure and private

---

**Questions?** Check the full documentation in `INTEGRATION_GUIDE.md`

**Issues?** Review the troubleshooting section above

**Ready to customize?** Edit `backend/config/llm_config.json`
