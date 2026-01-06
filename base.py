import os
import subprocess
import hashlib
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_DIR = os.path.join(BASE_DIR, "static", "streams")
os.makedirs(HLS_DIR, exist_ok=True)

@app.route("/convert", methods=["POST", "OPTIONS"])
def convert():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"status": "error", "message": "URL missing"}), 400

    video_url = data["url"]
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    out_dir = os.path.join(HLS_DIR, stream_id)
    playlist = os.path.join(out_dir, "index.m3u8")

    os.makedirs(out_dir, exist_ok=True)

    # Return existing if found
    if os.path.exists(playlist):
        proto = request.headers.get("X-Forwarded-Proto", "https")
        return jsonify({
            "status": "success",
            "hls_link": f"{proto}://{request.host}/static/streams/{stream_id}/index.m3u8"
        })

    # -------- STRENGTHENED FFMPEG COMMAND --------
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        
        # FIX: Increase probing to find all audio tracks in large MKV files
        "-analyzeduration", "20000000", 
        "-probesize", "20000000",
        
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
        "-i", video_url,

        # FIX: Explicit Mapping (Maps 1st video and ALL audio streams ONLY)
        # This ignores the corrupted PNG attachment causing your crash
        "-map", "0:v:0",
        "-map", "0:a",

        "-c:v", "copy",        # Direct stream copy for video
        "-c:a", "aac",         # Encode all audio to AAC for HLS
        "-ac", "2",            # Downmix to stereo for web stability
        
        # FIX: HLS VOD Flags (Removes Live Badge)
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-hls_playlist_type", "vod",  # Forces VOD (removes Live badge)
        "-hls_flags", "independent_segments",
        
        "-hls_segment_filename", os.path.join(out_dir, "seg_%05d.ts"),
        playlist
    ]

    try:
        # Start conversion in background
        subprocess.Popen(cmd)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # -------- WAIT UNTIL PLAYLIST IS READY --------
    timeout = 20 # Increased timeout for slow probing links
    while timeout > 0:
        if os.path.exists(playlist) and os.path.getsize(playlist) > 0:
            break
        time.sleep(1)
        timeout -= 1

    if not os.path.exists(playlist):
        return jsonify({"status": "error", "message": "FFmpeg failed to create playlist"}), 500

    proto = request.headers.get("X-Forwarded-Proto", "https")
    hls_url = f"{proto}://{request.host}/static/streams/{stream_id}/index.m3u8"

    return jsonify({"status": "success", "hls_link": hls_url})

@app.route("/static/streams/<path:filename>")
def serve_hls(filename):
    response = send_from_directory(HLS_DIR, filename)
    # Vital for multi-track support
    if filename.endswith(".m3u8"):
        response.headers["Content-Type"] = "application/vnd.apple.mpegurl"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
