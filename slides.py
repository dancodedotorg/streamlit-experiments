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


def curate_slides(data_source):
  """Creates the interactive UI for slides_data

  input: slides_data structure: a list of JSON objects with
    - index: int
    - notes: str
    - png_base64: str (base64 encoded)
  """

  # The container for the whole list
  main_layout = widgets.VBox([])

  # We will store our widget rows here
  widget_rows = []

  print(f"Loaded {len(data_source)} slides for curation.")
  print("------------------------------------------------")

  # We iterate over the ACTUAL dict objects in the list
  for slide_item in data_source:
      try:
          # --- A. PREPARE IMAGE ---
          b64_str = slide_item["png_base64"]
          if ',' in b64_str:
              b64_str = b64_str.split(',')[1]

          image_bytes = base64.b64decode(b64_str)

          img_widget = widgets.Image(
              value=image_bytes,
              format='png',
              width=300, # Use a thumbnail size for the list view
              height=200,
              layout=widgets.Layout(object_fit='contain')
          )

          # --- B. PREPARE EDITABLE NOTES ---
          # Textarea allows multi-line editing
          notes_widget = widgets.Textarea(
              value=slide_item["notes"],
              placeholder='Enter notes here...',
              description='Notes:',
              layout=widgets.Layout(width='95%', height='150px')
          )

          # --- C. PREPARE CONTROLS ---
          btn_remove = widgets.Button(
              description='Remove Slide',
              button_style='danger',
              icon='trash'
          )

          # --- D. LOGIC: SAVE EDITS ---
          # This function runs every time a key is pressed in the Textarea
          def on_notes_change(change, target_item=slide_item):
              # Update the specific dictionary in our final list
              target_item['notes'] = change['new']
              # (Optional) Print to console to verify it's working
              # print(f"Updated notes for index {target_item['index']}")

          # 'value' means we listen for changes to the text content
          notes_widget.observe(on_notes_change, names='value')

          # --- E. LOGIC: REMOVE ITEM ---
          def on_remove_click(b, target_row=None, target_item=slide_item):
              # 1. Remove the visual widget
              target_row.close()

              # 2. Remove the data from our global list
              # We use .remove() which looks for this specific object in memory
              if target_item in final_data:
                  final_data.remove(target_item)
                  print(f"Removed Index {target_item['index']}. Remaining: {len(final_data)}")

          # --- F. LAYOUT ---
          # Right side: Notes on top, Button on bottom
          right_column = widgets.VBox(
              [notes_widget, btn_remove],
              layout=widgets.Layout(width='100%', padding='0 0 0 20px')
            )

          # Row: Image on Left, Right Column on Right
          row_layout = widgets.HBox(
              [img_widget, right_column],
              layout=widgets.Layout(
                  border='1px solid #ccc',
                  margin='10px 0',
                  padding='10px',
                  align_items='center'
              )
          )

          # Now bind the remove click (we waited until row_layout was defined)
          # We use a 'partial' trick by passing arguments directly to lambda or function
          btn_remove.on_click(lambda b, row=row_layout, item=slide_item: on_remove_click(b, row, item))

          widget_rows.append(row_layout)

      except Exception as e:
          print(f"Error processing index {slide_item.get('index', 'Unknown')}: {e}")

  # Add a Save Changes button outside the loop
  save_button = widgets.Button(
      description='Save All Changes',
      button_style='success', # Green button for success
      icon='save',
      layout=widgets.Layout(margin='10px 0')
  )
  save_output = widgets.Output()



  def get_text_from_page_elements(page_content):
    """
    Helper function to recursively extract text from a Slides API Page object.

    The speaker notes are often found in the 'notes master' text box element.
    """
    notes_text = ""
    if 'pageElements' in page_content:
        for element in page_content['pageElements']:
            # Check if the element is a shape and contains text data
            if 'shape' in element and 'text' in element['shape']:
                text_content = element['shape']['text']
                for text_element in text_content.get('textElements', []):
                    # Concatenate the text from all runs
                    if 'textRun' in text_element:
                        notes_text += text_element['textRun']['content']
    return notes_text.strip()

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