# Amypo Automated Question Uploader

Welcome to the Amypo Question Automation script! This tool is designed to save you hours of manual data entry by automatically parsing your Word Documents and uploading the questions to Amypo.

## System Requirements

**CRITICAL: Python Version**
This script relies on `Playwright` for browser automation. Due to recent breaking changes in `asyncio` inside Python 3.13, **Python 3.13 is NOT SUPPORTED** and will cause a `Segmentation Fault` or `AttributeError` on macOS/Linux. 
- You **MUST** use Python 3.10, 3.11, or 3.12.
- **Mac Users:** If you installed Python via Homebrew (`brew install python`), it likely installed 3.13. Please run `brew install python@3.12` and use `python3.12 main.py`.

### Installation
1. Install a supported Python version (3.10 - 3.12).
2. Open your terminal and install the dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## Known Errors & Optimal Solutions

If your teammates encounter errors while running the uploads, here is the official diagnostic guide:

### 1. "Duplicate question detected by server"
* **Symptom:** The terminal prints `[BATCH FAILED]` and the reason is a duplicate question.
* **Reason:** The Amypo server scans the question database. If someone else already uploaded that exact question (or if a previous script run got cut off halfway), the server rejects it to prevent duplicates.
* **Optimal Solution:** The script intentionally aborts to protect your data. Look at the terminal output to see which chunk failed (e.g., Q61 to Q120). Open `questions_review.csv`, delete or fix the duplicate questions, and then run `python main.py` again, starting from Q61.

### 2. "Timeout 60000ms exceeded ... waiting for locator"
* **Symptom:** A batch of questions takes an incredibly long time (e.g., 27 minutes) and eventually crashes with a timeout.
* **Reason:** This is called **DOM Lag**. If the batch size is set too high (e.g., 60), Playwright is forced to load 60 massive Rich Text Editors on a single web page. This exhausts the browser's memory, causing every keystroke to lag until it completely freezes and times out.
* **Optimal Solution:** This was permanently fixed in our latest update! We reduced the `chunk_size` from 60 down to **15**. This keeps the browser memory perfectly clean and lightning-fast. **Ensure you run `git pull`** to get the latest code!

### 3. Traceback Crash on `page.locator('text=Add Questions').first.click()`
* **Symptom:** After finishing one batch, the script crashes while trying to start the next batch.
* **Reason:** After the server saves a massive batch of questions, the script navigates back to the Question Bank. If the server is slow, the page may not have fully rendered the "Add Questions" button yet, causing Playwright to click empty space or crash.
* **Optimal Solution:** Lowering the `chunk_size` to 15 (via `git pull`) prevents the server from hanging, meaning the page loads instantly and this error disappears.

### 4. `AttributeError: '_UnixSelectorEventLoop' object has no attribute '_closed'`
* **Symptom:** The script crashes instantly with a `segmentation fault` when you run `python main.py`.
* **Reason:** You are running Python 3.13 on a Mac. Playwright is currently incompatible with Python 3.13's new asyncio backend.
* **Optimal Solution:** Downgrade to Python 3.12 (`brew install python@3.12`) and run the script using `python3.12 main.py`.

## Configuration (`config.json`)
Make sure your URLs point to the correct environment. For testing, we use the `demolab` servers.
```json
{
  "login_url": "https://demolab.amypo.ai/login",
  "question_bank_url": "https://demolab.amypo.ai/question-bank"
}
```

## Running the Script
1. Set up your `.env` file with `AMYPO_USERNAME` and `AMYPO_PASSWORD`.
2. Run `python main.py` (or `python3.12 main.py` on Mac).
3. Select your `.docx` file in the popup.
4. Verify your `questions_review.csv`.
5. Enter your start/end question numbers and watch the script fly!
