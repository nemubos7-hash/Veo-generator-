-- coding: utf-8 --

""" Streamlit Gemini/Veo Video Generator (ASCII-safe)

Text -> Video (batch: one line per prompt)

Image -> Video (multi-image, optional prompt)


Requirements: pip install streamlit google-genai Run: streamlit run app.py """

import os import io import time import base64 from typing import List, Optional

import streamlit as st

Optional Google AI Studio SDK (pip install google-genai)

try: from google import genai from google.genai import types except Exception: genai = None types = None

APP_TITLE = "Gemini / Veo Video Generator" DEFAULT_MODEL = "veo-3.0-generate-001" DEFAULT_ASPECT = "9:16" DEFAULT_DURATION = 8  # seconds

------------------------- Utilities -------------------------

def _b64_download_bytes(data: bytes, fname: str, label: str): b64 = base64.b64encode(data).decode() href = f'<a download="{fname}" href="data:application/octet-stream;base64,{b64}">{label}</a>' st.markdown(href, unsafe_allow_html=True)

def split_prompts(multiline_text: str) -> List[str]: return [ln.strip() for ln in (multiline_text or "").splitlines() if ln.strip()]

def ensure_sdk(): if genai is None: st.error("SDK google-genai not installed. Run: pip install google-genai") return None return genai

def to_part_from_upload(upload): """Convert an uploaded file to a google.genai.types.Part if available.""" if types is None or upload is None: return None mime = upload.type or "application/octet-stream" data = upload.getvalue() try: return types.Part.from_bytes(data=data, mime_type=mime) except Exception: return None

def call_generate_video(client, model: str, prompt: str, aspect: str, duration_s: int, seed: Optional[int] = None, image_part: Optional[object] = None): """Calls Google AI Studio video generation for text->video or image->video. Returns: list[(filename, bytes)] """ kwargs = dict(model=model, prompt=prompt)

# Common optional parameters (be tolerant to SDK key names)
kwargs.update({
    "aspect_ratio": aspect,
    "aspectRatio": aspect,
    "duration_seconds": int(duration_s),
    "durationSeconds": int(duration_s),
})
if seed is not None:
    kwargs.update({"seed": int(seed)})

if image_part is not None:
    # Image -> Video
    kwargs.update({
        "images": [image_part],
        "image": image_part,
    })

resp = client.models.generate_video(**kwargs)

out_pairs = []

# Try resp.videos
vids = getattr(resp, "videos", None)
if vids:
    for i, v in enumerate(vids):
        blob = getattr(v, "bytes", None)
        if blob:
            out_pairs.append((f"video_{i+1}.mp4", blob))
            continue
        uri = getattr(v, "uri", None) or getattr(v, "file_uri", None)
        if uri and hasattr(client, "files"):
            try:
                file_obj = client.files.download(uri)
                data = getattr(file_obj, "data", None)
                if data:
                    out_pairs.append((f"video_{i+1}.mp4", data))
            except Exception:
                out_pairs.append((f"video_{i+1}.txt", f"URI: {uri}".encode()))

# Try resp.bytes
if not out_pairs:
    blob = getattr(resp, "bytes", None)
    if blob:
        out_pairs.append(("video.mp4", blob))

# Try resp.uri
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
    out_pairs.append(("response.txt", str(resp).encode()))

return out_pairs

--------------------------- UI ---------------------------

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide") st.title(APP_TITLE) st.caption("Text->Video and Image->Video (Veo). One line = one output. Use seed for consistency.")

with st.sidebar: st.header("Config") api_key = st.text_input("Google AI Studio API Key", type="password", help="From Google AI Studio / Gemini API") model = st.selectbox("Veo model", [ "veo-3.0-generate-001", "veo-3.0-generate-preview", "veo-3.0", "veo-2.0", ], index=0) aspect = st.selectbox("Aspect Ratio", ["9:16", "16:9", "1:1", "4:5", "3:4"], index=0) duration = st.slider("Duration (sec)", 4, 20, DEFAULT_DURATION) seed_val = st.text_input("Seed (optional)", value="", help="Number to keep randomness consistent") try: seed = int(seed_val) if seed_val.strip() else None except Exception: st.warning("Seed must be an integer. Ignored.") seed = None

