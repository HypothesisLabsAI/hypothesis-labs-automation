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
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    IS_V2 = False
except ImportError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    IS_V2 = True

# --- CONFIGURATION ---
VIDEO_PATH = "cloud_video.mp4"

SYSTEM_INSTRUCTION = """
You are the lead AI automated writer for 'Hypothesis Labs'.
Generate a 50-60 second vertical video script about speculative theoretical physics, chemistry, or AI architecture.

You MUST format your output exactly like this:

[TITLE]
Write an engaging, click-worthy title (under 50 characters). It MUST use speculative qualifiers (like "Speculative", "Theoretical", "Could", "Hypothesis") to protect channel compliance.

SCENE_START
[NARRATION]
Write a high-impact, gripping narration segment here (approx. 25-30 words). Speak directly to tech-enthusiasts. No actions, hashtags, or bracketed directions. Keep sentences clean and fluid.
[IMAGE_PROMPT]
Write a single, highly detailed, photorealistic 8K vertical (9:16) 3D render prompt for an image generator that matches this scene's narrative.
SCENE_END

Generate EXACTLY 4 distinct scenes using the SCENE_START and SCENE_END markers for each.
"""

def generate_script():
    print("--- STEP 1: Brainstorming Speculative Storyboard Script ---")
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
    print("--- STEP 2: Parsing & Cleaning Storyboard Scenes ---")
    
    # 1. Parse Title
    title_match = re.search(r'\\[TITLE\\](.*?)(\n\n|SCENE_START|$)', raw_text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else "A Speculative Leap in AI Architecture"
    title = re.sub(r"[*#`_]", "", title).strip()
    clean_title = f"{title[:70]} | Hypothesis Labs"
    
    # 2. Parse Scenes
    scene_blocks = re.findall(r'SCENE_START(.*?)SCENE_END', raw_text, re.DOTALL)
    if not scene_blocks:
        # Fallback split
        scene_blocks = re.split(r'SCENE_START|SCENE_END', raw_text)
        scene_blocks = [s.strip() for s in scene_blocks if s.strip()]
        
    parsed_scenes = []
    for block in scene_blocks:
        narr_match = re.search(r'\\[NARRATION\\](.*?)(\\[IMAGE_PROMPT\\]|$)', block, re.DOTALL)
        prompt_match = re.search(r'\\[IMAGE_PROMPT\\](.*)', block, re.DOTALL)
        
        if narr_match and prompt_match:
            narration = narr_match.group(1).strip()
            prompt = prompt_match.group(1).strip()
            
            # Clean syntax
            clean_narr = re.sub(r"[*#`_\-\\[\\]]", "", narration).strip()
            clean_prompt = re.sub(r"```[a-zA-Z]*|```|[*#`_\-\\[\\]]", "", prompt).strip()
            
            if clean_narr and clean_prompt:
                parsed_scenes.append((clean_narr, clean_prompt))
                
    if len(parsed_scenes) < 2:
        raise ValueError(f"AI response failed to format storyboard scenes properly. Found only {len(parsed_scenes)} valid scenes.")
        
    print(f"Successfully parsed Title: '{clean_title}' and {len(parsed_scenes)} storyboard scenes.")
    return clean_title, parsed_scenes

async def generate_audio(text, file_path):
    voice = "en-US-ChristopherNeural"  # Professional, deep narrator voice
    clean_text = re.sub(r"[<>#]", "", text)
    formatted_text = clean_text.replace(". ", "... ").replace("? ", "...? ").replace("! ", "...! ")
    
    communicate = edge_tts.Communicate(
        text=formatted_text,
        voice=voice,
        rate="-8%",   # Slower rate for a cinematic, authoritative pacing
        pitch="-5Hz"  # Deepened tone for added gravity
    )
    await communicate.save(file_path)

def generate_image(prompt, file_path):
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&private=true"
    
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
    else:
        raise RuntimeError(f"Image generation server failed for prompt: {prompt[:50]}")

def compile_scenes_to_video(scenes_data):
    print("--- STEP 5: Stitching Multi-Scene Cinematic Montage ---")
    clips = []
    
    for idx, (narration, prompt) in enumerate(scenes_data, 1):
        audio_path = f"scene_{idx}.mp3"
        image_path = f"scene_{idx}.png"
        
        print(f"Processing Scene {idx}/{len(scenes_data)} (Duration mapping...)")
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        
        image_clip = ImageClip(image_path).set_duration(duration)
        
        # Ken Burns Zoom Effect per scene: rapid visual movement
        if IS_V2:
            # MoviePy v2 uses .resized
            video_clip = image_clip.resized(lambda t: 1.0 + 0.12 * (t / duration))
            video_clip = video_clip.with_audio(audio)
        else:
            # MoviePy v1 uses .resize
            video_clip = image_clip.resize(lambda t: 1.0 + 0.12 * (t / duration))
            video_clip = video_clip.set_audio(audio)
            
        clips.append(video_clip)
        
    final_video = concatenate_videoclips(clips, method="compose")
    
    final_video.write_videofile(
        VIDEO_PATH,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    
    # Close resources
    for clip in clips:
        clip.close()
    final_video.close()
    print("Multi-scene cinematic montage rendering complete!")

def upload_to_youtube(title, full_narration):
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
    
    # Description Rules: Clear educational disclaimer placed at the very top
    description = (
        "DISCLAIMER: This video explores a speculative, theoretical scientific design. "
        "It is an entertaining scientific thought-experiment based on existing concepts "
        "and is not currently peer-reviewed.\n\n"
        f"{full_narration}\n\n"
        "What do you think of this theoretical architecture? If we actually built this, "
        "what bottlenecks would we hit first? Let's discuss in the comments!\n\n"
        "Produced automatically by Hypothesis Labs."
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
        # 1. Generate multi-scene script
        raw_script = generate_script()
        
        # 2. Parse into Title and distinct Scenes
        title, scenes_data = parse_assets(raw_script)
        
        # 3. Generate Audio assets
        print("--- STEP 3: Synthesizing Multi-Scene Voice Tracks ---")
        loop = asyncio.get_event_loop()
        for idx, (narration, _) in enumerate(scenes_data, 1):
            audio_path = f"scene_{idx}.mp3"
            loop.run_until_complete(generate_audio(narration, audio_path))
            
        # 4. Generate Image assets
        print("--- STEP 4: Downloading Multi-Scene Visual Backdrops ---")
        for idx, (_, prompt) in enumerate(scenes_data, 1):
            image_path = f"scene_{idx}.png"
            generate_image(prompt, image_path)
            
        # 5. Compile into a Multi-Scene Video with Independent zooms
        compile_scenes_to_video(scenes_data)
        
        # 6. Upload to YouTube
        full_narration = "\n\n".join([narr for narr, _ in scenes_data])
        upload_to_youtube(title, full_narration)
        
        # Cleanup temporary assets
        for idx in range(1, len(scenes_data) + 1):
            try:
                os.remove(f"scene_{idx}.mp3")
                os.remove(f"scene_{idx}.png")
            except OSError:
                pass
                
        print("\n🚀 Autopilot successfully completed. Video published to YouTube on the cloud!")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import sys
        sys.exit(1)  # Force non-zero status code so GitHub Actions reports failures correctly

if __name__ == "__main__":
    main()
