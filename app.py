import os,io
import uuid
import zipfile
import base64
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, url_for,current_app
from PIL import Image
import glob

# === Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
CLEANED_DIR = os.path.join(BASE_DIR, "static", "cleaned")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CLEANED_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.static_folder = 'static'

def normalize_masks_array(arr):
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]
    elif arr.ndim == 3:
        N, A, B = arr.shape
        if N > 50 and (A <= 50 or B <= 50):
            arr = np.transpose(arr, (2, 0, 1))
    arr = (arr != 0).astype(np.uint8)
    return arr

# === ROUTES ===

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/viewer")
def viewer():
    return render_template("mask-viewer.html")

@app.route("/clean")
def clean():
    return render_template("clean.html")


# --- Helper: ensure modified folder ---
def ensure_modified_dir():
    modified_dir = os.path.join(UPLOAD_DIR, "modified")
    os.makedirs(modified_dir, exist_ok=True)
    return modified_dir

# --- Upload route (your original, kept consistent) ---
@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "noisy_zip" not in request.files or "mask_zip" not in request.files:
            return jsonify({"error": "Please upload both noisy and mask ZIP files."}), 400

        noisy_zip = request.files["noisy_zip"]
        mask_zip = request.files["mask_zip"]

        uid = uuid.uuid4().hex
        noisy_folder = os.path.join(UPLOAD_DIR, f"noisy_{uid}")
        mask_folder = os.path.join(UPLOAD_DIR, f"mask_{uid}")
        os.makedirs(noisy_folder, exist_ok=True)
        os.makedirs(mask_folder, exist_ok=True)

        noisy_zip_path = os.path.join(UPLOAD_DIR, f"noisy_{uid}.zip")
        mask_zip_path = os.path.join(UPLOAD_DIR, f"mask_{uid}.zip")
        noisy_zip.save(noisy_zip_path)
        mask_zip.save(mask_zip_path)

        def extract_flat(zip_path, dest_folder):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if not filename:
                        continue
                    # write file bytes
                    with zip_ref.open(member) as source:
                        target_path = os.path.join(dest_folder, filename)
                        with open(target_path, "wb") as target:
                            target.write(source.read())

        extract_flat(noisy_zip_path, noisy_folder)
        extract_flat(mask_zip_path, mask_folder)
        os.remove(noisy_zip_path)
        os.remove(mask_zip_path)

        def list_files(path, exts):
            files = {}
            for f in os.listdir(path):
                ext = os.path.splitext(f)[1].lower()
                if ext in exts:
                    base = os.path.splitext(f)[0]
                    files[base] = os.path.join(path, f)
            return files

        noisy_files = list_files(noisy_folder, {".png", ".jpg", ".jpeg"})
        mask_files = list_files(mask_folder, {".npy"})

        def normalize_name(n):
            n = n.lower()
            for prefix in ["mask_", "output_", "pred_", "seg_", "m_"]:
                if n.startswith(prefix):
                    n = n[len(prefix):]
            for suffix in ["_mask", "_seg", "_output", "_pred"]:
                if n.endswith(suffix):
                    n = n[: -len(suffix)]
            return n

        normalized_noisy = {normalize_name(k): v for k, v in noisy_files.items()}
        normalized_masks = {normalize_name(k): v for k, v in mask_files.items()}

        matched_names = sorted(set(normalized_noisy.keys()) & set(normalized_masks.keys()))
        if not matched_names:
            return jsonify({"error": "No matching image/mask filenames found — even after normalization."}), 400

        pairs = []
        for name in matched_names[:50]:   # limit to 50 preview pairs by default
            noisy_path = normalized_noisy[name]
            mask_path = normalized_masks[name]

            try:
                masks_arr = np.load(mask_path, allow_pickle=False)
            except Exception as e:
                return jsonify({"error": f"Failed to load {name}.npy: {str(e)}"}), 400

            # normalize masks array shape to (N, H, W)
            if masks_arr.ndim == 2:
                masks = masks_arr[np.newaxis, ...]
            elif masks_arr.ndim == 3:
                masks = masks_arr
            else:
                return jsonify({"error": f"{name}.npy has unexpected shape {masks_arr.shape}"}), 400

            N, H, W = masks.shape
            if N > 254:
                return jsonify({"error": f"{name}.npy has too many masks (>254)."}), 400

            # create label_map (uint8) where each mask gets label i+1, last wins on overlap
            label_map = np.zeros((H, W), dtype=np.uint8)
            for i in range(N):
                label_map[masks[i] > 0] = i + 1

            # save a label png for client preview (mode L)
            label_name = f"{name}_label.png"
            label_path = os.path.join(UPLOAD_DIR, label_name)
            Image.fromarray(label_map, mode="L").save(label_path)

            # relative URL for static
            noisy_rel = os.path.relpath(noisy_path, UPLOAD_DIR).replace(os.sep, "/")
            pairs.append({
                "noisy_url": url_for('static', filename=f'uploads/{noisy_rel}'),
                "label_url": url_for('static', filename=f'uploads/{label_name}'),
                "width": int(W),
                "height": int(H),
                "num_masks": int(label_map.max()),
                "name": name
            })

        return jsonify({"pairs": pairs})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# --- Save single mask + base image (called by "Save Current") ---
