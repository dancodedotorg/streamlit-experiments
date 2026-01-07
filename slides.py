import google.auth
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
from google.auth import default

# for Google Slides speaker notes
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import json
import os.path
import requests
import base64
import io
import os
import copy
import uuid
import re

def get_slides_data(presentation_id, creds):
    """
    Orchestrates the fetching of speaker notes and thumbnails, returning a
    single JSON object.
    """
    #creds = get_credentials()
    #print(f"Authenticated for project: {creds.quota_project_id}")
    #access_token = creds.token

    notes_list = get_all_speaker_notes(presentation_id, creds)
    pngs = get_all_pngs_from_presentation(presentation_id, creds)

    if notes_list is None or pngs is None:
        return None # Or raise an exception

    slides_data = []
    for i, (note, png) in enumerate(zip(notes_list, pngs)):
        slides_data.append({
            "index": i,
            "notes": note,
            "png_base64": png
        })

    return slides_data


def get_all_pngs_from_presentation(presentation_id, creds):
    """
    Retrieves all slide thumbnails as PNG images from a Google Presentation.
    """
    #creds = Credentials(token=access_token, scopes=SCOPES)
    service = build('slides', 'v1', credentials=creds)

    presentation = service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get('slides', [])

    png_images = []

    for i, slide in enumerate(slides):
        # Get the thumbnail for each slide
        thumbnail = service.presentations().pages().getThumbnail(
            presentationId=presentation_id,
            pageObjectId=slide['objectId'],
            thumbnailProperties_thumbnailSize='LARGE',
            thumbnailProperties_mimeType='PNG'
        ).execute()

        image_content_url = thumbnail.get('contentUrl')
        if image_content_url:
            # 4. Fetch the image data from the contentUrl
            # Authentication is required for the temporary contentUrl
            image_response = requests.get(
                image_content_url,
                headers={'Authorization': f'Bearer {creds.token}'},
                stream=True
            )
            image_response.raise_for_status() # Check for HTTP errors

            # 5. Encode to Base64
            base64_bytes = base64.b64encode(image_response.content)
            base64_string = base64_bytes.decode('utf-8')

            # Prepend Data URI scheme
            data_uri = f'data:image/png;base64,{base64_string}'

            png_images.append(data_uri)
            print(f"  ✅ Success: Base64 thumbnail generated ({len(base64_string)} chars).")
        else:
            print("  ❌ Failure: No contentUrl found for thumbnail.")

    return png_images


def get_all_speaker_notes(presentation_id, creds):
    """
    Retrieves the speaker notes for every slide in a Google Presentation,
    with added DEBUG logging.
    """
    # ... (Authentication and Service Initialization remains the same) ...
    #creds = Credentials(token=access_token, scopes=SCOPES)
    service = build('slides', 'v1', credentials=creds)

    # 🛑 DEBUG POINT 0: Confirm service object creation
    print(f"--- Service created for Presentation ID: {presentation_id} ---")

    try:
        # 🛑 DEBUG POINT 0.5: Confirm API call parameters
        print(f"Attempting to fetch presentation structure with ID: {presentation_id}")

        # This is the line that might be failing without being properly caught
        presentation = service.presentations().get(presentationId=presentation_id).execute()

        # If the API call succeeds, this print will appear
        print("Successfully fetched presentation structure.")

        slides_data = presentation.get('slides', [])

        # This print should now appear before the loop starts
        print(f"Found {len(slides_data)} slides. Starting individual slide processing...")

    except Exception as e:
        # The script should always hit this if the API call fails
        print(f"--- 🛑 CRITICAL ERROR FETCHING PRESENTATION STRUCTURE ---")
        print(f"Error details: {type(e).__name__}: {e}")
        return None

    all_notes = []

    for slide in slides_data:
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        note_texts = []

        for elem in notes_page.get("pageElements", []):
            shape = elem.get("shape")
            if not shape:
                continue

            placeholder = shape.get("placeholder", {})
            # Speaker notes text box
            if placeholder.get("type") != "BODY":
                continue

            text = shape.get("text", {})
            for te in text.get("textElements", []):
                text_run = te.get("textRun")
                if text_run and "content" in text_run:
                    note_texts.append(text_run["content"])

        # Join & clean text
        full_text = "".join(note_texts).strip()

        all_notes.append(full_text)

    return all_notes


def get_slides_data(presentation_id, creds):
    """
    Orchestrates the fetching of speaker notes and thumbnails, returning a
    single JSON object.
    """
    #creds = get_credentials()
    #print(f"Authenticated for project: {creds.quota_project_id}")
    #access_token = creds.token

    notes_list = get_all_speaker_notes(presentation_id, creds)
    pngs = get_all_pngs_from_presentation(presentation_id, creds)

    if notes_list is None or pngs is None:
        return None # Or raise an exception

    slides_data = []
    for i, (note, png) in enumerate(zip(notes_list, pngs)):
        slides_data.append({
            "index": i,
            "notes": note,
            "png_base64": png
        })

    return slides_data