# Amypo Automated Question Uploader

Welcome to the Amypo Question Automation script! This tool is designed to save you hours of manual data entry by automatically parsing your Word Documents and uploading the questions to Amypo.

## System Requirements

**CRITICAL: Python Version**
This script relies on `Playwright` for browser automation. Due to recent breaking changes in `asyncio` inside Python 3.13, **Python 3.13 is NOT SUPPORTED** and will cause a `Segmentation Fault` or `AttributeError` on macOS/Linux. 
- You **MUST** use Python 3.10, 3.11, or 3.12.
- **Mac Users:** If you installed Python via Homebrew (`brew install python`), it likely installed 3.13. Please run `brew install python@3.12` and use `python3.12 main.py`.

### Installation (From Scratch)

If you are setting this up for the first time on a new computer:

**1. Install Prerequisites**
- Open the **Microsoft Store** on your Windows PC, search for **Python 3.12**, and click Install (this perfectly handles all PATH setup automatically!).
- Download and install **[Visual Studio Code (VS Code)](https://code.visualstudio.com/)**.
- Download and install **[Git Bash](https://git-scm.com/downloads)**.

**2. Clone and Setup**
Open VS Code, click **Terminal -> New Terminal** at the top, select **Git Bash** from the terminal dropdown on the right, and run these exact commands in order:

```bash
# Clone the repository
git clone https://github.com/dharanesh-vn/dotlab-content-upload-automation
cd dotlab-content-upload-automation

# Upgrade pip to avoid installation errors
python -m pip install --upgrade pip

# Install required Python packages
python -m pip install -r requirements.txt

# Install ONLY the Chromium browser for Playwright to save space/data
python -m playwright install chromium
```

**3. Configure Credentials**
This script requires your Amypo login credentials to run.
1. In VS Code, duplicate the `.env.example` file and rename the copy to `.env`.
2. Replace the placeholder email and password with your actual Amypo login:
```
AMYPO_USERNAME=your_email_here@example.com
AMYPO_PASSWORD=your_password_here
```

## Known Errors & Optimal Solutions

If your teammates encounter errors while running the uploads, here is the official diagnostic guide:

### 1. "Similar question detected by server"
* **Symptom:** A warning popup appears saying a similar question already exists.
* **Reason:** The Amypo server scans the database and flags if a very similar question title is found.
* **Optimal Solution:** This is now **fully automated**! The script will automatically scrape the database's existing question title from the popup, pair it with our question, hit the "Save Anyway" bypass button, and print a full "Similar Questions Report" at the very end of your run so you have a perfect audit trail!

### 2. "Timeout 60000ms exceeded ... waiting for locator"
* **Symptom:** A batch of questions takes an incredibly long time (e.g., 27 minutes) and eventually crashes with a timeout.
* **Reason:** This is called **DOM Lag**. If the batch size is set too high (e.g., 60), Playwright is forced to load 60 massive Rich Text Editors on a single web page. This exhausts the browser's memory, causing every keystroke to lag until it completely freezes and times out.
* **Optimal Solution:** This was permanently fixed in our latest update! We reduced the `chunk_size` down to **20**. This keeps the browser memory perfectly clean and lightning-fast. **Ensure you run `git pull`** to get the latest code!

### 3. Traceback Crash on `page.locator('text=Add Questions').first.click()`
* **Symptom:** After finishing one batch, the script crashes while trying to start the next batch.
* **Reason:** After the server saves a massive batch of questions, the script navigates back to the Question Bank. If the server is slow, the page may not have fully rendered the "Add Questions" button yet, causing Playwright to click empty space or crash.
* **Optimal Solution:** Lowering the `chunk_size` to 20 (via `git pull`) prevents the server from hanging, meaning the page loads instantly and this error disappears.

### 4. `AttributeError: '_UnixSelectorEventLoop' object has no attribute '_closed'`
* **Symptom:** The script crashes instantly with a `segmentation fault` when you run `python main.py`.
* **Reason:** You are running Python 3.13 on a Mac. Playwright is currently incompatible with Python 3.13's new asyncio backend.
* **Optimal Solution:** Downgrade to Python 3.12 (`brew install python@3.12`) and run the script using `python3.12 main.py`.

## Configuration (`config.json`)
Make sure your URLs point to the correct environment. For testing, we use the `dotlab` servers.
```json
{
  "login_url": "https://dotlab.amypo.ai/login",
  "question_bank_url": "https://dotlab.amypo.ai/question-bank"
}
```

## Running the Script
1. Ensure your `.env` file is set up correctly (see Installation step 3).
2. Run `python main.py` (or `python3.12 main.py` on Mac).
3. Select your `.docx` file in the file explorer popup.
4. Verify your `questions_review.csv` looks correct.
5. Enter your start/end question numbers and watch the script fly!
