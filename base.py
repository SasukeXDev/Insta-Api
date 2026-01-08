import os, subprocess, hashlib, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_DIR = os.path.join(BASE_DIR, "static", "streams")
os.makedirs(HLS_DIR, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(silent=True)
    video_url = data.get("url")

    if not video_url:
        return jsonify({"error": "No URL"}), 400

    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    out_dir = os.path.join(HLS_DIR, stream_id)
    playlist = os.path.join(out_dir, "index.m3u8")

    os.makedirs(out_dir, exist_ok=True)

    # Start ffmpeg ONLY if not already running
    if not os.path.exists(playlist):
        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",

            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",

            "-i", video_url,

            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "copy",
            "-c:a", "aac",
            "-ac", "2",

            "-f", "hls",
            "-hls_time", "6",
            "-hls_list_size", "0",
            "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments+append_list",
            "-hls_segment_filename", os.path.join(out_dir, "seg_%05d.ts"),

            playlist
        ]

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    proto = request.headers.get("X-Forwarded-Proto", "https")
    hls_url = f"{proto}://{request.host}/streams/{stream_id}/index.m3u8"

    return jsonify({
        "status": "starting",
        "hls": hls_url
    })


# ✅ CORRECT STATIC ROUTE (IMPORTANT)
@app.route("/streams/<stream_id>/<path:filename>")
def serve_hls(stream_id, filename):
    directory = os.path.join(HLS_DIR, stream_id)
    response = send_from_directory(directory, filename)
    response.headers["Access-Control-Allow-Origin"] = "*"

    if filename.endswith(".m3u8"):
        response.headers["Content-Type"] = "application/vnd.apple.mpegurl"
    elif filename.endswith(".ts"):
        response.headers["Content-Type"] = "video/mp2t"

    return response



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
