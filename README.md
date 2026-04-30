# ScreenBreak ⏳
ScreenBreak is a beautiful, minimalist desktop break reminder built with Python and PyQt6. It helps you maintain focus and build healthy screen habits by enforcing scheduled breaks with elegant, full-screen overlays, local GIF integration, and soothing audio cues.
## ✨ Features
* **Smart Phase Timer:** Automatically cycles between Work (25m), Short Breaks (5m), and Long Breaks (15m).
* **Minimalist UI:** A sleek, transparent circular timer that stays out of your way.
* **Immersive Breaks:** Full-screen overlays featuring curated local GIFs and sounds to help you step away from the screen.
* **Custom Break Flow:** Choose between Auto-cycling, Always Short, or Always Long breaks.
* **System Tray Integration:** Runs quietly in the background with quick access to pause, skip, or mute.
* **Google OAuth Login:** Secure session handling to personalize your experience.
* **Built-in Feedback:** Integrated Supabase connection for direct-to-developer feedback.
## 🚀 Getting Started (Development)
To run ScreenBreak locally for testing or development:
1. **Clone the repository:**
   ```bash
   git clone https://github.com/arunkumarm-git/ScreenBreak_App.git
   cd ScreenBreak
   ```
2. **Set up a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables:**
   Create a `.env` file in the root directory and add your Supabase credentials:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   ```
5. **Run the app:**
   ```bash
   python app.py
   ```
## 🤝 Contributing
I welcome bug reports, feature suggestions, and pull requests! 
Because this project is source-available and governed by a proprietary license, please note the following before contributing:
1. **Development Permission:** You are explicitly granted permission to download, modify, and run this code locally **solely for the purpose of testing and developing contributions** to this repository.
2. **Contributor License Agreement (CLA):** By submitting a Pull Request to this repository, you agree to assign the copyright of your contributed code to the project owner (Arun Kumar M). This ensures the project can be legally maintained and protected under its commercial licensing model.
## ⚖️ License & Usage
**Copyright (c) 2026 Arun Kumar M. All Rights Reserved.**
ScreenBreak is **Source-Available, not Open Source**. The code is public for portfolio and educational viewing. 
* **Personal/General Use:** You must obtain explicit permission before using, modifying, distributing, or packaging this software. (Exception granted for local development as outlined in the Contributing section).
* **Commercial Use:** Any commercial application of this software, its source code, or derivative works is strictly prohibited without a separately negotiated commercial license and royalty agreement.
For permission requests, commercial licensing inquiries, and royalty negotiations, please reach out via GitHub Issues or directly to the author.