st.markdown(
    "**Notes**

" "- Seed: repeatable randomness. " "- Batch: enter multiple prompts (one line each). " "- Image->Video: upload image(s) + optional prompt." )

Tabs

text_tab, image_tab = st.tabs(["Text -> Video", "Image -> Video"])

--------------------- Text -> Video ---------------------

with text_tab: st.subheader("Text -> Video (batch per line)") prompts_text = st.text_area( "Enter prompts (one line = one video)", height=180, placeholder=( "Example: " "A cute chubby orange cat taking a bubble bath, cinematic, soft bokeh. " "Drone shot of a rainforest waterfall at sunset, ultra-detailed, mist." ), ) go_txt = st.button("Generate from text", type="primary")

if go_txt:
    sdk = ensure_sdk()
    if not sdk:
        st.stop()
    if not api_key:
        st.error("Enter API key in the sidebar.")
        st.stop()

    client = sdk.Client(api_key=api_key)
    items = split_prompts(prompts_text)
    if not items:
        st.warning("No valid prompts.")
        st.stop()

    st.info(f"Processing {len(items)} video(s)...")
    for idx, p in enumerate(items, start=1):
        with st.status(f"[{idx}/{len(items)}] Generating...", expanded=False):
            try:
                files = call_generate_video(client, model, p, aspect, duration, seed, image_part=None)
            except Exception as e:
                st.error(f"API call failed: {e}")
                continue

        for (fname, blob) in files:
            st.write(f"Prompt {idx}: {p}")
            if fname.endswith('.mp4') and blob:
                st.video(blob)
                _b64_download_bytes(blob, fname, "Download video")
            else:
                text_out = blob.decode(errors='ignore') if isinstance(blob, (bytes, bytearray)) else str(blob)
                st.code(text_out)
        st.divider()

--------------------- Image -> Video ---------------------

with image_tab: st.subheader("Image -> Video (optional prompt; multi-image supported)") prompt_img = st.text_area("Companion prompt (optional)", height=120, placeholder="Example: A cinematic zoom-in with soft lighting and gentle camera sway.") uploads = st.file_uploader("Upload one or more images", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True) go_img = st.button("Generate from image(s)")

if go_img:
    sdk = ensure_sdk()
    if not sdk:
        st.stop()
    if not api_key:
        st.error("Enter API key in the sidebar.")
        st.stop()
    if not uploads:
        st.warning("Upload at least one image.")
        st.stop()

    client = sdk.Client(api_key=api_key)
    st.info(f"Processing {len(uploads)} image(s)...")

    for i, up in enumerate(uploads, start=1):
        part = to_part_from_upload(up)
        if part is None:
            st.error(f"File #{i} is not readable by SDK: {up.name}")
            continue

        with st.status(f"[{i}/{len(uploads)}] Generating for {up.name}...", expanded=False):
            try:
                files = call_generate_video(client, model, prompt_img or "", aspect, duration, seed, image_part=part)
            except Exception as e:
                st.error(f"API call failed for {up.name}: {e}")
                continue

        for (fname, blob) in files:
            st.write(f"Source: {up.name}")
            if fname.endswith('.mp4') and blob:
                st.video(blob)
                base, _ = os.path.splitext(up.name)
                outname = f"{base}_video.mp4"
                _b64_download_bytes(blob, outname, "Download video")
            else:
                text_out = blob.decode(errors='ignore') if isinstance(blob, (bytes, bytearray)) else str(blob)
                st.code(text_out)
        st.divider()

------------------------- Footer -------------------------

st.caption( "If you hit API/SDK errors, check the printed logs. This app sends multiple key variants (aspect_ratio vs aspectRatio, etc.) to stay compatible across SDK versions." )

