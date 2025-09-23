# app.py — Gemini/Veo Streamlit (fixed Image→Video upload + multi-prompt Flash Image)
import os, time
from typing import List
import streamlit as st

# SDK resmi Google GenAI
from google import genai
from google.genai import types

APP_TITLE = "🎬 Gemini / Veo Video Generator (Fixed)"
DEFAULT_ASPECT = "9:16"
DEFAULT_DURATION = 8  # detik

MODEL_CHOICES = {
    "Veo 3 — Quality (stable)": "veo-3.0-generate-001",
    "Veo 3 — Preview": "veo-3.0-generate-preview",
    "Veo 3 Fast — (stable)": "veo-3.0-fast-generate-001",
    "Veo 3 Fast — Preview": "veo-3.0-fast-generate-preview",
    "Veo 2": "veo-2.0-generate-001",
}

def split_lines(s: str) -> List[str]:
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

def poll_until_done(client: genai.Client, operation):
    # Long-running operation polling
    with st.spinner("⏳ Memproses..."):
        while not operation.done:
            time.sleep(6)
            operation = client.operations.get(operation)
    return operation

def save_video(client: genai.Client, op, out_name: str):
    # Ambil video pertama dari respons
    gen_video = op.response.generated_videos[0]
    # Download via Files API
    client.files.download(file=gen_video.video)
    # Simpan (SDK beberapa versi punya .save)
    if hasattr(gen_video.video, "save"):
        gen_video.video.save(out_name)
    else:
        data = getattr(gen_video.video, "video_bytes", None) or getattr(gen_video.video, "bytes", None)
        if not data:
            raise RuntimeError("Tidak menemukan bytes video untuk disimpan.")
        with open(out_name, "wb") as f:
            f.write(data)
    return out_name

def sidebar():
    st.sidebar.header("🔑 API & Pengaturan")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")

    model_label = st.sidebar.selectbox("Model Veo", list(MODEL_CHOICES.keys()), index=0)
    model_id = MODEL_CHOICES[model_label]

    aspect = st.sidebar.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1"], index=0)

    # Veo 3/3 Fast: 16:9 → bisa 1080p; portrait 9:16 umumnya 720p
    if aspect == "16:9" and model_id.startswith("veo-3"):
        resolution = st.sidebar.selectbox("Resolusi", ["720p", "1080p"], index=0)
    else:
        resolution = st.sidebar.selectbox("Resolusi", ["720p"], index=0)

    duration = st.sidebar.slider("Durasi (detik)", 5 if model_id.startswith("veo-2") else 8, 30, DEFAULT_DURATION)
    seed = st.sidebar.number_input("Seed (opsional)", min_value=0, value=0, step=1)

    st.sidebar.caption("• Multi-prompt: 1 baris = 1 output\n• Seed bantu konsistensi (tidak 100% deterministik).")
    return api_key, model_id, aspect, resolution, duration, seed

def upload_streamlit_files(client: genai.Client, files):
    """Upload Streamlit UploadedFile ke Files API (mime_type & display_name benar)."""
    handles = []
    for uf in files:
        mime = uf.type or "application/octet-stream"  # ex: image/png, image/jpeg
        try:
            handle = client.files.upload(
                file=uf,                 # UploadedFile (file-like) didukung SDK
                mime_type=mime,
                display_name=getattr(uf, "name", "uploaded_image")
            )
            handles.append(handle)
        except Exception as e:
            st.error(f"Gagal upload {getattr(uf, 'name', '(tanpa nama)')}: {e}")
    return handles

