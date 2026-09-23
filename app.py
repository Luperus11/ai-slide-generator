import os
import glob
import re
import uuid
import textwrap
import json
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
from flask import Flask, render_template, request, jsonify
from google import genai
from pypdf import PdfReader
from docx import Document

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except (ImportError, ModuleNotFoundError):
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)

BUILD_BASE_DIR = "static/build"
os.makedirs(BUILD_BASE_DIR, exist_ok=True)

# อ่าน URL จาก Environment Variable ของ Render ถ้าไม่มีจะใช้ ngrok URL ล่าสุดจาก Colab
DEFAULT_COLAB_URL = "https://252b-34-7-7-122.ngrok-free.app/clone"
COLAB_TTS_URL = os.getenv("COLAB_TTS_URL", DEFAULT_COLAB_URL).strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

def setup_thai_font():
    thai_fonts = ['Tahoma', 'Leelawadee UI', 'Angsana New', 'Cordia New', 'TH Sarabun PSK', 'Arial']
    available_fonts = [f.name for f in font_manager.fontManager.ttflist]
    selected_font = 'sans-serif'
    for font in thai_fonts:
        if font in available_fonts:
            selected_font = font
            break
    plt.rcParams['font.family'] = selected_font
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['mathtext.fontset'] = 'cm'

setup_thai_font()

