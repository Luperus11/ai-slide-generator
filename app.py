import os
import glob
import re
import uuid
import textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager
from flask import Flask, render_template, request, jsonify
from gtts import gTTS

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except (ImportError, ModuleNotFoundError):
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)

BUILD_BASE_DIR = "static/build"
os.makedirs(BUILD_BASE_DIR, exist_ok=True)

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

def auto_generate_10_outline(topic):
    """
    สร้างสไลด์โดยแยกส่วน:
    - points: ข้อความสรุปสั้นๆ บนหน้าจอ
    - narration: บทพากย์เสียงอธิบายละเอียด เป็นธรรมชาติ
    """
    return [
        {
            "sub_title": "1. ความรู้เบื้องต้นและนิยาม",
            "points": [
                f"แนวคิดพื้นฐานเกี่ยวกับ {topic} ในการวิเคราะห์ระบบ",
                "การเปลี่ยนโดเมนจากโดเมนเวลา (t) ไปสู่โดเมนความถี่เชิงซ้อน (s)",
                "ช่วยเปลี่ยนสมการเชิงอนุพันธ์ให้เป็นสมการพีชคณิตที่คำนวณง่ายขึ้น"
            ],
            "narration": f"ยินดีต้อนรับสู่บทเรียนเกี่ยวกับ {topic} ครับ ในหัวข้อแรกนี้ เราจะมาดูแนวคิดพื้นฐานกันก่อน "
                         f"จุดประสงค์หลักคือการแปลงสัญญาณหรือระบบจากโดเมนเวลา ให้อยู่ในโดเมนความถี่เชิงซ้อน s "
                         f"ซึ่งประโยชน์ที่สำคัญมาก คือการช่วยเปลี่ยนสมการเชิงอนุพันธ์ที่ซับซ้อน ให้กลายเป็นสมการพีชคณิตธรรมดาที่แก้ไขได้ง่ายขึ้นเยอะเลยครับ"
        },
        {
            "sub_title": "2. สมการนิยามและการลู่เข้า",
            "points": [
                "สูตรนิยามหลัก: $F(s) = \\mathcal{L}\\{f(t)\\} = \\int_{0}^{\\infty} f(t) e^{-st} dt$",
                "เงื่อนไขการคงอยู่และการลู่เข้าของสัญญาณ (Region of Convergence)",
                "ตัวแปรเชิงซ้อน $s = \\sigma + j\\omega$ ที่ใช้ในระบบ"
            ],
            "narration": "ถัดมาในส่วนของสมการนิยาม ตัวฟังก์ชัน F(s) จะหาได้จากการอินทิเกรต f(t) คูณกับ e ยกกำลังลบ st ตั้งแต่ศูนย์ถึงอินฟินิตี้ครับ "
                         "และสิ่งสำคัญที่ต้องพิจารณาคู่กันเสมอคือ ขอบเขตการลู่เข้า หรือ ROC เพื่อให้มั่นใจว่าอินทิกรัลนี้หาค่าได้จริง "
                         "โดยตัวแปร s นั้นจะเป็นตัวแปรเชิงซ้อนที่มีทั้งส่วนจริง ซิกมา และส่วนจินตภาพ เจโอเมกา ครับ"
        },
        {
            "sub_title": "3. คุณสมบัติพื้นฐานที่สำคัญ",
            "points": [
                "คุณสมบัติเชิงเส้น (Linearity): $\\mathcal{L}\\{af(t)+bg(t)\\} = aF(s)+bG(s)$",
                "การเลื่อนในโดเมนเวลา (Time Shifting): $\\mathcal{L}\\{f(t-a)u(t-a)\\} = e^{-as}F(s)$",
                "การคูณด้วยฟังก์ชันเอ็กโปเนนเชียล: $\\mathcal{L}\\{e^{at}f(t)\\} = F(s-a)$"
            ],
            "narration": "มาดูคุณสมบัติพื้นฐานที่ช่วยให้เราคำนวณได้เร็วขึ้นกันครับ ข้อแรกคือคุณสมบัติเชิงเส้น ที่เราสามารถดึงค่าคงค้างูออกมาคูณข้างนอกได้เลย "
                         "ข้อสองคือการเลื่อนในโดเมนเวลา หากสัญญาณมีความหน่วงเวลาไป a หน่วย จะเทียบเท่ากับการคูณ e ยกกำลังลบ as ในโดเมน s "
                         "และถ้ามีการคูณด้วยเอ็กโปเนนเชียล ก็จะเป็นการเลื่อนแกน s ไปทางขวาหรือซ้ายตามค่าคงที่นั้นครับ"
        },
        {
            "sub_title": "4. การแปลงอนุพันธ์และอินทิเกรต",
            "points": [
                "อนุพันธ์อันดับหนึ่ง: $\\mathcal{L}\\{f'(t)\\} = sF(s) - f(0)$",
                "อนุพันธ์อันดับสอง: $\\mathcal{L}\\{f''(t)\\} = s^2F(s) - sf(0) - f'(0)$",
                "รองรับการใส่เงื่อนไขเริ่มต้น (Initial Conditions) ของระบบ"
            ],
            "narration": "หัวข้อนี้ถือเป็นหัวใจสำคัญในการแก้สมการดิฟเลยครับ เมื่อเราแปลงอนุพันธ์อันดับหนึ่ง ผลลัพธ์จะได้เป็น s คูณ F(s) ลบด้วยเงื่อนไขเริ่มต้น f(0) "
                         "และถ้าเป็นอนุพันธ์อันดับสอง ก็จะเป็น s กำลังสอง คูณ F(s) แล้วลบด้วยเงื่อนไขเริ่มต้นถัดๆ ไป "
                         "ทำให้การคิดเงื่อนไขเริ่มต้นของระบบทำได้ง่ายและเป็นระบบมากครับ"
        },
        {
            "sub_title": "5. ฟังก์ชันมาตรฐานที่ใช้บ่อย",
            "points": [
                "ฟังก์ชันขั้นบันได (Unit Step): $\\mathcal{L}\\{u(t)\\} = \\frac{1}{s}$",
                "ฟังก์ชันเอ็กโปเนนเชียล: $\\mathcal{L}\\{e^{at}\\} = \\frac{1}{s-a}$",
                "ฟังก์ชันไซน์และโคไซน์: $\\mathcal{L}\\{\\sin(\\omega t)\\} = \\frac{\\omega}{s^2+\\omega^2}$"
            ],
            "narration": "ในการใช้งานจริง เราไม่จำเป็นต้องอินทิเกรตใหม่ทุกครั้งครับ เพราะมีตารางตารางการแปลงมาตรฐานให้ใช้อยู่แล้ว "
                         "เช่น ฟังก์ชันขั้นบันได u(t) แปลงได้ 1 ส่วน s, ฟังก์ชันเอ็กโปเนนเชียล ได้ 1 ส่วน s ลบ a "
                         "รวมถึงฟังก์ชันคลื่นไซน์และโคไซน์ ที่เรานำค่าความถี่ โอเมกา ไปใช้ในสูตรสำเร็จได้ทันทีครับ"
        },
        {
            "sub_title": "6. การแปลงกลับ (Inverse Transform)",
            "points": [
                "การหาผลเฉลยย้อนกลับสู่โดเมนเวลา $f(t) = \\mathcal{L}^{-1}\\{F(s)\\}$",
                "เทคนิคการแยกเป็นเศษส่วนย่อย (Partial Fraction Expansion)",
                "การพิจารณากรณีรากจริง รากซ้ำ และรากเชิงซ้อน"
            ],
            "narration": "หลังจากที่เราคำนวณในโดเมน s เสร็จแล้ว ขั้นตอนสุดท้ายคือการหาคำตอบกลับมายังโดเมนเวลาด้วยการแปลงกลับครับ "
                         "เครื่องมือหลักที่เรามักใช้คือการแยกสมการออกเป็นเศษส่วนย่อย "
                         "ซึ่งต้องแยกคิดตามลักษณะรากของตัวส่วน ว่าเป็นรากจริงที่ไม่ซ้ำกัน รากซ้ำ หรือรากที่เป็นจำนวนเชิงซ้อนครับ"
        },
        {
            "sub_title": "7. การประยุกต์ใช้กับวงจรไฟฟ้า",
            "points": [
                "แบบจำลองอิมพีแดนซ์: $Z_R = R, \\, Z_L = sL, \\, Z_C = \\frac{1}{sC}$",
                "วิเคราะห์ตอบสนองชั่วครู่ (Transient Response) ในวงจร RLC",
                "การคำนวณหาแรงดันและกระแสไฟฟ้าในสภาวะต่างๆ"
            ],
            "narration": "ลองมาดูการประยุกต์ใช้ในงานจริงกันบ้างครับ ในงานวิศวกรรมไฟฟ้า เราจะเปลี่ยนอุปกรณ์วงจรให้กลายเป็นอิมพีแดนซ์ในโดเมน s "
                         "โดย ตัวต้านทาน R จะคงเดิม ตัวเหนี่ยวนำ L กลายเป็น sL และตัวเก็บประจุ C กลายเป็น 1 ส่วน sC "
                         "ช่วยให้เราวิเคราะห์พฤติกรรมชั่วครู่ของวงจร RLC และหาแรงดันกระแสได้ง่ายขึ้นมากครับ"
        },
        {
            "sub_title": "8. การวิเคราะห์ระบบควบคุม",
            "points": [
                "ฟังก์ชันถ่ายโอน (Transfer Function): $H(s) = \\frac{Y(s)}{X(s)}$",
                "การหาตำแหน่งจุดโพล (Poles) และซีโร่ (Zeros)",
                "การประเมินความเสถียรของระบบจากตำแหน่งโพลบน s-plane"
            ],
            "narration": "ในทางระบบควบคุม ตัวแปลงนี้ใช้สร้างฟังก์ชันถ่ายโอน H(s) ซึ่งเป็นอัตราส่วนระหว่างสัญญาณเอาต์พุตต่ออินพุต "
                         "เราสามารถหาจุดโพลและซีโร่ของระบบ เพื่อนำมาพล็อตลงบน s-plane "
                         "และใช้บอกได้ทันทีเลยว่าระบบควบคุมของเรามีเสถียรภาพหรือไม่ครับ"
        },
        {
            "sub_title": "9. เทคนิคและข้อควรระวังในการแก้ปัญหา",
            "points": [
                "ตรวจสอบเงื่อนไขเริ่มต้นก่อนจัดรูปสมการเสมอ",
                "ระวังเรื่องขอบเขตการลู่เข้าเมื่อทำการแปลงกลับ",
                "ตรวจสอบมิติและหน่วยของตัวแปรในโดเมนความถี่"
            ],
            "narration": "ข้อควรระวังสำคัญเวลาทำโจทย์หรือใช้งานจริงครับ อันดับแรก ต้องตรวจสอบค่าเงื่อนไขเริ่มต้นให้ดี "
                         "อันดับที่สอง ต้องแน่ใจว่าผลลัพธ์อยู่ในขอบเขตการลู่เข้าที่ถูกต้อง "
                         "และอย่าลืมเช็กมิติหรือหน่วยของตัวแปรในโดเมนความถี่ เพื่อป้องกันข้อผิดพลาดในการคำนวณครับ"
        },
        {
            "sub_title": "10. สรุปภาพรวมการใช้งาน",
            "points": [
                f"{topic} ช่วยลดความซับซ้อนของการคำนวณทางคณิตศาสตร์",
                "เปลี่ยนโจทย์อนุพันธ์ที่ซับซ้อนให้เป็นการแก้สมการพีชคณิต",
                "เป็นเครื่องมือสำคัญในงานวิศวกรรมไฟฟ้า ควบคุม และระบบสัญญาณ"
            ],
            "narration": f"สรุปภาพรวมทั้งหมดเกี่ยวกับ {topic} นะครับ ถือเป็นเครื่องมือทางคณิตศาสตร์ที่มีพลังและสำคัญมากในงานวิศวกรรม "
                         f"เพราะช่วยแปลงงานยากๆ อย่างสมการเชิงอนุพันธ์ ให้กลายเป็นสมการพีชคณิตเบสิก "
                         f"เหมาะสำหรับนำไปประยุกต์ใช้ในระบบไฟฟ้าระบบควบคุม และการประมวลผลสัญญาณต่างๆ ครับ"
        }
    ]

