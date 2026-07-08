# Amypo Automated Question Uploader

Welcome to the Amypo Question Automation script! This tool is designed to save you hours of manual data entry. You just provide a Word Document (`.docx`) containing your questions, and the script will automatically parse them, map the attachments, and upload them to the Amypo platform.

## 🚀 Getting Started

### 1. Prerequisites
If you haven't already, you need Python installed on your computer.
- Download Python from [python.org](https://www.python.org/downloads/)
- Once installed, open your terminal (Command Prompt) and run:
  ```bash
  pip install -r requirements.txt
  playwright install
  ```

### 2. Prepare Your Assignment Folder
For the script to work magically, keep your files organized.
- Ensure your questions are formatted correctly inside a **Master Word Document (`.docx`)**.
- Keep all of your attachment files (PDFs, Images, Data Tables) in the same folder (or sub-folders) as your Master Word Document.
- **Note:** You do not need to name the attachments folder perfectly. The script is smart enough to scan the entire project folder and find the attachments based on the file names listed in your Word Document!

## 🖱️ How to Run the Script

1. Open your terminal (Command Prompt).
2. Navigate to this `content_automation` folder.
3. Run the following command:
   ```bash
   python main.py
   ```
4. **The Setup Window:** A native Windows popup will appear!
   - Enter your **Amypo Email**.
   - Enter your **Amypo Password**.
   - Click **Browse...** and select your Master Assignment `.docx` file.
   - Click **Start Automation**.

5. **Terminal Questions:** Look back at your terminal. The script will ask you a few quick questions (like the Course Name, Subject Type, and Module Name). Answer them and press Enter.
6. **OTP:** Check your WhatsApp for the Amypo OTP and enter it into the terminal when prompted.

## ☕ Sit Back and Relax!
Once the OTP is entered, a Chromium browser window will open automatically. 
**Do not click inside the browser!** Watch as the script logs in, navigates to the correct course, creates the questions, attaches the files, and saves everything for you.

## ⚠️ Troubleshooting
- **Missing Attachments Error?** Ensure the exact file name (e.g., `26CSS01A_M1_Q2_Result_Data_Table.docx`) is mentioned in the Word Document, and that the file actually exists somewhere in the same folder as the Master Word Document.
- **Website Rejects Save?** The script will print a Critical Error in red if the website rejects the save. This usually means a value in your Word Document (like a Tags or Difficulty setting) does not exactly match the dropdown options available on the Amypo website. Check the `questions_review.csv` file to spot the typo!
