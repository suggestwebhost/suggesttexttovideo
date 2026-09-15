import os
import math
import subprocess
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import FileResponse

app = FastAPI(title="Text to Video Web Service", redirect_slashes=False)

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Backend is active!"}

@app.post("/generate-video")
def generate_video(
    text: str = Form(...),
    headline: str = Form(""),
    num_images: int = Form(3),
    duration_per_image: int = Form(3)
):
    # Use the local app root directory directly for stable container paths
    build_dir = os.path.join(os.getcwd(), "temp_build")
    output_filename = os.path.join(os.getcwd(), "output.mp4")
    
    # Clean previous artifacts safely
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    
    if os.path.exists(output_filename):
        os.remove(output_filename)

    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Safe font processing configuration fallback
        body_font = ImageFont.load_default()
        headline_font = ImageFont.load_default()

        words = text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Text payload cannot be empty.")

        words_per_image = math.ceil(len(words) / num_images)
        
        # 1. Generate PNG Slide Frames
        for i in range(num_images):
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            
            start_idx = i * words_per_image
            chunk_text = " ".join(words[start_idx : start_idx + words_per_image])
            
            # Render labels
            draw.text((100, 100), headline, fill=(255, 215, 0), font=headline_font)
            draw.text((100, 500), chunk_text, fill=(255, 255, 255), font=body_font)
            
            # Absolute explicit path construction string
            frame_path = os.path.join(build_dir, f"frame_{i:03d}.png")
            img.save(frame_path)

        # 2. Check for FFmpeg tool presence inside Docker layer
        if shutil.which("ffmpeg") is None:
            raise HTTPException(status_code=500, detail="FFmpeg missing inside container environment.")

        # 3. Explicit input path pattern compilation for Linux environment
        input_pattern = os.path.join(build_dir, "frame_%03d.png")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", f"1/{duration_per_image}",
            "-i", input_pattern,
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename
        ]
        
        # Run subprocess execution tracking output streams
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            # If FFmpeg breaks, return the exact log back to client to view details
            raise HTTPException(status_code=500, detail=f"FFmpeg compilation error: {result.stderr}")

        if not os.path.exists(output_filename):
            raise HTTPException(status_code=500, detail="Video file generation process timed out.")

        return FileResponse(output_filename, media_type="video/mp4", filename="output.mp4")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Server Script Exception: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, forwarded_allow_ips="*")