def clean_text_for_speech(text):
    """ทำความสะอาดบทบรรยาย เพื่อให้เสียงอ่านพากย์ราบรื่นไม่มีสะดุด"""
    # ลบตัวเลขหัวข้อ เช่น "1. " ออก
    text = re.sub(r'^\d+\.\s*', '', text)
    # ลบสัญลักษณ์คณิตศาสตร์/LaTeX ออกคงเหลือคำอ่านภาษาไทย
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
    data = request.json
    topic = data.get("topic", "การแปลงลาปลาซ")

    user_session_id = str(uuid.uuid4())[:8]
    user_build_dir = os.path.join(BUILD_BASE_DIR, user_session_id)
    os.makedirs(user_build_dir, exist_ok=True)

    bullet_list = auto_generate_10_outline(topic)

    total_slides = len(bullet_list)
    video_clips = []

    print(f"\n---> [Session {user_session_id}] เริ่มสร้างวิดีโอเรื่อง: {topic}")
    for idx, slide_data in enumerate(bullet_list, start=1):
        print(f"---> [Session {user_session_id}] กำลังประมวลผล สไลด์ {idx}/10...")
        img_path = os.path.join(user_build_dir, f"slide_{idx}.png")
        audio_path = os.path.join(user_build_dir, f"audio_{idx}.mp3")

        # 1. วาดรูปภาพสไลด์เฉพาะส่วน points
        generate_slide_image(topic, slide_data, idx, total_slides, img_path)

        # 2. ดึงบทบรรยายภาษาไทยเชิงลึก (Narration) ไปทำเสียงพากย์
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)