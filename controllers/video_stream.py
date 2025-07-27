from flask import Blueprint, request, Response, abort, send_file
import os

video_stream_bp = Blueprint('video_stream', __name__)

@video_stream_bp.route('/video/<path:filename>')
def stream_video(filename):
    """
    Video dosyasını stream et
    ---
    tags:
      - Video
    parameters:
      - name: filename
        in: path
        type: string
        required: true
        description: Video dosya adı (uploads klasöründe)
    produces:
      - video/mp4
    responses:
      200:
        description: Video stream
        schema:
          type: file
      404:
        description: Dosya bulunamadı
    """
    video_path = os.path.join('static', 'uploads', filename)
    if not os.path.exists(video_path):
        abort(404)
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(video_path)
    size = os.path.getsize(video_path)
    byte1, byte2 = 0, None
    m = range_header.replace('bytes=', '').split('-')
    if m[0]:
        byte1 = int(m[0])
    if len(m) == 2 and m[1]:
        byte2 = int(m[1])
    length = size - byte1 if byte2 is None else byte2 - byte1 + 1
    with open(video_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
    rv = Response(data, 206, mimetype='video/mp4', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{size}')
    rv.headers.add('Accept-Ranges', 'bytes')
    return rv 