# app.py — Gemini/Veo Streamlit (multi-prompt, 9:16)
import os, time
from typing import List, Optional
import streamlit as st

# SDK resmi
from google import genai
from google.genai import types

APP_TITLE = "🎬 Gemini / Veo Video Generator"
DEFAULT_ASPECT = "9:16"
DEFAULT_DURATION = 8  # detik

# Varian model persis sesuai docs (Quality/Preview/Fast/Veo2)
MODEL_CHOICES = {
    "Veo 3 — Quality (stable)": "veo-3.0-generate-001",
    "Veo 3 — Preview": "veo-3.0-generate-preview",
    "Veo 3 Fast — (stable)": "veo-3.0-fast-generate-001",
    "Veo 3 Fast — Preview": "veo-3.0-fast-generate-preview",
    "Veo 2": "veo-2.0-generate-001",
}

def split_prompts(s: str) -> List[str]:
    return [x.strip() for x in (s or "").splitlines() if x.strip()]

def ensure_client(key: str) -> genai.Client:
    if not key:
        st.error("Masukkan Gemini API Key di sidebar.")
        st.stop()
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        st.error(f"Gagal init client: {e}")
        st.stop()

def poll_until_done(client: genai.Client, operation):
    # Pola polling resmi (lihat docs Gemini API — Operations)
    while not operation.done:
        time.sleep(6)
        operation = client.operations.get(operation)
    return operation

def save_video_from_operation(client: genai.Client, op, out_path: str):
    # Ambil video pertama dari respons long-running operation
    generated = op.response.generated_videos[0]
    # Unduh via Files API lalu simpan — SDK menyediakan .save()
    client.files.download(file=generated.video)
    generated.video.save(out_path)  # <<— cara resmi di docs
    return out_path

def sidebar():
    st.sidebar.header("🔑 API & Pengaturan")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")

    model_label = st.sidebar.selectbox("Model Veo", list(MODEL_CHOICES.keys()), index=0)
    model_id = MODEL_CHOICES[model_label]

    aspect = st.sidebar.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1"], index=0)

    # Veo 3/Fast bisa 1080p pada 16:9; portrait masih 720p (lihat docs)
    if aspect == "16:9" and model_id.startswith("veo-3"):
        resolution = st.sidebar.selectbox("Resolusi", ["720p", "1080p"], index=0)
    else:
        resolution = st.sidebar.selectbox("Resolusi", ["720p"], index=0)

    duration = st.sidebar.slider("Durasi (detik)", 5 if model_id.startswith("veo-2") else 8, 30, DEFAULT_DURATION)
    seed = st.sidebar.number_input("Seed (opsional)", min_value=0, value=0, step=1)

    st.sidebar.caption("• Multi-prompt: 1 baris = 1 output\n• Seed bantu konsistensi (tidak 100% deterministik).")
    return api_key, model_id, aspect, resolution, duration, seed

