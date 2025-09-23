# app.py
import os
import time
from typing import List, Optional

import streamlit as st

# Official Google GenAI SDK
from google import genai
from google.genai import types

APP_TITLE = "🎬 Gemini / Veo Video Generator"
DEFAULT_ASPECT = "9:16"
DEFAULT_DURATION = 8

MODEL_CHOICES = {
    "Veo 3 — Quality (stable)": "veo-3.0-generate-001",
    "Veo 3 — Preview": "veo-3.0-generate-preview",
    "Veo 3 Fast — (stable)": "veo-3.0-fast-generate-001",
    "Veo 3 Fast — Preview": "veo-3.0-fast-generate-preview",
    "Veo 2": "veo-2.0-generate-001",
}

def split_prompts(s: str):
    return [x.strip() for x in (s or "").splitlines() if x.strip()]

def ensure_client(key: str):
    if not key:
        st.error("Masukkan Gemini API Key di sidebar.")
        st.stop()
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        st.error(f"Gagal init client: {e}")
        st.stop()

def poll_video_until_done(client: genai.Client, operation):
    tries = 0
    with st.spinner("⏳ Menunggu proses video selesai..."):
        while not operation.done:
            time.sleep(5)
            operation = client.operations.get(operation)
            tries += 1
            if tries > 240:
                raise RuntimeError("Timeout menunggu operasi selesai.")
    return operation

def download_video_to(path: str, client: genai.Client, op_response) -> str:
    video_handle = op_response.response.generated_videos[0].video
    client.files.download(file=video_handle)
    data = getattr(video_handle, "video_bytes", None) or getattr(video_handle, "bytes", None)
    if data is None:
        raise RuntimeError("Tidak menemukan bytes video setelah download.")
    with open(path, "wb") as f:
        f.write(data)
    return path

def configure_sidebar():
    st.sidebar.header("🔑 API & Pengaturan")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    model_human = st.sidebar.selectbox("Model Veo", list(MODEL_CHOICES.keys()), index=0)
    model_id = MODEL_CHOICES[model_human]
    aspect = st.sidebar.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1"], index=0)

    if aspect == "16:9" and model_id.startswith("veo-3"):
        resolution = st.sidebar.selectbox("Resolusi", ["720p", "1080p"], index=0)
    else:
        resolution = st.sidebar.selectbox("Resolusi", ["720p"], index=0)

    duration = st.sidebar.slider("Durasi (detik)", 5 if model_id.startswith("veo-2") else 8, 30, DEFAULT_DURATION)
    seed = st.sidebar.number_input("Seed (opsional)", min_value=0, value=0, step=1)
    st.sidebar.caption("• Multi‑prompt: 1 baris = 1 output\n• Seed membantu konsistensi (tidak 100% deterministik)")
    return api_key, model_id, aspect, resolution, duration, seed

