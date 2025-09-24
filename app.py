import os import io import time import base64 from typing import List, Optional

import streamlit as st

===== Optional Google AI Studio SDK (pip install google-genai) =====

Docs evolve fast; this app tries to be resilient to minor SDK changes.

try: from google import genai from google.genai import types except Exception as e:  # SDK not installed yet genai = None types = None

APP_TITLE = "🎬 Gemini / Veo Video Generator" DEFAULT_MODEL = "veo-3.0-generate-001"  # You can switch to: veo-3.0-generate-preview, veo-3.0, veo-2.0 DEFAULT_ASPECT = "9:16" DEFAULT_DURATION = 8  # seconds

========================= Utilities =========================

def _b64_download_bytes(data: bytes, fname: str, label: str): b64 = base64.b64encode(data).decode() href = f'<a download="{fname}" href="data:application/octet-stream;base64,{b64}">{label}</a>' st.markdown(href, unsafe_allow_html=True)

def split_prompts(multiline_text: str) -> List[str]: return [ln.strip() for ln in (multiline_text or "").splitlines() if ln.strip()]

def ensure_sdk() -> Optional[genai]: if genai is None: st.error("SDK google-genai belum terpasang. Jalankan: pip install google-genai") return None return genai

def to_part_from_upload(upload) -> Optional[object]: """Convert an uploaded file to a google.genai.types.Part if available.""" if types is None or upload is None: return None mime = upload.type or "application/octet-stream" data = upload.getvalue() try: return types.Part.from_bytes(data=data, mime_type=mime) except Exception: return None

def call_generate_video(client, model: str, prompt: str, aspect: str, duration_s: int, seed: Optional[int] = None, image_part: Optional[object] = None): """Calls Google AI Studio video generation, handling both text→video and image→video.

This function is defensive to minor SDK changes.
Returns: list[(filename, bytes)] or raises Exception.
"""
kwargs = dict(model=model, prompt=prompt)

# Common optional params (SDK may accept one of these)
# Some SDK versions expect aspect_ratio vs aspectRatio vs video.aspect_ratio, etc.
# We pass several hints; unknown keys will be ignored by the backend.
kwargs.update({
    "aspect_ratio": aspect,
    "aspectRatio": aspect,
    "duration_seconds": int(duration_s),
    "durationSeconds": int(duration_s),
})
if seed is not None:
    kwargs.update({"seed": int(seed)})

# Image→Video if image_part is provided:
if image_part is not None:
    # Some SDK versions want images=[Part,...]; some want image=imagePart
    kwargs.update({
        "images": [image_part],
        "image": image_part,
    })

# Actual call
resp = client.models.generate_video(**kwargs)

# Extract bytes: different SDKs may return list of videos with .bytes or .uri.
out_pairs = []

# Path 1: resp.videos (list of Parts or blobs)
vids = getattr(resp, "videos", None)
if vids:
    for i, v in enumerate(vids):
        # Try .bytes first
        blob = getattr(v, "bytes", None)
        if blob:
            out_pairs.append((f"video_{i+1}.mp4", blob))
            continue
        # If only uri, attempt client.files.download(uri)
        uri = getattr(v, "uri", None) or getattr(v, "file_uri", None)
        if uri and hasattr(client, "files"):
            try:
                file_obj = client.files.download(uri)
                data = getattr(file_obj, "data", None)
                if data:
                    out_pairs.append((f"video_{i+1}.mp4", data))
            except Exception as e:
                # As a fallback, expose the URI if direct bytes not available
                out_pairs.append((f"video_{i+1}.txt", f"URI: {uri}".encode()))

# Path 2: Some SDKs put bytes at resp.bytes
if not out_pairs:
    blob = getattr(resp, "bytes", None)
    if blob:
        out_pairs.append(("video.mp4", blob))

# Path 3: Some SDKs return file URIs in resp
if not out_pairs:
    uri = getattr(resp, "uri", None) or getattr(resp, "file_uri", None)
    if uri and hasattr(client, "files"):
        try:
            file_obj = client.files.download(uri)
            data = getattr(file_obj, "data", None)
            if data:
                out_pairs.append(("video.mp4", data))
        except Exception:
            out_pairs.append(("video.txt", f"URI: {uri}".encode()))

if not out_pairs:
    # Last resort: dump raw response for debugging
    out_pairs.append(("response.json", str(resp).encode()))

return out_pairs

========================= UI =========================

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide") st.title(APP_TITLE) st.caption("Text→Video dan Image→Video (Veo). 1 baris = 1 output. Gunakan seed untuk konsistensi.")