def main():
    st.set_page_config(page_title="Veo / Gemini Generator", layout="wide")
    st.title(APP_TITLE)
    st.caption("Text→Video, Image→Video (Veo 3 / Veo 3 Fast / Veo 2) + Image Generation (Gemini 2.5 Flash Image)")

    api_key, model_id, aspect, resolution, duration, seed = sidebar()
    client = ensure_client(api_key)

    tab1, tab2, tab3 = st.tabs(["🅣 Text → Video", "🖼️ Image → Video", "🖌️ Gambar (Gemini 2.5 Flash)"])

    # ---------------------- TEXT → VIDEO ----------------------
    with tab1:
        st.subheader("Text → Video (multi-prompt)")
        text_mp = st.text_area(
            "Masukkan prompt (pisahkan Enter, 1 baris = 1 video)",
            height=180,
            placeholder=(
                "Bayi imut berjalan di catwalk, pakaian modis, latar blur bokeh, lighting lembut\n"
                "Kucing oren gendut mandi busa, suasana ceria, bokeh halus, fokus ekspresi wajah"
            ),
        )
        if st.button("Generate Video dari Teks", type="primary"):
            prompts = split_prompts(text_mp)
            if not prompts:
                st.warning("Isi minimal satu prompt dulu.")
            else:
                for i, p in enumerate(prompts, start=1):
                    st.write(f"**Prompt {i}:** {p}")
                    try:
                        # Generate + polling
                        op = client.models.generate_videos(
                            model=model_id,
                            prompt=p,
                            # config opsional; gunakan hanya field yang valid agar tidak error
                            config=types.GenerateVideosConfig(
                                aspect_ratio=aspect,          # "9:16" | "16:9" | "1:1"
                                resolution=resolution,        # "720p" | "1080p" (16:9 Veo3/3Fast)
                                duration_seconds=int(duration),
                                seed=(seed or None),
                                # negative_prompt="cartoon, low quality", # contoh opsional
                            ),
                        )
                        op = poll_until_done(client, op)
                        out_name = f"video_txt_{i:02d}.mp4"
                        save_video_from_operation(client, op, out_name)
                        st.video(out_name)
                        with open(out_name, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Gagal generate video untuk prompt {i}: {e}")

    # ---------------------- IMAGE → VIDEO (gambar → video Veo) ----------------------
    with tab2:
        st.subheader("Image → Video (multi-prompt, multi-image)")
        up_files = st.file_uploader("Upload 1–5 gambar (png/jpg/jpeg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        text_mp2 = st.text_area("Multi-prompt (opsional, 1 baris = 1 video)", height=140,
                                placeholder="Perbanyak busa saat karakter menggosok perut — gaya lucu anak-anak")
        if st.button("Generate Video dari Gambar", type="primary"):
            if not up_files:
                st.warning("Upload minimal satu gambar dulu.")
            else:
                prompts2 = split_prompts(text_mp2) or [""]  # kosong tetap 1 run
                try:
                    # Upload ke Files API (handle image siap dipakai oleh Veo)
                    uploaded = [client.files.upload(file=f, mime_type=f.type) for f in up_files[:5]]
                except Exception as e:
                    st.error(f"Gagal upload gambar ke Files API: {e}")
                    uploaded = []

                for i, p in enumerate(prompts2, start=1):
                    st.write(f"**Prompt {i}:** {p or '(tanpa prompt tambahan)'}")
                    try:
                        image_handle = uploaded[0] if uploaded else None
                        op = client.models.generate_videos(
                            model=model_id,
                            prompt=p or "",
                            image=image_handle,  # <<— gambar→video Veo 3/3Fast/Veo2
                            config=types.GenerateVideosConfig(
                                aspect_ratio=aspect,
                                resolution=resolution if model_id.startswith("veo-3") else "720p",
                                duration_seconds=int(duration),
                                seed=(seed or None),
                            ),
                        )
                        op = poll_until_done(client, op)
                        out_name = f"video_img_{i:02d}.mp4"
                        save_video_from_operation(client, op, out_name)
                        st.video(out_name)
                        with open(out_name, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Gagal generate image→video untuk prompt {i}: {e}")

    # ---------------------- GENERATE GAMBAR (Gemini 2.5 Flash Image) ----------------------
    with tab3:
        st.subheader("Generate Gambar — Gemini 2.5 Flash Image")
        img_prompt = st.text_area(
            "Prompt gambar",
            height=140,
            placeholder="Bayi imut berjalan di catwalk, bokeh lembut, style fashion editorial",
        )
        if st.button("Generate Gambar", type="primary"):
            if not img_prompt.strip():
                st.warning("Isi prompt dulu ya.")
            else:
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash-image-preview",
                        contents=[img_prompt],
                    )
                    # Ambil inline image dari parts
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
    with st.expander("ℹ️ Catatan penting"):
        st.markdown(
            "- **Model IDs (Gemini API):** Veo 3 (`veo-3.0-generate-001`), Veo 3 Preview (`veo-3.0-generate-preview`), "
            "Veo 3 Fast (`veo-3.0-fast-generate-001`), Veo 3 Fast Preview (`veo-3.0-fast-generate-preview`), Veo 2 (`veo-2.0-generate-001`).\n"
            "- **9:16** didukung di Veo 3/3 Fast; **1080p** saat ini untuk **16:9** saja (Veo 3/3 Fast). Veo 2: 720p.\n"
            "- **Multi-prompt**: Enter per baris = banyak video.\n"
            "- **Image→Video** pakai Files API supaya handle gambarnya valid untuk Veo.\n"
        )

if __name__ == "__main__":
    main()