@app.route("/save_mask", methods=["POST"])
def save_mask():
    try:
        # expected fields: name, width, height, file 'label' (raw bytes), file 'base_image' (png)
        name = request.form.get("name")
        width = int(request.form.get("width"))
        height = int(request.form.get("height"))
        if not name:
            return jsonify({"error": "Missing name"}), 400
        if "label" not in request.files or "base_image" not in request.files:
            return jsonify({"error": "Missing files"}), 400

        label_file = request.files["label"]
        base_file = request.files["base_image"]

        # read label raw bytes
        label_bytes = label_file.read()
        arr = np.frombuffer(label_bytes, dtype=np.uint8)
        if arr.size != width * height:
            # maybe the client sent a typed array with extra header; try reshape with smaller dims
            return jsonify({"error": f"Label size mismatch: expected {width*height} bytes, got {arr.size}"}), 400
        label_map = arr.reshape((height, width))

        modified_dir = ensure_modified_dir()

        # Save .npy version of label map
        npy_path = os.path.join(modified_dir, f"{name}.npy")
        # We save as one-hot stack? To keep parity with original format we will save the label map as uint8
        # (the original .npy contained N x H x W masks; we reconstruct N from labels)
        # We'll save label_map as a uint8 2D array inside a .npy for convenience
        np.save(npy_path, label_map)  # user can adapt to their original format if needed

        # Save base image (overwrite or keep new)
        base_image_path = os.path.join(modified_dir, f"{name}_noisy.png")
        base_file.seek(0)
        with open(base_image_path, "wb") as f:
            f.write(base_file.read())

        return jsonify({"ok": True, "npy": os.path.basename(npy_path), "image": os.path.basename(base_image_path)})

    except Exception as e:
        return jsonify({"error": f"Save failed: {str(e)}"}), 500

# --- Export ZIP of modified files ---
@app.route("/export_zip", methods=["GET"])
def export_zip():
    try:
        modified_dir = os.path.join(UPLOAD_DIR, "modified")
        if not os.path.exists(modified_dir):
            return jsonify({"error": "No modified files to export."}), 400

        # collect all files in modified_dir
        files = [os.path.join(modified_dir, f) for f in os.listdir(modified_dir)]
        if not files:
            return jsonify({"error": "No modified files to export."}), 400

        # create zip in-memory
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fpath in files:
                zf.write(fpath, arcname=os.path.basename(fpath))
        mem_zip.seek(0)
        return send_file(mem_zip, mimetype="application/zip", as_attachment=True, download_name="modified_masks_and_images.zip")

    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500

