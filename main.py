import os
import re
import asyncio
import urllib.parse
import requests
import edge_tts
from google import genai
from google.genai import types

# Robust MoviePy import handling for cloud environments
try:
    from moviepy.editor import ImageClip, AudioFileClip
    IS_V2 = False
except ImportError:
    from moviepy import ImageClip, AudioFileClip
    IS_V2 = True

# --- CONFIGURATION ---
AUDIO_PATH = "cloud_audio.mp3"
IMAGE_PATH = "cloud_image.png"
VIDEO_PATH = "cloud_video.mp4"

SYSTEM_INSTRUCTION = """
You are the lead AI automated writer for 'Hypothesis Labs'.
Generate a 50-60 second vertical video script about speculative theoretical physics, chemistry, or AI architecture.

You MUST format your output exactly like this:

[NARRATION]
Write the high-impact, gripping narration text here. Speak directly to tech-enthusiasts. Keep it to roughly 120 words. Do not include action notes, hashtags, or bracketed directions.

[IMAGE_PROMPT]
Write a single, highly detailed, photorealistic 8K 3D render prompt for an image generator that matches the narration.
"""

def generate_script():
    print("--- STEP 1: Brainstorming Speculative Script ---")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    models = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
    for model in models:
        try:
            print(f"Attempting script generation with: {model}")
            response = client.models.generate_content(
                model=model,
                contents="Write a script about a theoretical physics or speculative AI concept.",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.8
                )
            )
            print(f"🎉 Successfully generated using model: {model}")
            return response.text
        except Exception as e:
            print(f"⚠️ Model {model} failed. Trying next... Error: {e}")
            continue
    raise RuntimeError("All Gemini models failed to respond.")

def parse_assets(raw_text):
    print("--- STEP 2: Parsing & Cleaning Script Assets ---")
    clean = raw_text.replace("**[NARRATION]**", "[NARRATION]").replace("**[IMAGE_PROMPT]**", "[IMAGE_PROMPT]")
    if "[NARRATION]" not in clean or "[IMAGE_PROMPT]" not in clean:
        raise ValueError("AI response missed required structural markers.")
        
    parts = clean.split("[IMAGE_PROMPT]")
    narration = parts[0].replace("[NARRATION]", "").strip()
    img_prompt = parts[1].strip() if len(parts) > 1 else ""
    
    # Scrubbing out any stray asterisks, hashes, brackets, or code blocks
    clean_narration = re.sub(r"[*#`_\-\\[\\]]", "", narration).strip()
    clean_prompt = re.sub(r"```[a-zA-Z]*|```|[*#`_\-\\[\\]]", "", img_prompt).strip()
    
    return clean_narration, clean_prompt

async def generate_audio(text):
    print("--- STEP 3: Synthesizing Neural Narrator Voice ---")
    voice = "en-US-ChristopherNeural"  # Professional, deep narrator voice
    
    # Clean text of XML special characters to prevent rendering bugs
    clean_text = re.sub(r"[<>#]", "", text)
    formatted_text = clean_text.replace(". ", "... ").replace("? ", "...? ").replace("! ", "...! ")
    
    communicate = edge_tts.Communicate(
        text=formatted_text,
        voice=voice,
        rate="-8%",   # Slower rate for a cinematic, authoritative pacing
        pitch="-5Hz"  # Deepened tone for added gravity
    )
    await communicate.save(AUDIO_PATH)
    print("Voice track successfully synthesized!")

def generate_image(prompt):
    print("--- STEP 4: Downloading Cinematic Visual backdrop ---")
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&private=true"
    
    response = requests.get(url)
    if response.status_code == 200:
        with open(IMAGE_PATH, 'wb') as f:
            f.write(response.content)
        print("Visual backdrop successfully rendered!")
    else:
        raise RuntimeError("Image generation server failed.")

def compile_video_with_zoom():
    print("--- STEP 5: Stitching Assets & Rendering Dynamic Visuals ---")
    audio = AudioFileClip(AUDIO_PATH)
    duration = audio.duration
    
    # Ken Burns Zoom Effect: Keep viewer retention high by scaling the image dynamically over time
    image_clip = ImageClip(IMAGE_PATH).set_duration(duration)
    
    if IS_V2:
        video_clip = image_clip.resized(lambda t: 1.0 + 0.15 * (t / duration))
        video_clip = video_clip.with_audio(audio)
    else:
        video_clip = image_clip.resize(lambda t: 1.0 + 0.15 * (t / duration))
        video_clip = video_clip.set_audio(audio)
    
    video_clip.write_videofile(
        VIDEO_PATH,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    audio.close()
    video_clip.close()
    print("Video rendering complete!")

def upload_to_youtube(narration):
    print("--- STEP 6: Publishing to YouTube ---")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"]
    )
    youtube = build("youtube", "v3", credentials=creds)
    
    # Title Rules: Always include speculative qualifiers
    title = "A Speculative Leap in Quantum AI Architecture | Hypothesis Labs"
    
    # Description Rules: Clear educational disclaimer placed at the very top
    description = (
        f"DISCLAIMER: This video explores a speculative, theoretical design. "
        f"It is an entertaining scientific thought-experiment and is not currently peer-reviewed.\n\n"
        f"{narration}\n\n"
        f"Produced automatically by Hypothesis Labs."
    )
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "28"  # Science & Technology category
        },
        "status": {
            "privacyStatus": "private",  # Uploads as Private first for safety reviews
            "selfDeclaredSyntheticContent": True  # 100% compliant AI policy labeling
        }
    }
    
    media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress() * 100)}% complete.")
            
    print(f"🎉 Success! Video successfully uploaded. Video ID: {response['id']}")

def main():
    try:
        script = generate_script()
        narration, prompt = parse_assets(script)
        
        asyncio.run(generate_audio(narration))
        generate_image(prompt)
        compile_video_with_zoom()
        upload_to_youtube(narration)
        
        print("\n🚀 Autopilot successfully completed. Video published to YouTube on the cloud!")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    main()