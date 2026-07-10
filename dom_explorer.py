import os
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright
import time
from dotenv import load_dotenv

load_dotenv()

# Credentials should be set in a .env file
# AMYPO_USERNAME=your_username
# AMYPO_PASSWORD=your_password

def explore_dom():
    username = os.getenv("AMYPO_USERNAME")
    password = os.getenv("AMYPO_PASSWORD")

    if not username or not password:
        print("Please set AMYPO_USERNAME and AMYPO_PASSWORD in your .env file")
        return

    print("Launching browser for DOM exploration...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to login page...")
        page.goto("https://dotlab.amypo.ai/login")

        print("Filling credentials...")
        page.fill('input[name="username"], input[type="email"], input[id="email"]', username)
        page.fill('input[name="password"], input[type="password"], input[id="password"]', password)
        
        # Click login - guessing selector based on standard forms
        # We try a few common button texts/selectors
        try:
            page.click('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")')
        except Exception as e:
            print(f"Could not automatically click login button: {e}")
            print("Please click login manually if needed.")

        print("Waiting for you to complete the OTP and navigate to the Question Bank...")
        print("Once you are on the 'Add Question' screen inside the Question Bank, press ENTER here.")
        input("Press ENTER here to capture the DOM...")

        print("Capturing DOM of the current page...")
        # Get the HTML content
        html_content = page.content()
        
        with open("question_bank_dom.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("DOM saved to 'question_bank_dom.html'. We will use this to build the final selectors.")
        
        browser.close()

if __name__ == "__main__":
    explore_dom()
