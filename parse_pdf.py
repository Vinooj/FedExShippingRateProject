import os
import base64
import io
import openai
from pdf2image import convert_from_path
from pypdf import PdfReader # Import PdfReader to get total pages

# --- Configuration ---
# IMPORTANT: Set your OpenAI API key.
# It is highly recommended to set it as an environment variable for security.
# Example:
# In your terminal, run:
# export OPENAI_API_KEY='your_super_secret_api_key'
#
# If you are not using environment variables, you can uncomment the following line
# and replace "YOUR_OPENAI_API_KEY" with your actual key.
# os.environ['OPENAI_API_KEY'] = "YOUR_OPENAI_API_KEY"

# Initialize the OpenAI client
# The client will automatically look for the OPENAI_API_KEY environment variable.
try:
    client = openai.OpenAI()
    if not client.api_key:
        raise ValueError("OpenAI API key not found.")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    print("Please make sure the OpenAI library is installed (`pip install openai`) and your API key is set.")
    exit()


PDF_FILE_PATH = "Service_Guide_2025_p13-15.pdf"
OUTPUT_CSV_PATH = "output.csv"
# PAGES_TO_PARSE is no longer a fixed tuple, it will be determined dynamically
# PAGES_TO_PARSE = (13, 14, 15)  # Page numbers are 1-based

def get_pdf_page_count(file_path):
    """Gets the total number of pages in a PDF file."""
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return len(reader.pages)
    except Exception as e:
        print(f"Error getting PDF page count: {e}")
        return 0

def pdf_pages_to_base64_images(file_path, start_page, end_page):
    """Converts specified pages of a PDF to a list of base64 encoded images."""
    print(f"Converting PDF pages {start_page}-{end_page} to images. This may take a moment...")
    try:
        images = convert_from_path(file_path, first_page=start_page, last_page=end_page)
    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        print("\n---")
        print("This script requires 'poppler' to be installed on your system.")
        print("On macOS, you can install it with Homebrew: `brew install poppler`")
        print("On Debian/Ubuntu, use: `sudo apt-get install poppler-utils`")
        print("---")
        return None

    base64_images = []
    for image in images:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        base64_images.append(base64_image)
    print(f"Successfully converted {len(base64_images)} pages to images.")
    return base64_images

def parse_tables_with_openai(base64_images):
    """Uses OpenAI's GPT-4 Vision model to extract tabular data from images."""
    print("Sending images to OpenAI for analysis. This can take some time...")
    
    # Constructing the prompt for the vision model
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are an expert data extraction assistant. Your task is to analyze the provided image(s) containing data tables and convert them into a single, clean CSV format. **Instructions** 1. Extract all tabular data, using the table's headers as the header row for the CSV. The first row of data must be the entry for the 'FedEx® Envelope up to 8 oz.'. Proceed to extract the data for all subsequent weight increments shown, from 1 lb up to 150 lbs. **Output Format:** Return only the raw CSV data. Do not include any explanations, comments, or surrounding text"
                    )
                },
                *[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img}"
                        }
                    } for img in base64_images
                ]
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except openai.APIError as e:
        print(f"An error occurred with the OpenAI API: {e}")
        # You can add more specific error handling here if needed
        # For example, for authentication errors:
        if "authentication" in str(e).lower():
            print("\n---")
            print("Authentication error: Please check if your OpenAI API key is correct and has sufficient credits.")
            print("---")
    except Exception as e:
        print(f"An unexpected error occurred while calling the OpenAI API: {e}")
    
    return None

def main():
    """Main function to orchestrate the PDF parsing and CSV generation."""
    if not os.path.exists(PDF_FILE_PATH):
        print(f"Error: PDF file not found at '{PDF_FILE_PATH}'")
        return

    total_pages = get_pdf_page_count(PDF_FILE_PATH)
    if total_pages == 0:
        print("Could not determine the number of pages in the PDF. Exiting.")
        return

    print(f"Total pages in PDF: {total_pages}")
    
    # Process all pages
    base64_images = pdf_pages_to_base64_images(PDF_FILE_PATH, 1, total_pages)
    
    if not base64_images:
        return # Stop if PDF to image conversion failed

    csv_data = parse_tables_with_openai(base64_images)

    if csv_data:
        # The model might return the CSV data enclosed in markdown code blocks (```csv ... ```).
        # This part of the script cleans that up.
        if csv_data.startswith("```csv"):
            csv_data = csv_data[5:]
        if csv_data.endswith("```"):
            csv_data = csv_data[:-3]
        
        csv_data = csv_data.strip()

        try:
            with open(OUTPUT_CSV_PATH, "w", newline="", encoding='utf-8') as f:
                f.write(csv_data)
            print(f"\nSuccessfully saved extracted data to '{OUTPUT_CSV_PATH}'")
        except IOError as e:
            print(f"Error writing to file '{OUTPUT_CSV_PATH}': {e}")
    else:
        print("\nFailed to extract data using the OpenAI API. No output file was created.")

if __name__ == "__main__":
    main()