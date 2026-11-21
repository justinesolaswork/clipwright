"""Optional live smoke test: run the studio, install playwright, then run this file."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

project = {
    "topic": "Bring your next idea to life", "tts": "kokoro", "voice": "af_heart",
    "motion": "lively", "avatar_style": "cat", "avatar_color": "#70CFFF",
    "avatar_accessory": "glasses", "avatar_size": 100, "talking": True,
    "scenes": [
        {"line1": "YOUR NEXT", "line2": "BIG IDEA", "voiceover": "Bring your next idea to life.",
         "pose": "happy", "image_query": "laptop computer"},
        {"line1": "LET YOUR", "line2": "STORY MOVE", "voiceover": "Give your story a voice, and let it move.",
         "pose": "surprised"},
    ],
}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000")
    page.evaluate("(project) => localStorage.setItem('clipwright-project', JSON.stringify(project))", project)
    page.reload()
    expect(page.locator(".scene")).to_have_count(2)
    page.wait_for_function("document.getElementById('still').naturalWidth > 0")
    page.locator("#look summary").click()
    expect(page.locator("#avatar_style")).to_have_value("cat")
    page.locator("#avatar_accessory").select_option("headphones")
    with page.expect_response(lambda response: response.url.endswith("/api/preview")
                              and response.request.post_data_json["scenes"][0].get("image"), timeout=120000):
        page.locator(".scene").first.get_by_role("button", name="Find image", exact=True).click()
    expect(page.locator(".image-tools img")).to_be_visible(timeout=120000)
    expect(page.locator("#task-title")).to_have_text("Complete")
    Path("work").mkdir(exist_ok=True)
    page.screenshot(path="work/animation-studio.png", full_page=True)
    page.locator("#motion-preview").click()
    expect(page.locator("#task-progress")).to_be_visible()
    expect(page.locator("#video")).to_be_visible(timeout=120000)
    page.wait_for_function("document.getElementById('video').videoWidth === 540")
    assert page.locator("#video").evaluate("(video) => video.duration") > 1
    page.locator("#render").click()
    expect(page.locator("#download")).to_be_visible(timeout=180000)
    page.wait_for_function("document.getElementById('video').videoWidth === 1080")
    credits = page.request.get("http://127.0.0.1:8000" + page.locator("#credits").get_attribute("href")).text()
    assert "Scene 1:" in credits and "https://" in credits
    url = page.locator("#download").get_attribute("href")
    Path("work/animation-browser-result.json").write_text(json.dumps({"url": url}), encoding="utf-8")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    print("Browser checks passed: image search, avatar settings, motion preview, MP4 export, credits, mobile layout.")
    print("Video:", "http://127.0.0.1:8000" + url)
    browser.close()
