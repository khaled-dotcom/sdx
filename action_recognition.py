import cv2
import base64
import time
from groq import Groq
import argparse
import os
from pathlib import Path

class ActionRecognitionSystem:
    def __init__(self, api_key, model=None):
        """Initialize the Groq client with API key"""
        self.client = Groq(api_key=api_key)
        # Use user's model or default to a working model
        # Try: meta-llama/llama-4-scout-17b-16e-instruct (user's original) or llama-3.1-70b-versatile
        self.model = model or "meta-llama/llama-4-scout-17b-16e-instruct"
        
    def frame_to_base64(self, frame):
        """Convert OpenCV frame to base64 string"""
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        return frame_base64
    
    def analyze_frame(self, frame_base64, frame_number, total_frames=None):
        """Send frame to Groq API for analysis"""
        progress = f" ({frame_number}/{total_frames})" if total_frames else f" (Frame {frame_number})"
        
        prompt = f"""Analyze this video frame and describe:
1. What actions or activities are visible
2. Who or what is in the frame
3. Any notable movements or gestures
4. The context or setting

Frame{progress}:"""
        
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_base64}"
                            }
                        }
                    ]
                }
            ]
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_completion_tokens=512,
                top_p=1,
                stream=False
            )
            
            return completion.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "vision" in error_msg.lower() or "image" in error_msg.lower():
                return f"Error: Model '{self.model}' may not support vision. Try using --model llama-3.2-11b-vision-preview"
            return f"Error analyzing frame: {error_msg}"
    
    def process_video_file(self, video_path, frame_interval=30):
        """Process a recorded video file"""
        print(f"\n[VIDEO] Processing video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"[ERROR] Could not open video file {video_path}")
            return None
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"[INFO] Video Info: {total_frames} frames, {fps} FPS, {duration:.2f} seconds")
        print(f"[INFO] Analyzing every {frame_interval} frames...\n")
        
        frame_analyses = []
        frame_count = 0
        analyzed_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Analyze every Nth frame
            if frame_count % frame_interval == 0:
                print(f"[ANALYZING] Frame {frame_count}...", end=" ", flush=True)
                frame_base64 = self.frame_to_base64(frame)
                analysis = self.analyze_frame(frame_base64, frame_count, total_frames)
                frame_analyses.append({
                    'frame': frame_count,
                    'time': frame_count / fps if fps > 0 else 0,
                    'analysis': analysis
                })
                print("[OK]")
                analyzed_count += 1
                time.sleep(0.5)  # Rate limiting
            
            frame_count += 1
        
        cap.release()
        return self.generate_summary(frame_analyses, duration)
    
    def process_live_video(self, frame_interval=30, duration_seconds=30):
        """Process live video from webcam"""
        print(f"\n[LIVE] Starting live video capture...")
        print(f"[INFO] Will capture for {duration_seconds} seconds")
        print(f"[INFO] Analyzing every {frame_interval} frames...")
        print("Press 'q' to stop early\n")
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("[ERROR] Could not open webcam")
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        frame_analyses = []
        frame_count = 0
        analyzed_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Show live preview
            cv2.imshow('Action Recognition - Press Q to quit', frame)
            
            # Check if duration exceeded or 'q' pressed
            elapsed = time.time() - start_time
            if elapsed >= duration_seconds:
                break
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Analyze every Nth frame
            if frame_count % frame_interval == 0:
                print(f"[ANALYZING] Frame {frame_count} (Time: {elapsed:.1f}s)...", end=" ", flush=True)
                frame_base64 = self.frame_to_base64(frame)
                analysis = self.analyze_frame(frame_base64, frame_count)
                frame_analyses.append({
                    'frame': frame_count,
                    'time': elapsed,
                    'analysis': analysis
                })
                print("[OK]")
                analyzed_count += 1
                time.sleep(0.5)  # Rate limiting
            
            frame_count += 1
        
        cap.release()
        cv2.destroyAllWindows()
        
        return self.generate_summary(frame_analyses, elapsed)
    
    def generate_summary(self, frame_analyses, duration):
        """Generate final summary report from all frame analyses"""
        if not frame_analyses:
            return "No frames were analyzed."
        
        print("\n[SUMMARY] Generating final summary report...\n")
        
        # Combine all analyses
        combined_analysis = "\n\n".join([
            f"[Frame {fa['frame']} at {fa['time']:.1f}s]: {fa['analysis']}"
            for fa in frame_analyses
        ])
        
        summary_prompt = f"""Based on the following frame-by-frame analysis of a video ({duration:.1f} seconds), create a comprehensive summary report:

{combined_analysis}

Please provide:
1. Overall summary of the actions and activities observed
2. Key moments and notable events
3. Description of participants/objects
4. Timeline of main activities
5. Any patterns or trends noticed

Format as a clear, structured report."""
        
        try:
            # Try with the current model first
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": summary_prompt
                    }
                ],
                temperature=0.7,
                max_completion_tokens=1024,
                top_p=1,
                stream=True
            )
            
            summary = ""
            print("=" * 60)
            print("FINAL VIDEO REPORT")
            print("=" * 60)
            for chunk in completion:
                content = chunk.choices[0].delta.content or ""
                summary += content
                print(content, end="", flush=True)
            print("\n" + "=" * 60 + "\n")
            
            # Generate concise summary at the end
            print("[SUMMARY] Generating executive summary...\n")
            summary_prompt_final = f"""Based on the following comprehensive video analysis report, create a brief executive summary (2-3 sentences) that captures the most important points:

{summary}

Provide a concise summary that highlights:
- Main activities and actions
- Key participants or objects
- Most notable events or moments

Keep it brief and to the point."""
            
            try:
                final_summary_completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": summary_prompt_final
                        }
                    ],
                    temperature=0.7,
                    max_completion_tokens=256,
                    top_p=1,
                    stream=False
                )
                
                final_summary = final_summary_completion.choices[0].message.content
                
                # Append summary to the report
                summary += "\n\n" + "=" * 60 + "\n"
                summary += "EXECUTIVE SUMMARY\n"
                summary += "=" * 60 + "\n\n"
                summary += final_summary
                summary += "\n\n" + "=" * 60 + "\n"
                
                print("=" * 60)
                print("EXECUTIVE SUMMARY")
                print("=" * 60)
                print(final_summary)
                print("=" * 60 + "\n")
                
            except Exception as e:
                # If summary generation fails, just return the main report
                print(f"[WARNING] Could not generate executive summary: {str(e)}")
                summary += "\n\n" + "=" * 60 + "\n"
                summary += "EXECUTIVE SUMMARY\n"
                summary += "=" * 60 + "\n\n"
                summary += "Summary generation unavailable. Please refer to the detailed report above."
                summary += "\n\n" + "=" * 60 + "\n"
            
            return summary
        except Exception as e:
            error_msg = str(e)
            # If model is decommissioned, try alternative models
            if "decommissioned" in error_msg.lower() or "no longer supported" in error_msg.lower():
                print(f"[WARNING] Model {self.model} is decommissioned. Trying alternative model...")
                try:
                    # Try with a different model for summary
                    alt_model = "llama-3.1-70b-versatile"
                    completion = self.client.chat.completions.create(
                        model=alt_model,
                        messages=[
                            {
                                "role": "user",
                                "content": summary_prompt
                            }
                        ],
                        temperature=0.7,
                        max_completion_tokens=1024,
                        top_p=1,
                        stream=True
                    )
                    
                    summary = ""
                    print("=" * 60)
                    print("FINAL VIDEO REPORT")
                    print("=" * 60)
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        summary += content
                        print(content, end="", flush=True)
                    print("\n" + "=" * 60 + "\n")
                    
                    # Generate concise summary at the end
                    print("[SUMMARY] Generating executive summary...\n")
                    summary_prompt_final = f"""Based on the following comprehensive video analysis report, create a brief executive summary (2-3 sentences) that captures the most important points:

{summary}

Provide a concise summary that highlights:
- Main activities and actions
- Key participants or objects
- Most notable events or moments

Keep it brief and to the point."""
                    
                    try:
                        final_summary_completion = self.client.chat.completions.create(
                            model=alt_model,
                            messages=[
                                {
                                    "role": "user",
                                    "content": summary_prompt_final
                                }
                            ],
                            temperature=0.7,
                            max_completion_tokens=256,
                            top_p=1,
                            stream=False
                        )
                        
                        final_summary = final_summary_completion.choices[0].message.content
                        
                        # Append summary to the report
                        summary += "\n\n" + "=" * 60 + "\n"
                        summary += "EXECUTIVE SUMMARY\n"
                        summary += "=" * 60 + "\n\n"
                        summary += final_summary
                        summary += "\n\n" + "=" * 60 + "\n"
                        
                        print("=" * 60)
                        print("EXECUTIVE SUMMARY")
                        print("=" * 60)
                        print(final_summary)
                        print("=" * 60 + "\n")
                        
                    except Exception as e:
                        # If summary generation fails, just return the main report
                        print(f"[WARNING] Could not generate executive summary: {str(e)}")
                        summary += "\n\n" + "=" * 60 + "\n"
                        summary += "EXECUTIVE SUMMARY\n"
                        summary += "=" * 60 + "\n\n"
                        summary += "Summary generation unavailable. Please refer to the detailed report above."
                        summary += "\n\n" + "=" * 60 + "\n"
                    
                    return summary
                except Exception as e2:
                    return f"Error generating summary with alternative model: {str(e2)}"
            return f"Error generating summary: {error_msg}"