with st.sidebar: st.header("🔑 Konfigurasi") api_key = st.text_input("Google AI Studio API Key", type="password", help="Dari Google AI Studio / Gemini API.") model = st.selectbox("Model Veo", [ "veo-3.0-generate-001", "veo-3.0-generate-preview", "veo-3.0", "veo-2.0", ], index=0) aspect = st.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1", "4:5", "3:4"], index=0) duration = st.slider("Durasi (detik)", 4, 20, DEFAULT_DURATION) seed_val = st.text_input("Seed (opsional)", value="", help="Angka untuk kontrol random agar hasil lebih konsisten.") try: seed = int(seed_val) if seed_val.strip() else None except Exception: st.warning("Seed harus angka. Diabaikan.") seed = None

st.markdown("""
**Tips**
- **Seed**: angka untuk mengulang pola random yang sama.
- **Batch**: masukkan beberapa prompt (tiap baris 1 prompt) agar dirender banyak video sekaligus.
- **Image→Video**: unggah gambar (JPG/PNG/WebP) + prompt (opsional).
""")

tabs = st.tabs(["📝 Text → Video", "🖼️ Image → Video"])  # noqa

========================= Text -> Video =========================

with tabs[0]: st.subheader("Text -> Video (Batch per baris)") prompts_text = st.text_area("Masukkan prompt (tiap baris = 1 video)", height=180, placeholder="Contoh:\nA cute chubby orange cat taking a bubble bath, cinematic, soft bokeh.\nDrone shot of a rainforest waterfall at sunset, ultra-detailed, mist.") go_txt = st.button("Generate Video dari Teks", type="primary")

if go_txt:
    sdk = ensure_sdk()
    if not sdk:
        st.stop()
    if not api_key:
        st.error("Masukkan API Key dulu di sidebar.")
        st.stop()

    client = sdk.Client(api_key=api_key)
    items = split_prompts(prompts_text)
    if not items:
        st.warning("Tidak ada prompt yang valid.")
        st.stop()

    st.info(f"Memproses {len(items)} video…")
    for idx, p in enumerate(items, start=1):
        with st.status(f"[{idx}/{len(items)}] Generating…", expanded=False):
            try:
                files = call_generate_video(client, model, p, aspect, duration, seed, image_part=None)
            except Exception as e:
                st.error(f"Gagal memanggil API: {e}")
                continue

        for (fname, blob) in files:
            st.write(f"**Prompt {idx}:** {p}")
            if fname.endswith('.mp4') and blob:
                st.video(blob)
                _b64_download_bytes(blob, fname, "⬇️ Download video")
            else:
                st.code(blob.decode(errors='ignore') if isinstance(blob, (bytes, bytearray)) else str(blob))
        st.divider()

========================= Image → Video =========================

with tabs[1]: st.subheader("Image → Video (Opsional prompt, bisa multi-gambar)") prompt_img = st.text_area("Prompt pendamping (opsional)", height=120, placeholder="Contoh: A cinematic zoom-in with soft lighting and gentle camera sway.") uploads = st.file_uploader("Unggah 1 atau beberapa gambar", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True) go_img = st.button("Generate Video dari Gambar")

if go_img:
    sdk = ensure_sdk()
    if not sdk:
        st.stop()
    if not api_key:
        st.error("Masukkan API Key dulu di sidebar.")
        st.stop()
    if not uploads:
        st.warning("Unggah minimal 1 gambar dulu.")
        st.stop()

    client = sdk.Client(api_key=api_key)
    st.info(f"Memproses {len(uploads)} gambar…")

    for i, up in enumerate(uploads, start=1):
        part = to_part_from_upload(up)
        if part is None:
            st.error(f"File #{i} tidak bisa dibaca SDK: {up.name}")
            continue

        with st.status(f"[{i}/{len(uploads)}] Generating untuk {up.name}…", expanded=False):
            try:
                files = call_generate_video(client, model, prompt_img or "", aspect, duration, seed, image_part=part)
            except Exception as e:
                st.error(f"Gagal memanggil API untuk {up.name}: {e}")
                continue

        for (fname, blob) in files:
            label = f"**{up.name}**"
            st.write(label)
            if fname.endswith('.mp4') and blob:
                st.video(blob)
                # name file unik per input
                base, _ = os.path.splitext(up.name)
                outname = f"{base}_video.mp4"
                _b64_download_bytes(blob, outname, "⬇️ Download video")
            else:
                st.code(blob.decode(errors='ignore') if isinstance(blob, (bytes, bytearray)) else str(blob))
        st.divider()

========================= Footer =========================

st.caption( "Made with Streamlit • Jika terjadi error API/SDK, lihat log yang ditampilkan. " "Beberapa versi SDK memiliki perbedaan field (aspect_ratio vs aspectRatio, dll); app ini sudah mengirim beberapa variasi agar lebih kompatibel." )

