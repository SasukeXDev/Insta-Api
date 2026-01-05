import os
import subprocess
import hashlib
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)

# 1. FIXED CORS: This allows ANY domain to access your HLS files
CORS(app, resources={r"/*": {"origins": "*"}})

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_OUTPUT_DIR = os.path.join(BASE_DIR, "static", "streams")
os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

# Headers to mimic a real browser for FFmpeg
COMMON_HEADERS = (
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
    "Referer: https://forproduction.onrender.com/\r\n"
)

@app.route('/convert', methods=['POST', 'OPTIONS'])
def convert():
    # Handle preflight request for CORS
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400

    video_url = data.get('url')
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    output_path = os.path.join(HLS_OUTPUT_DIR, stream_id)
    playlist_file = os.path.join(output_path, 'index.m3u8')

    # Full URL for the frontend
    base_server_url = request.host_url.rstrip('/')

    if not os.path.exists(playlist_file):
        os.makedirs(output_path, exist_ok=True)

        # 2. IMPROVED FFmpeg: Added headers and better HLS flags
        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-headers', COMMON_HEADERS, # Pass headers to the source
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-i', video_url,
            '-map', '0:v:0', '-map', '0:a?', '-map', '0:s?',
            '-c:v', 'copy',           # Copy video codec (Fast)
            '-c:a', 'aac',            # Encode audio to AAC
            '-c:s', 'webvtt',         # Convert subs to WebVTT
            '-f', 'hls', 
            '-hls_time', '10', 
            '-hls_list_size', '0',
            '-hls_flags', 'delete_segments+append_list', # Keeps playlist updated
            '-hls_segment_filename', os.path.join(output_path, 'seg_%03d.ts'),
            playlist_file
        ]
        
        # Start conversion in background
        subprocess.Popen(cmd)

    return jsonify({
        "status": "success",
        "hls_link": f"{base_server_url}/static/streams/{stream_id}/index.m3u8"
    }), 200

# 3. MANUAL STATIC SERVING: Fixes 404s on some cloud platforms
@app.route('/static/streams/<path:filename>')
def custom_static(filename):
    response = send_from_directory(HLS_OUTPUT_DIR, filename)
    # Ensure HLS segments have CORS headers too
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