def clean_extracted_pdf_text(text):
    text = re.sub(r'---\s*หน้า\s*\d+\s*---', '', text)
    text = re.sub(r'Page\s*\d+\s*of\s*\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

def extract_text_from_file(file):
    filename = file.filename.lower()
    extracted_text = ""
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted_text += "\n" + t
        elif filename.endswith('.docx'):
            doc = Document(file)
            for para in doc.paragraphs:
                if para.text.strip():
                    extracted_text += para.text + "\n"
        elif filename.endswith('.txt'):
            extracted_text = file.read().decode('utf-8')
    except Exception as e:
        print(f"File reading error: {e}")
        
    return clean_extracted_pdf_text(extracted_text)

def generate_slides_from_gemini(topic_or_content):
    if not GEMINI_API_KEY:
        print("⚠️ Warning: ไม่พบ GEMINI_API_KEY")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        truncated_input = topic_or_content[:12000]

        prompt = f"""
        คุณคืออาจารย์มหาวิทยาลัยผู้เชี่ยวชาญ
        จงนำเนื้อหาเอกสารวิชาการต่อไปนี้ มาสกัดความรู้ สรุปสูตร คำนวณ แนวคิดหลัก และจัดทำเป็นสไลด์การสอนจำนวน 10 สไลด์เต็ม:

        === เนื้อหาเอกสารต้นฉบับ ===
        "{truncated_input}"
        ==========================

        ข้อกำหนดสำคัญมาก:
        1. ดึงสาระสำคัญ สัญลักษณ์ทางคณิตศาสตร์ สูตร และรายละเอียดจริงจากเอกสารมาใส่ ห้ามใช้คำกว้างๆ เช่น "ประเด็นสำคัญ" หรือ "รายละเอียดเนื้อหา" เด็ดขาด
        2. sub_title ให้สรุปชื่อหัวข้อย่อยสั้นๆ ไม่เกิน 6-8 คำ (ห้ามเอาเลขหน้าหรือข้อความขยะมาใส่)
        3. points ในแต่ละสไลด์ ต้องมี 4 ข้อเสมอ ในรูปแบบ "หัวข้อเน้นย้ำ: อธิบายรายละเอียดความรู้ ความหมาย หรือสูตรที่เกี่ยวข้องอย่างชัดเจน"
        4. narration ให้เขียนบทบรรยายสอนภาษาไทยแบบเป็นธรรมชาติ สรุปอธิบายสไลด์นั้นๆ อย่างกระชับ

        ตอบกลับเป็น JSON Array เท่านั้น (ห้ามใส่คำว่า ```json):
        [
          {{
            "sub_title": "1. ชื่อหัวข้อย่อยสั้นกระชับ",
            "points": [
              "คำศัพท์/หัวข้อ 1: อธิบายความหมายและรายละเอียดความรู้จริงจากเอกสาร",
              "คำศัพท์/หัวข้อ 2: อธิบายรายละเอียดความรู้จริงจากเอกสาร",
              "สูตร/แนวคิด 3: อธิบายรายละเอียดและวิธีการนำไปใช้",
              "ข้อสรุป 4: สรุปสาระสำคัญประจำสไลด์นี้"
            ],
            "narration": "บทบรรยายภาษาไทยพากย์สอนเนื้อหาสไลด์นี้"
          }}
        ]
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        raw_response = response.text.strip()
        clean_json_str = re.sub(r'^```json\s*|^```\s*|\s*```$', '', raw_response, flags=re.MULTILINE)
        slides_data = json.loads(clean_json_str)
        return slides_data
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None

def clean_text_for_speech(text):
    text = re.sub(r'^\d+\.\d*\s*', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = text.replace("$", "").replace("{", "").replace("}", "").replace("^", " กำลัง ")
    text = text.replace("_", "").replace("\\", "").replace("(", "").replace(")", "")
    text = text.replace("=", "เท่ากับ").replace("+", "บวก").replace("-", "ลบ").replace("*", "คูณ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_slide_image(topic, slide_data, slide_num, total_slides, output_path):
    fig, ax = plt.subplots(figsize=(13.33, 7.5), dpi=100)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56.25)
    ax.axis("off")

    bg = mpatches.Rectangle((0, 0), 100, 56.25, facecolor="#F8FAFC", edgecolor="#1E293B", linewidth=1.5)
    ax.add_patch(bg)

    raw_subtitle = slide_data.get("sub_title", "")
    wrapped_subtitle = textwrap.shorten(raw_subtitle, width=45, placeholder="...")
    
    ax.text(6, 51.5, f"{wrapped_subtitle}", fontsize=16, weight="bold", color="#0F172A", ha="left", va="center")
    ax.text(94, 51.5, f"{slide_num:02d}/{total_slides:02d}", fontsize=13, weight="bold", color="#64748B", ha="right", va="center")
    ax.plot([4, 96], [47, 47], color="#EA580C", linewidth=3.5)

    card = mpatches.FancyBboxPatch((4, 7.5), 92, 37.5, boxstyle="round,pad=0,rounding_size=1.2", facecolor="#FFFFFF", edgecolor="#CBD5E1")
    ax.add_patch(card)

    curr_y = 40.5
    points = slide_data.get("points", [])
    
    for pt in points:
        ax.text(7.5, curr_y, "•", fontsize=15, color="#EA580C", weight="bold", va="top")
        if ":" in pt:
            parts = pt.split(":", 1)
            title_part = parts[0].strip() + ":"
            desc_part = parts[1].strip()
            
            ax.text(10, curr_y, title_part, fontsize=11.5, color="#EA580C", weight="bold", va="top")
            wrapped_desc = textwrap.fill(desc_part, width=54)
            ax.text(32.0, curr_y, wrapped_desc, fontsize=11, color="#1E293B", va="top", linespacing=1.3)
            
            num_lines = wrapped_desc.count('\n') + 1
            curr_y -= (num_lines * 2.6) + 3.0
        else:
            wrapped_pt = textwrap.fill(pt, width=70)
            ax.text(10, curr_y, wrapped_pt, fontsize=11, color="#1E293B", va="top", linespacing=1.3)
            num_lines = wrapped_pt.count('\n') + 1
            curr_y -= (num_lines * 2.6) + 3.0

    clean_topic_footer = textwrap.shorten(topic, width=55, placeholder="...")
    ax.text(4, 2.5, clean_topic_footer, fontsize=9.5, color="#94A3B8", va="center")

    plt.savefig(output_path, bbox_inches="tight", pad_inches=0.1)
    plt.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate_video", methods=["POST"])
def generate_video():
    try:
        topic = request.form.get("topic", "").strip()
        uploaded_file = request.files.get("file")

        file_text = ""
        if uploaded_file and uploaded_file.filename != "":
            file_text = extract_text_from_file(uploaded_file)
            if not topic:
                topic = os.path.splitext(uploaded_file.filename)[0]

        if not topic and not file_text:
            return jsonify({"success": False, "error": "กรุณากรอกหัวข้อ หรืออัปโหลดไฟล์เนื้อหา"})

        user_session_id = str(uuid.uuid4())[:8]
        user_build_dir = os.path.join(BUILD_BASE_DIR, user_session_id)
        os.makedirs(user_build_dir, exist_ok=True)

        input_content = file_text if file_text else topic

        bullet_list = generate_slides_from_gemini(input_content)
        
        if not bullet_list:
            return jsonify({
                "success": False, 
                "error": "ไม่สามารถสกัดเนื้อหาด้วย Gemini ได้ กรุณาเช็ก GEMINI_API_KEY บน Render"
            })

        total_slides = len(bullet_list)
        video_clips = []

        for idx, slide_data in enumerate(bullet_list, start=1):
            img_path = os.path.join(user_build_dir, f"slide_{idx}.png")
            audio_path = os.path.join(user_build_dir, f"audio_{idx}.wav")

            generate_slide_image(topic, slide_data, idx, total_slides, img_path)

            speech_text = clean_text_for_speech(slide_data["narration"])
            headers = {"ngrok-skip-browser-warning": "69420"}
            
            tts_response = requests.post(
                COLAB_TTS_URL,
                json={"text": speech_text},
                headers=headers,
                timeout=120
            )
            
            if tts_response.status_code == 200:
                with open(audio_path, "wb") as f:
                    f.write(tts_response.content)
            else:
                raise Exception(f"TTS API Error จาก Colab: {tts_response.text}")

            audio_clip = AudioFileClip(audio_path)
            if hasattr(ImageClip(img_path), "with_duration"):
                image_clip = ImageClip(img_path).with_duration(audio_clip.duration).with_audio(audio_clip)
            else:
                image_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
                
            video_clips.append(image_clip)

        final_clip = concatenate_videoclips(video_clips, method="compose")
        output_video_path = os.path.join(user_build_dir, "final_output.mp4")
        
        final_clip.write_videofile(
            output_video_path, 
            fps=15, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast", 
            threads=4,
            logger=None
        )

        web_video_url = output_video_path.replace("\\", "/")
        return jsonify({"success": True, "video_url": f"/{web_video_url}"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
