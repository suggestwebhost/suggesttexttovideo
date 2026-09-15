import os
import math
import subprocess
import shutil
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, VideoTask

app = FastAPI(title="Database Backed Video Service")

# Dependency to safely manage database connections
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/generate-by-id")
def generate_by_id(task_id: str, db: Session = Depends(get_db)):
    # 🌟 1. Fetch data directly from DB instead of request network travel
    task = db.query(VideoTask).filter(VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Requested Task ID not found in DB.")

    build_dir = os.path.join(os.getcwd(), "temp_build")
    output_filename = os.path.join(os.getcwd(), "output.mp4")
    
    if os.path.exists(build_dir): shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    if os.path.exists(output_filename): os.remove(output_filename)

    try:
        from PIL import Image, ImageDraw, ImageFont
        words = task.text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Database record text block is empty.")

        # 2. Build your slide images
        words_per_image = math.ceil(len(words) / task.num_images)
        for i in range(task.num_images):
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            
            start_idx = i * words_per_image
            chunk_text = " ".join(words[start_idx : start_idx + words_per_image])
            
            draw.text((100, 100), task.headline, fill=(255, 215, 0))
            draw.text((100, 500), chunk_text, fill=(255, 255, 255))
            img.save(os.path.join(build_dir, f"frame_{i:03d}.png"))

        # 3. Compile the frames into video using FFmpeg
        input_pattern = os.path.join(build_dir, "frame_%03d.png")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", f"1/{task.duration_per_image}",
            "-i", input_pattern,
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename
        ]
        
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg Error: {result.stderr}")

        return FileResponse(output_filename, media_type="video/mp4", filename="output.mp4")

    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(build_dir): shutil.rmtree(build_dir)
