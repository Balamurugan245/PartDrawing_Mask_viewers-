# 🧠 Partdrawing Mask Viewer

An **interactive web application** built with Flask that visualizes engineering part drawings along with their segmentation mask overlays.  
Users can upload ZIP files containing *noisy images* and *corresponding `.npy` mask files*, preview overlays, and explore each mask interactively.

---

## 🚀 Features

- 📂 Upload two ZIP files: one containing noisy images, and one with `.npy` mask arrays.
- 🧩 Automatic image–mask matching using filename normalization.
- 🎨 Overlay visualization with unique colors for each mask.
- 🖱️ Hover interaction: highlights the active mask region and displays its ID.
- 🔄 Navigation buttons for browsing multiple images.
- 💡 Error handling with clear messages and progress indication.

---

## 🖼️ Application Preview

### 🔹 Upload Page
<p align="center">
<img src="UI.png" alt="UI">
</p>

### 🔹 Mask Visualization
<p align="center">
<img src="Mask_view.png" alt="Mask_view">
</p>

---

## 🏗️ Project Structure

PartDrawing_Mask_viewers-/
│
├── app.py # Flask backend server
├── requirements.txt # Dependencies
├── templates/
│ └── index.html # Main frontend HTML (UI + JS)
├── static/
│ ├── images/
│ │ └── com logo.jpg
│ ├── uploads/ # Auto-created for temporary uploads
│ └── css/, js/ (optional)
└── README.md

yaml
Copy code

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/Balamurugan245/PartDrawing_Mask_viewers-.git
cd PartDrawing_Mask_viewers-
2️⃣ Create Virtual Environment (Optional but Recommended)
bash
Copy code
python -m venv venv
source venv/Scripts/activate      # On Windows
# or
source venv/bin/activate          # On Linux/Mac
3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Run the App
bash
Copy code
python app.py
Then open your browser and go to:
👉 http://127.0.0.1:5000/

🧪 Example Workflow
Prepare two ZIP files:

Noisy images ZIP — contains .jpg or .png files.

Mask files ZIP — contains .npy arrays for each corresponding image.

Upload both via the web interface.

Click Upload & Preview.

Use Next / Previous buttons to browse images.

Hover over regions to see mask details.

🧰 Built With
Flask

NumPy

Pillow (PIL)

HTML5, CSS3, JavaScript

📸 Screenshots
Upload Page	Mask Overlay

👨‍💻 Authors
Balamurugan
🔗 GitHub Profile

Kaviya
🔗 GitHub Profile

📜 License
This project is licensed under the MIT License — feel free to use, modify, and share.

yaml
Copy code

---

✅ Just copy this whole block into your `README.md`,  
then run:
```bash
git add README.md
git commit -m "Added final README with authors and screenshots"
git push
