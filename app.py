from flask import Flask, request, jsonify
import cv2
import speech_recognition as sr
import arabic_reshaper
from bidi.algorithm import get_display
import mediapipe as mp
import os
from flask import Flask, render_template
app = Flask(__name__)

# Initialize MediaPipe for lip detection
mp_face_mesh = mp.solutions.face_mesh

# Speech recognition function
def recognize_speech(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="ar-AR")
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text

# Lip detection function
def detect_lips_in_frame(frame):
    with mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1) as face_mesh:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        return results.multi_face_landmarks

# Process video route
@app.route('/process-video', methods=['POST'])
def process_video():
    if 'videoFile' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    video_file = request.files['videoFile']
    video_path = os.path.join('/tmp', video_file.filename)
    video_file.save(video_path)

    # Open the video file
    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Prepare to save segments as .mov files
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    audio_segment_path = '/tmp/audio.wav'

    # Extract audio from video for speech recognition
    os.system(f"ffmpeg -i {video_path} -q:a 0 -map a {audio_segment_path}")

    # Perform speech recognition on the extracted audio
    recognized_text = recognize_speech(audio_segment_path)
    words = recognized_text.split()  # Split recognized text into individual words
    print(f"Recognized Words: {words}")

    frame_interval = fps * 5  # Define a frame interval for segmentation, e.g., every 5 seconds

    frame_index = 0
    segment_index = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_index % frame_interval == 0:
            # Detect lips
            lip_landmarks = detect_lips_in_frame(frame)
            if lip_landmarks:
                # Start saving a new segment
                segment_filename = f'/tmp/segment_{segment_index}.mov'
                out = cv2.VideoWriter(segment_filename, fourcc, fps, (frame_width, frame_height))

                # Save video frames for a duration (e.g., 5 seconds)
                for _ in range(int(frame_interval)):
                    out.write(frame)
                    ret, frame = cap.read()
                    if not ret:
                        break

                out.release()

                # Rename the segment based on the recognized word
                if segment_index < len(words):
                    word = words[segment_index]
                    renamed_segment = f'/tmp/{word}.mov'
                    os.rename(segment_filename, renamed_segment)
                    print(f"Segment saved as: {renamed_segment}")

                segment_index += 1

        frame_index += 1

    cap.release()

    return jsonify({'message': 'Video processed successfully'}), 200

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
