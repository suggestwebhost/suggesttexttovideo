import os
import math
import subprocess
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="Text to Video Web Service")

# Request validation model
class VideoRequest(BaseModel):
    text: str
    headline: Optional[str] = ""
    num_images: int = 3
    duration_per_image: int = 3  # in seconds
    width: int = 1920
    height: int = 1080

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Helper to cleanly wrap lines within a maximum bounding pixel width."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        # Use font.getbbox() to measure text width
        bbox = font.getbbox(" ".join(current_line))
        if bbox[2] - bbox[0] > max_width:
            current_line.pop()
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

@app.post("/generate-video")
def generate_video(payload: VideoRequest):
    # Set up safe execution directories
    build_dir = os.path.abspath("temp_build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    
    output_filename = "output.mp4"
    if os.path.exists(output_filename):
        os.remove(output_filename)

    try:
        # 1. Cleanly split text chunk assignments evenly across slides
        words = payload.text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Text payload cannot be empty.")
            
        words_per_image = math.ceil(len(words) / payload.num_images)
        chunks = []
        for i in range(payload.num_images):
            start_idx = i * words_per_image
            end_idx = start_idx + words_per_image
            chunk_text = " ".join(words[start_idx:end_idx])
            if chunk_text:  # Avoid creating blank images if word count is small
                chunks.append(chunk_text)

        # Use fallback Linux paths for default bundled fonts
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not os.path.exists(font_path):
            font_path = None # Fallback to default low-res bitmap font if missing locally

        # Load fonts
        try:
            headline_font = ImageFont.truetype(font_path, 64) if font_path else ImageFont.load_default()
            body_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
        except Exception:
            headline_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # 2. Build Slide Images
        for idx, chunk in enumerate(chunks):
            # Create dark canvas backdrop
            img = Image.new("RGB", (payload.width, payload.height), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)

            # Draw top headline if provided
            if payload.headline:
                h_bbox = draw.textbbox((0, 0), payload.headline, font=headline_font)
                h_width = h_bbox[2] - h_bbox[0]
                h_x = (payload.width - h_width) // 2
                draw.text((h_x, 100), payload.headline, font=headline_font, fill=(255, 215, 0)) # Gold Headline

            # Wrap and render body paragraph text blocks
            max_text_width = int(payload.width * 0.8)
            wrapped_lines = wrap_text(chunk, body_font, max_text_width)
            
            # Center the text block vertically on the canvas
            line_height = draw.textbbox((0, 0), "Abc", font=body_font)[3] + 15
            total_block_height = len(wrapped_lines) * line_height
            current_y = (payload.height - total_block_height) // 2 + 50

            for line in wrapped_lines:
                l_bbox = draw.textbbox((0, 0), line, font=body_font)
                l_width = l_bbox[2] - l_bbox[0]
                l_x = (payload.width - l_width) // 2
                draw.text((l_x, current_y), line, font=body_font, fill=(255, 255, 255))
                current_y += line_height

            # Save frame file sequential identifiers for ffmpeg input matching
            img.save(os.path.join(build_dir, f"frame_{idx:03d}.png"))

        # If text length was small, align actual count
        actual_images_count = len(chunks)
        if actual_images_count == 0:
            raise HTTPException(status_code=400, detail="Failed to parse text blocks.")

        # 3. Compile Images via FFmpeg Subprocess
        # Uses image2 loop format filter to cleanly space out durations without heavy disk writes
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", f"1/{payload.duration_per_image}",
            "-i", os.path.join(build_dir, "frame_%03d.png"),
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename
        ]
        
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg Error: {result.stderr}")

        return FileResponse(output_filename, media_type="video/mp4", filename=output_filename)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup loose building image blocks
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
