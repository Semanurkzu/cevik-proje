from gtts import gTTS
import requests
import os
import sqlite3

from flask import Flask, render_template, request
from google import genai

from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    TextClip,
    CompositeVideoClip
)

uygulama = Flask(__name__)

# =========================
# API KEYS
# =========================
GEMINI_API_KEY = "AIzaSyAtpL4k8WFeMPEYmx3oLuKi_KxnrMcNK6s"
STABILITY_API_KEY = "sk-IsTyXqPswwgEJguGjw9hydDa6TGy7XYgf7kYyFgFrAEj6tLS"

client = genai.Client(api_key=GEMINI_API_KEY)


# =========================
# DB KAYIT
# =========================
def db_kaydet(hikaye, tur, konu, karakter):
    conn = sqlite3.connect("hikaye.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hikayeler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu TEXT,
            tur TEXT,
            karakter TEXT,
            hikaye TEXT
        )
    """)

    cursor.execute(
        "INSERT INTO hikayeler (konu, tur, karakter, hikaye) VALUES (?, ?, ?, ?)",
        (konu, tur, karakter, hikaye)
    )

    conn.commit()
    conn.close()


# =========================
# SAHNE AYIKLAMA
# =========================
def sahneleri_ayikla(metin):
    satirlar = metin.split("\n")
    sahneler = []

    for s in satirlar:
        s = s.strip()
        if s.lower().startswith("sahne"):
            if ":" in s:
                sahne = s.split(":", 1)[1].strip()
                sahneler.append(sahne)

    return sahneler


# =========================
# GÖRSEL ÜRET (STABILITY)
# =========================
def goruntu_uret(prompt, ad):
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"

    response = requests.post(
        url,
        headers={
            "authorization": f"Bearer {STABILITY_API_KEY}",
            "accept": "image/*"
        },
        data={
            "prompt": prompt,
            "output_format": "png"
        },
        files={"none": ""}
    )

    os.makedirs("static", exist_ok=True)

    if response.status_code == 200:
        with open(f"static/{ad}.png", "wb") as f:
            f.write(response.content)
    else:
        raise Exception("Stability API Hatası: " + response.text)


# =========================
# SES ÜRET
# =========================
def ses_uret(metin):
    tts = gTTS(text=metin, lang="tr")
    os.makedirs("static", exist_ok=True)
    tts.save("static/ses.mp3")


# =========================
# ALTYAZI DOSYASI ÜRET
# =========================
def altyazi_metni_olustur(hikaye):
    # Video için altyazı kısa olsun
    # Çok uzun olursa ekrana sığmaz
    cümleler = hikaye.split(".")
    temiz = [c.strip() for c in cümleler if len(c.strip()) > 3]
    return temiz[:6]  # ilk 6 cümle altyazı


# =========================
# VIDEO ÜRET (Efekt + Altyazı)
# =========================
def video_uret(hikaye):

    # Görselleri al
    img1 = ImageClip("static/s1.png").set_duration(4).fadein(1).fadeout(1)
    img2 = ImageClip("static/s2.png").set_duration(4).fadein(1).fadeout(1)
    img3 = ImageClip("static/s3.png").set_duration(4).fadein(1).fadeout(1)

    audio = AudioFileClip("static/ses.mp3")

    # Video birleştir
    video = concatenate_videoclips([img1, img2, img3], method="compose")

    # Ses ekle
    video = video.set_audio(audio)

    # =========================
    # ALTYAZI EKLE
    # =========================
    altyazi_listesi = altyazi_metni_olustur(hikaye)

    altyazi_clips = []
    zaman = 0

    for cumle in altyazi_listesi:
        txt = TextClip(
            cumle,
            fontsize=40,
            color="white",
            font="Arial-Bold"
        ).set_position(("center", "bottom")).set_duration(2).set_start(zaman)

        altyazi_clips.append(txt)
        zaman += 2

    final_video = CompositeVideoClip([video] + altyazi_clips)

    os.makedirs("static", exist_ok=True)

    final_video.write_videofile("static/video.mp4", fps=24)


# =========================
# WEB
# =========================
@uygulama.route("/", methods=["GET", "POST"])
def anasayfa():

    if request.method == "POST":

        konu = request.form["konu"]
        tur = request.form["tur"]
        karakter = request.form["karakter"]

        # =========================
        # GEMINI PROMPT
        # =========================
        tek_prompt = f"""
        Tür: {tur}
        Konu: {konu}
        Ana karakter: {karakter}

        1) Türkçe 3 paragraf hikaye yaz.

        2) Ardından aşağıdaki formatta 3 sahne betimlemesi yaz:
        Sahne 1: ...
        Sahne 2: ...
        Sahne 3: ...

        Sahne betimlemeleri sinematik olsun ve görsel üretmeye uygun yaz.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=tek_prompt
        )

        sonuc = response.text

        # Hikaye kısmını ayır
        if "Sahne 1" in sonuc:
            hikaye = sonuc.split("Sahne 1")[0].strip()
        else:
            hikaye = sonuc

        # Sahne ayıkla
        sahneler = sahneleri_ayikla(sonuc)

        # DB kaydet
        db_kaydet(hikaye, tur, konu, karakter)

        # Ses üret
        ses_uret(hikaye)

        # Görseller üret
        if len(sahneler) >= 3:
            goruntu_uret(sahneler[0], "s1")
            goruntu_uret(sahneler[1], "s2")
            goruntu_uret(sahneler[2], "s3")

            # Video üret (efekt + altyazı dahil)
            video_uret(hikaye)

        return render_template(
            "anasayfa.html",
            hikaye=hikaye,
            sahneler=sahneler,
            video="video.mp4"
        )

    return render_template("anasayfa.html")


if __name__ == "__main__":
    uygulama.run(debug=True)