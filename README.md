# Satellite Collision Detection System

## Error Fix Instructions

The "TypeError: Failed to fetch" error occurs because the backend server is not running. Follow these steps to fix the issue:

### 1. Install Python Dependencies

First, install the required Python packages:

```bash
cd backend
pip install -r requirements.txt
```

Or install individually:
```bash
pip install flask flask-cors requests numpy sgp4 scikit-learn
```

### 2. Start the Backend Server

#### Option A: Use the batch file (Windows)
Double-click `start_server.bat` in the project root directory.

#### Option B: Manual start
```bash
cd backend
python server.py
```

### 3. Verify Server is Running

The server should start on `http://127.0.0.1:5000`. You should see:
```
Starting satellite collision probability server...
* Running on http://127.0.0.1:5000
```

### 4. Test the Application

1. Open `index.html` in your browser
2. Click on any satellite in the 3D view
3. The collision probability data should now load without errors

## Troubleshooting

### Common Issues:

1. **Port 5000 already in use**: 
   - Kill any process using port 5000
   - Or change the port in `server.py` and `index.js`

2. **Python packages not installed**:
   - Make sure you have Python 3.7+ installed
   - Install packages using pip as shown above

3. **CORS errors**:
   - The server now includes proper CORS headers
   - Make sure you're accessing the frontend via a web server, not file://

4. **Space-Track.org API issues**:
   - The server uses Space-Track.org API for TLE data
   - If you get authentication errors, you may need to update credentials in `server.py`

### Error Messages Explained:

- **"Backend server is not running"**: Start the server using steps above
- **"Request timed out"**: Server is slow or overloaded, try again
- **"Satellite not found in database"**: The selected satellite is not in the dataset
- **"No collision risks detected"**: No collision risks found (this is good!)

## Features Added:

1. **Better Error Handling**: Clear error messages for different scenarios
2. **Server Health Check**: Automatic verification that backend is available
3. **Timeout Protection**: Requests timeout after 30 seconds
4. **Improved UI Feedback**: Loading states and error displays
5. **Logging**: Server logs all requests and errors for debugging

## File Structure:

```
LYNX_TEST_1/
├── backend/
│   ├── server.py           # Flask backend server
│   ├── requirements.txt    # Python dependencies
│   └── data/
│       └── satellites_norad_ids.txt
├── index.js               # Main frontend logic (fixed)
├── index.html            # Main HTML file
├── start_server.bat      # Windows batch file to start server
└── README.md            # This file
```