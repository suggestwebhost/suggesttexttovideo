import os
import math
import subprocess
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

#app = FastAPI(title="Text to Video Web Service")
app = FastAPI(title="Text to Video Web Service", redirect_slashes=False)

# 🌟 TEST ROUTE: To check if GET requests can see queries
@app.get("/")
def read_root(text: Optional[str] = None, headline: Optional[str] = None):
    return {
        "status": "Online", 
        "message": "Backend is active!",
        "received_text": text,
        "received_headline": headline
    }

# 🌟 FORM POST ROUTE: Reliable format for Render proxies
@app.post("/generate-video")
@app.post("/generate-video/")
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
        from PIL import Image, ImageDraw
        words = text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Text cannot be empty.")

        # Basic slide generation logic
        words_per_image = math.ceil(len(words) / num_images)
        for i in range(num_images):
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            start_idx = i * words_per_image
            chunk_text = " ".join(words[start_idx : start_idx + words_per_image])
            
            # Simple placeholder text drawing
            draw.text((100, 100), headline, fill=(255, 215, 0))
            draw.text((100, 500), chunk_text, fill=(255, 255, 255))
            img.save(os.path.join(build_dir, f"frame_{i:03d}.png"))

        # FFmpeg compilation
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", f"1/{duration_per_image}",
            "-i", os.path.join(build_dir, "frame_%03d.png"),
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename
        ]
        subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return FileResponse(output_filename, media_type="video/mp4", filename=output_filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

# 🌟 MISSING FORCE RUNNER CODE
if __name__ == "__main__":
    import uvicorn
    # Render assigns a dynamic port via environment variables. If none exists, default to 10000.
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
