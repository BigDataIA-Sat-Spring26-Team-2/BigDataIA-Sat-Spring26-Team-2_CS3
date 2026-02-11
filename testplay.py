# Quick test
from playwright.async_api import async_playwright
import asyncio

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # See what it gets
        page = await browser.new_page()
        await page.goto('https://craft.co/unitedhealth/executives')
        await page.wait_for_timeout(3000)
        print(await page.content())
        await browser.close()

asyncio.run(test())