def main():
    parser = argparse.ArgumentParser(description='Action Recognition System using Groq Vision API')
    parser.add_argument('--mode', choices=['live', 'file'], default='live',
                        help='Mode: live (webcam) or file (recorded video)')
    parser.add_argument('--video', type=str, default=None,
                        help='Path to video file (required for file mode)')
    parser.add_argument('--api-key', type=str, default=None,
                        help='Groq API key (or set GROQ_API_KEY environment variable)')
    parser.add_argument('--interval', type=int, default=30,
                        help='Frame interval for analysis (analyze every N frames)')
    parser.add_argument('--duration', type=int, default=30,
                        help='Duration in seconds for live mode')
    parser.add_argument('--model', type=str, default=None,
                        help='Groq model to use (default: meta-llama/llama-4-scout-17b-16e-instruct)')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.getenv('GROQ_API_KEY')
    if not api_key:
        print("[ERROR] API key required!")
        print("   Set it via --api-key argument or GROQ_API_KEY environment variable")
        return
    
    # Initialize system
    system = ActionRecognitionSystem(api_key, model=args.model)
    
    # Process based on mode
    if args.mode == 'live':
        summary = system.process_live_video(
            frame_interval=args.interval,
            duration_seconds=args.duration
        )
    else:
        if not args.video:
            print("[ERROR] --video path required for file mode")
            return
        
        if not os.path.exists(args.video):
            print(f"[ERROR] Video file not found: {args.video}")
            return
        
        summary = system.process_video_file(
            video_path=args.video,
            frame_interval=args.interval
        )
    
    # Save report to file
    if summary:
        report_file = f"video_report_{int(time.time())}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"[SAVED] Report saved to: {report_file}")

if __name__ == "__main__":
    main()

