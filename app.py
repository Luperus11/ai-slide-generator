import os
import glob
import re
import uuid
import textwrap
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
from flask import Flask, render_template, request, jsonify
from gtts import gTTS
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except (ImportError, ModuleNotFoundError):
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)

BUILD_BASE_DIR = "static/build"
os.makedirs(BUILD_BASE_DIR, exist_ok=True)

# ตั้งค่า Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

def extract_text_from_file(file):
    """อ่านเนื้อหาข้อความจากไฟล์ PDF, Word หรือ TXT"""
    filename = file.filename.lower()
    extracted_text = ""
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        elif filename.endswith('.docx'):
            doc = Document(file)
            for para in doc.paragraphs:
                extracted_text += para.text + "\n"
        elif filename.endswith('.txt'):
            extracted_text = file.read().decode('utf-8')
    except Exception as e:
        print(f"File reading error: {e}")
    return extracted_text.strip()

def generate_slides_from_gemini(topic_or_content):
    """ส่งเนื้อหาให้ Gemini AI สรุปและสร้างเป็นสไลด์ 5-10 หน้า"""
    if not GEMINI_API_KEY:
        return None

    model = genai.GenerativeModel('gemini-1.5-flash')
    truncated_input = topic_or_content[:4000]

    prompt = f"""
    คุณคือผู้เชี่ยวชาญด้านการสร้างวิดีโอสื่อการสอน
    โปรดสรุปเนื้อหาต่อไปนี้ แล้วจัดทำเป็นบทเรียนการสอนภาษาไทยจำนวน 5 ถึง 10 สไลด์:
    "{truncated_input}"

    ตอบกลับในรูปแบบ JSON Array เท่านั้น ห้ามใส่ markdown code blocks (ไม่ต้องใส่ ```json):
    [
      {{
        "sub_title": "1. ชื่อหัวข้อย่อยสไลด์",
        "points": [
          "ประเด็นสำคัญที่ 1 (สั้นกระชับ สรุปเน้นๆ)",
          "ประเด็นสำคัญที่ 2",
          "ประเด็นสำคัญที่ 3"
        ],
        "narration": "บทบรรยายพากย์เสียงพูดภาษาไทยที่เป็นธรรมชาติ อธิบายรายละเอียดเพิ่มเติมจากประเด็นบนสไลด์อย่างเข้าใจง่าย"
      }}
    ]
    """

    try:
        response = model.generate_content(prompt)
        raw_response = response.text.strip()
        clean_json_str = re.sub(r'^```json\s*|^```\s*|\s*```$', '', raw_response, flags=re.MULTILINE)
        slides_data = json.loads(clean_json_str)
        return slides_data
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None

def auto_generate_10_outline(topic):
    """กรณีไม่ได้ใช้ Gemini หรือ API Key ไม่มี ให้ใช้อุตสาหกรรมสำรอง"""
    return [
        {
            "sub_title": f"1. ความรู้เบื้องต้นเกี่ยวกับ {topic}",
            "points": [
                f"แนวคิดพื้นฐานเกี่ยวกับ {topic} ในการวิเคราะห์ระบบ",
                "การประยุกต์ใช้งานและหลักการสำคัญเบื้องต้น",
                "ทำความเข้าใจภาพรวมกระบวนการทำงาน"
            ],
            "narration": f"ยินดีต้อนรับสู่บทเรียนเกี่ยวกับ {topic} ครับ ในหัวข้อแรกนี้ เราจะมาดูแนวคิดและหลักการพื้นฐานที่สำคัญกันก่อนครับ"
        },
        {
            "sub_title": f"2. สรุปภาพรวมของ {topic}",
            "points": [
                "การประยุกต์ใช้ในทางปฏิบัติ",
                "ข้อดีและจุดเด่นที่สำคัญ",
                "ข้อควรระวังในการนำไปใช้งาน"
            ],
            "narration": f"สรุปภาพรวมทั้งหมดเกี่ยวกับ {topic} นะครับ ถือเป็นเครื่องมือที่มีประโยชน์และสำคัญมากในการศึกษาวิชาการและวิศวกรรมครับ"
        }
    ]

