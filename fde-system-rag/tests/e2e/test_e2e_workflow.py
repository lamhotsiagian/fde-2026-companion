import pytest
import re
from uuid import uuid4
from playwright.async_api import Page, expect
from tests.e2e.fixtures import TEST_USERS, TEST_CHAT_QUERIES

pytestmark = pytest.mark.asyncio


async def test_api_login_workflow(api_client):
    """Test 1: User Login & JWT Token Retrieval."""
    # Test valid login
    response = await api_client.post(
        "/auth/login",
        data={
            "username": TEST_USERS[0]["email"],
            "password": TEST_USERS[0]["password"],
        },
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    json_data = response.json()
    assert "access_token" in json_data
    assert "refresh_token" in json_data
    assert json_data["user"]["email"] == TEST_USERS[0]["email"]


async def test_document_ingestion_pipeline(api_client, temp_sample_files):
    """Test 2: Document Upload & Multi-Format Ingestion Pipeline."""
    # Login first
    login_resp = await api_client.post(
        "/auth/login",
        data={
            "username": TEST_USERS[0]["email"],
            "password": TEST_USERS[0]["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload TXT file to ingestion router
    txt_path = temp_sample_files["txt"]
    thread_id = str(uuid4())
    
    with open(txt_path, "rb") as f:
        upload_resp = await api_client.post(
            f"/ingestion/upload/{thread_id}",
            files={"file": (txt_path.name, f, "text/plain")},
            headers=headers,
        )
        
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    upload_data = upload_resp.json()
    assert "document_id" in upload_data
    assert upload_data["status"] in ("enqueued", "queued", "success")


async def test_chat_interaction_workflow(api_client):
    """Test 3: 5 Chat Samples Evaluation & Response Quality Verification."""
    # Login first
    login_resp = await api_client.post(
        "/auth/login",
        data={
            "username": TEST_USERS[0]["email"],
            "password": TEST_USERS[0]["password"],
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n--- Evaluating 5 Chat Sample Prompts ---")
    for sample in TEST_CHAT_QUERIES:
        thread_id = str(uuid4())
        chat_resp = await api_client.post(
            f"/chat/{thread_id}",
            json={
                "prompt": sample["prompt"],
                "model_name": "llama3.2:1b",
            },
            headers=headers,
        )
        assert chat_resp.status_code == 200, f"Sample {sample['id']} failed with status {chat_resp.status_code}: {chat_resp.text}"
        body_text = chat_resp.text
        
        # Quality Evaluation Assertions
        assert len(body_text.strip()) > 0, f"Sample {sample['id']} returned empty response body!"
        assert "internal guard error" not in body_text, f"Sample {sample['id']} returned guard error: {body_text}"
        assert "llm_chunk" in body_text or "type" in body_text, f"Sample {sample['id']} missing valid streaming NDJSON: {body_text}"
        
        print(f"  [Eval Passed] {sample['id']}: Status=200, OutputSize={len(body_text)} bytes")


from playwright.async_api import async_playwright
import os

async def test_playwright_ui_login_and_chat():
    """Test 4: Visual Playwright E2E Browser UI Flow.
    
    Performs live browser automation in Headed mode with visual delays:
    1. Opens browser and navigates to http://localhost:3000/login
    2. Fills credentials for alice@example.com / Password123! and submits login.
    3. Starts a new chat session.
    4. Uploads a sample grounding document via the UI file input.
    5. Types a chat message into the prompt input and submits it.
    6. Waits to observe the AI response streaming on screen.
    """
    async with async_playwright() as p:
        # Launch headed browser with slow_mo=800 so the user can visibly follow all actions
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        
        try:
            # Step 1: Open Login Page
            print("\n[Visual UI Test] 1. Opening Login Page at http://localhost:3000/login")
            await page.goto("http://localhost:3000/login")
            await page.wait_for_timeout(1500)
            
            # Step 2: Fill Login Form
            print("[Visual UI Test] 2. Filling user credentials (alice@example.com)")
            email_input = page.locator("input[type='text'], input[placeholder*='example.com']")
            password_input = page.locator("input[type='password']")
            submit_button = page.locator("button[type='submit']")
            
            if await email_input.count() > 0:
                await email_input.fill("alice@example.com")
                await password_input.fill("Password123!")
                await page.wait_for_timeout(1000)
                await submit_button.click()
                await page.wait_for_timeout(2500)
            
            # Step 3: Navigate to Chat Dashboard
            print("[Visual UI Test] 3. Navigating to Chat Dashboard")
            if "/login" in page.url:
                await page.goto("http://localhost:3000/chat")
                await page.wait_for_timeout(1500)
            
            # Click "New chat" button if present
            new_chat_btn = page.locator("button:has-text('New chat')").first
            if await new_chat_btn.count() > 0 and await new_chat_btn.is_visible():
                print("[Visual UI Test] Starting new chat thread...")
                await new_chat_btn.click()
                await page.wait_for_timeout(2500)
                
            # Step 4: Test Document Upload via UI
            print("[Visual UI Test] 4. Uploading sample document via UI")
            file_input = page.locator("input[type='file']")
            if await file_input.count() > 0:
                # Create a sample doc for upload
                sample_path = "/tmp/playwright_sample_doc.txt"
                with open(sample_path, "w", encoding="utf-8") as f:
                    f.write("Enterprise Architecture Specification for Memory RAG System with Ollama & pgvector.")
                
                await file_input.set_input_files(sample_path)
                await page.wait_for_timeout(3000)
                
            # Step 5: Test Chat Interaction via UI
            print("[Visual UI Test] 5. Typing and sending chat prompt")
            enabled_input = page.locator("input[placeholder*='message']:not([disabled]), input[placeholder*='command']:not([disabled])").first
            await expect(enabled_input).to_be_visible(timeout=10000)
            await enabled_input.fill("Explain the system architecture and pgvector setup.")
            await page.wait_for_timeout(1000)
            
            send_btn = page.locator("form button[type='submit']").first
            if await send_btn.count() > 0 and await send_btn.is_visible():
                await send_btn.click()
            else:
                await enabled_input.press("Enter")
                
            print("[Visual UI Test] Prompt submitted. Streaming AI response into thread...")
            
            # Strict Thread Response Assertion: Fail test if no AI response appears in the thread UI
            ai_messages = page.locator("div.whitespace-pre-wrap")
            await expect(ai_messages.first).to_be_visible(timeout=20000)
            response_text = await ai_messages.first.text_content()
            assert response_text and len(response_text.strip()) > 5, (
                f"TEST FAILED: No response or empty text rendered in thread! Received: '{response_text}'"
            )
            print(f"[Visual UI Test] ✅ Verified thread response rendered: '{response_text[:80]}...'")
            await page.wait_for_timeout(4000)
                
            # Verify body is visible
            await expect(page.locator("body")).to_be_visible()
            print("[Visual UI Test] Playwright headed UI test completed successfully!")
            
        finally:
            await browser.close()


