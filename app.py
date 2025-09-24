-- coding: utf-8 --

import os import io import time import base64 from typing import List, Optional

import streamlit as st from google import genai from google.genai import types

Judul aplikasi

st.set_page_config(page_title="🎬 Gemini / Veo Video Generator", layout="wide") st.title("🎬 Gemini / Veo Video Generator") st.caption("Text->Video, Image->Video, dan Generate Image (Gemini Flash 2.5). 1 baris prompt = 1 output.")

API Key

API_KEY = st.sidebar.text_input("Masukkan Google AI Studio API Key", type="password") if not API_KEY: st.warning("⚠️ Masukkan API Key terlebih dahulu di sidebar.") st.stop()

client = genai.Client(api_key=API_KEY)

Sidebar

st.sidebar.header("Pengaturan") DEFAULT_ASPECT = "9:16" DEFAULT_DURATION = 8

aspect_ratio = st.sidebar.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1"], index=0) duration = st.sidebar.number_input("Durasi Video (detik)", 4, 60, DEFAULT_DURATION) seed = st.sidebar.text_input("Seed (opsional)")

st.sidebar.markdown("""Notes

Seed: repeatable randomness.

Batch: masukkan banyak prompt (satu baris tiap prompt).

Image->Video: upload 1 atau banyak gambar + prompt opsional. """)


========================= Text -> Video =========================

st.header("Text -> Video") text_prompts = st.text_area("Masukkan 1 atau lebih prompt (1 baris = 1 video)")

if st.button("Generate dari Text"): if not text_prompts.strip(): st.error("Prompt kosong!") else: for idx, prompt in enumerate(text_prompts.strip().splitlines(), start=1): with st.spinner(f"Menghasilkan video untuk prompt {idx}..."): try: resp = client.models.generate_video( model="veo-3.0-generate-001", prompt=prompt, config=types.VideoConfig(duration=duration, aspect_ratio=aspect_ratio, seed=seed if seed else None) ) file_resp = client.files.download(name=resp.files[0].name) video_bytes = file_resp.read() st.video(video_bytes) st.download_button(f"Download Video {idx}", video_bytes, file_name=f"video_{idx}.mp4") except Exception as e: st.error(f"Gagal generate video: {e}")

========================= Image -> Video =========================

st.header("Image -> Video") uploaded_files = st.file_uploader("Upload 1 atau lebih gambar", type=["png", "jpg", "jpeg"], accept_multiple_files=True) img_prompt = st.text_input("Tambahkan prompt opsional untuk gambar")

if st.button("Generate dari Gambar"): if not uploaded_files: st.error("Belum ada gambar diupload!") else: for idx, file in enumerate(uploaded_files, start=1): with st.spinner(f"Menghasilkan video dari gambar {idx}..."): try: upload = client.files.upload(file=file) resp = client.models.generate_video( model="veo-3.0-generate-001", prompt=img_prompt, config=types.VideoConfig(duration=duration, aspect_ratio=aspect_ratio, seed=seed if seed else None), files=[upload] ) file_resp = client.files.download(name=resp.files[0].name) video_bytes = file_resp.read() st.video(video_bytes) st.download_button(f"Download Video Gambar {idx}", video_bytes, file_name=f"image_video_{idx}.mp4") except Exception as e: st.error(f"Gagal generate video dari gambar: {e}")

========================= Generate Image (Gemini Flash 2.5) =========================

st.header("Generate Image (Gemini Flash 2.5)") img_prompt2 = st.text_area("Masukkan prompt untuk generate gambar (1 baris = 1 gambar)")

if st.button("Generate Gambar"): if not img_prompt2.strip(): st.error("Prompt kosong!") else: for idx, prompt in enumerate(img_prompt2.strip().splitlines(), start=1): with st.spinner(f"Menghasilkan gambar {idx}..."): try: resp = client.models.generate_images( model="gemini-2.5-flash", prompt=prompt ) file_resp = client.files.download(name=resp.files[0].name) image_bytes = file_resp.read() st.image(image_bytes, caption=f"Hasil Gambar {idx}") st.download_button(f"Download Gambar {idx}", image_bytes, file_name=f"image_{idx}.png") except Exception as e: st.error(f"Gagal generate gambar: {e}")