def clean_text_for_speech(text):
    text = re.sub(r'^\d+\.\s*', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = text.replace("$", "").replace("{", "").replace("}", "").replace("^", "")
    text = text.replace("_", "").replace("\\", "").replace("(", "").replace(")", "")
    text = text.replace("=", "เท่ากับ").replace("+", "บวก").replace("-", "ลบ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_slide_image(topic, slide_data, slide_num, total_slides, output_path):
    fig, ax = plt.subplots(figsize=(13.33, 7.5), dpi=100)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56.25)
    ax.axis("off")

    bg = mpatches.Rectangle((0, 0), 100, 56.25, facecolor="#F4F8F5", edgecolor="#1E293B", linewidth=1.5)
    ax.add_patch(bg)

    wrapped_topic = textwrap.fill(topic, width=45)
    ax.text(50, 51.5, f"{wrapped_topic} ({slide_num}/{total_slides})", fontsize=16, weight="bold", color="#0F172A", ha="center")
    ax.plot([4, 96], [47, 47], color="#EA580C", linewidth=4)

    card = mpatches.FancyBboxPatch((4, 5), 92, 39, boxstyle="round,pad=0,rounding_size=1.5", facecolor="#FFFFFF", edgecolor="#CBD5E1")
    ax.add_patch(card)

    sub_title = slide_data.get("sub_title", "")
    ax.text(8, 38, f"{sub_title}", fontsize=16, color="#EA580C", weight="bold")

    curr_y = 30
    for pt in slide_data.get("points", []):
        ax.text(10, curr_y, "•", fontsize=14, color="#EA580C", weight="bold")
        
        if "$" not in pt and len(pt) > 48:
            wrapped_pt = textwrap.fill(pt, width=48)
            ax.text(13, curr_y, wrapped_pt, fontsize=13, color="#1E293B", va="top")
            curr_y -= 8.5
        else:
            ax.text(13, curr_y, pt, fontsize=13, color="#1E293B", va="center")
            curr_y -= 7.0

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

        # รวมข้อความสำหรับสร้างสไลด์
        input_content = file_text if file_text else topic

        # ลองใช้ Gemini สร้างสไลด์ก่อน หากไม่ได้ผลค่อยใช้ตัวสำรอง
        bullet_list = generate_slides_from_gemini(input_content)
        if not bullet_list:
            bullet_list = auto_generate_10_outline(topic)

        total_slides = len(bullet_list)
        video_clips = []

        print(f"\n---> [Session {user_session_id}] เริ่มสร้างวิดีโอเรื่อง: {topic}")
        for idx, slide_data in enumerate(bullet_list, start=1):
            print(f"---> [Session {user_session_id}] กำลังประมวลผล สไลด์ {idx}/{total_slides}...")
            img_path = os.path.join(user_build_dir, f"slide_{idx}.png")
            audio_path = os.path.join(user_build_dir, f"audio_{idx}.mp3")

            generate_slide_image(topic, slide_data, idx, total_slides, img_path)

            speech_text = clean_text_for_speech(slide_data["narration"])
            tts = gTTS(text=speech_text, lang='th', slow=False)
            tts.save(audio_path)

            audio_clip = AudioFileClip(audio_path)
            if hasattr(ImageClip(img_path), "with_duration"):
                image_clip = ImageClip(img_path).with_duration(audio_clip.duration).with_audio(audio_clip)
            else:
                image_clip = ImageClip(img_path).set_duration(audio_clip.duration).set_audio(audio_clip)
                
            video_clips.append(image_clip)

        print(f"---> [Session {user_session_id}] กำลังรวมไฟล์วิดีโอ MP4...")
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
        
        print(f"---> [Session {user_session_id}] เสร็จเรียบร้อย 100%!\n")

        web_video_url = output_video_path.replace("\\", "/")
        return jsonify({"success": True, "video_url": f"/{web_video_url}"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