def main():
    st.set_page_config(page_title="Veo / Gemini Generator", layout="wide")
    st.title(APP_TITLE)
    st.caption("Text→Video, Image→Video (Veo 3 / Veo 3 Fast / Veo 2) + Image Generation (Gemini 2.5 Flash Image)")

    api_key, model_id, aspect, resolution, duration, seed = configure_sidebar()
    client = ensure_client(api_key)

    tab1, tab2, tab3 = st.tabs(["🅣 Text → Video", "🖼️ Image → Video", "🖌️ Generate Gambar (Gemini 2.5 Flash)"])

    # TEXT -> VIDEO
    with tab1:
        st.subheader("Text → Video (multi‑prompt)")
        text_mp = st.text_area(
            "Masukkan prompt (Enter per baris, 1 baris = 1 video)",
            height=180,
            placeholder=(
                "Anak kecil berjalan di catwalk, pakaian modis, latar blur bokeh, lighting lembut\n"
                "Kucing oren gendut mandi busa, suasana ceria, bokeh halus, fokus ekspresi"
            ),
        )
        run = st.button("Generate Video dari Teks", type="primary")
        if run:
            prompts = split_prompts(text_mp)
            if not prompts:
                st.warning("Isi minimal satu prompt dulu.")
            else:
                for i, p in enumerate(prompts, start=1):
                    st.write(f"**Prompt {i}:** {p}")
                    try:
                        cfg = types.GenerateVideosConfig(
                            aspect_ratio=aspect,
                            resolution=resolution if model_id.startswith("veo-3") else "720p",
                            seed=seed or None,
                            duration_seconds=int(duration),
                        )
                        op = client.models.generate_videos(model=model_id, prompt=p, config=cfg)
                        op_done = poll_video_until_done(client, op)
                        out_name = f"video_txt_{i:02d}.mp4"
                        out_path = os.path.join(".", out_name)
                        download_video_to(out_path, client, op_done)
                        st.video(out_path)
                        with open(out_path, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Gagal generate video untuk prompt {i}: {e}")

    # IMAGE -> VIDEO
    with tab2:
        st.subheader("Image → Video (multi‑prompt, multi‑image)")
        up_files = st.file_uploader("Upload 1–5 gambar (png/jpg/jpeg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        text_mp2 = st.text_area("Multi‑prompt (opsional, 1 baris = 1 video)", height=140,
                                placeholder="Perbanyak busa saat karakter menggosok perut — gaya lucu anak-anak")
        run2 = st.button("Generate Video dari Gambar", type="primary")
        if run2:
            if not up_files:
                st.warning("Upload minimal satu gambar dulu.")
            else:
                prompts2 = split_prompts(text_mp2) or [""]
                try:
                    uploaded_images = [client.files.upload(file=f, mime_type=f"type/{f.type.split('/')[-1]}") for f in up_files[:5]]
                except Exception as e:
                    st.error(f"Gagal upload gambar ke Files API: {e}")
                    uploaded_images = []

                for i, p in enumerate(prompts2, start=1):
                    st.write(f"**Prompt {i}:** {p or '(tanpa prompt tambahan)'}")
                    try:
                        cfg = types.GenerateVideosConfig(
                            aspect_ratio=aspect,
                            resolution=resolution if model_id.startswith("veo-3") else "720p",
                            seed=seed or None,
                            duration_seconds=int(duration),
                        )
                        image_handle = uploaded_images[0] if uploaded_images else None
                        op = client.models.generate_videos(model=model_id, prompt=p or "", image=image_handle, config=cfg)
                        op_done = poll_video_until_done(client, op)
                        out_name = f"video_img_{i:02d}.mp4"
                        out_path = os.path.join(".", out_name)
                        download_video_to(out_path, client, op_done)
                        st.video(out_path)
                        with open(out_path, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Gagal generate image→video untuk prompt {i}: {e}")

    # IMAGE GENERATION
    with tab3:
        st.subheader("Generate Gambar — Gemini 2.5 Flash Image")
        img_prompt = st.text_area("Prompt gambar", height=140, placeholder="Bayi imut berjalan di catwalk, bokeh lembut, style fashion editorial")
        run3 = st.button("Generate Gambar", type="primary")
        if run3:
            if not img_prompt.strip():
                st.warning("Isi prompt dulu ya.")
            else:
                try:
                    resp = client.models.generate_content(model="gemini-2.5-flash-image-preview", contents=[img_prompt])
                    image_bytes = None
                    for cand in getattr(resp, "candidates", []) or []:
                        content = getattr(cand, "content", None)
                        parts = getattr(content, "parts", []) if content else []
                        for part in parts:
                            inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
                            if inline and getattr(inline, "data", None):
                                image_bytes = inline.data
                                break
                        if image_bytes:
                            break
                    if not image_bytes:
                        st.warning("Tidak menemukan payload gambar di respons.")
                    else:
                        out_name = "gemini_image.png"
                        with open(out_name, "wb") as f:
                            f.write(image_bytes)
                        st.image(out_name, caption=out_name)
                        with open(out_name, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="image/png")
                except Exception as e:
                    st.error(f"Gagal generate gambar: {e}")

    st.divider()
    with st.expander("ℹ️ Catatan Penting"):
        st.markdown(
            "- Model IDs: Veo 3 (`veo-3.0-generate-001`), Veo 3 Preview (`veo-3.0-generate-preview`), "
            "Veo 3 Fast (`veo-3.0-fast-generate-001`), Veo 3 Fast Preview (`veo-3.0-fast-generate-preview`), Veo 2 (`veo-2.0-generate-001`).\\n"
            "- Aspect ratio & resolusi: 9:16 (720p). 16:9 bisa 720p/1080p di Veo 3/3 Fast.\\n"
            "- Multi‑prompt: Satu baris = satu video.\\n"
            "- Files API dipakai untuk Image→Video."
        )

if __name__ == "__main__":
    main()
