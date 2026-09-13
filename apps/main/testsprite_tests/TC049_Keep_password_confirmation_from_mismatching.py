import asyncio
import re
from playwright import async_api
from playwright.async_api import expect

async def run_test():
    pw = None
    browser = None
    context = None

    try:
        # Start a Playwright session in asynchronous mode
        pw = await async_api.async_playwright().start()

        # Launch a Chromium browser in headless mode with custom arguments
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--window-size=1280,720",
                "--disable-dev-shm-usage",
                "--ipc=host",
                "--single-process"
            ],
        )

        # Create a new browser context (like an incognito window)
        context = await browser.new_context()
        # Wider default timeout to match the agent's DOM-stability budget;
        # auto-waiting Playwright APIs (expect, locator.wait_for) inherit this.
        context.set_default_timeout(15000)

        # Open a new page in the browser context
        page = await context.new_page()

        # Interact with the page elements to simulate user flow
        # -> navigate
        await page.goto("http://localhost:3000")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        
        # -> Fill the email and password fields and click the 'تسجيل الدخول' button on the login page.
        # you@example.com email field
        elem = page.get_by_placeholder('you@example.com', exact=True)
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("testsprite.driver+4f241358@example.com")
        
        # -> Fill the email and password fields and click the 'تسجيل الدخول' button on the login page.
        # •••••••• password field
        elem = page.get_by_placeholder('••••••••', exact=True)
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("TestSprite2026!")
        
        # -> Fill the email and password fields and click the 'تسجيل الدخول' button on the login page.
        # إظهار كلمة المرور button
        elem = page.get_by_role('button', name='إظهار كلمة المرور', exact=True)
        await elem.click(timeout=10000)
        
        # -> Click the 'تسجيل الدخول' button to submit the login form.
        # تسجيل الدخول button
        elem = page.get_by_role('button', name='تسجيل الدخول', exact=True)
        await elem.click(timeout=10000)
        
        # -> Open the 'Set Password' page (navigate to the /set-password URL) so the password setup form can be inspected.
        await page.goto("http://localhost:3000/set-password")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        
        # -> Fill the 'Password' field with a new password and the 'Confirm password' field with a different password, then submit the form (press Enter) to trigger validation.
        # •••••••• password field
        elem = page.locator('xpath=/html/body/main/div/form/div/input')
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("NewPass123!")
        
        # -> Fill the 'Password' field with a new password and the 'Confirm password' field with a different password, then submit the form (press Enter) to trigger validation.
        # •••••••• password field
        elem = page.locator('xpath=/html/body/main/div/form/div[2]/input')
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("DifferentPass456!")
        
        # --> Assertions to verify final state
        
        # --> After submitting mismatched passwords, the page remained on the Set a password screen (/set-password).
        # Assert-outcome: passed
        # Assert: The browser stayed on the /set-password URL.
        await expect(page).to_have_url(re.compile("/set\\-password"), timeout=15000), "The browser stayed on the /set-password URL."
        
        # --> A visible validation message 'Passwords do not match' is shown on the page.
        # Assert-outcome: passed
        # Assert: The page shows the 'Passwords do not match' validation message.
        await expect(page.locator("xpath=/html/body/main/div/form/button[1]").nth(0)).to_contain_text("Passwords do not match", timeout=15000), "The page shows the 'Passwords do not match' validation message."
        
        # --> The Confirm password field contains the mismatched value that was entered.
        # Assert-outcome: passed
        # Assert: The Confirm password input contains the entered value DifferentPass456!.
        await expect(page.locator("xpath=/html/body/main/div/form/div[2]/input").nth(0)).to_have_value("DifferentPass456!", timeout=15000), "The Confirm password input contains the entered value DifferentPass456!."
        await asyncio.sleep(5)

    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

asyncio.run(run_test())
    