def main():
    st.set_page_config(page_title="Veo / Gemini Generator (Fixed)", layout="wide")
    st.title(APP_TITLE)
    st.caption("Text→Video, Image→Video (Veo 3 / Fast / Veo 2) + Multi-prompt Image Generation (Gemini 2.5 Flash)")

    api_key, model_id, aspect, resolution, duration, seed = sidebar()
    client = ensure_client(api_key)

    tab1, tab2, tab3 = st.tabs(["🅣 Text → Video", "🖼️ Image → Video", "🖌️ Gambar (Gemini 2.5 Flash)"])

    # ---------------------- TEXT → VIDEO ----------------------
    with tab1:
        st.subheader("Text → Video (multi-prompt)")
        text_mp = st.text_area(
            "Masukkan prompt (Enter per baris, 1 baris = 1 video)",
            height=180,
            placeholder=(
                "Bayi imut berjalan di catwalk, pakaian modis, latar blur bokeh, lighting lembut\n"
                "Kucing oren gendut mandi busa, suasana ceria, bokeh halus, fokus ekspresi wajah"
            ),
        )
        if st.button("Generate Video dari Teks", type="primary"):
            prompts = split_lines(text_mp)
            if not prompts:
                st.warning("Isi minimal satu prompt dulu.")
            else:
                for i, p in enumerate(prompts, start=1):
                    st.write(f"**Prompt {i}:** {p}")
                    try:
                        op = client.models.generate_videos(
                            model=model_id,
                            prompt=p,
                            config=types.GenerateVideosConfig(
                                aspect_ratio=aspect,
                                resolution=resolution if model_id.startswith("veo-3") else "720p",
                                duration_seconds=int(duration),
                                seed=(seed or None),
                            ),
                        )
                        op = poll_until_done(client, op)
                        out_name = f"video_txt_{i:02d}.mp4"
                        save_video(client, op, out_name)
                        st.video(out_name)
                        with open(out_name, "rb") as fh:
                            st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Gagal generate video untuk prompt {i}: {e}")

    # ---------------------- IMAGE → VIDEO ----------------------
    with tab2:
        st.subheader("Image → Video (multi-prompt, multi-image) — Fixed Upload")
        up_files = st.file_uploader("Upload 1–5 gambar (png/jpg/jpeg)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        text_mp2 = st.text_area("Multi-prompt (opsional, 1 baris = 1 video)", height=140,
                                placeholder="Perbanyak busa saat karakter menggosok perut — gaya lucu anak-anak")
        if st.button("Generate Video dari Gambar", type="primary"):
            if not up_files:
                st.warning("Upload minimal satu gambar dulu.")
            else:
                prompts2 = split_lines(text_mp2) or [""]
                # 1) Upload ke Files API dengan MIME & display_name yang benar
                handles = upload_streamlit_files(client, up_files[:5])
                if not handles:
                    st.error("Semua upload gagal. Coba ulangi dengan gambar lain atau periksa API Key/kuota.")
                else:
                    for i, p in enumerate(prompts2, start=1):
                        st.write(f"**Prompt {i}:** {p or '(tanpa prompt tambahan)'}")
                        try:
                            # Coba dukung multiple images; fallback ke 1 image bila SDK belum support
                            kwargs = dict(
                                model=model_id,
                                prompt=p or "",
                                config=types.GenerateVideosConfig(
                                    aspect_ratio=aspect,
                                    resolution=resolution if model_id.startswith("veo-3") else "720p",
                                    duration_seconds=int(duration),
                                    seed=(seed or None),
                                ),
                            )
                            try:
                                # Beberapa versi SDK: images=[File,...]
                                op = client.models.generate_videos(images=handles, **kwargs)  # type: ignore
                            except TypeError:
                                # Fallback: image=File tunggal
                                op = client.models.generate_videos(image=handles[0], **kwargs)  # type: ignore

                            op = poll_until_done(client, op)
                            out_name = f"video_img_{i:02d}.mp4"
                            save_video(client, op, out_name)
                            st.video(out_name)
                            with open(out_name, "rb") as fh:
                                st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="video/mp4")
                        except Exception as e:
                            st.error(f"Gagal generate image→video untuk prompt {i}: {e}")

    # ---------------------- MULTI-PROMPT IMAGE GENERATION ----------------------
    with tab3:
        st.subheader("Generate Gambar — Gemini 2.5 Flash (multi-prompt)")
        img_mp = st.text_area(
            "Masukkan beberapa prompt gambar (Enter per baris)",
            height=160,
            placeholder=(
                "Bayi imut berjalan di catwalk, bokeh lembut, style fashion editorial\n"
                "Kucing oren gendut di bak mandi busa, ekspresi ceria, cinematic soft light"
            ),
        )
        if st.button("Generate Beberapa Gambar", type="primary"):
            prompts = split_lines(img_mp)
            if not prompts:
                st.warning("Isi minimal satu prompt dulu.")
            else:
                for i, p in enumerate(prompts, start=1):
                    st.write(f"**Prompt {i}:** {p}")
                    try:
                        resp = client.models.generate_content(
                            model="gemini-2.5-flash-image-preview",
                            contents=[p],
                        )
                        image_bytes = None
                        # Ambil inline image dari respon
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
                            st.warning(f"Tidak menemukan payload gambar untuk prompt {i}.")
                        else:
                            out_name = f"gemini_image_{i:02d}.png"
                            with open(out_name, "wb") as f:
                                f.write(image_bytes)
                            st.image(out_name, caption=out_name)
                            with open(out_name, "rb") as fh:
                                st.download_button("⬇️ Download", data=fh.read(), file_name=out_name, mime="image/png")
                    except Exception as e:
                        st.error(f"Gagal generate gambar (prompt {i}): {e}")

    st.divider()
    with st.expander("ℹ️ Catatan & Debug"):
        st.markdown(
            "- **Perbaikan upload**: gunakan `client.files.upload(file=uf, mime_type=uf.type, display_name=uf.name)`.\n"
            "- Jika `images=[...]` tidak didukung oleh SDK, otomatis fallback ke `image=handles[0]`.\n"
            "- Jika masih gagal upload, cek ukuran file, tipe MIME (`image/png` / `image/jpeg`), kuota & akses model."
        )

if __name__ == "__main__":
    main()
