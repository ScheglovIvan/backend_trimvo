import os
import subprocess
import tempfile


def create_preview_compressed(input_path: str, output_path: str) -> None:
    """Preview for My Works cards: 720p, CRF 26, H.264 High profile, no audio.

    preset=slow gives better compression ratio than fast — same or smaller file
    size at significantly better visual quality. High profile enables more
    efficient encoding tools (CABAC, B-frames) absent in Baseline/Main.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-an",
            "-vf", "scale=720:-2",
            "-c:v", "libx264",
            "-crf", "26",
            "-preset", "slow",
            "-profile:v", "high",
            "-level", "4.0",
            "-movflags", "+faststart",
            output_path,
        ],
        check=True, capture_output=True,
    )


def create_preview(input_path: str, output_path: str) -> None:
    """Full quality preview for detail screen: 1080p, CRF 22, no audio."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-an",
            "-vf", "scale=1080:-2",
            "-c:v", "libx264",
            "-crf", "22",
            "-preset", "slow",
            "-profile:v", "high",
            "-level", "4.1",
            "-movflags", "+faststart",
            output_path,
        ],
        check=True, capture_output=True,
    )


def create_gif(input_path: str, output_path: str) -> None:
    """First 3 seconds, 480px, 10fps"""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-t", "3", "-vf", "fps=10,scale=480:-2", output_path],
        check=True, capture_output=True,
    )


def extract_thumb(input_path: str, output_path: str) -> None:
    """Extract first frame as jpg"""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-vframes", "1", "-f", "image2", output_path],
        check=True, capture_output=True,
    )


def process_video(video_bytes: bytes, base_key: str, bucket: str) -> dict:
    """
    Create preview/gif/thumb from video bytes, upload to MinIO.
    Returns dict with subset of: preview_path, gif_path, thumb_path
    """
    from services import storage as stor

    result = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.mp4")
        with open(input_path, "wb") as f:
            f.write(video_bytes)

        tasks = [
            ("preview_compressed_path", "preview_small.mp4", "video/mp4", create_preview_compressed),
            ("preview_path", "preview.mp4", "video/mp4", create_preview),
            ("gif_path", "preview.gif", "image/gif", create_gif),
            ("thumb_path", "thumb.jpg", "image/jpeg", extract_thumb),
        ]

        for field, filename, content_type, fn in tasks:
            out_path = os.path.join(tmpdir, filename)
            try:
                fn(input_path, out_path)
                with open(out_path, "rb") as f:
                    data = f.read()
                key = f"{base_key}/{filename}"
                stor.upload_file(bucket, key, data, content_type)
                result[field] = key
            except Exception as e:
                print(f"media_processor: {field} failed: {e}")

    return result
