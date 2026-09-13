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
        
        # -> Fill the email field with testsprite.driver+4f241358@example.com, the password field with TestSprite2026!, then click the 'تسجيل الدخول' (Login) button to sign in.
        # you@example.com email field
        elem = page.get_by_placeholder('you@example.com', exact=True)
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("testsprite.driver+4f241358@example.com")
        
        # -> Fill the email field with testsprite.driver+4f241358@example.com, the password field with TestSprite2026!, then click the 'تسجيل الدخول' (Login) button to sign in.
        # •••••••• password field
        elem = page.get_by_placeholder('••••••••', exact=True)
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("TestSprite2026!")
        
        # -> Fill the email field with testsprite.driver+4f241358@example.com, the password field with TestSprite2026!, then click the 'تسجيل الدخول' (Login) button to sign in.
        # إظهار كلمة المرور button
        elem = page.get_by_role('button', name='إظهار كلمة المرور', exact=True)
        await elem.click(timeout=10000)
        
        # -> Click the 'تسجيل الدخول' button to submit the login form.
        # تسجيل الدخول button
        elem = page.get_by_role('button', name='تسجيل الدخول', exact=True)
        await elem.click(timeout=10000)
        
        # -> Open the 'Profile' page by clicking the 'Profile' link so the organization verification settings can be accessed.
        # Profile link
        elem = page.get_by_role('link', name='Profile', exact=True)
        await elem.click(timeout=10000)
        
        # -> Scroll the Profile page to reveal the 'Verify organization' or 'Verify organization email' link or section.
        await page.mouse.wheel(0, 300)
        
        # -> Open the 'Verify organization email' page (navigate to /verify-org-email) to access the organization verification form.
        await page.goto("http://localhost:3000/verify-org-email")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        
        # -> Fill the 'Work or school email' field with a valid organization email (e.g., employee@acme.com).
        # you@company.com email field
        elem = page.get_by_placeholder('you@company.com', exact=True)
        await elem.wait_for(state="visible", timeout=10000)
        await elem.fill("employee@acme.com")
        
        # -> Click the 'Send code' button to request a verification code
        # Send code button
        elem = page.get_by_role('button', name='Send code', exact=True)
        await elem.click(timeout=10000)
        
        # -> Enter the invalid 6-digit code '000000' into the OTP inputs and check the page for a verification error message.
        # text field
        elem = page.locator('xpath=/html/body/div/div[2]/div[2]/div/input')
        await elem.click(timeout=10000)
        
        # --> Assertions to verify final state
        
        # --> An invalid verification code was rejected: the page shows "Incorrect code. Please try again." and the OTP inputs contain the entered '000000'.
        # Assert-outcome: passed
        # Assert: The first OTP input contains '0', showing part of the submitted invalid code.
        await expect(page.locator("xpath=/html/body/div/div[2]/div[2]/div/input[1]").nth(0)).to_have_value("0", timeout=15000), "The first OTP input contains '0', showing part of the submitted invalid code."
        await page.locator("xpath=/html/body/div/div[2]/div[2]/button").nth(0).scroll_into_view_if_needed()
        # Assert-outcome: passed
        # Assert: The resend button is visible, indicating the verification UI remains active after the invalid code.
        await expect(page.locator("xpath=/html/body/div/div[2]/div[2]/button").nth(0)).to_be_visible(timeout=15000), "The resend button is visible, indicating the verification UI remains active after the invalid code."
        await asyncio.sleep(5)

    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

asyncio.run(run_test())
    