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
    build_dir = os.path.abspath("temp_build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    
    output_filename = "output.mp4"
    if os.path.exists(output_filename):
        os.remove(output_filename)

    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 🌟 SAFE FONT HANDLING: Avoid path crashes
        try:
            # Try loading default system fonts if available
            body_font = ImageFont.load_default()
            headline_font = ImageFont.load_default()
        except Exception:
            body_font = None
            headline_font = None

        words = text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Text cannot be empty.")

        words_per_image = math.ceil(len(words) / num_images)
        
        # Generate Images
        for i in range(num_images):
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            
            start_idx = i * words_per_image
            chunk_text = " ".join(words[start_idx : start_idx + words_per_image])
            
            # Draw layout texts cleanly with fallbacks
            draw.text((100, 100), headline, fill=(255, 215, 0), font=headline_font)
            draw.text((100, 500), chunk_text, fill=(255, 255, 255), font=body_font)
            
            img.save(os.path.join(build_dir, f"frame_{i:03d}.png"))

        # 🌟 CHECK IF FFMPEG IS INSTALLED EXPLICITLY
        if shutil.which("ffmpeg") is None:
            raise HTTPException(
                status_code=500, 
                detail="FFmpeg is not installed on the server environment. Please use a Dockerfile deployment."
            )

        # Execute FFmpeg Compilation
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", f"1/{duration_per_image}",
            "-i", os.path.join(build_dir, "frame_%03d.png"),
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename
        ]
        
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg Execution Failed: {result.stderr}")

        return FileResponse(output_filename, media_type="video/mp4", filename=output_filename)

    except Exception as e:
        # Pass the exact internal python error back to the client instead of a blind 502
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Server Script Crash: {str(e)}")
        
    finally:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, forwarded_allow_ips="*")
