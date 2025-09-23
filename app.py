import os
import time
import io
import streamlit as st

from google import genai
from google.genai import types

st.set_page_config(page_title="Veo Generator (Video & Image)", layout="wide")
st.title("🎬 Veo Generator — Video & Image")
st.caption("Text→Video, Image→Video, dan Generate Image (alias “Nano Banana”). 1 baris prompt = 1 output.")

# ========== API KEY ==========
API_KEY = None
try:
    API_KEY = st.sidebar.text_input("Masukkan API Key Gemini", type="password")
    if API_KEY:
        client = genai.Client(api_key=API_KEY)
        st.sidebar.success("API Key berhasil dimuat")
    else:
        st.sidebar.warning("Masukkan API Key untuk mulai")
except Exception as e:
    st.sidebar.error(f"Error memuat API Key: {e}")

# ========== PILIHAN FITUR ==========
feature = st.sidebar.radio("Pilih Fitur", ["Text to Video (Veo)", "Image to Video (Veo)", "Generate Image (Gemini 2.5 Flash)"])

# Input multi-prompt
prompts = st.text_area("Masukkan Prompt (1 baris = 1 output)", height=150)
prompt_list = [p.strip() for p in prompts.split("\n") if p.strip()]

aspect_ratio = st.sidebar.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1"], index=0)
duration = st.sidebar.slider("Durasi Video (detik)", 2, 30, 8)
seed = st.sidebar.text_input("Seed (opsional, untuk konsistensi hasil)")

st.sidebar.markdown("**Keterangan:**")
st.sidebar.markdown("- *Seed*: angka acak untuk konsistensi hasil video/gambar.")
st.sidebar.markdown("- *Batch*: jumlah output yang dihasilkan dari prompt.")

if st.button("Generate"):
    if not API_KEY:
        st.error("Masukkan API Key terlebih dahulu.")
    elif not prompt_list:
        st.error("Masukkan minimal satu prompt.")
    else:
        for idx, p in enumerate(prompt_list, 1):
            with st.spinner(f"⏳ Memproses prompt {idx}/{len(prompt_list)}..."):
                try:
                    if feature == "Text to Video (Veo)":
                        st.write(f"🎬 [DEBUG] Generate Video dari Text Prompt: {p}, Rasio: {aspect_ratio}, Durasi: {duration}, Seed: {seed}")
                        st.video("https://samplelib.com/lib/preview/mp4/sample-5s.mp4")
                    elif feature == "Image to Video (Veo)":
                        uploaded_files = st.file_uploader("Upload Gambar (bisa multi-upload)", type=["jpg", "png"], accept_multiple_files=True)
                        if uploaded_files:
                            for file in uploaded_files:
                                st.image(file, caption=f"Input Image: {file.name}", use_column_width=True)
                                st.write(f"🎬 [DEBUG] Generate Video dari Image: {file.name}, Rasio: {aspect_ratio}, Durasi: {duration}, Seed: {seed}")
                                st.video("https://samplelib.com/lib/preview/mp4/sample-5s.mp4")
                    elif feature == "Generate Image (Gemini 2.5 Flash)":
                        st.write(f"🖼️ [DEBUG] Generate Image: {p}, Rasio: {aspect_ratio}, Seed: {seed}")
                        st.image("https://placekitten.com/400/600", caption=f"Hasil Gambar {idx}")
                except Exception as e:
                    st.error(f"❌ Error saat generate: {e}")