# ---------- save_all: package edited labels & npy into a zip and return ----------
@app.route("/save_all", methods=["POST"])
def save_all():
    """
    Expects JSON: { "session": "<uid>" }
    Packages all <name>_label.png files in UPLOAD_DIR and corresponding .npy in mask_{uid} (if present)
    into a zip and returns it.
    """
    try:
        payload = request.get_json(force=True)
        session = payload.get("session")
        if not session:
            return "Missing session", 400

        mask_folder = os.path.join(UPLOAD_DIR, f"mask_{session}")
        # gather label pngs in UPLOAD_DIR matching "*_label.png"
        label_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith("_label.png")]
        if not label_files:
            return "No label files found to save.", 400

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
            for lbl in label_files:
                lbl_path = os.path.join(UPLOAD_DIR, lbl)
                zf.write(lbl_path, arcname=lbl)
                # attempt to include corresponding .npy from session mask_folder first, else look in UPLOAD_DIR
                base = lbl[:-10]  # remove "_label.png"
                npy_candidate = os.path.join(mask_folder, f"{base}.npy")
                if not os.path.exists(npy_candidate):
                    npy_candidate = os.path.join(UPLOAD_DIR, f"{base}.npy")
                if os.path.exists(npy_candidate):
                    zf.write(npy_candidate, arcname=os.path.basename(npy_candidate))
        mem.seek(0)
        return send_file(mem, mimetype='application/zip',
                         as_attachment=True,
                         download_name=f"session_{session}_masks.zip")

    except Exception as e:
        return jsonify({"error": f"Save all failed: {str(e)}"}), 500


# ---------- export_mask: return single image's PNG + npy in a tiny zip ----------
@app.route("/export_mask", methods=["GET"])
def export_mask():
    """
    Query params: session=<uid>&name=<basename>
    Returns a zip with <name>_label.png and <name>.npy (if present).
    """
    try:
        session = request.args.get("session")
        name = request.args.get("name")
        if not name:
            return "Missing name", 400

        label_name = f"{name}_label.png"
        label_path = os.path.join(UPLOAD_DIR, label_name)
        mask_folder = os.path.join(UPLOAD_DIR, f"mask_{session}") if session else None
        npy_path = None
        # prefer session mask folder
        if mask_folder and os.path.exists(os.path.join(mask_folder, f"{name}.npy")):
            npy_path = os.path.join(mask_folder, f"{name}.npy")
        elif os.path.exists(os.path.join(UPLOAD_DIR, f"{name}.npy")):
            npy_path = os.path.join(UPLOAD_DIR, f"{name}.npy")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(label_path):
                zf.write(label_path, arcname=os.path.basename(label_path))
            if npy_path and os.path.exists(npy_path):
                zf.write(npy_path, arcname=os.path.basename(npy_path))
        mem.seek(0)
        return send_file(mem, mimetype='application/zip', as_attachment=True,
                         download_name=f"{name}_export.zip")
    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


# === UPLOAD FOR ERASER PAGE ===
@app.route("/upload_clean", methods=["POST"])
def upload_clean():
    try:
        if "image_zip" not in request.files:
            return jsonify({"error": "Please upload an image or ZIP file."}), 400

        file = request.files["image_zip"]
        uid = uuid.uuid4().hex
        folder = os.path.join(UPLOAD_DIR, f"clean_{uid}")
        os.makedirs(folder, exist_ok=True)

        zip_path = os.path.join(folder, file.filename)
        file.save(zip_path)

        image_urls = []

        # Handle ZIP or single file
        if zip_path.lower().endswith(".zip"):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder)
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        rel = os.path.relpath(os.path.join(root, f), UPLOAD_DIR)
                        image_urls.append(url_for('static', filename=f"uploads/{rel.replace(os.sep, '/')}"))
        else:
            rel = os.path.relpath(zip_path, UPLOAD_DIR)
            image_urls.append(url_for('static', filename=f"uploads/{rel.replace(os.sep, '/')}"))

        if not image_urls:
            return jsonify({"error": "No images found in upload."}), 400

        return jsonify({"images": image_urls})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === SAVE SINGLE CLEANED IMAGE ===
@app.route('/save_cleaned_image', methods=['POST'])
def save_cleaned_image():
    try:
        image_data = request.form['image_data']
        filename = request.form['filename']

        image_data = image_data.split(',')[1]
        img_bytes = base64.b64decode(image_data)

        file_path = os.path.join(CLEANED_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(img_bytes)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === DOWNLOAD ALL CLEANED IMAGES AS ZIP ===
@app.route('/download_all_cleaned')
def download_all_cleaned():
    zip_filename = "cleaned_images.zip"
    zip_path = os.path.join(CLEANED_DIR, zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(CLEANED_DIR):
            for f in files:
                if f.endswith(('.png', '.jpg', '.jpeg')):
                    zipf.write(os.path.join(root, f), f)

    return send_file(zip_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
