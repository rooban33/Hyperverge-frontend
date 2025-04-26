import openai
import base64
from openai import OpenAI
from urllib.parse import urlparse
import re
import json

# Replace this with your actual OpenAI API key
api_key = "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"

def extract_json(text):
    # Try to extract JSON wrapped in ```json ... ```
    match = re.search(r'```json\s*(.*?)```', text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Otherwise assume the entire string is the JSON
        json_str = text

    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        return None
    
def generate_summary(data):
    summary = f"Text content in the image: {data['text'] or 'None'}.\n"
    summary += f"A small description of the image: {data['image_description']}.\n"
    summary += "And contents found in the image are:\n"

    for diagram, details in data['diagrams_or_objects'].items():
        summary += f"- {diagram}: {details['description']}\n"
        summary += f"  Contents: {', '.join(details['contents'])}\n"

    return summary

def process_image(image_path):
  # --- Read and encode the image ---
  with open(f".{urlparse(image_path).path}", "rb") as img_file:
      image_bytes = img_file.read()
      encoded_image = base64.b64encode(image_bytes).decode("utf-8")

  # --- Initialize client ---
  client = OpenAI(api_key=api_key)

  # --- Prompt for full visual understanding with image description ---
  prompt = """
  You are a vision model. Process this image and return a structured JSON with:

  1. "text": All the visible standalone text in the image.
  2. "image_description": A brief description of the overall image. What is this image about? Summarize its content.
  3. "diagrams_or_objects": A dictionary where:
    - The key is the name of each diagram or visual object (e.g., "Flowchart", "Pie Chart", "Network Diagram").
    - The value is another dictionary with:
        - "description": A brief description of the diagram/object.
        - "contents": Texts or elements found **inside** that diagram (e.g., labeled parts, titles, arrows, steps).

  Example output format:
  {
    "text": "Full image text here...",
    "image_description": "A flowchart representing a login process",
    "diagrams_or_objects": {
      "Flowchart": {
        "description": "A flowchart representing a login process.",
        "contents": ["Start", "Enter username", "Validate credentials", "Login successful"]
      },
      "Pie Chart": {
        "description": "A pie chart showing market share.",
        "contents": ["Apple 40%", "Samsung 30%", "Others 30%"]
      }
    }
  }
  """

  # --- Call OpenAI API ---
  response = client.chat.completions.create(
      model="gpt-4o",  # Use gpt-4o or gpt-4o-mini
      messages=[
          {
              "role": "user",
              "content": [
                  {"type": "text", "text": prompt},
                  {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}},
              ],
          }
      ]
  )

  # --- Display the structured result ---
  js = extract_json(response.choices[0].message.content)
  final_text = generate_summary(js)
  return final_text

#print(process_image(image_path))
