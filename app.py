import os
import math
import subprocess
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

# 1. Initialize the FastAPI app object
app = FastAPI(title="Text to Video Web Service")

# 2. ADD THIS ROOT ROUTE FOR TESTING
@app.get("/")
def read_root():
    return {"status": "Online", "message": "Go to /generate-video to post text"}

# 3. Keep your Pydantic data model exactly the same
class VideoRequest(BaseModel):
    text: str
    headline: Optional[str] = ""
    num_images: int = 3
    duration_per_image: int = 3
    width: int = 1920
    height: int = 1080

# ... keep the rest of your wrap_text and @app.post("/generate-video") logic exactly the same below ...


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Correctly wraps text by calculating the true pixel width of strings."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        bbox = font.getbbox(" ".join(current_line))
        # bbox[2] is 'right', bbox[0] is 'left'. (Right - Left = Width)
        text_width = bbox[2] - bbox[0] 
        
        if text_width > max_width:
            current_line.pop()
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines

@app.post("/generate-video")
def generate_video(payload: VideoRequest):
    build_dir = os.path.abspath("temp_build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    
    output_filename = "output.mp4"
    if os.path.exists(output_filename):
        os.remove(output_filename)

    try:
        words = payload.text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Text payload cannot be empty.")
            
        words_per_image = math.ceil(len(words) / payload.num_images)
        chunks = []
        for i in range(payload.num_images):
            start_idx = i * words_per_image
            end_idx = start_idx + words_per_image
            chunk_text = " ".join(words[start_idx:end_idx])
            if chunk_text:  
                chunks.append(chunk_text)

        # Correct Linux path for fonts bundled in our Dockerfile template
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not os.path.exists(font_path):
            font_path = None 

        try:
            headline_font = ImageFont.truetype(font_path, 64) if font_path else ImageFont.load_default()
            body_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
        except Exception:
            headline_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Generate Slide Images
        for idx, chunk in enumerate(chunks):
            img = Image.new("RGB", (payload.width, payload.height), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)

            if payload.headline:
                h_bbox = draw.textbbox((0, 0), payload.headline, font=headline_font)
                h_width = h_bbox[2] - h_bbox[0]
                h_x = (payload.width - h_width) // 2
                draw.text((h_x, 100), payload.headline, font=headline_font, fill=(255, 215, 0))

            max_text_width = int(payload.width * 0.8)
            wrapped_lines = wrap_text(chunk, body_font, max_text_width)
            
            # Fixed textbbox vertical calculation line height 
            sample_bbox = draw.textbbox((0, 0), "Abc", font=body_font)
            line_height = (sample_bbox[3] - sample_bbox[1]) + 20
            total_block_height = len(wrapped_lines) * line_height
            current_y = (payload.height - total_block_height) // 2 + 50

            for line in wrapped_lines:
                l_bbox = draw.textbbox((0, 0), line, font=body_font)
                l_width = l_bbox[2] - l_bbox[0]
                l_x = (payload.width - l_width) // 2
                draw.text((l_x, current_y), line, font=body_font, fill=(255, 255, 255))
                current_y += line_height

            img.save(os.path.join(build_dir, f"frame_{idx:03d}.png"))

        actual_images_count = len(chunks)
        if actual_images_count == 0:
            raise HTTPException(status_code=400, detail="Failed to parse text blocks.")

        # Compile Video
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
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
