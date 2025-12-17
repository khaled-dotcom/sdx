from flask import Flask, render_template, request, jsonify, send_file
import os
import time
import io
from werkzeug.utils import secure_filename
from groq import Groq
from action_recognition import ActionRecognitionSystem
from app.tts import synthesize_speech
from app.pdf_utils import extract_summary_only, build_summary_pdf

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm', 'm4v'}

# Default API keys for testing (provided)
# Default API keys were present here. For security, they are redacted.
# Always set `GROQ_API_KEY` (or `CHAT_API_KEY`) as an environment variable in production.
DEFAULT_API_KEY = '<REDACTED>'
DEFAULT_CHAT_API_KEY = '<REDACTED>'

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('reports', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_chat_client():
    """Return a Groq client for chat endpoints using provided or env key."""
    api_key = (
        os.getenv('GROQ_API_KEY')
        or os.getenv('CHAT_API_KEY')
        or DEFAULT_CHAT_API_KEY
    )
    return Groq(api_key=api_key)

def run_chat_completion(messages, model="openai/gpt-oss-120b", temperature=0.3):
    """Call Groq chat completion with safety defaults."""
    client = get_chat_client()
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=800,
        stream=False,
        top_p=1,
    )
    return completion.choices[0].message.content

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: mp4, avi, mov, mkv, flv, wmv, webm'}), 400
    
    # Use default API key or from environment
    api_key = os.getenv('GROQ_API_KEY') or DEFAULT_API_KEY
    
    # Get optional parameters
    frame_interval = int(request.form.get('frame_interval', 30))
    model = request.form.get('model') or None
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = int(time.time())
    safe_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    file.save(filepath)
    
    try:
        # Initialize action recognition system
        system = ActionRecognitionSystem(api_key, model=model)
        
        # Process video
        summary = system.process_video_file(
            video_path=filepath,
            frame_interval=frame_interval
        )
        
        if summary:
            # Save report
            report_filename = f"video_report_{timestamp}.txt"
            report_path = os.path.join('reports', report_filename)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            # Clean up uploaded video file (optional - comment out if you want to keep videos)
            # os.remove(filepath)
            
            return jsonify({
                'success': True,
                'report': summary,
                'report_file': report_filename,
                'video_file': safe_filename
            })
        else:
            return jsonify({'error': 'Failed to process video'}), 500
            
    except Exception as e:
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Error processing video: {str(e)}'}), 500

@app.route('/save_recorded_video', methods=['POST'])
def save_recorded_video():
    """Save recorded video from webcam"""
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file
        timestamp = int(time.time())
        safe_filename = f"recorded_{timestamp}.webm"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'video_file': safe_filename,
            'message': 'Video recorded and saved successfully'
        })
            
    except Exception as e:
        return jsonify({'error': f'Error saving video: {str(e)}'}), 500

@app.route('/report/<filename>')
def download_report(filename):
    report_path = os.path.join('reports', filename)
    if os.path.exists(report_path):
        return send_file(report_path, as_attachment=True)
    return jsonify({'error': 'Report not found'}), 404

@app.route('/report/pdf/<filename>')
def download_summary_pdf(filename):
    """Return a PDF containing only the executive summary (or first part) of the report."""
    report_path = os.path.join('reports', filename)
    if not os.path.exists(report_path):
        return jsonify({'error': 'Report not found'}), 404
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()
        summary = extract_summary_only(report_text)
        pdf_bytes = build_summary_pdf(summary, title=f"Summary for {filename}")
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{os.path.splitext(filename)[0]}_summary.pdf"
        )
    except Exception as e:
        return jsonify({'error': f'Could not generate PDF: {str(e)}'}), 500

@app.route('/reports/list', methods=['GET'])
def list_reports():
    """Return available report filenames for chat selection."""
    try:
        files = []
        for name in os.listdir('reports'):
            if name.lower().endswith('.txt'):
                files.append(name)
        # Sort newest first
        files.sort(reverse=True)
        return jsonify({'success': True, 'reports': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/chat/report', methods=['POST'])
def chat_about_report():
    """Chatbot that answers questions about a selected video report."""
    data = request.get_json(force=True, silent=True) or {}
    user_message = (data.get('message') or '').strip()
    report_file = data.get('report_file')

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    report_text = ""
    if report_file:
        report_path = os.path.join('reports', report_file)
        if not os.path.exists(report_path):
            return jsonify({'error': 'Report file not found'}), 404
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_text = f.read()
        except Exception as e:
            return jsonify({'error': f'Could not read report: {str(e)}'}), 500

    system_prompt = (
        "You are a precise assistant that answers questions about video analysis reports. "
        "Use the provided report content to answer. If the question is outside the report, "
        "say you only know what is in the report. Keep answers concise and actionable."
    )

    messages = [{"role": "system", "content": system_prompt}]
    if report_text:
        messages.append({"role": "user", "content": f"Here is the report to use:\n\n{report_text}"})
    messages.append({"role": "user", "content": user_message})

    try:
        response = run_chat_completion(messages)
        return jsonify({'success': True, 'reply': response})
    except Exception as e:
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500

@app.route('/chat/project', methods=['POST'])
def chat_about_project():
    """Chatbot that answers how to use the project and workflow questions."""
    data = request.get_json(force=True, silent=True) or {}
    user_message = (data.get('message') or '').strip()

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    system_prompt = (
        "You are the product guide for the AI Action Recognition System (Flask web app). "
        "Explain how to upload or record videos, frame interval meaning, allowed formats, "
        "how reports are saved, and troubleshooting basics. Be concise, step-by-step when helpful. "
        "If you do not know something, say so briefly."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        response = run_chat_completion(messages)
        return jsonify({'success': True, 'reply': response})
    except Exception as e:
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500

@app.route('/tts', methods=['POST'])
def text_to_speech():
    """Return speech audio for given text (wav)."""
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    try:
        api_key = (
            os.getenv('GROQ_API_KEY')
            or os.getenv('CHAT_API_KEY')
            or DEFAULT_CHAT_API_KEY
        )
        audio_bytes = synthesize_speech(text, api_key=api_key)
        return send_file(
            io.BytesIO(audio_bytes),
            mimetype='audio/wav',
            as_attachment=False,
            download_name='speech.wav'
        )
    except Exception as e:
        return jsonify({'error': f'TTS failed: {str(e)}'}), 400

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Action Recognition Web Server")
    print("="*60)
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Max file size: {app.config['MAX_CONTENT_LENGTH'] / (1024*1024):.0f}MB")
    print(f"Allowed formats: {', '.join(app.config['ALLOWED_EXTENSIONS'])}")
    print("\nStarting server on http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)

