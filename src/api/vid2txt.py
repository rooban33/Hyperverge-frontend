import os
import cv2
import numpy as np
from .img2txt import process_image 
import json
import moviepy as mp
from openai import OpenAI
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv() 

client = OpenAI(api_key="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")

def separate_audio_and_video(video_file):
    os.makedirs("audio", exist_ok=True)
    os.makedirs("video", exist_ok=True)
    # Load the video file
    video = mp.VideoFileClip(video_file)
    
    if video.audio is None:
        print("⚠️ No audio track found in the video.")
        return "", video_file 
    
    # Extract audio
    audio = video.audio
    audio_file = "audio//separated_audio.wav"
    
    # Write the audio to a separate file
    audio.write_audiofile(audio_file)
    print(f"Audio extracted and saved as {audio_file}")
    
    # Remove the audio from the video (keeping the video only)
    video_without_audio = video.without_audio()
    video_file_without_audio = "video//video_without_audio.mp4"
    
    # Write the video without audio to a new file
    video_without_audio.write_videofile(video_file_without_audio, codec="libx264")
    print(f"Video without audio saved as {video_file_without_audio}")

    return audio_file,video_file

def audio_to_text(audio_file):
    if not audio_file:
        print("⚠️ Skipping transcription: No audio file provided.")
        return ""
    client = OpenAI(api_key="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")

    # Open the audio file in binary mode
    with open(audio_file, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text

def preprocess(frame):
    return cv2.resize(frame, (640, 480))[:, :, :3]

def merge_text_fields(data):
    all_lines = set()
    merged_lines = []

    for frame in data.values():
        # Ensure frame is a dictionary before accessing keys
        if isinstance(frame, dict):
            text = frame.get("text", "")
        else:
            text = frame.strip()  # If frame is a string, treat it directly

        text_lower = text.lower()
        if "text content in the image:" in text_lower:
            start_idx = text_lower.find("text content in the image:") + len("text content in the image:")
            end_idx = text_lower.find("a small description")  # End marker

            if end_idx == -1:
                end_idx = len(text)

            content = text[start_idx:end_idx].strip()

            for line in content.splitlines():
                clean_line = line.strip().rstrip('.')
                if clean_line and clean_line not in all_lines:
                    all_lines.add(clean_line)
                    merged_lines.append(clean_line)

    return "\n".join(merged_lines)


def normalized_frame_difference(frame1, frame2):
    frame1 = preprocess(frame1)
    frame2 = preprocess(frame2)
    difference = cv2.absdiff(frame1, frame2)
    diff_sum = np.sum(difference)

    height, width, channels = frame1.shape
    max_diff = height * width * 255 * channels

    return diff_sum / max_diff

def is_unique(extracted, complete):
    """Check if extracted JSON has unique content not in complete."""
    # Handle text field comparison
    extracted_text = extracted.get('text', '').strip().lower() if isinstance(extracted, dict) else extracted.strip().lower()

    for key, value in complete.items():
        if isinstance(value, dict):
            existing_text = value.get('text', '').strip().lower()
        else:
            existing_text = value.strip().lower()

        if extracted_text == existing_text:
            return False

    # Handle image_description field comparison
    extracted_description = extracted.get('image_description', '').strip().lower() if isinstance(extracted, dict) else extracted.strip().lower()
    for key, value in complete.items():
        if isinstance(value, dict):
            existing_description = value.get('image_description', '').strip().lower()
        else:
            existing_description = value.strip().lower()

        if extracted_description == existing_description:
            return False

    # Check diagrams/objects comparison (empty in this case)
    extracted_diagrams = extracted.get('diagrams_or_objects', {}) if isinstance(extracted, dict) else {}
    for key, value in complete.items():
        if isinstance(value, dict):
            existing_diagrams = value.get('diagrams_or_objects', {})
        else:
            existing_diagrams = {}

        if extracted_diagrams == existing_diagrams:
            return False
    
    return True

def merge_unique_data(complete, extracted):
    """Append only unique parts of extracted into complete."""
    if not is_unique(extracted, complete):
        print("⚠ Skipped (duplicate data).")
        return complete  # Nothing new to add

    # Add or merge text field
    text = extracted.get('text', '')
    if text:
        complete['text'] = text

    # Add or merge image_description field
    description = extracted.get('image_description', '')
    if description:
        complete['image_description'] = description

    # Add or merge diagrams_or_objects field
    diagrams = extracted.get('diagrams_or_objects', {})
    if diagrams:
        complete['diagrams_or_objects'] = diagrams

    print("✅ Unique data added.")
    return complete

def compare_video_frames(video_path, threshold=0.0001, interval=3):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = int(fps * interval)

    if not cap.isOpened():
        print("Error: Cannot open video file.")
        return

    frame_index = 0
    saved_frame_index = 0
    prev_frame = None
    complete_json = {}

    while frame_index < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, curr_frame = cap.read()
        if not ret:
            break

        if prev_frame is not None:
            norm_diff = normalized_frame_difference(prev_frame, curr_frame)
            print(f"Frame {frame_index} (Time: {frame_index // fps:.2f}s): Normalized difference = {norm_diff:.6f}")

            if norm_diff > threshold:
                print(f"Significant change detected at frame {frame_index}. Extracting text...")
                frame_path = f"frame.jpg"
                cv2.imwrite(frame_path, curr_frame)
                extracted_data = process_image(frame_path,1)

                if extracted_data is None:
                    print("⚠ No data extracted. Skipping this frame.")
                else:
                    # If extracted_data is a string, wrap it in a dictionary with a frame key
                    if isinstance(extracted_data, str):
                        extracted_data = {f"frame_{saved_frame_index}": {"text": extracted_data}}

                    print(f"Extracted Text: {extracted_data}")

                    # Merge unique data
                    complete_json = merge_unique_data(complete_json, extracted_data)

                saved_frame_index += 1

        prev_frame = curr_frame
        frame_index += frame_interval

    # Always extract last frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    ret, last_frame = cap.read()
    if ret:
        print("📌 Extracting text from the last frame of the video...")
        last_frame_path = f"frame_last.jpg"
        cv2.imwrite(last_frame_path, last_frame)
        last_extracted = process_image(last_frame_path,1)

        if last_extracted is not None:
            # If last_extracted is a string, wrap it in a dictionary with a frame key
            if isinstance(last_extracted, str):
                last_extracted = {"last_frame": {"text": last_extracted}}

            print(f"Extracted Text (last frame): {last_extracted}")

            # Merge unique data
            complete_json = merge_unique_data(complete_json, last_extracted)

    cap.release()

    # Save final result
    with open("unique_data.json", "w", encoding="utf-8") as f:
        json.dump(complete_json, f, indent=2, ensure_ascii=False)
    print("\n📝 Final unique JSON saved to unique_data.json")

    # Merge text fields and print
    merged_text = merge_text_fields(complete_json)
    print("📄 Merged Text:\n")
    print(merged_text)
    return complete_json


def correlate_audio_video(video_file: str) -> str:
    """
    Given a video file, extracts audio & video content, correlates them via GPT-4, and returns the explanation text.
    """
    video_file=f".{urlparse(video_file).path}"
    audio_file, video_file_no_audio = separate_audio_and_video(video_file)
    audio_descp = audio_to_text(audio_file)
    text_from_video = compare_video_frames(video_file_no_audio)
    prompt = f"""
You are a smart assistant. Your task is to correlate the audio transcript with the video content.

### AUDIO TRANSCRIPT:
{audio_descp}

### VIDEO CONTENT:
{json.dumps(text_from_video, indent=2)}

Explain how the audio supports the visuals, and identify direct matches or references between spoken explanation and written/drawn content in the video.
"""
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


# print("Pranav Vid:",correlate_audio_video("./sample.mp4"))