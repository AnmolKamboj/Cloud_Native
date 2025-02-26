import os
from flask import Flask, render_template, request, redirect, url_for, Response
from google.cloud import storage
import google.generativeai as genai
import json
import io

app = Flask(__name__)

# Google Cloud Storage configuration
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
if not BUCKET_NAME:
    raise ValueError("GCS_BUCKET_NAME environment variable is not set")
client = storage.Client()

# Configure Gemini API
genai.configure(api_key=os.environ['GEMINI_API'])

model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# Define the prompt
PROMPT = """Describe the image in detail. Provide a title and a description. 
Format your response as a JSON object with the following structure:
{
  "title": "Generated Title",
  "description": "Generated Description"
}"""

def generate_image_description(image_path, mime_type):
    """Generates a description for the image using Gemini API."""
    try:
        print("Calling Gemini API...")
        # Read the image file as binary data
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        # Generate content using the image data and the prompt
        response = model.generate_content(
            [{"mime_type": mime_type, "data": image_data}, PROMPT]
        )
        print("Gemini API Response (Raw):", response.text) 

        # Remove the triple backticks and "json" marker from the response
        cleaned_response = response.text.strip().strip("```json").strip("```").strip()
        print("Cleaned Response:", cleaned_response) 

        # Parse the cleaned response as JSON
        description_data = json.loads(cleaned_response)
        print("Parsed JSON:", description_data) 

        return json.dumps(description_data, indent=4)  # Return pretty-printed JSON
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("Raw Response:", response.text)  # Debug: Print the raw response if JSON parsing fails
        return None
    except Exception as e:
        print(f"Error generating description: {e}")
        return None

def save_description_to_gcs(bucket_name, image_name, description):
    """Saves the description as a JSON file in the same GCS bucket."""
    try:
        print(f"Saving description for {image_name}...")
        bucket = client.bucket(bucket_name)
        json_blob = bucket.blob(f"{image_name}.json")
        json_blob.upload_from_string(description)
        print(f"Saved description to {image_name}.json")
    except Exception as e:
        print(f"Error saving description to GCS: {e}")

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        # Handle file upload
        file = request.files["image"]
        if file:
            # Generate a unique filename
            filename = file.filename
            temp_path = f"/tmp/{filename}"
            file.save(temp_path)

            # Upload the file to Google Cloud Storage
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(filename)
            blob.upload_from_filename(temp_path)

            # Generate description using Gemini API
            description = generate_image_description(temp_path, file.mimetype)
            if description:
                save_description_to_gcs(BUCKET_NAME, filename, description)

            # Clean up the temporary file
            os.remove(temp_path)

            return redirect(url_for("home"))

    # List existing files in the bucket
    bucket = client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs()
    images = [blob.name for blob in blobs]

    return render_template("homepage.html", images=images, BUCKET_NAME=BUCKET_NAME)

@app.route("/view_image/<filename>")
def view_image(filename):
    """Route to view the image with its title and description."""
    bucket = client.bucket(BUCKET_NAME)
    json_blob = bucket.blob(f"{filename}.json")
    
    if json_blob.exists():
        description = json_blob.download_as_text()
        try:
            description_data = json.loads(description)
        except json.JSONDecodeError:
            description_data = {"title": "Untitled", "description": "No description available."}
    else:
        description_data = {"title": "Untitled", "description": "No description available."}

    # Serve the image directly from GCS
    image_blob = bucket.blob(filename)
    image_data = image_blob.download_as_bytes()
    image_url = f"/images/{filename}"

    return render_template("view_image.html", image_url=image_url, title=description_data["title"], description=description_data["description"])

@app.route("/images/<filename>")
def get_image(filename):
    """Route to serve images directly from GCS."""
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    file_data = blob.download_as_bytes()
    return Response(io.BytesIO(file_data), mimetype='image/jpeg')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
