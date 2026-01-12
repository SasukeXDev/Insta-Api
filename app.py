from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import uuid

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route("/")
def home():
    return {"status": "API running"}

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Video URL required"}), 400

    video_url = data["url"]
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    ydl_opts = {
        "outtmpl": filepath,
        "format": "mp4",
        "cookiefile": "cookies.txt",
        "noplaylist": True,
        "quiet": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return jsonify({
            "status": "success",
            "download_url": f"/file/{filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/file/<filename>")
def serve_file(filename):
    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True
    )
