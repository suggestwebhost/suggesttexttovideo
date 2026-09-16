import os
import math
import asyncio
import shutil
import uuid
import gc
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, VideoTask

app = FastAPI(title="Database Backed Video Service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)

# Define async endpoint to prevent thread pool starvation
@app.get("/generate-by-id")
async def generate_by_id(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(VideoTask).filter(VideoTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Requested Task ID not found in DB.")

    unique_run_id = str(uuid.uuid4())
    build_dir = os.path.join(os.getcwd(), f"temp_build_{unique_run_id}")
    output_filename = os.path.join(os.getcwd(), f"output_{unique_run_id}.mp4")
    
    os.makedirs(build_dir, exist_ok=True)

    try:
        from PIL import Image, ImageDraw
        words = task.text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Database record text block is empty.")

        words_per_image = math.ceil(len(words) / task.num_images)
        
        # 1. Memory Leak Fix: Explicitly manage Image lifecycles using context managers
        for i in range(task.num_images):
            with Image.new("RGB", (1920, 1080), color=(30, 30, 30)) as img:
                draw = ImageDraw.Draw(img)
                
                start_idx = i * words_per_image
                chunk_text = " ".join(words[start_idx : start_idx + words_per_image])
                
                draw.text((100, 100), task.headline, fill=(255, 215, 0))
                draw.text((100, 500), chunk_text, fill=(255, 255, 255))
                
                img.save(os.path.join(build_dir, f"frame_{i:03d}.png"))
        
        # Force Python's garbage collector to free unused image allocations immediately
        gc.collect()

        # 2. Event Loop Fix: Non-blocking asynchronous FFmpeg execution
        input_pattern = os.path.join(build_dir, "frame_%03d.png")
        
        # Create the sub-process asynchronously
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-framerate", f"1/{task.duration_per_image}",
            "-i", input_pattern,
            "-c:v", "libx264",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            output_filename,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Await the process completion without blocking other incoming API requests
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg Error: {stderr.decode().strip()}")

        background_tasks.add_task(remove_file, output_filename)

        return FileResponse(
            path=output_filename, 
            media_type="video/mp4", 
            filename=f"video_{task_id}.mp4"
        )

    except Exception as e:
        if os.path.exists(output_filename): 
            os.remove(output_filename)
        if isinstance(e, HTTPException): 
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(build_dir): 
            shutil.rmtree(build_dir)
