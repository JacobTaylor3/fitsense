# FitSense 👕🌦️
FitSense is a smart wardrobe-assistant web app that helps you choose outfits based on weather conditions, style, and occasion.  

---

## 🚀 Features

- 👚 **Wardrobe Management** — Add and manage tops, bottoms, outerwear, and accessories.  
- 🌤️ **Weather Integration** — Fetch live or forecasted weather data to plan your outfit.  
- 🤖 **Smart Outfit Suggestions** — Get automatic outfit recommendations suited to the temperature and conditions.  
- 🎨 **Interactive Interface** — Browse, preview, and adjust outfits directly in the browser.  
- 🧩 **Modular Design** — Organized codebase with separate modules for wardrobe, weather, and outfit generation logic.  
- ⚙️ **Easy to Extend** — Swap out weather providers or improve the recommendation algorithm easily.  

---


## 🛠️ How to Run Locally

To run FitSense locally, follow these steps:

1. **Clone the Repository**  
```bash
git clone https://github.com/JacobTaylor3/fitsense.git
cd fitsense

    Set Up a Virtual Environment

python -m venv venv
source venv/bin/activate     # On macOS/Linux
venv\Scripts\activate        # On Windows

    Install Dependencies

pip install --upgrade pip
pip install -r requirements.txt

    (Optional) Add API Keys
    If gemini_client.py or other weather modules require API keys, configure them in an .env file or environment variable:

export WEATHER_API_KEY=your_api_key_here

    Run the Application

python app.py

or

python main.py

    Open the App in Your Browser
    Navigate to:

http://localhost:5000

    Deactivate When Finished

deactivate

Tips:

    Store uploaded images in static/uploads/.

    Modify outfit logic in core_outfits.py to fine-tune recommendations.

    For production deployment, use a WSGI server like Gunicorn and set environment variables securely.

