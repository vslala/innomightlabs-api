from pydantic import BaseModel
from app.chatbot.chatbot_models import ActionResult, AgentState
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from langchain.tools import tool
import re
import os

WEBPAGE_DIR = "/tmp/innomightlabs/webpages"
os.makedirs(WEBPAGE_DIR, exist_ok=True)


class BrowserParams(BaseModel):
    url: str


@tool(
    "download_webpage",
    description="""
    Downloads the webpage at the specified URL and saves it to a text file.
    The file contains the body text of the webpage.
    You can read the contents of the file later using appropriate tools.
    """,
    args_schema=BrowserParams,
    infer_schema=False,
    return_direct=True,
)
async def download_webpage(state: AgentState, input: BrowserParams) -> ActionResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(input.url)
        html = await page.content()
        await browser.close()

        soup = BeautifulSoup(html, "html.parser")
        html_body = soup.find("body")
        title = soup.find("title")

        if title:
            title = title.get_text(strip=True) or "current_webpage"
            title = re.sub(r"[^A-Za-z0-9\s]", "", title)
            title = re.sub(r"\s+", "_", title)
            title = title.lower()
        if html_body:
            body_text = html_body.get_text(separator="\n", strip=True)

        filepath = f"{WEBPAGE_DIR}/{title}.txt"
        with open(filepath, "w") as f:
            f.write(body_text)

        return ActionResult(
            thought=f"Downloading webpage at {input.url}", action="download_webpage", result=f"Your downloaded webpage ({input.url}) can be read from following path: {filepath}"
        )
